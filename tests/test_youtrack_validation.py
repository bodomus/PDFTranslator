"""PDFTR-47 deterministic validation: no live credentials or remote mutations."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from scripts.project_tracking import (
    APIError,
    IdentityError,
    ProjectTracking,
    TrackingError,
    YouTrack,
    validate_live,
)

from tests.test_project_tracking import (
    CONFIG,
    SHA,
    TEXT,
    TICKET,
    FakeYouTrack,
    manifest,
    mutations,
    tracker,
)


def configured(root: Path, yt: Any = None, **settings: Any) -> ProjectTracking:
    return ProjectTracking(
        root,
        TICKET,
        TEXT,
        config={"youtrack": {"enabled": True, "project": "PDFTR", **settings}},
        youtrack=yt,
        warn=lambda _: None,
    )


@pytest.mark.parametrize("enabled,status", [(False, "disabled"), (True, "credentials unavailable")])
def test_preflight_no_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, enabled: bool, status: str
) -> None:
    monkeypatch.delenv("YOUTRACK_TOKEN", raising=False)
    monkeypatch.delenv("YOUTRACK_URL", raising=False)
    tr = configured(tmp_path, enabled=enabled)
    tr.bootstrap()
    assert tr.data["preflight_status"] == status
    assert tr.issue is None


@pytest.mark.parametrize(
    "endpoint,code,status",
    [
        ("users/me", 401, "authentication failed"),
        ("users/me", 403, "authentication failed"),
        ("admin/projects?", 403, "project unavailable"),
        ("users/me", 500, "endpoint unavailable"),
    ],
)
def test_preflight_categories(tmp_path: Path, endpoint: str, code: int, status: str) -> None:
    class Rejected(FakeYouTrack):
        def request(self, method: str, path: str, body: Any = None) -> Any:
            if path.startswith(endpoint):
                raise APIError(code)
            return super().request(method, path, body)

    yt = Rejected()
    tr = configured(tmp_path, yt)
    tr.bootstrap()
    assert tr.data["preflight_status"] == status
    assert not mutations(yt)


def test_ready_and_project_unavailable(tmp_path: Path) -> None:
    tr = configured(tmp_path, FakeYouTrack())
    assert tr.preflight() == "ready"
    tr.yconfig["project"] = "OTHER"
    assert tr.preflight() == "project unavailable"


@pytest.mark.parametrize("failure", [TimeoutError("token-secret"), APIError(401), APIError(500)])
def test_ambiguous_lookup_never_creates(tmp_path: Path, failure: Exception) -> None:
    class FailedLookup(FakeYouTrack):
        def request(self, method: str, path: str, body: Any = None) -> Any:
            if method == "GET" and path.startswith("issues/"):
                raise failure
            return super().request(method, path, body)

    yt = FailedLookup(False)
    tr = tracker(tmp_path, yt)
    tr.bootstrap(allow_create=True)
    assert not mutations(yt)
    assert tr.issue is None
    assert "token-secret" not in tr.path.read_text()
    assert tr.data["last_sync_status"] == "failed"


def test_absent_requires_explicit_permission(tmp_path: Path) -> None:
    yt = FakeYouTrack(False)
    tr = configured(tmp_path, yt)
    tr.bootstrap()
    assert not mutations(yt)
    assert any("exact issue absent" in w for w in tr.data["warnings"])
    tr.bootstrap(allow_create=True)
    assert tr.issue and tr.data["issue_key"] == TICKET
    before = len(mutations(yt))
    tr.bootstrap(allow_create=True)
    assert len(mutations(yt)) == before
    creates = [(m, p) for m, p, _ in yt.calls if m == "POST" and p.startswith("issues?")]
    assert len(creates) == 1


def test_create_reread_mismatch_fails_closed(tmp_path: Path) -> None:
    class ChangedReadback(FakeYouTrack):
        def request(self, method: str, path: str, body: Any = None) -> Any:
            result = super().request(method, path, body)
            if method == "GET" and path.startswith("issues/1-") and result:
                return {**result, "idReadable": "PDFTR-99"}
            return result

    yt = ChangedReadback(False)
    tr = tracker(tmp_path, yt)
    tr.bootstrap(allow_create=True)
    assert tr.data["identity_unsafe"]
    assert len(mutations(yt)) == 1


def test_create_race_discovers_canonical_only(tmp_path: Path) -> None:
    class Conflict(FakeYouTrack):
        def request(self, method: str, path: str, body: Any = None) -> Any:
            result = super().request(method, path, body)
            if method == "POST" and path.startswith("issues?"):
                raise APIError(409)
            return result

    yt = Conflict(False)
    tr = tracker(tmp_path, yt)
    tr.bootstrap(allow_create=True)
    assert tr.issue and tr.issue["idReadable"] == TICKET
    tr.bootstrap(allow_create=True)
    assert len([p for m, p, _ in yt.calls if m == "POST" and p.startswith("issues?")]) == 1


def test_concurrent_validation_is_nonwaiting_and_cannot_create(tmp_path: Path) -> None:
    yt = FakeYouTrack(False)
    first, second = tracker(tmp_path, yt), tracker(tmp_path, yt)
    with first.synchronization():
        second.bootstrap(allow_create=True)
        assert not mutations(yt)
    first.bootstrap(allow_create=True)
    second.bootstrap(allow_create=True)
    assert len([p for m, p, _ in yt.calls if m == "POST" and p.startswith("issues?")]) == 1


@pytest.mark.parametrize("missing", ["Assignee", "Estimation", "Due Date", "State"])
def test_missing_fields_reported_nonblocking(tmp_path: Path, missing: str) -> None:
    yt = FakeYouTrack()
    yt.fields = [f for f in yt.fields if f["field"]["name"] != missing]
    tr = tracker(tmp_path, yt)
    assert validate_live(tr) == 0
    assert "field unavailable: " + missing in tr.data["warnings"]
    assert not mutations(yt)


def test_user_login_not_display_name_or_bundle_guess(tmp_path: Path) -> None:
    class Unresolved(FakeYouTrack):
        def request(self, method: str, path: str, body: Any = None) -> Any:
            if path.startswith("users?"):
                return [{"id": "other", "login": "someone", "name": "bodomus"}]
            return super().request(method, path, body)

    yt = Unresolved()
    tr = tracker(tmp_path, yt)
    tr.bootstrap()
    assert "Assignee" not in yt.values
    assert any("login unresolved" in w for w in tr.data["warnings"])
    assert tr.issue


@pytest.mark.parametrize(
    "action,state",
    [
        ("NEW", "4"),
        ("IMPLEMENTING", "0"),
        ("READY_FOR_REVIEW", "1"),
        ("READY_FOR_REVIEW_2", "1"),
        ("PASSED", "2"),
        ("merged", "3"),
    ],
)
def test_semantic_lifecycle(tmp_path: Path, action: str, state: str) -> None:
    yt = FakeYouTrack()
    tr = tracker(tmp_path, yt)
    tr.bootstrap()
    tr.lifecycle(action, manifest())
    assert yt.values["State"] == {"id": state}
    assert any(m == "GET" and "customFields(name,value" in p for m, p, _ in yt.calls)


def test_no_guessed_state_and_no_done_on_pass(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    tr = tracker(tmp_path, yt)
    tr.bootstrap()
    tr.yconfig = {**tr.yconfig, "states": {"PASS": "Done"}}
    tr.lifecycle("PASS", manifest())
    assert "State" not in yt.values
    tr.yconfig["states"]["PASS"] = "Unknown"
    tr.lifecycle("PASS", {**manifest(), "current_head_sha": "b" * 40})
    assert "State" not in yt.values


@pytest.mark.parametrize(
    "semantic,value",
    [
        ("state", "In Progress"),
        ("assignee", "bodomus"),
        ("estimation", "4h"),
        ("due_date", "2099-01-01"),
    ],
)
def test_read_after_write_not_http_success(tmp_path: Path, semantic: str, value: str) -> None:
    class IgnoredWrite(FakeYouTrack):
        def request(self, method: str, path: str, body: Any = None) -> Any:
            result = super().request(method, path, body)
            if method == "POST" and isinstance(body, dict) and "customFields" in body:
                self.values.clear()
            return result

    yt = IgnoredWrite()
    tr = tracker(tmp_path, yt)
    tr.bootstrap(mutate=False)
    tr.apply_fields({semantic: value}, "operator", SHA, 0)
    assert tr.sync_failed
    assert any("read-after-write mismatch" in w for w in tr.data["warnings"])


def test_only_explicit_period_and_utc_date(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    tr = configured(tmp_path, yt, defaults={"estimation": "4h", "due_date": "2099-01-01"})
    tr.bootstrap()
    assert yt.values["Estimation"] == {"presentation": "4h"}
    from datetime import UTC, datetime

    assert (
        datetime.fromtimestamp(yt.values["Due Date"] / 1000, UTC).isoformat()
        == "2099-01-01T00:00:00+00:00"
    )
    before = len(mutations(yt))
    tr.apply_fields(
        {"estimation": "4h", "due_date": "2099-01-01"}, "other-role", "different-sha", 2
    )
    assert len(mutations(yt)) == before


@pytest.mark.parametrize("dry_run,allow_create", [(True, True), (False, False)])
def test_validation_no_mutation_by_default(
    tmp_path: Path, dry_run: bool, allow_create: bool
) -> None:
    yt = FakeYouTrack(False)
    messages: list[str] = []
    tr = configured(tmp_path, yt)
    tr.warn = messages.append
    validate_live(tr, dry_run=dry_run, allow_create=allow_create)
    assert not mutations(yt)
    assert (
        any("Would create" in m for m in messages)
        if dry_run
        else any("exact issue absent" in m for m in messages)
    )


def test_successful_operator_validation_second_run_idempotent(tmp_path: Path) -> None:
    yt = FakeYouTrack(False)
    tr = configured(tmp_path, yt)
    assert validate_live(tr, allow_create=True, state="start") == 0
    before = len(mutations(yt))
    assert validate_live(tr, allow_create=True, state="start") == 0
    assert len(mutations(yt)) == before
    assert yt.values["State"] == {"id": "0"}
    assert not yt.comments  # No fabricated review, SHA or CI from validator.
    with pytest.raises(TrackingError, match="finalize"):
        validate_live(tr, state="merged")
    assert validate_live(tr, state="merged", finalize=True) == 0
    assert yt.values["State"] == {"id": "3"}


def test_config_host_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YOUTRACK_TOKEN", "token-secret")
    monkeypatch.setenv("YOUTRACK_URL", "https://other.example")
    with pytest.raises(IdentityError, match="host mismatch"):
        configured(tmp_path, base_url="https://tracker.example")


@pytest.mark.parametrize(
    "path", ["https://other.example/api/issues", "//other.example", "../issues"]
)
def test_transport_refuses_agent_url(path: str) -> None:
    with pytest.raises(IdentityError):
        YouTrack("https://tracker.example", "secret").request("POST", path, {})


def test_hung_transport_overall_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.project_tracking as module

    release = threading.Event()

    class Hung:
        def open(self, *args: Any, **kwargs: Any) -> Any:
            assert kwargs["timeout"] == 5
            release.wait(2)
            raise OSError("secret")

    monkeypatch.setattr(module, "build_opener", lambda *args: Hung())
    yt = YouTrack("https://tracker.example", "secret")
    yt.overall_timeout = 0.03
    started = time.monotonic()
    try:
        with pytest.raises(TrackingError, match="overall timeout"):
            yt.request("GET", "users/me")
        assert time.monotonic() - started < 0.5
    finally:
        release.set()


def test_secret_never_persisted_from_identity_exception(tmp_path: Path) -> None:
    class Malicious(FakeYouTrack):
        def request(self, method: str, path: str, body: Any = None) -> Any:
            if path.startswith("issues/"):
                raise IdentityError("token-secret")
            return super().request(method, path, body)

    tr = tracker(tmp_path, Malicious())
    tr.bootstrap()
    for path in tr.directory.glob("*.json*"):
        assert "token-secret" not in path.read_text()
    assert tr.data["identity_unsafe"]


def test_event_journal_append_only(tmp_path: Path) -> None:
    tr = tracker(tmp_path, FakeYouTrack())
    tr.bootstrap()
    path = tr.directory / "youtrack-events.jsonl"
    first = path.read_bytes()
    tr.lifecycle("PASS", manifest())
    assert path.read_bytes().startswith(first)
    assert all(json.loads(line)["ticket"] == TICKET for line in path.read_text().splitlines())


@pytest.mark.parametrize("exists", [True, False])
def test_pdftr47_exact_identity(tmp_path: Path, exists: bool) -> None:
    class Ticket47(FakeYouTrack):
        def request(self, method: str, path: str, body: Any = None) -> Any:
            result = super().request(method, path, body)
            if method == "POST" and path.startswith("issues?"):
                self.issue["idReadable"] = "PDFTR-47"
            return result

    yt = Ticket47(exists)
    if yt.issue:
        yt.issue["idReadable"] = "PDFTR-47"
    tr = ProjectTracking(
        tmp_path,
        "PDFTR-47",
        "# PDFTR-47 — Sync\n\nBody",
        config=CONFIG,
        youtrack=yt,
        warn=lambda _: None,
    )
    assert validate_live(tr, allow_create=True, state="start") == 0
    assert tr.data["issue_key"] == "PDFTR-47"
    assert tr.issue["project"]["shortName"] == "PDFTR"


def test_operator_cli_dry_run_uses_local_ticket_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.project_tracking as module

    tickets = tmp_path / "Tickets"
    tickets.mkdir()
    (tickets / "PDFTR-47-sync.md").write_text("# PDFTR-47 — Sync\n", "utf-8")
    yt = FakeYouTrack(False)
    tr = configured(tmp_path, yt)
    monkeypatch.setattr(module, "__file__", str(tmp_path / "scripts" / "project_tracking.py"))
    monkeypatch.setattr(module, "ProjectTracking", lambda *args, **kwargs: tr)
    assert module.main(["validate-live", "PDFTR-47", "--dry-run", "--allow-create"]) == 1
    assert not mutations(yt)
    with pytest.raises(SystemExit):
        module.main(["validate-live", "OTHER-47"])


def test_field_action_and_event_redact_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YOUTRACK_TOKEN", "token-secret")
    tr = tracker(tmp_path, FakeYouTrack())
    tr.bootstrap()
    tr.apply_fields({"priority": "token-secret"}, "operator", SHA, 0)
    for path in tr.directory.glob("*.json*"):
        assert "token-secret" not in path.read_text()


def test_uncertain_prior_comment_is_visible(tmp_path: Path) -> None:
    tr = tracker(tmp_path, FakeYouTrack())
    tr.bootstrap()
    tr.operation("harness", "comment:test", SHA, 0, lambda: (_ for _ in ()).throw(TimeoutError()))
    tr.operation("harness", "comment:test", SHA, 0, lambda: pytest.fail("must not duplicate"))
    assert any("discovery/reconciliation required" in w for w in tr.data["warnings"])


def test_definition_divergence_is_detected_and_repaired(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    tr = tracker(tmp_path, yt)
    tr.bootstrap()
    yt.issue["summary"] = "Changed remotely"
    tr.bootstrap()
    assert yt.issue["summary"] == TEXT.splitlines()[0].lstrip("# ")
    assert tr.data["last_sync_status"] == "success"


def test_lifecycle_comment_success_does_not_hide_field_failure(tmp_path: Path) -> None:
    yt = FakeYouTrack()
    yt.fields = [f for f in yt.fields if f["field"]["name"] != "State"]
    tr = tracker(tmp_path, yt)
    tr.bootstrap()
    tr.lifecycle("PASS", manifest())
    assert yt.comments
    assert tr.data["last_sync_status"] == "partial"
    assert tr.data["last_sync_action"] == "PASS"
