"""Harness-only external workflow integration; never decides local cycle verdicts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tomllib
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

INTENT_BEGIN = "<<<YOUTRACK_UPDATE_JSON>>>"
INTENT_END = "<<<END_YOUTRACK_UPDATE_JSON>>>"
INTENT_HELP = f"""
Optional YouTrack update: output a separate {INTENT_BEGIN} ... {INTENT_END} envelope
with exactly ticket, role, summary, proposed_fields, comment. proposed_fields permits only
assignee, estimation, due_date, type, priority. Values are strings. Do not supply state or
issue ID. Harness validates and applies to the current ticket only. Never call YouTrack
API directly or write tracking artifacts. External failure does not change your verdict.
"""
STATES = {
    "start": "In Progress",
    "handoff": "Ready for Review",
    "CHANGES_REQUIRED": "In Progress",
    "PASS": "Ready for Human Review",
    "merged": "Done",
}


class TrackingError(RuntimeError):
    pass


class IdentityError(TrackingError):
    pass


def child_environment() -> dict[str, str]:
    """Integration secrets belong to the parent harness, not agent processes."""
    return {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("YOUTRACK_")
        and key.upper() not in {"GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN"}
    }


def parse_intent(stdout: str, ticket: str, role: str) -> dict[str, Any] | None:
    if INTENT_BEGIN not in stdout and INTENT_END not in stdout:
        return None
    if stdout.count(INTENT_BEGIN) != 1 or stdout.count(INTENT_END) != 1:
        raise TrackingError("ambiguous update intent")
    if stdout.index(INTENT_BEGIN) >= stdout.index(INTENT_END):
        raise TrackingError("reversed update delimiters")
    body = stdout.split(INTENT_BEGIN, 1)[1].split(INTENT_END, 1)[0]

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TrackingError("duplicate update member")
            result[key] = value
        return result

    intent = json.loads(body, object_pairs_hook=unique)
    if not isinstance(intent, dict) or set(intent) != {
        "ticket",
        "role",
        "summary",
        "proposed_fields",
        "comment",
    }:
        raise TrackingError("invalid update schema")
    if intent["ticket"] != ticket or intent["role"] != role:
        raise IdentityError("update intent target/role mismatch")
    fields = intent["proposed_fields"]
    if not isinstance(fields, dict) or set(fields) - {
        "assignee",
        "estimation",
        "due_date",
        "type",
        "priority",
    }:
        raise TrackingError("unsupported proposed fields")
    if not all(isinstance(v, str) and len(v) <= 8000 for v in fields.values()):
        raise TrackingError("invalid field value")
    if not all(
        isinstance(intent[k], str) and len(intent[k]) <= 16000 for k in ("summary", "comment")
    ):
        raise TrackingError("invalid update text")
    return intent


def review_without_intent(stdout: str, ticket: str) -> str:
    """Strip bounded metadata without hiding competing review envelopes.

    Lifecycle validates intent cardinality/schema separately. Unmatched delimiters
    remain visible to the strict review parser because their boundaries are ambiguous.
    """

    def strip(match: re.Match[str]) -> str:
        body = match.group(0)
        before = stdout[: match.start()]
        review_begin = "<<<AGENT_CYCLE_REVIEW_JSON>>>"
        review_end = "<<<END_AGENT_CYCLE_REVIEW_JSON>>>"
        if any(marker in body for marker in (review_begin, review_end, "```")) or before.count(
            review_begin
        ) != before.count(review_end):
            return body
        return ""

    return re.sub(
        re.escape(INTENT_BEGIN) + r".*?" + re.escape(INTENT_END), strip, stdout, flags=re.S
    )


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        raise TrackingError("YouTrack redirect refused")


class YouTrack:
    """Narrow REST boundary; errors deliberately omit server bodies and credentials."""

    def __init__(self, url: str, token: str) -> None:
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
            or not token
            or token in url
        ):
            raise TrackingError("YouTrack requires credential-free HTTPS URL")
        self.url = url.rstrip("/")
        self.token = token

    def request(self, method: str, path: str, body: Any = None) -> Any:
        headers = {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if isinstance(body, tuple):
            payload, content_type = body
            headers["Content-Type"] = content_type
        else:
            payload = None if body is None else json.dumps(body).encode()
        request = Request(self.url + "/api/" + path, data=payload, headers=headers, method=method)
        try:
            with build_opener(NoRedirect()).open(request, timeout=20) as response:
                payload = response.read()
                result = json.loads(payload) if payload else None
                if method == "GET" and result is None:
                    raise TrackingError("YouTrack empty/null read response")
                return result
        except HTTPError as error:
            if method == "GET" and error.code == 404:
                return None
            raise TrackingError(f"YouTrack HTTP {error.code}") from None
        except (OSError, ValueError):
            raise TrackingError("YouTrack transport/response failure") from None


class GitHub:
    def __init__(self, root: Path, repository: str) -> None:
        self.root = root
        self.repository = repository

    def command(self, *args: str, input_text: str | None = None) -> Any:
        try:
            result = subprocess.run(
                ["gh", *args],
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=45,
                check=False,
                env={**os.environ, "GH_HOST": "github.com"},
                input=input_text,
            )
            if result.returncode:
                raise TrackingError("GitHub command failed")
            if args[:2] in {("pr", "create"), ("pr", "edit")}:
                return None
            return json.loads(result.stdout) if result.stdout.strip() else None
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise TrackingError("GitHub unavailable") from None

    def ensure(self, branch: str, base: str, sha: str, title: str, body: str) -> dict[str, Any]:
        prs = self.command(
            "pr",
            "list",
            "--repo",
            self.repository,
            "--head",
            branch,
            "--base",
            base,
            "--state",
            "open",
            "--json",
            "number",
        )
        if len(prs) > 1:
            raise IdentityError("ambiguous PR identity")
        if not prs:
            # Head verification precedes creation, so an unreviewed branch is never advertised.
            remote = self.command(
                "api", f"repos/{self.repository}/commits/{quote(branch, safe='')}"
            )
            if remote["sha"] != sha:
                raise IdentityError("remote branch moved")
            self.command(
                "pr",
                "create",
                "--repo",
                self.repository,
                "--head",
                branch,
                "--base",
                base,
                "--title",
                title,
                "--body-file",
                "-",
                input_text=body,
            )
            prs = self.command(
                "pr",
                "list",
                "--repo",
                self.repository,
                "--head",
                branch,
                "--base",
                base,
                "--state",
                "open",
                "--json",
                "number",
            )
        if len(prs) != 1:
            raise IdentityError("PR identity unavailable")
        number = str(prs[0]["number"])

        def view() -> dict[str, Any]:
            return self.command(
                "pr",
                "view",
                number,
                "--repo",
                self.repository,
                "--json",
                "url,headRefOid,headRefName,baseRefName,statusCheckRollup,"
                "headRepository,headRepositoryOwner",
            )

        pr = view()
        owner, repository = self.repository.split("/", 1)
        if (
            pr.get("headRepositoryOwner", {}).get("login") != owner
            or pr.get("headRepository", {}).get("name") != repository
        ):
            raise IdentityError("PR head repository differs from configured repository")
        if (pr["headRefOid"], pr["headRefName"], pr["baseRefName"]) != (sha, branch, base):
            raise IdentityError("PR head/base differs from reviewed implementation")
        self.command(
            "pr",
            "edit",
            number,
            "--repo",
            self.repository,
            "--title",
            title,
            "--body-file",
            "-",
            input_text=body + "\nExact-head CI snapshot: " + ci_status(pr.get("statusCheckRollup")),
        )
        pr = view()
        if (
            (pr["headRefOid"], pr["headRefName"], pr["baseRefName"]) != (sha, branch, base)
            or pr.get("headRepositoryOwner", {}).get("login") != owner
            or pr.get("headRepository", {}).get("name") != repository
        ):
            raise IdentityError("PR head/base/repository moved during update")
        return pr


def ci_status(checks: list[dict[str, Any]] | None) -> str:
    if not checks:
        return "unavailable"
    values = [c.get("conclusion") or c.get("state") or c.get("status") for c in checks]
    if any(v in {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"} for v in values):
        return "failed"
    pending = {"PENDING", "QUEUED", "IN_PROGRESS", "WAITING", "REQUESTED"}
    if any(v in pending for v in values) or any(c.get("status") in pending for c in checks):
        return "pending"
    # Neutral/skipped-only rollups are not evidence that any CI actually succeeded.
    return (
        "passed"
        if "SUCCESS" in values and all(v in {"SUCCESS", "NEUTRAL", "SKIPPED"} for v in values)
        else "unavailable"
    )


class ProjectTracking:
    def __init__(
        self,
        root: Path,
        ticket: str,
        text: str,
        *,
        config: dict[str, Any] | None = None,
        youtrack: Any = None,
        github: Any = None,
        warn: Callable[[str], None] = print,
    ) -> None:
        self.root, self.ticket, self.text, self.warn = root, ticket, text, warn
        if config is None:
            path = root / "project-tracking.toml"
            config = tomllib.loads(path.read_text("utf-8")) if path.exists() else {}
        self.config = config
        self.yconfig = config.get("youtrack", {})
        self.gconfig = config.get("github", {})
        self.directory = root / ".agent-cycle" / ticket
        self.path = self.directory / "youtrack.json"
        self.data = (
            json.loads(self.path.read_text("utf-8"))
            if self.path.exists()
            else {
                "ticket": ticket,
                "operations": {},
                "warnings": [],
            }
        )
        if self.data.get("ticket") != ticket:
            raise IdentityError("tracking artifact target mismatch")
        self.yt = youtrack
        if self.yt is None and self.yconfig.get("enabled"):
            url, token = os.getenv("YOUTRACK_URL"), os.getenv("YOUTRACK_TOKEN")
            if url and token:
                self.yt = YouTrack(url, token)
        self.gh = github
        if self.gh is None and self.gconfig.get("create_pr_on_pass"):
            repository = self.gconfig.get("repository", "")
            if re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
                self.gh = GitHub(root, repository)
        self.issue: dict[str, Any] | None = None
        self.fields: list[dict[str, Any]] = []

    def save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        staging = self.path.with_suffix(".tmp")
        staging.write_text(json.dumps(self.data, indent=2) + "\n", "utf-8")
        staging.replace(self.path)

    def warning(self, message: str) -> None:
        self.data["warnings"].append(message)
        self.warn("Integration warning: " + message)
        self.save()

    def operation(
        self,
        role: str,
        action: str,
        sha: str,
        round_: int,
        fn: Callable[[], Any],
        *,
        repeatable: bool = False,
    ) -> Any:
        key = hashlib.sha256(f"{self.ticket}|{role}|{round_}|{sha}|{action}".encode()).hexdigest()
        previous = self.data["operations"].get(key)
        if previous and (previous["status"] == "success" or not repeatable):
            return previous.get("result")
        self.data["operations"][key] = {"status": "pending"}
        self.save()  # At-most-once mutation even if response is lost or runner crashes.
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "ticket": self.ticket,
            "role": role,
            "action": action,
            "sha": sha,
            "round": round_,
            "idempotency_key": key,
            "issue_id": self.data.get("issue_id"),
        }
        try:
            result = fn()
            event["status"] = "success"
            self.data["operations"][key] = {"status": "success", "result": result}
            return result
        except Exception as error:
            # Never include arbitrary server/error text, which may contain credentials.
            event.update(
                status="failed",
                error_class=type(error).__name__,
                message="external operation failed; local workflow continues",
            )
            self.data["operations"][key] = {"status": "failed"}
            if isinstance(error, IdentityError):
                self.data["identity_unsafe"] = True
            self.warning(f"{action}: {type(error).__name__}; local workflow continues")
            return None
        finally:
            self.data.update(
                last_sync_role=role, last_sync_sha=sha, last_sync_status=event["status"]
            )
            self.save()
            with (self.directory / "youtrack-events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event) + "\n")

    def verify(self, issue: Any) -> dict[str, Any]:
        if not isinstance(issue, dict) or issue.get("idReadable") != self.ticket:
            raise IdentityError("unexpected issue key")
        if issue.get("project", {}).get("shortName") != self.yconfig.get("project", "PDFTR"):
            raise IdentityError("unexpected project")
        if not isinstance(issue.get("id"), str) or not re.fullmatch(r"[\w-]+", issue["id"]):
            raise IdentityError("missing/unsafe issue ID")
        if not re.fullmatch(r"[\w-]+", str(issue.get("project", {}).get("id", ""))):
            raise IdentityError("missing/unsafe project ID")
        if self.data.get("issue_id") not in {None, issue["id"]}:
            raise IdentityError("remote identity changed")
        return {
            "id": issue["id"],
            "idReadable": issue["idReadable"],
            "project": {"id": issue["project"]["id"], "shortName": issue["project"]["shortName"]},
        }

    def bootstrap(self, manifest: dict[str, Any] | None = None) -> None:
        local_sha = self.data.setdefault(
            "bootstrap_sha", manifest["current_head_sha"] if manifest else ""
        )
        if self.ticket in {f"PDFTR-{number}" for number in range(38, 43)}:
            self.warning("historical placeholder excluded from automatic YouTrack synchronization")
            return
        if not self.yt:
            if self.yconfig.get("enabled"):
                self.warning("YouTrack credentials unavailable")
            return
        if self.data.get("identity_unsafe"):
            return

        def ensure() -> Any:
            if self.yconfig.get("project", "PDFTR") != self.ticket.split("-", 1)[0]:
                raise IdentityError("configured project does not match ticket key")
            if not re.match(r"#\s+" + re.escape(self.ticket) + r"(?:\s|:|$)", self.text):
                raise IdentityError("Markdown ticket identity mismatch")
            expected_login = self.yconfig.get("expected_login")
            if expected_login:
                account = self.yt.request("GET", "users/me?fields=login")
                if not isinstance(account, dict) or account.get("login") != expected_login:
                    raise IdentityError("unexpected authenticated account")
            query = "?fields=id,idReadable,project(id,shortName)"
            issue = self.yt.request("GET", "issues/" + self.ticket + query)
            if issue is None:

                def create() -> Any:
                    project = self.yt.request("GET", "admin/projects?fields=id,shortName")
                    matches = [
                        p for p in project if p["shortName"] == self.yconfig.get("project", "PDFTR")
                    ]
                    if len(matches) != 1:
                        raise IdentityError("ambiguous project")
                    lines = self.text.strip().splitlines()
                    summary = lines[0].lstrip("# ")
                    created = self.yt.request(
                        "POST",
                        "issues" + query,
                        {
                            "project": {"id": matches[0]["id"]},
                            "summary": summary,
                            "description": "\n".join(lines[1:]).strip(),
                        },
                    )
                    if isinstance(created, dict):
                        remote_id, remote_key = created.get("id"), created.get("idReadable")
                        self.data["create_response_identity"] = {
                            "id": remote_id
                            if isinstance(remote_id, str)
                            and re.fullmatch(r"[A-Za-z0-9_-]+", remote_id)
                            else "malformed",
                            "key": remote_key
                            if isinstance(remote_key, str)
                            and re.fullmatch(r"[A-Z]+-[0-9]+[A-Z]?", remote_key)
                            else "malformed",
                        }
                        self.save()
                    return self.verify(created)

                issue = self.operation("harness", "create", local_sha, 0, create)
                if issue is None:
                    raise TrackingError("create outcome uncertain; discovery only on resume")
            self.issue = self.verify(issue)
            self.data.update(
                issue_id=self.issue["id"], issue_url=self.yt.url + "/issue/" + self.ticket
            )
            lines = self.text.strip().splitlines()
            definition = {
                "summary": lines[0].lstrip("# "),
                "description": "\n".join(lines[1:]).strip(),
            }
            digest = hashlib.sha256(self.text.encode()).hexdigest()

            def sync_definition() -> None:
                self.yt.request("POST", "issues/" + self.issue["id"], definition)

            self.operation(
                "harness", "definition:" + digest, local_sha, 0, sync_definition, repeatable=True
            )
            self.attach(self.ticket + ".md", self.text, "harness", local_sha, 0)
            try:
                fields = self.yt.request(
                    "GET",
                    "admin/projects/"
                    + self.issue["project"]["id"]
                    + "/customFields?fields=id,field(name,fieldType(isMultiValue,valueType)),$type,"
                    "bundle(values(id,name),aggregatedUsers(id,login))",
                )
                if not isinstance(fields, list):
                    raise TrackingError("unsupported project field schema")
                self.fields = [
                    f
                    for f in fields
                    if isinstance(f, dict)
                    and isinstance(f.get("field"), dict)
                    and isinstance(f["field"].get("name"), str)
                ]
                if len(self.fields) != len(fields):
                    self.warning("malformed project field definitions skipped")
            except Exception as error:
                self.fields = []
                self.warning(f"project field schema unavailable: {type(error).__name__}")
            # Coarse scope buckets, not a claim of precise implementation time.
            days = 1 if len(self.text) < 8000 else 3
            defaults = {
                "assignee": self.yconfig.get("assignee", "bodomus"),
                "estimation": f"{days}d",
                "due_date": (date.today() + timedelta(days=days + 2)).isoformat(),
            }
            for key, choices in {"type": ["Task", "Feature"], "priority": ["Normal"]}.items():
                name = self.yconfig.get("fields", {}).get(key, key.title())
                candidates = [f for f in self.fields if f["field"]["name"] == name]
                if len(candidates) == 1:
                    values = {
                        v.get("name") for v in candidates[0].get("bundle", {}).get("values", [])
                    }
                    safe = next((choice for choice in choices if choice in values), None)
                    if safe:
                        defaults[key] = safe
                    else:
                        self.warning(f"bootstrap field {name}: no supported conservative value")
            defaults.update(self.yconfig.get("defaults", {}))
            defaults = self.data.setdefault("bootstrap_defaults", defaults)
            self.save()
            self.apply_fields(defaults, "harness", local_sha, 0)

        # Reads always repeat: recover uncertain create by discovering exact key, never recreate.
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "ticket": self.ticket,
            "role": "harness",
            "action": "ensure_issue",
            "sha": local_sha,
            "status": "failed",
        }
        try:
            ensure()
            event.update(status="success", issue_id=self.data.get("issue_id"))
            self.save()
        except Exception as error:
            event["error_class"] = type(error).__name__
            if isinstance(error, IdentityError):
                self.data["identity_unsafe"] = True
            self.warning(f"bootstrap: {type(error).__name__}; local workflow continues")
        finally:
            event["remote_response_identity"] = self.data.get("create_response_identity")
            with (self.directory / "youtrack-events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event) + "\n")

    def apply_fields(self, proposed: dict[str, str], role: str, sha: str, round_: int) -> None:
        if not self.issue or self.data.get("identity_unsafe"):
            return
        names = {
            "assignee": "Assignee",
            "estimation": "Estimation",
            "due_date": "Due Date",
            "state": "State",
            "type": "Type",
            "priority": "Priority",
        }
        names.update(self.yconfig.get("fields", {}))
        for key, value in proposed.items():
            if self.data.get("identity_unsafe"):
                break

            def update(key: str = key, value: str = value) -> None:
                self.verify(
                    self.yt.request(
                        "GET",
                        "issues/" + self.ticket + "?fields=id,idReadable,project(id,shortName)",
                    )
                )
                candidates = [f for f in self.fields if f["field"]["name"] == names[key]]
                if len(candidates) != 1:
                    raise TrackingError("missing/ambiguous custom field")
                field = candidates[0]
                kind = field["$type"].removesuffix("ProjectCustomField")
                cardinal_kinds = {"Enum", "User", "Version", "Build", "Owned"}
                if kind not in cardinal_kinds | {"State", "Period", "Simple"}:
                    raise TrackingError("unsupported custom-field type")
                field_type = field["field"].get("fieldType", {})
                if kind in cardinal_kinds and not isinstance(field_type.get("isMultiValue"), bool):
                    raise TrackingError("unknown custom-field cardinality")
                prefix = "Multi" if field_type.get("isMultiValue") else "Single"
                type_ = (prefix + kind if kind in cardinal_kinds else kind) + "IssueCustomField"
                if kind == "Simple" and field_type.get("valueType") == "date":
                    type_ = "DateIssueCustomField"
                if type_ == "DateIssueCustomField" and key == "due_date":
                    target = date.fromisoformat(value)
                    if target < date.today():
                        raise TrackingError("past due date")
                    mapped: Any = int(
                        datetime.combine(target, datetime.min.time(), UTC).timestamp() * 1000
                    )
                elif type_ == "PeriodIssueCustomField" and key == "estimation":
                    if not re.fullmatch(r"\d+[wdhm](?: \d+[wdhm])*", value):
                        raise TrackingError("unsupported estimation")
                    mapped = {"presentation": value}
                else:
                    bundle = field.get("bundle", {})
                    values = (
                        bundle.get("aggregatedUsers", [])
                        if key == "assignee"
                        else bundle.get("values", [])
                    )
                    matches = [v for v in values if value in {v.get("name"), v.get("login")}]
                    if len(matches) != 1:
                        raise TrackingError("unsupported field value")
                    if not isinstance(matches[0].get("id"), str) or not matches[0]["id"]:
                        raise TrackingError("malformed bundle value identity")
                    mapped = {"id": matches[0]["id"]}
                    if type_.startswith("Multi"):
                        mapped = [mapped]
                self.yt.request(
                    "POST",
                    "issues/" + self.issue["id"],
                    {"customFields": [{"name": names[key], "$type": type_, "value": mapped}]},
                )

            self.operation(role, "field:" + key + ":" + value, sha, round_, update, repeatable=True)

    def lifecycle(
        self, action: str, manifest: dict[str, Any], role: str = "harness", stdout: str = ""
    ) -> None:
        sha, round_ = manifest["current_head_sha"], manifest["review_round"]
        try:
            intent = parse_intent(stdout, self.ticket, role)
        except Exception as error:
            self.warning(f"intent rejected: {type(error).__name__}")
            if isinstance(error, IdentityError):
                return
            intent = None
        if not self.issue or self.data.get("identity_unsafe"):
            return
        proposed = intent["proposed_fields"] if intent else {}
        self.apply_fields(proposed, role, sha, round_)
        state = self.yconfig.get("states", {}).get(action, STATES.get(action))
        if state:
            self.apply_fields({"state": state}, role, sha, round_)
        if self.data.get("identity_unsafe"):
            return
        if action == "PASS":
            review_report = (self.root / "reviews" / f"review-{self.ticket}.md").resolve()
            if review_report.is_relative_to(self.root.resolve()) and review_report.is_file():
                self.attach(review_report.name, review_report.read_text("utf-8"), role, sha, round_)
        if action == "handoff":
            handoff_path = self.directory / "handoff.json"
            if handoff_path.exists():
                report = (
                    json.loads(handoff_path.read_text("utf-8"))
                    .get("implementer", {})
                    .get("implementation_report")
                )
                if isinstance(report, str):
                    path = (self.root / report).resolve()
                    if (
                        path.is_relative_to(self.root.resolve())
                        and path.is_file()
                        and path.suffix == ".md"
                    ):
                        self.attach(path.name, path.read_text("utf-8"), role, sha, round_)
        if self.data.get("identity_unsafe"):
            return
        if intent or action in {"handoff", "PASS", "CHANGES_REQUIRED"}:
            marker = f"[{self.ticket}:{role}:{round_}:{sha}:{action}]"
            text = f"{marker}\n{action} at {sha}."
            if action == "CHANGES_REQUIRED":
                review_path = self.directory / f"review-{round_}.json"
                if review_path.exists():
                    text += "\nFindings: " + json.dumps(
                        json.loads(review_path.read_text("utf-8")).get("findings", [])
                    )
            if action == "handoff":
                handoff_path = self.directory / "handoff.json"
                if handoff_path.exists():
                    text += "\nValidation: " + json.dumps(
                        json.loads(handoff_path.read_text("utf-8")).get("implementer", {})
                    )
            if intent:
                text += "\n" + intent["summary"] + "\n" + intent["comment"]

            def comment() -> None:
                self.verify(
                    self.yt.request(
                        "GET",
                        "issues/" + self.ticket + "?fields=id,idReadable,project(id,shortName)",
                    )
                )
                comments = (
                    self.yt.request(
                        "GET", "issues/" + self.issue["id"] + "/comments?fields=id,text&$top=1000"
                    )
                    or []
                )
                if not any(marker in c["text"] for c in comments):
                    self.yt.request(
                        "POST", "issues/" + self.issue["id"] + "/comments", {"text": text}
                    )

            self.operation(role, "comment:" + action, sha, round_, comment)

    def attach(self, filename: str, content: str, role: str, sha: str, round_: int) -> None:
        if not self.issue or self.data.get("identity_unsafe"):
            return
        digest = hashlib.sha256(content.encode()).hexdigest()

        def upload() -> None:
            self.verify(
                self.yt.request(
                    "GET", "issues/" + self.ticket + "?fields=id,idReadable,project(id,shortName)"
                )
            )
            boundary = "pdftranslate-" + digest
            payload = (
                f'--{boundary}\r\nContent-Disposition: form-data; name="upload"; '
                f'filename="{filename}"\r\nContent-Type: text/markdown\r\n\r\n'
                + content
                + f"\r\n--{boundary}--\r\n"
            ).encode()
            self.yt.request(
                "POST",
                "issues/" + self.issue["id"] + "/attachments",
                (payload, "multipart/form-data; boundary=" + boundary),
            )

        self.operation(role, "attachment:" + filename + ":" + digest, sha, round_, upload)

    def role_metadata(self, role: str, config: Any) -> None:
        self.data.setdefault("roles", {})[role] = {
            "provider": config.provider,
            "model": config.model,
        }
        self.save()

    def passed(self, manifest: dict[str, Any], config: Any) -> None:
        if manifest["state"] != "PASSED" or not self.gconfig.get("create_pr_on_pass"):
            return
        sha = manifest["current_head_sha"]
        output = self.directory / "human-review.json"
        output.unlink(
            missing_ok=True
        )  # Never leave stale readiness after a failed re-verification.
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "ticket": self.ticket,
            "role": "harness",
            "action": "ensure_pr",
            "sha": sha,
            "status": "failed",
        }
        try:
            if not self.gh:
                raise TrackingError("GitHub repository unavailable")
            handoff = json.loads((self.directory / "handoff.json").read_text("utf-8"))
            base = self.gconfig.get("base_branch", "master")
            title = self.text.splitlines()[0].lstrip("# ").replace(" — ", ": ")
            roles = self.data.get("roles", {})
            implementer = roles.get(
                "implementer", {"provider": "unavailable", "model": "unavailable"}
            )
            reviewer = roles.get("reviewer", {"provider": "unavailable", "model": "unavailable"})
            report = handoff["implementer"].get("implementation_report")
            report_evidence = ""
            if isinstance(report, str):
                path = (self.root / report).resolve()
                if path.is_relative_to(self.root.resolve()) and path.is_file():
                    report_evidence = (
                        "\n<details><summary>Implementation validation report</summary>\n\n"
                        + path.read_text("utf-8")[:20000]
                        + "\n</details>"
                    )
            body = "\n".join(
                [
                    f"Ticket: {self.ticket}",
                    f"YouTrack: {self.data.get('issue_url', 'unavailable')}",
                    f"Implementation SHA: {sha}",
                    f"Branch/base: {manifest['branch']} / {base}",
                    f"Implementer: {implementer['provider']} / {implementer['model']}",
                    f"Reviewer: {reviewer['provider']} / {reviewer['model']}",
                    f"Review rounds: {manifest['review_round']}; automated verdict: PASS",
                    "Validation evidence (local, NOT CI):\n```json\n"
                    + json.dumps(handoff["implementer"], indent=2)
                    + "\n```",
                    "Warnings: " + json.dumps(self.data["warnings"]),
                    "Human recovery history: " + json.dumps(manifest.get("human_recoveries", [])),
                    "CI: inspect exact-head checks on this PR; "
                    "local checks do not imply CI success.",
                    "READY FOR HUMAN REVIEW. Merge remains human-owned.",
                    report_evidence,
                ]
            )
            pr = self.gh.ensure(manifest["branch"], base, sha, title, body)
            document = {
                "ticket": self.ticket,
                "youtrack_url": self.data.get("issue_url"),
                "github_pr_url": pr["url"],
                "head_sha": sha,
                "base_branch": base,
                "verified_at": datetime.now(UTC).isoformat(),
                "cycle_state": "PASSED",
                "automated_review": "PASS",
                "ci_status": ci_status(pr.get("statusCheckRollup")),
                "checks": [
                    {
                        k: c[k]
                        for k in ("name", "workflowName", "state", "status", "conclusion")
                        if k in c
                    }
                    for c in (pr.get("statusCheckRollup") or [])
                ],
                "validation": handoff["implementer"],
                "warnings": self.data["warnings"],
                "review_rounds": manifest["review_round"],
                "roles": roles,
                "human_recoveries": manifest.get("human_recoveries", []),
            }
            staging = output.with_suffix(".tmp")
            staging.write_text(json.dumps(document, indent=2) + "\n", "utf-8")
            staging.replace(output)
            event.update(status="success", pr_url=pr["url"], ci_status=document["ci_status"])
            self.warn("Human review PR: " + pr["url"] + "; CI: " + document["ci_status"])
        except Exception as error:
            event["error_class"] = type(error).__name__
            self.warning(f"PR readiness unavailable: {type(error).__name__}; cycle remains PASSED")
        finally:
            with (self.directory / "github-events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event) + "\n")
