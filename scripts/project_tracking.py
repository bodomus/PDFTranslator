"""Harness-only external workflow integration; never decides local cycle verdicts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tomllib
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.review_protocol import (
    JSON_FENCE,
    REVIEW_SENTINEL_BEGIN,
    REVIEW_SENTINEL_END,
    ReviewProtocolError,
    single_envelope,
)

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
    "NEW": "Open",
    "IMPLEMENTING": "In Progress",
    "READY_FOR_REVIEW": "Ready for Review",
    "READY_FOR_REVIEW_2": "Ready for Review",
    "PASSED": "Ready for Human Review",
    "start": "In Progress",
    "handoff": "Ready for Review",
    "CHANGES_REQUIRED": "In Progress",
    "PASS": "Ready for Human Review",
    "merged": "Done",
}


class TrackingError(RuntimeError):
    pass


class UncertainTransport(TrackingError):
    """A terminated or timed-out client transport does not prove remote failure."""


class APIError(TrackingError):
    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"YouTrack HTTP {status}")


class IdentityError(TrackingError):
    pass


class SynchronizationBusy(TrackingError):
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
    """Select the strict review envelope before removing separate external metadata."""
    try:
        single_envelope(stdout)  # Reject ambiguous review envelopes before any stripping.
    except ReviewProtocolError as error:
        raise TrackingError(str(error)) from error
    protected: tuple[int, int] | None = None
    if REVIEW_SENTINEL_BEGIN in stdout:
        protected = (
            stdout.index(REVIEW_SENTINEL_BEGIN),
            stdout.index(REVIEW_SENTINEL_END) + len(REVIEW_SENTINEL_END),
        )
    elif match := JSON_FENCE.search(stdout):
        protected = match.span()

    spans: list[tuple[int, int]] = []
    opened: int | None = None
    for marker in re.finditer(re.escape(INTENT_BEGIN) + "|" + re.escape(INTENT_END), stdout):
        if marker.group() == INTENT_BEGIN:
            if opened is not None:
                raise TrackingError("nested tracking metadata delimiters")
            opened = marker.start()
        else:
            if opened is None:
                raise TrackingError("unmatched tracking metadata delimiter")
            spans.append((opened, marker.end()))
            opened = None
    if opened is not None:
        raise TrackingError("unmatched tracking metadata delimiter")
    if not spans:
        return stdout

    if protected is None:
        # Whole-stdout JSON also has a protected span. Skip leading external metadata
        # without rewriting stdout, then decode the first complete review object.
        offset = 0
        for start, end in spans:
            if stdout[offset:start].strip():
                break
            offset = end
        offset += len(stdout[offset:]) - len(stdout[offset:].lstrip())
        try:
            _, end = json.JSONDecoder().raw_decode(stdout, offset)
        except ValueError as error:
            raise TrackingError("invalid raw review before metadata stripping") from error
        protected = (offset, end)

    for start, end in spans:
        if start < protected[1] and end > protected[0]:
            raise TrackingError("tracking metadata overlaps the selected review envelope")
        metadata = stdout[start + len(INTENT_BEGIN) : end - len(INTENT_END)]
        # Invalid metadata remains non-blocking, but it must never hide a raw review.
        if re.search(r'"verdict"\s*:', metadata):
            raise TrackingError("tracking metadata contains a competing review verdict")

    for start, end in reversed(spans):
        stdout = stdout[:start] + stdout[end:]
    return stdout


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

    overall_timeout = 10.0

    def request(self, method: str, path: str, body: Any = None) -> Any:
        # DNS/TLS and trickling bodies must not hold the local workflow indefinitely.
        # A timeout is an uncertain outcome, never permission to retry a create.
        outcome: queue.Queue[Any] = queue.Queue(maxsize=1)

        def call() -> None:
            try:
                outcome.put((True, self._request(method, path, body)))
            except Exception as error:
                outcome.put((False, error))

        threading.Thread(target=call, daemon=True).start()
        try:
            success, value = outcome.get(timeout=self.overall_timeout)
        except queue.Empty:
            raise UncertainTransport("YouTrack overall timeout; remote outcome uncertain") from None
        if not success:
            if isinstance(value, TrackingError):
                raise value
            raise TrackingError("YouTrack transport/response failure") from None
        return value

    def _request(self, method: str, path: str, body: Any = None) -> Any:
        if path.startswith(("/", "\\")) or "://" in path or ".." in path:
            raise IdentityError("YouTrack request target refused")
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
            deadline = time.monotonic() + 10
            with build_opener(NoRedirect()).open(request, timeout=5) as response:
                if hasattr(response, "read1"):
                    chunks = []
                    size = 0
                    while True:
                        if time.monotonic() >= deadline:
                            raise TrackingError("YouTrack overall timeout")
                        chunk = response.read1(65536)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > 4 * 1024 * 1024:
                            raise TrackingError("YouTrack response too large")
                        chunks.append(chunk)
                    payload = b"".join(chunks)
                else:
                    payload = response.read()
                result = json.loads(payload) if payload else None
                if method == "GET" and result is None:
                    raise TrackingError("YouTrack empty/null read response")
                return result
        except HTTPError as error:
            if method == "GET" and error.code == 404:
                return None
            raise APIError(error.code) from None
        except Exception:
            # Once open() is entered, a mutation may have reached the server. Socket
            # timeout/connection loss, truncated JSON, and response-limit failures do
            # not prove it failed remotely, even after the client transport terminates.
            # HTTP errors above remain definite responses; pre-dispatch validation is
            # outside this try block. Never expose transport/server exception text.
            if method != "GET":
                raise UncertainTransport(
                    "YouTrack transport/response failure; remote outcome uncertain"
                ) from None
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
        neutral = (
            f"Expected reviewed SHA: {sha}\n"
            "Readiness: unavailable; exact PR head verification is required.\n"
            "Merge remains human-owned."
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
        if len(prs) > 1:
            raise IdentityError("ambiguous PR identity")
        if not prs:
            # Creation publishes no verdict/readiness even if the branch moves after this read.
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
                input_text=neutral,
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

        owner, repository = self.repository.split("/", 1)

        def verify(pr: dict[str, Any], *, exact_head: bool = True) -> None:
            if (
                pr.get("headRepositoryOwner", {}).get("login") != owner
                or pr.get("headRepository", {}).get("name") != repository
                or (pr["headRefName"], pr["baseRefName"]) != (branch, base)
            ):
                raise IdentityError("PR branch/base/repository differs from configured identity")
            if exact_head and pr["headRefOid"] != sha:
                raise IdentityError("PR head differs from reviewed implementation")

        def publish(metadata: str) -> None:
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
                input_text=metadata,
            )

        # Verify mutation identity separately: a moved SHA may be neutralized, but a
        # different head repository/branch/base must never gain mutation permission.
        verify(view(), exact_head=False)
        try:
            publish(neutral)
            pr = view()
            verify(pr)
            readiness = "\n".join(
                [
                    f"All review/validation evidence below applies to reviewed SHA {sha}.",
                    body,
                    f"Automated review for reviewed SHA {sha}: PASS",
                    f"READY FOR HUMAN REVIEW for reviewed SHA {sha}.",
                    f"CI snapshot for observed head SHA {sha}: "
                    + ci_status(pr.get("statusCheckRollup")),
                    "CI observed at: " + datetime.now(UTC).isoformat(),
                ]
            )
            publish(readiness)
            pr = view()
            verify(pr)
            return pr
        except Exception:
            # Includes ambiguous edit/response failures: revoke possibly applied claims.
            publish(neutral)
            raise


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
        self.root, self.ticket, self.text = root, ticket, text
        self.warn = lambda message: warn(self.safe_text(message))
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
            url, token = self.yconfig.get("base_url"), os.getenv("YOUTRACK_TOKEN")
            override = os.getenv("YOUTRACK_URL")
            if override and override.rstrip("/") != str(url).rstrip("/"):
                raise IdentityError("YouTrack configured host mismatch")
            if url and token:
                self.yt = YouTrack(url, token)
        self.gh = github
        if self.gh is None and self.gconfig.get("create_pr_on_pass"):
            repository = self.gconfig.get("repository", "")
            if re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
                self.gh = GitHub(root, repository)
        self.issue: dict[str, Any] | None = None
        self.fields: list[dict[str, Any]] = []
        self.project: dict[str, Any] | None = None
        self.sync_failed = False

    def safe_text(self, text: str) -> str:
        token = getattr(getattr(self, "yt", None), "token", None) or os.getenv("YOUTRACK_TOKEN")
        return text.replace(token, "[REDACTED]") if token else text

    def save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        staging = self.path.with_suffix(".tmp")
        staging.write_text(self.safe_text(json.dumps(self.data, indent=2)) + "\n", "utf-8")
        staging.replace(self.path)

    def warning(self, message: str, *, persist: bool = True) -> None:
        message = self.safe_text(message)
        if message not in self.data["warnings"]:
            self.data["warnings"].append(message)
        self.warn(f"[{self.ticket}] Integration warning: " + message)
        if persist:
            self.save()

    def synchronization_failure(self, error: Exception) -> None:
        self.sync_failed = True
        # Never replace another owner's write-ahead fence with this instance's stale snapshot.
        self.warning(self.diagnostic(error), persist=False)

    def diagnostic(self, error: Exception) -> str:
        if isinstance(error, SynchronizationBusy):
            return "YouTrack synchronization busy; local workflow continues"
        if isinstance(error, APIError):
            return f"YouTrack HTTP {error.status}"
        if isinstance(error, IdentityError):
            return "YouTrack identity mismatch; remote mutation refused"
        if type(error) in {TrackingError, UncertainTransport}:
            # Only our fixed diagnostics; never arbitrary fake/server exception text.
            safe = str(error)
            if safe.startswith(
                (
                    "field unavailable:",
                    "field value unavailable:",
                    "read-after-write",
                    "YouTrack",
                    "exact issue absent",
                    "create outcome",
                    "unsupported",
                    "past due date",
                )
            ):
                return safe
        return "YouTrack transport/response failure"

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
        self.require_reconciled_writes()
        key = hashlib.sha256(f"{self.ticket}|{role}|{round_}|{sha}|{action}".encode()).hexdigest()
        previous = self.data["operations"].get(key)
        if previous and not repeatable:
            if previous["status"] != "success":
                self.warning(
                    f"YouTrack uncertain prior {action}; discovery/reconciliation required"
                )
                self.sync_failed = True
            return previous.get("result")
        self.data["operations"][key] = {"status": "pending", "conflicting_write": repeatable}
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
            self.sync_failed = True
            # Never include arbitrary server/error text, which may contain credentials.
            event.update(
                status="failed",
                error_class=type(error).__name__,
                message="external operation failed; local workflow continues",
            )
            self.data["operations"][key] = {
                "status": "uncertain" if isinstance(error, UncertainTransport) else "failed",
                "conflicting_write": repeatable,
            }
            if isinstance(error, IdentityError):
                self.data["identity_unsafe"] = True
            self.warning(f"{action}: {self.diagnostic(error)}; local workflow continues")
            return None
        finally:
            self.data.update(
                last_sync_role=role,
                last_sync_sha=sha,
                last_sync_status=event["status"],
                last_sync_action=action,
            )
            self.save()
            with (self.directory / "youtrack-events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(self.safe_text(json.dumps(event)) + "\n")

    def require_reconciled_writes(self) -> None:
        # Pending survives process death; uncertain survives any lost write response. Neither
        # lock release nor a later GET proves a detached transport cannot still write.
        if any(
            op.get("conflicting_write") and op.get("status") in {"pending", "uncertain"}
            for op in self.data["operations"].values()
        ):
            self.sync_failed = True
            self.data["last_sync_status"] = "failed"
            message = (
                "YouTrack uncertain prior field/definition write; operator reconciliation required"
            )
            self.warning(message)
            raise TrackingError(message)

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

    @contextmanager
    def synchronization(self, *, require_youtrack_writes: bool = True) -> Any:
        """OS-held, non-waiting lock shared by operator validation and harness calls."""
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / "youtrack.lock"
        if path.is_symlink():
            raise IdentityError("YouTrack lock symlink refused")
        with path.open("a+b") as stream:
            if os.name == "nt":
                import msvcrt

                def lock() -> None:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)

                def unlock() -> None:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                def lock() -> None:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                def unlock() -> None:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

            try:
                lock()
            except OSError:
                raise SynchronizationBusy(
                    "YouTrack synchronization busy; local workflow continues"
                ) from None
            try:
                if self.path.exists():
                    fresh = json.loads(self.path.read_text("utf-8"))
                    self.data.clear()
                    self.data.update(fresh)
                    if self.data.get("ticket") != self.ticket:
                        raise IdentityError("tracking artifact target mismatch")
                if require_youtrack_writes:
                    self.require_reconciled_writes()
                yield
            finally:
                unlock()

    def preflight(self) -> str:
        status = "disabled"
        if self.yconfig.get("enabled"):
            status = "credentials unavailable"
            if self.yt:
                stage = "authentication"
                try:
                    account = self.yt.request("GET", "users/me?fields=id,login")
                    if not isinstance(account, dict) or not account.get("login"):
                        raise TrackingError("YouTrack authentication response unavailable")
                    expected = self.yconfig.get("expected_login")
                    if expected and account["login"] != expected:
                        raise IdentityError("unexpected authenticated account")
                    stage = "project"
                    projects = self.yt.request(
                        "GET", "admin/projects?fields=id,shortName&$top=1000"
                    )
                    matches = [
                        p
                        for p in (projects or [])
                        if p.get("shortName") == self.yconfig.get("project", "PDFTR")
                    ]
                    if len(matches) != 1:
                        status = "project unavailable"
                    else:
                        self.project = matches[0]
                        stage = "endpoint"
                        try:
                            fields = self.yt.request(
                                "GET",
                                "admin/projects/"
                                + quote(self.project["id"], safe="")
                                + "/customFields?fields=id,field(name,"
                                "fieldType(isMultiValue,valueType)),$type,"
                                "bundle(values(id,name),aggregatedUsers(id,login))&$top=1000",
                            )
                        except APIError:
                            raise
                        except Exception:
                            fields = None
                            self.warning("YouTrack project field endpoint unavailable")
                        self.fields = (
                            [
                                f
                                for f in fields
                                if isinstance(f, dict)
                                and isinstance(f.get("field"), dict)
                                and isinstance(f["field"].get("name"), str)
                            ]
                            if isinstance(fields, list)
                            else []
                        )
                        if not isinstance(fields, list):
                            self.warning("YouTrack project field schema unavailable")
                        elif len(self.fields) != len(fields):
                            self.warning("malformed project field definitions skipped")
                        status = "ready"
                except APIError as error:
                    status = (
                        "authentication failed"
                        if error.status == 401
                        or (error.status == 403 and stage == "authentication")
                        else "project unavailable"
                        if stage == "project"
                        else "endpoint unavailable"
                    )
                except IdentityError as error:
                    self.data["identity_unsafe"] = True
                    self.warning(self.diagnostic(error))
                    status = "authentication failed"
                except Exception:
                    status = "transport/endpoint unavailable"
        self.data["preflight_status"] = status
        self.warn(f"[{self.ticket}] YouTrack: {status}")
        if status not in {"ready", "disabled"}:
            self.warning("YouTrack " + status)
        return status

    def ensure_youtrack_issue(self, *, allow_create: bool = False, dry_run: bool = False) -> Any:
        if self.yconfig.get("project", "PDFTR") != self.ticket.split("-", 1)[0]:
            raise IdentityError("configured project does not match ticket key")
        if not re.match(r"#\s+" + re.escape(self.ticket) + r"(?:\s|:|$)", self.text):
            raise IdentityError("Markdown ticket identity mismatch")
        query = "?fields=id,idReadable,project(id,shortName)"
        issue = self.yt.request("GET", "issues/" + self.ticket + query)
        if issue is None:
            if dry_run:
                self.warn(f"Would create: {self.ticket} (requires --allow-create)")
                return None
            if not allow_create:
                raise TrackingError(
                    "exact issue absent; remote create unavailable (explicit permission required)"
                )

            def create() -> Any:
                # Recheck under the synchronization lock, including a remote race before POST.
                found = self.yt.request("GET", "issues/" + self.ticket + query)
                if found is not None:
                    return self.verify(found)
                lines = self.text.strip().splitlines()
                try:
                    created = self.yt.request(
                        "POST",
                        "issues" + query,
                        {
                            "project": {"id": self.project["id"]},
                            "summary": lines[0].lstrip("# "),
                            "description": "\n".join(lines[1:]).strip(),
                        },
                    )
                except Exception as error:
                    if isinstance(error, APIError) and error.status < 500 and error.status != 409:
                        raise
                    # Lost response/conflict: only exact discovery can authorize continuation.
                    found = self.yt.request("GET", "issues/" + self.ticket + query)
                    if found is None:
                        raise TrackingError(
                            "create outcome uncertain; discovery only on resume"
                        ) from None
                    return self.verify(found)
                if isinstance(created, dict):
                    self.data["create_response_identity"] = {
                        "id": created.get("id")
                        if re.fullmatch(r"[\w-]+", str(created.get("id", "")))
                        else "malformed",
                        "key": created.get("idReadable")
                        if re.fullmatch(r"[A-Z]+-[0-9]+", str(created.get("idReadable", "")))
                        else "malformed",
                    }
                    self.save()
                verified = self.verify(created)
                reread = self.verify(self.yt.request("GET", "issues/" + verified["id"] + query))
                if reread != verified:
                    raise IdentityError("create read-back identity mismatch")
                canonical = self.verify(self.yt.request("GET", "issues/" + self.ticket + query))
                if canonical != verified:
                    raise IdentityError("duplicate/conflicting issue identity")
                self.warn(f"[{self.ticket}] YouTrack created issue {self.ticket}")
                return canonical

            issue = self.operation(
                "harness", "create", self.data.get("bootstrap_sha", ""), 0, create
            )
            if issue is None:
                raise TrackingError("create outcome uncertain; discovery only on resume")
        self.issue = self.verify(issue)
        self.data.update(
            issue_id=self.issue["id"],
            issue_key=self.ticket,
            project=self.issue["project"]["shortName"],
            issue_url=self.yt.url + "/issue/" + self.ticket,
        )
        self.warn(f"[{self.ticket}] YouTrack ready: {self.ticket}")
        return self.issue

    def bootstrap(
        self,
        manifest: dict[str, Any] | None = None,
        *,
        allow_create: bool | None = None,
        mutate: bool = True,
        dry_run: bool = False,
    ) -> None:
        try:
            with self.synchronization():
                self._bootstrap(manifest, allow_create=allow_create, mutate=mutate, dry_run=dry_run)
        except Exception as error:
            self.synchronization_failure(error)

    def _bootstrap(
        self,
        manifest: dict[str, Any] | None = None,
        *,
        allow_create: bool | None = None,
        mutate: bool = True,
        dry_run: bool = False,
    ) -> None:
        self.sync_failed = False
        self.issue = None
        local_sha = self.data.setdefault(
            "bootstrap_sha", manifest["current_head_sha"] if manifest else ""
        )
        if self.ticket in {f"PDFTR-{number}" for number in range(38, 43)}:
            self.warning("historical placeholder excluded from automatic YouTrack synchronization")
            return
        if self.yconfig.get("project", "PDFTR") != self.ticket.split("-", 1)[0]:
            self.data["identity_unsafe"] = True
            self.warning("configured project does not match ticket key")
            return
        status = self.preflight()
        if status != "ready" or self.data.get("identity_unsafe"):
            if status != "disabled":
                self.save()
            return

        def ensure() -> Any:
            if self.yconfig.get("project", "PDFTR") != self.ticket.split("-", 1)[0]:
                raise IdentityError("configured project does not match ticket key")
            if not re.match(r"#\s+" + re.escape(self.ticket) + r"(?:\s|:|$)", self.text):
                raise IdentityError("Markdown ticket identity mismatch")
            defaults = {"assignee": self.yconfig.get("assignee", "bodomus")}
            defaults.update(self.yconfig.get("defaults", {}))
            self.validate_field_values(defaults)
            self.discover_mappings()
            if dry_run:
                self.warn("Would assign: " + self.yconfig.get("assignee", "bodomus"))
                for key, value in self.yconfig.get("defaults", {}).items():
                    self.warn(f"Would set {key}: {value}")
            self.ensure_youtrack_issue(
                allow_create=(
                    self.yconfig.get("allow_create", False)
                    if allow_create is None
                    else allow_create
                )
                and mutate
                and not dry_run,
                dry_run=dry_run,
            )
            if not self.issue:
                return
            if not mutate or dry_run:
                return
            lines = self.text.strip().splitlines()
            definition = {
                "summary": lines[0].lstrip("# "),
                "description": "\n".join(lines[1:]).strip(),
            }
            digest = hashlib.sha256(self.text.encode()).hexdigest()

            def sync_definition() -> None:
                query = "?fields=id,idReadable,project(id,shortName),summary,description"
                remote = self.yt.request("GET", "issues/" + self.ticket + query)
                self.verify(remote)
                if all(remote.get(k) == v for k, v in definition.items()):
                    return
                self.yt.request("POST", "issues/" + self.issue["id"], definition)
                remote = self.yt.request("GET", "issues/" + self.ticket + query)
                self.verify(remote)
                if not all(remote.get(k) == v for k, v in definition.items()):
                    raise TrackingError("read-after-write mismatch: ticket definition")

            self.operation(
                "harness", "definition:" + digest, local_sha, 0, sync_definition, repeatable=True
            )
            self.attach(self.ticket + ".md", self.text, "harness", local_sha, 0)
            self.data["bootstrap_defaults"] = defaults
            self.save()
            self._apply_fields(defaults, "harness", local_sha, 0)

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
            event.update(
                status="partial" if self.sync_failed else "success",
                issue_id=self.data.get("issue_id"),
            )
            self.save()
        except Exception as error:
            self.sync_failed = True
            event["error_class"] = type(error).__name__
            if isinstance(error, IdentityError):
                self.data["identity_unsafe"] = True
            self.warning(f"bootstrap: {self.diagnostic(error)}; local workflow continues")
        finally:
            self.data.update(last_sync_status=event["status"], last_sync_action="ensure_issue")
            self.save()
            event["remote_response_identity"] = self.data.get("create_response_identity")
            with (self.directory / "youtrack-events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(self.safe_text(json.dumps(event)) + "\n")

    def discover_mappings(self) -> None:
        names = {
            "assignee": "Assignee",
            "state": "State",
            "estimation": "Estimation",
            "due_date": "Due Date",
        }
        names.update(self.yconfig.get("fields", {}))
        for name in names.values():
            candidates = [f for f in self.fields if f["field"]["name"] == name]
            if len(candidates) != 1:
                self.warning("field unavailable: " + name)
        states = [f for f in self.fields if f["field"]["name"] == names["state"]]
        if len(states) == 1:
            values = {v.get("name") for v in states[0].get("bundle", {}).get("values", [])}
            for target in set({**STATES, **self.yconfig.get("states", {})}.values()):
                if target not in values:
                    self.warning("field value unavailable: State -> " + target)
        self.resolve_assignee(self.yconfig.get("assignee", "bodomus"))

    def resolve_assignee(self, login: str) -> dict[str, Any] | None:
        try:
            users = self.yt.request(
                "GET", "users?query=" + quote(login, safe="") + "&fields=id,login&$top=1000"
            )
            matches = [u for u in (users or []) if u.get("login") == login]
            if len(matches) == 1 and isinstance(matches[0].get("id"), str):
                return {"id": matches[0]["id"]}
        except Exception:
            pass
        self.warning("field value unavailable: Assignee (login unresolved)")
        return None

    def read_field(self, name: str) -> Any:
        remote = self.yt.request(
            "GET",
            "issues/" + self.ticket + "?fields=id,idReadable,project(id,shortName),"
            "customFields(name,value(id,presentation,minutes))",
        )
        self.verify(remote)
        values = [f.get("value") for f in remote.get("customFields", []) if f.get("name") == name]
        if len(values) > 1:
            raise TrackingError("read-after-write ambiguous field")
        return values[0] if values else None

    @staticmethod
    def same_value(actual: Any, expected: Any) -> bool:
        if isinstance(expected, list):
            return isinstance(actual, list) and sorted(v.get("id", "") for v in actual) == sorted(
                v["id"] for v in expected
            )
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                return False
            if "id" in expected:
                return actual.get("id") == expected["id"]
            # Preserve period units; do not assume a project's workday/week duration.
            return re.sub(r"\s+", "", str(actual.get("presentation", ""))) == re.sub(
                r"\s+", "", expected["presentation"]
            )
        return type(actual) is type(expected) and actual == expected

    def apply_fields(self, proposed: dict[str, str], role: str, sha: str, round_: int) -> None:
        try:
            with self.synchronization():
                self._apply_fields(proposed, role, sha, round_)
        except Exception as error:
            self.synchronization_failure(error)

    @staticmethod
    def validate_field_values(proposed: dict[str, Any]) -> None:
        for key, value in proposed.items():
            if not isinstance(value, str):
                raise TrackingError(f"unsupported {key}; expected string")
            if key == "estimation" and not re.fullmatch(r"\d+[wdhm](?: \d+[wdhm])*", value):
                raise TrackingError("unsupported estimation; expected unit-bearing period string")
            if key == "due_date":
                try:
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        raise ValueError
                    date.fromisoformat(value)
                except ValueError:
                    raise TrackingError("unsupported due date; expected ISO YYYY-MM-DD") from None

    def _apply_fields(self, proposed: dict[str, str], role: str, sha: str, round_: int) -> None:
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
            try:
                self.validate_field_values({key: value})
            except TrackingError as error:
                self.sync_failed = True
                self.warning(self.diagnostic(error))
                continue

            def update(key: str = key, value: str = value) -> None:
                self.verify(
                    self.yt.request(
                        "GET",
                        "issues/" + self.ticket + "?fields=id,idReadable,project(id,shortName)",
                    )
                )
                candidates = [f for f in self.fields if f["field"]["name"] == names[key]]
                if len(candidates) != 1:
                    raise TrackingError("field unavailable: " + names[key])
                field = candidates[0]
                kind = field["$type"].removesuffix("ProjectCustomField")
                cardinal_kinds = {"Enum", "User", "Version", "Build", "Owned"}
                expected_kind = {
                    "assignee": "User",
                    "state": "State",
                    "estimation": "Period",
                    "due_date": "Simple",
                    "type": "Enum",
                    "priority": "Enum",
                }
                if kind not in cardinal_kinds | {
                    "State",
                    "Period",
                    "Simple",
                } or kind != expected_kind.get(key):
                    raise TrackingError("unsupported custom-field type")
                field_type = field["field"].get("fieldType", {})
                if key == "due_date" and field_type.get("valueType") != "date":
                    raise TrackingError("unsupported due date field type")
                if (
                    kind in {"State", "Period", "Simple"}
                    and field_type.get("isMultiValue") is not False
                ):
                    raise TrackingError("unsupported custom-field cardinality")
                if kind in cardinal_kinds and not isinstance(field_type.get("isMultiValue"), bool):
                    raise TrackingError("unknown custom-field cardinality")
                prefix = "Multi" if field_type.get("isMultiValue") else "Single"
                type_ = (prefix + kind if kind in cardinal_kinds else kind) + "IssueCustomField"
                if kind == "Simple" and field_type.get("valueType") == "date":
                    type_ = "DateIssueCustomField"
                if type_ == "DateIssueCustomField" and key == "due_date":
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        raise TrackingError("unsupported due date; expected ISO YYYY-MM-DD")
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
                    if key == "assignee":
                        user = self.resolve_assignee(value)
                        matches = [v for v in values if user and v.get("id") == user["id"]]
                    else:
                        matches = [v for v in values if value == v.get("name")]
                    if len(matches) != 1:
                        raise TrackingError("field value unavailable: " + names[key])
                    if not isinstance(matches[0].get("id"), str) or not matches[0]["id"]:
                        raise TrackingError("malformed bundle value identity")
                    mapped = {"id": matches[0]["id"]}
                    if type_.startswith("Multi"):
                        mapped = [mapped]
                if self.same_value(self.read_field(names[key]), mapped):
                    return
                self.yt.request(
                    "POST",
                    "issues/" + self.issue["id"],
                    {"customFields": [{"name": names[key], "$type": type_, "value": mapped}]},
                )
                if not self.same_value(self.read_field(names[key]), mapped):
                    raise TrackingError("read-after-write mismatch: " + names[key])
                if key == "state":
                    self.warn(f"[{self.ticket}] YouTrack state -> {value}")

            self.operation(role, "field:" + key + ":" + value, sha, round_, update, repeatable=True)

    def lifecycle(
        self, action: str, manifest: dict[str, Any], role: str = "harness", stdout: str = ""
    ) -> None:
        try:
            with self.synchronization():
                self.sync_failed = False
                self._lifecycle(action, manifest, role, stdout)
                if self.issue:
                    self.data.update(
                        last_sync_action=action,
                        last_sync_status="failed"
                        if self.data.get("identity_unsafe")
                        else "partial"
                        if self.sync_failed
                        else "success",
                    )
                    self.save()
        except Exception as error:
            self.synchronization_failure(error)

    def _lifecycle(self, action: str, manifest: dict[str, Any], role: str, stdout: str) -> None:
        sha, round_ = manifest["current_head_sha"], manifest["review_round"]
        try:
            intent = parse_intent(stdout, self.ticket, role)
        except Exception as error:
            self.warning(f"intent rejected: {type(error).__name__}")
            if isinstance(error, IdentityError):
                self.sync_failed = True
                return
            intent = None
        if not self.issue or self.data.get("identity_unsafe"):
            return
        proposed = intent["proposed_fields"] if intent else {}
        self._apply_fields(proposed, role, sha, round_)
        state = self.yconfig.get("states", {}).get(action, STATES.get(action))
        done = self.yconfig.get("states", {}).get("merged", "Done")
        if state in {"Done", done} and action != "merged":
            self.warning("field value unavailable: Done requires explicit finalization")
        elif state:
            self._apply_fields({"state": state}, role, sha, round_)
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
        if intent or action in {"start", "handoff", "PASS", "CHANGES_REQUIRED"}:
            marker = f"[{self.ticket}:{role}:{round_}:{sha}:{action}]"
            text = f"{marker}\n{action} at {sha}."
            if action == "start":
                text += "\nImplementation started"
            if action in {"PASS", "CHANGES_REQUIRED"}:
                text += f"\nReview round {round_}: {action}"
            if action == "PASS":
                text += "\nReady for human review"
            # Agent prose is not verified CI/PR/review evidence; do not publish it as claims.

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
        try:
            with self.synchronization():
                self.data.setdefault("roles", {})[role] = {
                    "provider": config.provider,
                    "model": config.model,
                }
                self.save()
        except Exception as error:
            self.synchronization_failure(error)

    def passed(self, manifest: dict[str, Any], config: Any) -> None:
        if manifest["state"] != "PASSED" or not self.gconfig.get("create_pr_on_pass"):
            return
        try:
            with self.synchronization(require_youtrack_writes=False):
                self._passed(manifest, config)
        except Exception as error:
            self.synchronization_failure(error)

    def _passed(self, manifest: dict[str, Any], config: Any) -> None:
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
            youtrack_writes_allowed = True
            try:
                self.require_reconciled_writes()
            except TrackingError:
                youtrack_writes_allowed = False
                self.warning("YouTrack PR cross-link skipped; operator reconciliation required")
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
                    f"Review rounds: {manifest['review_round']}",
                    f"Validation evidence for reviewed SHA {sha} (local, NOT CI):\n```json\n"
                    + json.dumps(handoff["implementer"], indent=2)
                    + "\n```",
                    "Warnings: " + json.dumps(self.data["warnings"]),
                    "Human recovery history: " + json.dumps(manifest.get("human_recoveries", [])),
                    f"CI evidence must match reviewed SHA {sha}; "
                    "local checks do not imply CI success.",
                    "Merge remains human-owned.",
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
            if youtrack_writes_allowed and self.issue and not self.data.get("identity_unsafe"):
                marker = f"[{self.ticket}:pr:{sha}]"

                def crosslink() -> None:
                    self.verify(
                        self.yt.request(
                            "GET",
                            "issues/" + self.ticket + "?fields=id,idReadable,project(id,shortName)",
                        )
                    )
                    comments = self.yt.request(
                        "GET", "issues/" + self.issue["id"] + "/comments?fields=id,text&$top=1000"
                    )
                    if not any(marker in c["text"] for c in comments):
                        self.yt.request(
                            "POST",
                            "issues/" + self.issue["id"] + "/comments",
                            {
                                "text": marker
                                + "\nPR: "
                                + pr["url"]
                                + "\nImplementation SHA: "
                                + sha
                                + "\nCI snapshot: "
                                + document["ci_status"]
                            },
                        )

                self.operation("harness", "pr-link", sha, manifest["review_round"], crosslink)
            self.warn("Human review PR: " + pr["url"] + "; CI: " + document["ci_status"])
        except Exception as error:
            event["error_class"] = type(error).__name__
            self.warning(f"PR readiness unavailable: {type(error).__name__}; cycle remains PASSED")
        finally:
            with (self.directory / "github-events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(self.safe_text(json.dumps(event)) + "\n")


def validate_live(
    tracking: ProjectTracking,
    *,
    dry_run: bool = False,
    allow_create: bool = False,
    apply_fields: bool = False,
    state: str | None = None,
    finalize: bool = False,
) -> int:
    """Operator-only validation; default is remote read-only, never advances a local cycle."""
    target = (
        tracking.yconfig.get("states", {}).get(state, STATES.get(state, state)) if state else None
    )
    done = tracking.yconfig.get("states", {}).get("merged", "Done")
    if (state == "merged" or target in {"Done", done}) and not finalize:
        raise TrackingError("Done requires explicit --finalize")
    mutate = (allow_create or apply_fields or state is not None) and not dry_run
    tracking.bootstrap(allow_create=allow_create, mutate=mutate, dry_run=dry_run)
    if dry_run:
        if state:
            target = tracking.yconfig.get("states", {}).get(state, STATES.get(state, state))
            tracking.warn("Would set state: " + target)
        tracking.warn("Dry-run: no remote mutation")
    elif tracking.issue and mutate:
        if tracking.sync_failed:
            return 1
        if state:
            target = tracking.yconfig.get("states", {}).get(state, STATES.get(state, state))
            # Do not publish simulated SHA/review/CI evidence during operator validation.
            tracking.apply_fields({"state": target}, "operator", "", 0)
            if tracking.sync_failed:
                return 1
        tracking.bootstrap(allow_create=allow_create, mutate=True)
        if tracking.sync_failed:
            return 1
        if state:
            tracking.apply_fields({"state": target}, "operator", "", 0)
        if tracking.sync_failed:
            return 1
        tracking.warn(
            "Idempotent second synchronization completed; inspect warnings for limitations"
        )
    else:
        tracking.warn("Read-only validation: no remote mutation")
    return (
        0
        if (
            tracking.data.get("preflight_status") == "ready"
            and tracking.issue
            and not tracking.sync_failed
            and not tracking.data.get("identity_unsafe")
        )
        else 1
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explicit operator YouTrack validation")
    parser.add_argument("command", choices=["validate-live"])
    parser.add_argument("ticket")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-create", action="store_true")
    parser.add_argument("--apply-fields", action="store_true")
    parser.add_argument("--state", help="Configured lifecycle action or exact discovered state")
    parser.add_argument("--finalize", action="store_true", help="Explicit human close signal")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"PDFTR-[1-9][0-9]*", args.ticket):
        parser.error("exact PDFTR ticket key required")
    root = Path(__file__).resolve().parents[1]
    tickets = list((root / "Tickets").glob(args.ticket + "*.md"))
    tickets = [
        p
        for p in tickets
        if re.match(r"#\s+" + re.escape(args.ticket) + r"(?:\s|:|$)", p.read_text("utf-8"))
    ]
    if len(tickets) != 1:
        parser.error("exact local Markdown ticket unavailable/ambiguous")
    try:
        tracking = ProjectTracking(root, args.ticket, tickets[0].read_text("utf-8"))
        return validate_live(
            tracking,
            dry_run=args.dry_run,
            allow_create=args.allow_create,
            apply_fields=args.apply_fields,
            state=args.state,
            finalize=args.finalize,
        )
    except Exception as error:
        # Never expose raw exception text (including local configuration parse errors).
        print(
            f"[{args.ticket}] Integration warning: validation unavailable ({type(error).__name__})"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
