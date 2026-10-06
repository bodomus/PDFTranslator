"""Deterministic external workflow tests: no network, tokens or providers."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from scripts.pi_ticket_cycle import (
    REVIEW_SENTINEL_BEGIN,
    REVIEW_SENTINEL_END,
    RunnerError,
    extract_review_json,
)
from scripts.project_tracking import (
    INTENT_BEGIN,
    INTENT_END,
    GitHub,
    IdentityError,
    ProjectTracking,
    TrackingError,
    child_environment,
    ci_status,
    parse_intent,
    review_without_intent,
)

TICKET = "PDFTR-43"
SHA = "a" * 40
CONFIG = {
    "youtrack": {"enabled": True, "project": "PDFTR", "assignee": "bodomus", "allow_create": True},
    "github": {"create_pr_on_pass": True},
}
TEXT = "# PDFTR-43 — Integration\n\nTask body.\n"


def field(name: str, kind: str, values: list[dict[str, str]] | None = None) -> dict[str, Any]:
    bundle_key = "aggregatedUsers" if kind == "User" else "values"
    return {
        "field": {
            "name": name,
            "fieldType": {"valueType": "date" if kind == "Date" else kind, "isMultiValue": False},
        },
        "$type": ("Simple" if kind == "Date" else kind) + "ProjectCustomField",
        "bundle": {bundle_key: values or []},
    }


class FakeYouTrack:
    url = "https://tracker.example"

    def __init__(self, exists: bool = True, wrong: bool = False) -> None:
        self.issue: dict[str, Any] | None = (
            {
                "id": "1-43",
                "idReadable": "OTHER-1" if wrong else TICKET,
                "project": {"id": "p", "shortName": "PDFTR"},
            }
            if exists
            else None
        )
        self.fields = [
            field("Assignee", "User", [{"id": "u", "login": "bodomus"}]),
            field("Estimation", "Period"),
            field("Due Date", "Date"),
            field(
                "State",
                "State",
                [
                    {"id": str(i), "name": name}
                    for i, name in enumerate(
                        [
                            "In Progress",
                            "Ready for Review",
                            "Ready for Human Review",
                            "Done",
                            "Open",
                        ]
                    )
                ],
            ),
        ]
        self.calls: list[tuple[str, str, Any]] = []
        self.comments: list[dict[str, Any]] = []
        self.outage = False
        self.lose_create_response = False
        self.values: dict[str, Any] = {}

    def request(self, method: str, path: str, body: Any = None) -> Any:
        self.calls.append((method, path, body))
        if self.outage:
            raise TimeoutError("secret-token must never be logged")
        if method == "GET":
            if path.startswith("users/me"):
                return {"id": "u", "login": "bodomus"}
            if path.startswith("users?"):
                return [{"id": "u", "login": "bodomus"}]
            if path.startswith("issues/") and "/comments" not in path:
                if self.issue is None:
                    return None
                return {
                    **self.issue,
                    "customFields": [{"name": k, "value": v} for k, v in self.values.items()],
                }
            if path.startswith("admin/projects?"):
                return [{"id": "p", "shortName": "PDFTR"}]
            if "/customFields" in path:
                return self.fields
            if "/comments" in path:
                return self.comments
        elif path.startswith("issues?"):
            self.issue = {
                "id": "1-43",
                "idReadable": TICKET,
                "project": {"id": "p", "shortName": "PDFTR"},
            }
            if self.lose_create_response:
                raise TimeoutError("lost response")
            return self.issue
        elif "/comments" in path:
            self.comments.append(body)
        elif isinstance(body, dict) and "customFields" in body:
            for custom in body["customFields"]:
                self.values[custom["name"]] = custom["value"]
        elif isinstance(body, dict) and "summary" in body and self.issue:
            self.issue.update(body)
        return {}


def tracker(tmp_path: Path, yt: FakeYouTrack, **kwargs: Any) -> ProjectTracking:
    return ProjectTracking(
        tmp_path, TICKET, TEXT, config=CONFIG, youtrack=yt, warn=lambda _: None, **kwargs
    )


def manifest(state: str = "PASSED") -> dict[str, Any]:
    return {"state": state, "current_head_sha": SHA, "review_round": 1, "branch": "ticket-branch"}


def mutations(yt: FakeYouTrack) -> list[Any]:
    return [body for method, _, body in yt.calls if method == "POST"]


@pytest.mark.parametrize("exists", [True, False])
def test_bootstrap_reuses_or_creates_and_maps_markdown(tmp_path: Path, exists: bool) -> None:
    yt = FakeYouTrack(exists)
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    created = [
        body for method, path, body in yt.calls if method == "POST" and path.startswith("issues?")
    ]
    assert len(created) == (0 if exists else 1)
    definition = next(b for b in mutations(yt) if "summary" in b)
    assert definition["summary"] == "PDFTR-43 — Integration"
    assert definition["description"] == "Task body."
    fields = [b["customFields"][0] for b in mutations(yt) if "customFields" in b]
    assert fields[0]["value"] == {"id": "u"}
    assert fields[0]["$type"] == "SingleUserIssueCustomField"
    assert len(fields) == 1  # Never invent estimation or due date.
    tracker(tmp_path, yt).bootstrap()
    assert len(
        [1 for method, path, _ in yt.calls if method == "POST" and path.startswith("issues?")]
    ) == len(created)
    assert json.loads(tracking.path.read_text())["issue_id"] == "1-43"


def test_lost_create_response_discovered_without_duplicate(tmp_path: Path) -> None:
    yt = FakeYouTrack(False)
    yt.lose_create_response = True
    tracker(tmp_path, yt).bootstrap()
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    assert tracking.issue is not None
    assert len([1 for m, p, _ in yt.calls if m == "POST" and p.startswith("issues?")]) == 1


def test_unresolved_create_not_retried(tmp_path: Path) -> None:
    yt = FakeYouTrack(False)
    yt.lose_create_response = True
    tracker(tmp_path, yt).bootstrap()
    yt.issue = None
    tracker(tmp_path, yt).bootstrap()
    assert len([1 for m, p, _ in yt.calls if m == "POST" and p.startswith("issues?")]) == 1


@pytest.mark.parametrize("mismatch", ["key", "project", "id"])
def test_identity_mismatch_prevents_mutation(tmp_path: Path, mismatch: str) -> None:
    yt = FakeYouTrack()
    assert yt.issue
    if mismatch == "key":
        yt.issue["idReadable"] = "OTHER-3"
    elif mismatch == "project":
        yt.issue["project"]["shortName"] = "OTHER"
    else:
        del yt.issue["id"]
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    tracking.lifecycle("PASS", manifest())
    assert not mutations(yt)
    assert tracking.data["identity_unsafe"]


def test_wrong_created_key_fails_closed(tmp_path: Path) -> None:
    class WrongCreated(FakeYouTrack):
        def request(self, method: str, path: str, body: Any = None) -> Any:
            result = super().request(method, path, body)
            if method == "POST" and path.startswith("issues?"):
                result["idReadable"] = "PDFTR-44"
            return result

    yt = WrongCreated(False)
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    assert tracking.data["identity_unsafe"]
    assert len(mutations(yt)) == 1


@pytest.mark.parametrize(
    "action,state",
    [("start", "0"), ("handoff", "1"), ("CHANGES_REQUIRED", "0"), ("PASS", "2"), ("merged", "3")],
)
def test_lifecycle_idempotent(tmp_path: Path, action: str, state: str) -> None:
    yt = FakeYouTrack()
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    tracking.lifecycle(action, manifest())
    before = len(mutations(yt))
    tracking.lifecycle(action, manifest())
    assert len(mutations(yt)) == before
    states = [
        b["customFields"][0]["value"]
        for b in mutations(yt)
        if "customFields" in b and b["customFields"][0]["name"] == "State"
    ]
    assert states == [{"id": state}]
    resumed = tracker(tmp_path, yt)
    resumed.bootstrap()
    resumed.lifecycle(action, manifest())
    assert len(mutations(yt)) == before


def test_fields_unsupported_nonfatal_and_due_date(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    tracking.apply_fields(
        {
            "estimation": "nonsense",
            "priority": "Unknown",
            "due_date": (date.today() + timedelta(days=10)).isoformat(),
        },
        "implementer",
        SHA,
        1,
    )
    assert len(tracking.data["warnings"]) == 2
    assert mutations(yt)[-1]["customFields"][0]["name"] == "Due Date"


def intent(ticket: str = TICKET, role: str = "reviewer") -> str:
    return (
        INTENT_BEGIN
        + json.dumps(
            {
                "ticket": ticket,
                "role": role,
                "summary": "Complete",
                "proposed_fields": {"estimation": "2d"},
                "comment": "Validation passed",
            }
        )
        + INTENT_END
    )


def test_structured_intent_harness_only(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    before = len(mutations(yt))
    assert parse_intent(intent(), TICKET, "reviewer")
    assert len(mutations(yt)) == before
    tracking.lifecycle("PASS", manifest(), "reviewer", intent())
    assert "Validation passed" not in yt.comments[-1]["text"]
    assert "Review round 1: PASS" in yt.comments[-1]["text"]
    before = len(mutations(yt))
    another_sha = manifest()
    another_sha["current_head_sha"] = "c" * 40
    tracking.lifecycle("PASS", another_sha, "reviewer", intent("PDFTR-44"))
    assert len(mutations(yt)) == before
    assert any("intent rejected" in w for w in tracking.data["warnings"])


def test_outage_preserves_review_verdict_and_redacts_errors(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    tracking = tracker(tmp_path, yt)
    yt.outage = True
    tracking.bootstrap()
    tracking.lifecycle("PASS", manifest(), "reviewer", intent())
    verdict = {"verdict": "PASS"}
    stdout = json.dumps(verdict) + "\n" + intent()
    assert extract_review_json(review_without_intent(stdout, TICKET)) == verdict
    assert "secret-token" not in tracking.path.read_text()


def test_credentials_not_in_child_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("YOUTRACK_TOKEN", "YOUTRACK_URL", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.setenv(key, "secret")
    assert (
        not {"YOUTRACK_TOKEN", "YOUTRACK_URL", "GH_TOKEN", "GITHUB_TOKEN"}
        & child_environment().keys()
    )


@pytest.mark.parametrize(
    "checks,expected",
    [
        ([], "unavailable"),
        ([{"status": "IN_PROGRESS"}], "pending"),
        ([{"state": "PENDING"}], "pending"),
        ([{"conclusion": "SUCCESS"}], "passed"),
        ([{"conclusion": "FAILURE"}], "failed"),
        ([{"conclusion": "UNKNOWN"}], "unavailable"),
        ([{"conclusion": "SKIPPED"}], "unavailable"),
        ([{"conclusion": "NEUTRAL"}], "unavailable"),
        ([{"conclusion": "SUCCESS", "status": "IN_PROGRESS"}], "pending"),
    ],
)
def test_ci_states(checks: list[dict[str, Any]], expected: str) -> None:
    assert ci_status(checks) == expected


class FakeGitHub(GitHub):
    def __init__(self, root: Path, exists: bool = False) -> None:
        super().__init__(root, "owner/repo")
        self.exists = exists
        self.sha = SHA
        self.calls: list[tuple[str, ...]] = []
        self.bodies: list[str] = []
        self.body = ""
        self.pr = {
            "url": "https://github.example/pr/1",
            "headRefOid": SHA,
            "headRefName": "ticket-branch",
            "baseRefName": "master",
            "statusCheckRollup": [{"status": "IN_PROGRESS"}],
            "headRepositoryOwner": {"login": "owner"},
            "headRepository": {"name": "repo"},
        }

    def command(self, *args: str, input_text: str | None = None) -> Any:
        self.calls.append(args)
        if input_text is not None:
            self.bodies.append(input_text)
            self.body = input_text
        if args[:2] == ("pr", "list"):
            return [{"number": 1}] if self.exists else []
        if args[0] == "api":
            return {"sha": self.sha}
        if args[:2] == ("pr", "create"):
            self.exists = True
        if args[:2] == ("pr", "view"):
            return self.pr.copy()
        return None


@pytest.mark.parametrize("exists", [True, False])
def test_pr_create_reuse_exact_sha_and_resume(tmp_path: Path, exists: bool) -> None:
    gh = FakeGitHub(tmp_path, exists)
    assert gh.ensure("ticket-branch", "master", SHA, "title", "body")["headRefOid"] == SHA
    gh.ensure("ticket-branch", "master", SHA, "title", "body")
    assert sum(c[:2] == ("pr", "create") for c in gh.calls) == (0 if exists else 1)


@pytest.mark.parametrize("exists", [True, False])
def test_pr_moved_head_fails_closed(tmp_path: Path, exists: bool) -> None:
    gh = FakeGitHub(tmp_path, exists)
    gh.sha = "b" * 40
    gh.pr["headRefOid"] = "b" * 40
    with pytest.raises(IdentityError):
        gh.ensure("ticket-branch", "master", SHA, "title", "body")
    assert "READY FOR HUMAN REVIEW" not in gh.body
    assert "automated verdict: PASS" not in gh.body


def test_human_handoff_and_nonfatal_github_failure(tmp_path: Path) -> None:
    gh = FakeGitHub(tmp_path)
    tracking = tracker(tmp_path, FakeYouTrack(), github=gh)
    tracking.bootstrap()
    (tracking.directory / "handoff.json").write_text(
        json.dumps(
            {"implementer": {"focused_tests": "PASS", "full_tests": "PASS", "check_ps1": "PASS"}}
        )
    )
    config = SimpleNamespace(
        implementer=SimpleNamespace(provider="p", model="m"),
        reviewer=SimpleNamespace(provider="r", model="n"),
    )
    tracking.passed(manifest("READY_FOR_REVIEW"), config)
    output = tracking.directory / "human-review.json"
    assert not output.exists()
    tracking.passed(manifest(), config)
    assert json.loads(output.read_text())["ci_status"] == "pending"
    assert json.loads(output.read_text())["head_sha"] == SHA
    body = gh.bodies[-1]
    assert f"Implementation SHA: {SHA}" in body
    assert "NOT CI" in body and "human-owned" in body
    gh.pr["headRefOid"] = "b" * 40
    local = manifest()
    tracking.passed(local, config)
    assert local["state"] == "PASSED"
    assert not output.exists()
    assert tracking.data["warnings"]


def test_github_api_failure_nonfatal(tmp_path: Path) -> None:
    class BrokenGitHub(FakeGitHub):
        def command(self, *args: str, input_text: str | None = None) -> Any:
            raise TrackingError("outage")

    tracking = tracker(tmp_path, FakeYouTrack(), github=BrokenGitHub(tmp_path))
    tracking.directory.mkdir(parents=True)
    (tracking.directory / "handoff.json").write_text('{"implementer": {}}')
    config = SimpleNamespace(
        implementer=SimpleNamespace(provider="p", model="m"),
        reviewer=SimpleNamespace(provider="r", model="n"),
    )
    local = manifest()
    tracking.passed(local, config)
    assert local["state"] == "PASSED"
    assert "PR readiness unavailable" in tracking.data["warnings"][-1]
    assert (
        json.loads((tracking.directory / "github-events.jsonl").read_text())["status"] == "failed"
    )


def test_attachments_are_multipart_and_idempotent(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    uploads = [b for m, p, b in yt.calls if m == "POST" and p.endswith("/attachments")]
    assert len(uploads) == 1
    payload, content_type = uploads[0]
    assert TEXT.encode() in payload
    assert b'filename="PDFTR-43.md"' in payload
    assert content_type.startswith("multipart/form-data;")
    tracker(tmp_path, yt).bootstrap()
    assert len([1 for m, p, _ in yt.calls if m == "POST" and p.endswith("/attachments")]) == 1


def test_account_mismatch_and_markdown_identity(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    config = {"youtrack": {"enabled": True, "expected_login": "other-user"}}
    tracking = ProjectTracking(
        tmp_path, TICKET, TEXT, config=config, youtrack=yt, warn=lambda _: None
    )
    tracking.bootstrap()
    assert not mutations(yt)
    assert tracking.data["identity_unsafe"]
    other = ProjectTracking(
        tmp_path / "other",
        TICKET,
        "# PDFTR-44 Wrong",
        config=CONFIG,
        youtrack=yt,
        warn=lambda _: None,
    )
    other.bootstrap()
    assert not mutations(yt)


def test_multi_user_schema_introspection(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    yt.fields[0]["field"]["fieldType"]["isMultiValue"] = True
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    assignee = next(b["customFields"][0] for b in mutations(yt) if "customFields" in b)
    assert assignee["$type"] == "MultiUserIssueCustomField"
    assert assignee["value"] == [{"id": "u"}]


def test_historical_placeholder_not_mutated(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    tracking = ProjectTracking(
        tmp_path, "PDFTR-42", "# PDFTR-42 Old", config=CONFIG, youtrack=yt, warn=lambda _: None
    )
    tracking.bootstrap()
    assert not yt.calls


def test_tracking_io_failure_does_not_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.tracking_hooks as hooks
    from scripts.tracking_hooks import TrackingHooks

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise OSError("unavailable audit")

    monkeypatch.setattr(hooks, "ProjectTracking", broken)
    warnings: list[str] = []
    tracking = TrackingHooks(tmp_path, TICKET, TEXT, warnings.append)
    tracking.call("bootstrap")
    tracking.call("passed", manifest(), None)
    assert warnings and tracking.adapter is None


def test_moved_head_during_edit_fails_readiness(tmp_path: Path) -> None:
    class MovingGitHub(FakeGitHub):
        def command(self, *args: str, input_text: str | None = None) -> Any:
            result = super().command(*args, input_text=input_text)
            if args[:2] == ("pr", "edit"):
                self.pr["headRefOid"] = "b" * 40
            return result

    gh = MovingGitHub(tmp_path, True)
    with pytest.raises(IdentityError):
        gh.ensure("ticket-branch", "master", SHA, "title", "body")


def test_malformed_metadata_does_not_change_valid_review() -> None:
    stdout = '{"verdict": "PASS"}' + INTENT_BEGIN + '{"ticket": "OTHER"}' + INTENT_END
    assert extract_review_json(review_without_intent(stdout, TICKET))["verdict"] == "PASS"
    with pytest.raises(TrackingError):
        parse_intent(stdout, TICKET, "reviewer")


@pytest.mark.parametrize("envelope", ["sentinel", "fence", "nested"])
def test_metadata_cannot_hide_competing_review_envelope(envelope: str) -> None:
    from scripts.pi_ticket_cycle import REVIEW_SENTINEL_BEGIN, REVIEW_SENTINEL_END, RunnerError

    passing = REVIEW_SENTINEL_BEGIN + '{"verdict":"PASS"}' + REVIEW_SENTINEL_END
    competing = REVIEW_SENTINEL_BEGIN + '{"verdict":"CHANGES_REQUIRED"}' + REVIEW_SENTINEL_END
    stdout = passing + INTENT_BEGIN + competing + INTENT_END
    if envelope == "fence":
        stdout = (
            passing + INTENT_BEGIN + '```json\n{"verdict":"CHANGES_REQUIRED"}\n```' + INTENT_END
        )
    elif envelope == "nested":
        stdout = (
            REVIEW_SENTINEL_BEGIN
            + '{"verdict":"PASS"}'
            + INTENT_BEGIN
            + "{}"
            + INTENT_END
            + REVIEW_SENTINEL_END
        )
    with pytest.raises((RunnerError, TrackingError)):
        extract_review_json(review_without_intent(stdout, TICKET))


def test_duplicate_bounded_metadata_preserves_valid_review() -> None:
    metadata = INTENT_BEGIN + '{"ticket":"OTHER"}' + INTENT_END
    stdout = '{"verdict":"PASS"}' + metadata + metadata
    assert extract_review_json(review_without_intent(stdout, TICKET))["verdict"] == "PASS"
    with pytest.raises(TrackingError, match="ambiguous"):
        parse_intent(stdout, TICKET, "reviewer")


@pytest.mark.parametrize("schema", ["outage", "malformed", "mixed"])
def test_schema_failure_preserves_attachment_and_review_comment(
    tmp_path: Path, schema: str
) -> None:
    class UnsupportedSchema(FakeYouTrack):
        def request(self, method: str, path: str, body: Any = None) -> Any:
            if method == "GET" and "/customFields" in path:
                if schema == "outage":
                    raise TimeoutError("private server diagnostic")
                if schema == "malformed":
                    return {"unexpected": "schema"}
                return [None, {"field": {}}, *self.fields]
            return super().request(method, path, body)

    yt = UnsupportedSchema()
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap(manifest("NEW"))
    tracking.lifecycle("PASS", manifest(), "reviewer")
    assert len([p for m, p, _ in yt.calls if m == "POST" and p.endswith("/attachments")]) == 1
    assert len(yt.comments) == 1
    assert SHA in yt.comments[0]["text"]
    assert tracking.data["warnings"]
    assert "private server diagnostic" not in tracking.path.read_text("utf-8")
    updates = [b["customFields"][0] for b in mutations(yt) if "customFields" in b]
    if schema == "mixed":
        assert any(f["name"] == "Assignee" for f in updates)
    else:
        assert not updates


def test_idempotent_field_retry_after_transient_failure(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    yt.outage = True
    tracking.apply_fields({"estimation": "2d"}, "implementer", SHA, 1)
    yt.outage = False
    tracking.apply_fields({"estimation": "2d"}, "implementer", SHA, 1)
    count = len(mutations(yt))
    tracking.apply_fields({"estimation": "2d"}, "implementer", SHA, 1)
    assert len(mutations(yt)) == count
    assert mutations(yt)[-1]["customFields"][0]["value"] == {"presentation": "2d"}


def test_configurable_schema_and_state_names(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    yt.fields[-1]["field"]["name"] = "Workflow"
    yt.fields[-1]["bundle"]["values"] = [{"id": "ready", "name": "Human Review"}]
    config = {
        "youtrack": {
            "enabled": True,
            "fields": {"state": "Workflow"},
            "states": {"PASS": "Human Review"},
        }
    }
    tracking = ProjectTracking(
        tmp_path, TICKET, TEXT, config=config, youtrack=yt, warn=lambda _: None
    )
    tracking.bootstrap()
    tracking.lifecycle("PASS", manifest())
    update = next(
        b["customFields"][0]
        for b in mutations(yt)
        if "customFields" in b and b["customFields"][0]["name"] == "Workflow"
    )
    assert update["value"] == {"id": "ready"}


def test_pr_fork_identity_rejected(tmp_path: Path) -> None:
    gh = FakeGitHub(tmp_path, True)
    gh.pr["headRepositoryOwner"] = {"login": "other"}
    with pytest.raises(IdentityError):
        gh.ensure("ticket-branch", "master", SHA, "title", "body")
    assert not any(c[:2] == ("pr", "edit") for c in gh.calls)


def test_real_github_command_handles_non_json_create_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.project_tracking as module

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout="https://github.example/pr/1\n"),
    )
    assert GitHub(tmp_path, "owner/repo").command("pr", "create") is None


def test_real_youtrack_boundary_multipart_and_no_credentials_in_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from urllib.error import HTTPError

    import scripts.project_tracking as module

    calls: list[Any] = []

    class Opener:
        def open(self, request: Any, **kwargs: Any) -> Any:
            calls.append(request)
            raise HTTPError(request.full_url, 401, "token-secret", {}, None)

    monkeypatch.setattr(module, "build_opener", lambda *args: Opener())
    yt = module.YouTrack("https://tracker.example", "token-secret")
    with pytest.raises(TrackingError) as raised:
        yt.request("POST", "issues/1-43/attachments", (b"payload", "multipart/form-data"))
    assert "token-secret" not in str(raised.value)
    assert calls[0].data == b"payload"
    assert calls[0].headers["Content-type"] == "multipart/form-data"
    with pytest.raises(TrackingError):
        module.NoRedirect().redirect_request(None)


def test_bootstrap_sha_binding_survives_resume(tmp_path: Path) -> None:
    yt = FakeYouTrack(False)
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap(manifest("NEW"))
    resumed = tracker(tmp_path, yt)
    changed = manifest("READY_FOR_REVIEW")
    changed["current_head_sha"] = "b" * 40
    resumed.bootstrap(changed)
    assert resumed.data["bootstrap_sha"] == SHA
    assert len([1 for m, p, _ in yt.calls if m == "POST" and p.startswith("issues?")]) == 1
    events = [
        json.loads(line)
        for line in (tracking.directory / "youtrack-events.jsonl").read_text().splitlines()
    ]
    assert all(e["sha"] == SHA for e in events)


def test_past_due_date_warns_without_invalid_mutation(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    before = len(mutations(yt))
    tracking.apply_fields({"due_date": "2000-01-01"}, "implementer", SHA, 1)
    assert len(mutations(yt)) == before
    assert tracking.data["warnings"]


def test_optional_type_and_priority_from_existing_bundles(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    yt.fields.extend(
        [
            field("Type", "Enum", [{"id": "task", "name": "Task"}]),
            field("Priority", "Enum", [{"id": "normal", "name": "Normal"}]),
        ]
    )
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    assert "type" not in tracking.data["bootstrap_defaults"]
    assert "priority" not in tracking.data["bootstrap_defaults"]
    tracking.apply_fields({"type": "Task", "priority": "Normal"}, "operator", SHA, 0)
    assert yt.values["Type"] == {"id": "task"}
    assert yt.values["Priority"] == {"id": "normal"}


def test_missing_issue_with_wrong_configured_project_never_created(tmp_path: Path) -> None:
    yt = FakeYouTrack(False)
    tracking = ProjectTracking(
        tmp_path,
        TICKET,
        TEXT,
        config={"youtrack": {"project": "OTHER"}},
        youtrack=yt,
        warn=lambda _: None,
    )
    tracking.bootstrap()
    assert not mutations(yt)
    assert tracking.data["identity_unsafe"]


def test_identity_failure_during_state_blocks_later_comment(tmp_path: Path) -> None:
    class FlakyIdentity(FakeYouTrack):
        bad_once = False

        def request(self, method: str, path: str, body: Any = None) -> Any:
            if self.bad_once and method == "GET" and path.startswith("issues/"):
                self.bad_once = False
                assert self.issue
                return {**self.issue, "idReadable": "PDFTR-44"}
            return super().request(method, path, body)

    yt = FlakyIdentity()
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    before = len(mutations(yt))
    yt.bad_once = True
    tracking.lifecycle("PASS", manifest())
    assert tracking.data["identity_unsafe"]
    assert len(mutations(yt)) == before


def test_youtrack_rejects_credentials_in_url() -> None:
    from scripts.project_tracking import YouTrack

    for url in (
        "http://tracker.example",
        "https://user:pass@tracker.example",
        "https://tracker.example?token=secret",
        "https://tracker.example/secret",
    ):
        with pytest.raises(TrackingError):
            YouTrack(url, "secret")


def test_review_summary_attachment_after_pass(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    report = tmp_path / "reviews" / "review-PDFTR-43.md"
    report.parent.mkdir()
    report.write_text("# Completed work\n")
    tracking.lifecycle("PASS", manifest(), "reviewer")
    uploads = [b for m, p, b in yt.calls if m == "POST" and p.endswith("/attachments")]
    assert b'filename="review-PDFTR-43.md"' in uploads[-1][0]


def test_youtrack_empty_success_response_is_success(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.project_tracking as module

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def read(self) -> bytes:
            return b""

    monkeypatch.setattr(
        module, "build_opener", lambda *args: SimpleNamespace(open=lambda *a, **kw: Response())
    )
    assert (
        module.YouTrack("https://tracker.example", "secret").request("POST", "issues/1-43", {})
        is None
    )


def test_raw_youtrack_responses_are_not_persisted(tmp_path: Path) -> None:
    class ExtraResponse(FakeYouTrack):
        def request(self, method: str, path: str, body: Any = None) -> Any:
            result = super().request(method, path, body)
            if isinstance(result, dict):
                result["auth_token"] = "response-secret"
            return result

    tracking = tracker(tmp_path, ExtraResponse(False))
    tracking.bootstrap()
    assert tracking.issue
    assert "response-secret" not in tracking.path.read_text()
    assert "auth_token" not in tracking.path.read_text()


@pytest.mark.parametrize("unsupported", ["type", "cardinality", "bundle_id"])
def test_unknown_schema_shape_never_guesses_field_payload(tmp_path: Path, unsupported: str) -> None:
    yt = FakeYouTrack()
    if unsupported == "type":
        yt.fields[0]["$type"] = "FutureUserProjectCustomField"
    elif unsupported == "cardinality":
        del yt.fields[0]["field"]["fieldType"]["isMultiValue"]
    else:
        yt.fields[0]["bundle"]["aggregatedUsers"][0]["id"] = None
    tracking = tracker(tmp_path, yt)
    tracking.bootstrap()
    updates = [b["customFields"][0] for b in mutations(yt) if "customFields" in b]
    assert not any(f["name"] == "Assignee" for f in updates)
    assert tracking.data["warnings"]
    assert not any(f["name"] == "Due Date" for f in updates)
    tracking.apply_fields({"due_date": "2099-01-01"}, "operator", SHA, 0)
    assert yt.values["Due Date"] > 0


@pytest.mark.parametrize("payload", [b"", b"null"])
def test_malformed_read_response_is_not_issue_absence(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    import scripts.project_tracking as module

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def read(self) -> bytes:
            return payload

    monkeypatch.setattr(
        module, "build_opener", lambda *args: SimpleNamespace(open=lambda *a, **kw: Response())
    )
    with pytest.raises(TrackingError):
        module.YouTrack("https://tracker.example", "secret").request("GET", "issues/PDFTR-43")


def test_large_pr_body_uses_stdin_not_windows_command_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.project_tracking as module

    captured: dict[str, Any] = {}

    def run(command: list[str], **kwargs: Any) -> Any:
        captured.update(command=command, **kwargs)
        return SimpleNamespace(returncode=0, stdout="https://github.example/pr/1\n")

    monkeypatch.setattr(module.subprocess, "run", run)
    body = "audit context " * 10000
    GitHub(tmp_path, "owner/repo").command("pr", "edit", "1", "--body-file", "-", input_text=body)
    assert captured["input"] == body
    assert body not in captured["command"]
    assert captured["env"]["GH_HOST"] == "github.com"


def test_duplicate_and_reversed_intents_rejected() -> None:
    duplicate = INTENT_BEGIN + '{"ticket":"PDFTR-44","ticket":"PDFTR-43"}' + INTENT_END
    for stdout in (duplicate, INTENT_END + INTENT_BEGIN + "{}"):
        with pytest.raises(TrackingError):
            parse_intent(stdout, TICKET, "reviewer")


def complete_review() -> str:
    return json.dumps(
        {
            "schema_version": "1.0",
            "ticket": TICKET,
            "review_round": 1,
            "reviewed_sha": SHA,
            "verdict": "PASS",
            "findings": [],
            "blocked_reason": None,
        }
    )


def test_tracking_metadata_inside_selected_fence_cannot_hide_verdict() -> None:
    stdout = (
        "```json\n"
        + complete_review()[:-1]
        + INTENT_BEGIN
        + ',"verdict":"CHANGES_REQUIRED"'
        + INTENT_END
        + "}\n```"
    )
    with pytest.raises((RunnerError, TrackingError)):
        extract_review_json(review_without_intent(stdout, TICKET))


@pytest.mark.parametrize(
    "metadata",
    [
        INTENT_BEGIN + INTENT_BEGIN + "{}" + INTENT_END + INTENT_END,
        INTENT_END + INTENT_BEGIN + "{}",
        INTENT_BEGIN + "{}",
        INTENT_END,
        INTENT_BEGIN + "{}" + INTENT_END + INTENT_END,
    ],
)
def test_nested_or_malformed_tracking_boundaries_rejected(metadata: str) -> None:
    stdout = "```json\n" + complete_review() + "\n```" + metadata
    with pytest.raises((RunnerError, TrackingError)):
        extract_review_json(review_without_intent(stdout, TICKET))


def test_tracking_envelope_overlapping_review_rejected() -> None:
    stdout = INTENT_BEGIN + "```json\n" + complete_review() + INTENT_END + "\n```"
    with pytest.raises((RunnerError, TrackingError)):
        extract_review_json(review_without_intent(stdout, TICKET))


@pytest.mark.parametrize("envelope", ["fence", "sentinel", "raw"])
@pytest.mark.parametrize("position", ["before", "after"])
def test_separate_tracking_metadata_preserves_complete_review(envelope: str, position: str) -> None:
    body = complete_review()
    review = {
        "fence": "```json\n" + body + "\n```",
        "sentinel": REVIEW_SENTINEL_BEGIN + body + REVIEW_SENTINEL_END,
        "raw": body,
    }[envelope]
    stdout = intent() + "\n" + review if position == "before" else review + "\n" + intent()
    assert extract_review_json(review_without_intent(stdout, TICKET)) == json.loads(body)
    assert parse_intent(stdout, TICKET, "reviewer") is not None


def test_raw_competing_review_inside_tracking_metadata_rejected() -> None:
    competing = json.loads(complete_review())
    competing["verdict"] = "CHANGES_REQUIRED"
    stdout = (
        REVIEW_SENTINEL_BEGIN
        + complete_review()
        + REVIEW_SENTINEL_END
        + INTENT_BEGIN
        + json.dumps(competing)
        + INTENT_END
    )
    with pytest.raises((RunnerError, TrackingError)):
        extract_review_json(review_without_intent(stdout, TICKET))


class RacingGitHub(FakeGitHub):
    def __init__(self, root: Path, phase: str) -> None:
        super().__init__(root, exists=phase != "create")
        self.phase = phase

    def command(self, *args: str, input_text: str | None = None) -> Any:
        result = super().command(*args, input_text=input_text)
        if self.phase == "create" and args[:2] == ("pr", "create"):
            self.pr["headRefOid"] = "b" * 40
        if args[:2] == ("pr", "edit"):
            ready = "READY FOR HUMAN REVIEW" in (input_text or "")
            if self.phase == "neutral" and not ready or self.phase == "ready" and ready:
                self.pr["headRefOid"] = "b" * 40
        return result


def passed_tracking(root: Path, gh: FakeGitHub) -> ProjectTracking:
    tracking = tracker(root, FakeYouTrack(), github=gh)
    tracking.directory.mkdir(parents=True)
    (tracking.directory / "handoff.json").write_text(
        json.dumps({"implementer": {"focused_tests": "PASS", "full_tests": "PASS"}})
    )
    return tracking


@pytest.mark.parametrize("phase", ["create", "neutral", "ready"])
def test_pr_races_leave_remote_neutral_and_revoke_local_readiness(
    tmp_path: Path, phase: str
) -> None:
    gh = RacingGitHub(tmp_path, phase)
    gh.body = "READY FOR HUMAN REVIEW; automated verdict: PASS; CI: passed"
    tracking = passed_tracking(tmp_path, gh)
    output = tracking.directory / "human-review.json"
    output.write_text('{"stale":true}')
    tracking.passed(manifest(), None)
    assert "READY FOR HUMAN REVIEW" not in gh.body
    assert "PASS" not in gh.body
    assert "CI: passed" not in gh.body
    assert not output.exists()
    assert tracking.data["warnings"]
    if phase == "ready":
        assert any("READY FOR HUMAN REVIEW" in body for body in gh.bodies[:-1])


def test_stable_pr_stages_readiness_and_binds_ci_to_observed_sha(tmp_path: Path) -> None:
    gh = FakeGitHub(tmp_path)
    gh.pr["statusCheckRollup"] = [{"conclusion": "SUCCESS"}]
    tracking = passed_tracking(tmp_path, gh)
    tracking.passed(manifest(), None)
    assert "READY FOR HUMAN REVIEW" not in gh.bodies[0]
    assert "PASS" not in gh.bodies[0]
    assert f"READY FOR HUMAN REVIEW for reviewed SHA {SHA}" in gh.body
    assert f"Automated review for reviewed SHA {SHA}: PASS" in gh.body
    assert f"CI snapshot for observed head SHA {SHA}: passed" in gh.body
    output = json.loads((tracking.directory / "human-review.json").read_text())
    assert output["head_sha"] == SHA and output["ci_status"] == "passed"
    tracking.passed(manifest(), None)
    assert sum(c[:2] == ("pr", "create") for c in gh.calls) == 1


def test_stale_pr_recovers_only_after_new_sha_is_reviewed(tmp_path: Path) -> None:
    gh = RacingGitHub(tmp_path, "ready")
    tracking = passed_tracking(tmp_path, gh)
    tracking.passed(manifest(), None)
    assert "READY FOR HUMAN REVIEW" not in gh.body
    gh.phase = "stable"
    newly_reviewed = manifest()
    newly_reviewed["current_head_sha"] = "b" * 40
    tracking.passed(newly_reviewed, None)
    assert "READY FOR HUMAN REVIEW for reviewed SHA " + "b" * 40 in gh.body
    output = json.loads((tracking.directory / "human-review.json").read_text())
    assert output["head_sha"] == "b" * 40
    assert not any(c[:2] == ("pr", "create") for c in gh.calls)


@pytest.mark.parametrize("status", ["pending", "uncertain"])
@pytest.mark.parametrize("action", ["field:State", "definition"])
@pytest.mark.parametrize("moved_head", [False, True])
def test_youtrack_write_fence_does_not_block_github_readiness(
    tmp_path: Path, status: str, action: str, moved_head: bool
) -> None:
    gh = FakeGitHub(tmp_path)
    tracking = passed_tracking(tmp_path, gh)
    tracking.issue = tracking.verify(tracking.yt.issue)
    tracking.data["operations"][action] = {"status": status, "conflicting_write": True}
    tracking.save()
    # Reload the persisted fence under the shared lock, rather than relying on instance state.
    tracking.data["operations"].clear()
    output = tracking.directory / "human-review.json"
    output.write_text('{"stale":true}')
    if moved_head:
        gh.pr["headRefOid"] = "b" * 40
    tracking.passed(manifest(), None)
    assert any(call[:2] == ("pr", "create") for call in gh.calls)
    assert tracking.yt.calls == []
    persisted = json.loads(tracking.path.read_text())
    assert persisted["operations"][action] == {"status": status, "conflicting_write": True}
    assert any("YouTrack PR cross-link skipped" in w for w in persisted["warnings"])
    assert any("PR readiness unavailable" in w for w in persisted["warnings"]) == moved_head
    events = [
        json.loads(line)
        for line in (tracking.directory / "github-events.jsonl").read_text().splitlines()
    ]
    assert events[-1]["status"] == ("failed" if moved_head else "success")
    if moved_head:
        assert not output.exists()
        assert "READY FOR HUMAN REVIEW" not in gh.body
    else:
        readiness = json.loads(output.read_text())
        assert readiness["head_sha"] == SHA
        assert any("YouTrack PR cross-link skipped" in w for w in readiness["warnings"])
        assert f"READY FOR HUMAN REVIEW for reviewed SHA {SHA}" in gh.body
        tracking.passed(manifest(), None)
        assert sum(call[:2] == ("pr", "create") for call in gh.calls) == 1
        assert tracking.yt.calls == []


def test_uncertain_readiness_write_is_neutralized_without_handoff(tmp_path: Path) -> None:
    class LostResponse(FakeGitHub):
        def command(self, *args: str, input_text: str | None = None) -> Any:
            result = super().command(*args, input_text=input_text)
            if args[:2] == ("pr", "edit") and "READY FOR HUMAN REVIEW" in (input_text or ""):
                raise TrackingError("response lost after remote publication")
            return result

    gh = LostResponse(tmp_path, True)
    tracking = passed_tracking(tmp_path, gh)
    tracking.passed(manifest(), None)
    assert "READY FOR HUMAN REVIEW" not in gh.body and "PASS" not in gh.body
    assert not (tracking.directory / "human-review.json").exists()
    assert tracking.data["warnings"]
