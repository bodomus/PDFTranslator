"""Uncertain creation survives failed discovery until exact reconciliation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError

import pytest
from scripts.project_tracking import (
    IdentityError,
    ProjectTracking,
    TrackingError,
    UncertainTransport,
    YouTrack,
)

TICKET = "PDFTR-47"
SHA = "a" * 40
CREATE_KEY = hashlib.sha256(f"{TICKET}|harness|0|{SHA}|create".encode()).hexdigest()


def creation_scenario(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation_failure: int | type[Exception],
    reconciliation_failure: int | type[Exception],
) -> tuple[Callable[[], ProjectTracking], dict[str, Any]]:
    import scripts.project_tracking as module

    state: dict[str, Any] = {
        "mode": "failure",
        "posts": 0,
        "issue": {"id": "1-47", "idReadable": TICKET, "project": {"id": "p", "shortName": "PDFTR"}},
    }
    path = root / ".agent-cycle" / TICKET / "youtrack.json"

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def read(self) -> bytes:
            return json.dumps(state["issue"]).encode()

    def reject(request: Any, failure: int | type[Exception]) -> None:
        if isinstance(failure, int):
            raise HTTPError(request.full_url, failure, "fake-token private details", {}, None)
        raise failure("fake-token private details")

    def open_request(request: Any, *, timeout: int) -> Response:
        assert timeout == 5
        if request.get_method() == "POST":
            assert request.full_url.split("/api/", 1)[1].startswith("issues?")
            state["posts"] += 1
            state["pending"] = json.loads(path.read_text())["operations"][CREATE_KEY]
            assert state["pending"]["status"] == "pending"
            reject(request, mutation_failure)
        assert request.get_method() == "GET"
        if not state["posts"] or state["mode"] == "absent":
            reject(request, 404)
        if state["mode"] == "failure":
            reject(request, reconciliation_failure)
        return Response()

    monkeypatch.setattr(module, "build_opener", lambda *args: SimpleNamespace(open=open_request))
    yt = YouTrack("https://tracker.example", "fake-token")

    def tracking() -> ProjectTracking:
        tr = ProjectTracking(
            root,
            TICKET,
            "# PDFTR-47 — Reconciliation\n\nTask body.\n",
            config={"youtrack": {"enabled": True, "project": "PDFTR"}},
            youtrack=yt,
            warn=lambda _: None,
        )
        tr.project = {"id": "p", "shortName": "PDFTR"}
        tr.data.setdefault("bootstrap_sha", SHA)
        return tr

    return tracking, state


@pytest.mark.parametrize("mutation_failure", [504, 502, 503, TimeoutError, ConnectionResetError])
@pytest.mark.parametrize(
    "reconciliation_failure", [401, 403, 408, 502, 503, 504, TimeoutError, ConnectionResetError]
)
def test_uncertain_create_survives_failed_discovery_and_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation_failure: int | type[Exception],
    reconciliation_failure: int | type[Exception],
) -> None:
    tracking, state = creation_scenario(
        tmp_path, monkeypatch, mutation_failure, reconciliation_failure
    )
    tr = tracking()
    with pytest.raises(TrackingError):
        tr.ensure_youtrack_issue(allow_create=True)
    persisted = json.loads(tr.path.read_text())
    original = persisted["operations"][CREATE_KEY]
    assert original == {"status": "uncertain", "conflicting_write": False}
    assert tr.sync_failed
    journal = (tr.directory / "youtrack-events.jsonl").read_text()
    assert json.loads(journal)["error_class"] == "UncertainTransport"
    mutation_diagnostic = (
        f"YouTrack HTTP {mutation_failure}; remote outcome uncertain"
        if isinstance(mutation_failure, int)
        else "YouTrack transport/response failure; remote outcome uncertain"
    )
    assert any(mutation_diagnostic in warning for warning in persisted["warnings"])
    assert "fake-token" not in tr.path.read_text() + journal
    assert "private details" not in tr.path.read_text() + journal

    # A failing lookup and a healthy absent lookup must both preserve the first POST's evidence.
    resumed = tracking()
    with pytest.raises(TrackingError):
        resumed.ensure_youtrack_issue(allow_create=True)
    assert json.loads(tr.path.read_text())["operations"][CREATE_KEY] == original
    state["mode"] = "absent"
    with pytest.raises(TrackingError):
        resumed.ensure_youtrack_issue(allow_create=True)
    assert json.loads(tr.path.read_text())["operations"][CREATE_KEY] == original
    assert state["posts"] == 1

    # Only a later successful exact-key/project discovery can resolve the operation.
    unrelated_fence = {"status": "uncertain", "conflicting_write": True}
    resumed.data["operations"]["unrelated-field"] = unrelated_fence
    resumed.save()
    state["mode"] = "resolved"
    reconciled = tracking()
    assert reconciled.ensure_youtrack_issue(allow_create=True) == state["issue"]
    resolved = json.loads(tr.path.read_text())["operations"][CREATE_KEY]
    assert resolved["status"] == "success"
    assert resolved["result"] == state["issue"]
    assert reconciled.data["operations"]["unrelated-field"] == unrelated_fence
    with pytest.raises(TrackingError, match="operator reconciliation required"):
        reconciled.require_reconciled_writes()
    assert reconciled.data["issue_id"] == state["issue"]["id"]
    assert (tr.directory / "youtrack-events.jsonl").read_text().startswith(journal)
    assert tracking().ensure_youtrack_issue(allow_create=True) == state["issue"]
    assert state["posts"] == 1


@pytest.mark.parametrize("stage", ["immediate", "restart"])
@pytest.mark.parametrize("mismatch", ["key", "project", "unsafe_id"])
def test_uncertain_create_cannot_resolve_to_mismatched_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str, mismatch: str
) -> None:
    tracking, state = creation_scenario(tmp_path, monkeypatch, 504, 503)
    expected = deepcopy(state["issue"])
    if mismatch == "key":
        state["issue"]["idReadable"] = "PDFTR-48"
    elif mismatch == "project":
        state["issue"]["project"]["shortName"] = "OTHER"
    else:
        state["issue"]["id"] = "unsafe/issue"
    if stage == "immediate":
        state["mode"] = "resolved"
    tr = tracking()
    with pytest.raises(TrackingError):
        tr.ensure_youtrack_issue(allow_create=True)
    assert json.loads(tr.path.read_text())["operations"][CREATE_KEY]["status"] == "uncertain"
    assert tr.issue is None
    if stage == "immediate":
        assert json.loads(tr.path.read_text())["identity_unsafe"]
        # A later healthy read must not silently repair an identity-safety fence.
        state["issue"] = expected
        tracking().ensure_youtrack_issue(allow_create=True)
        assert json.loads(tr.path.read_text())["identity_unsafe"]
    else:
        state["mode"] = "resolved"
        with pytest.raises(IdentityError):
            tracking().ensure_youtrack_issue(allow_create=True)
    assert json.loads(tr.path.read_text())["operations"][CREATE_KEY]["status"] == "uncertain"
    assert state["posts"] == 1


def test_uncertain_create_resolves_on_successful_immediate_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracking, state = creation_scenario(tmp_path, monkeypatch, 504, 503)
    state["mode"] = "resolved"
    tr = tracking()
    assert tr.ensure_youtrack_issue(allow_create=True) == state["issue"]
    assert json.loads(tr.path.read_text())["operations"][CREATE_KEY]["status"] == "success"
    assert tracking().ensure_youtrack_issue(allow_create=True) == state["issue"]
    assert state["posts"] == 1


@pytest.mark.parametrize("sink_failure", [BrokenPipeError, OSError])
@pytest.mark.parametrize("persistent_sink_failure", [False, True])
def test_uncertain_create_survives_secondary_diagnostic_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sink_failure: type[Exception],
    persistent_sink_failure: bool,
) -> None:
    tracking, state = creation_scenario(tmp_path, monkeypatch, 504, 503)
    tr = tracking()
    mutation_errors: list[UncertainTransport] = []
    authoritative_errors: list[UncertainTransport] = []
    request = tr.yt.request
    diagnostic = tr.diagnostic

    def observed_request(method: str, *args: Any, **kwargs: Any) -> Any:
        try:
            return request(method, *args, **kwargs)
        except UncertainTransport as error:
            mutation_errors.append(error)
            raise

    def observed_diagnostic(error: Exception) -> str:
        if isinstance(error, UncertainTransport):
            authoritative_errors.append(error)
        return diagnostic(error)

    def broken_warning_sink(message: str) -> None:
        if "create reconciliation failed:" in message or persistent_sink_failure:
            raise sink_failure("diagnostic sink unavailable")

    monkeypatch.setattr(tr.yt, "request", observed_request)
    monkeypatch.setattr(tr, "diagnostic", observed_diagnostic)
    monkeypatch.setattr(tr, "warn", broken_warning_sink)
    expected_error = sink_failure if persistent_sink_failure else TrackingError
    with pytest.raises(expected_error):
        tr.ensure_youtrack_issue(allow_create=True)

    # The very same mutation exception must reach operation outcome classification.
    assert len(mutation_errors) == len(authoritative_errors) == 1
    assert authoritative_errors[0] is mutation_errors[0]
    persisted = json.loads(tr.path.read_text())
    original = persisted["operations"][CREATE_KEY]
    assert original == {"status": "uncertain", "conflicting_write": False}
    assert any("YouTrack HTTP 504; remote outcome uncertain" in w for w in persisted["warnings"])
    assert any(
        "create reconciliation failed: YouTrack HTTP 503" in w for w in persisted["warnings"]
    )
    journal = (tr.directory / "youtrack-events.jsonl").read_text()
    assert json.loads(journal)["error_class"] == "UncertainTransport"
    assert sink_failure.__name__ not in journal

    resumed = tracking()
    assert resumed.data["operations"][CREATE_KEY] == original
    with pytest.raises(TrackingError):
        resumed.ensure_youtrack_issue(allow_create=True)
    state["mode"] = "absent"
    with pytest.raises(TrackingError):
        resumed.ensure_youtrack_issue(allow_create=True)
    assert json.loads(tr.path.read_text())["operations"][CREATE_KEY] == original
    assert state["posts"] == 1

    state["mode"] = "resolved"
    assert tracking().ensure_youtrack_issue(allow_create=True) == state["issue"]
    resolved = json.loads(tr.path.read_text())["operations"][CREATE_KEY]
    assert resolved["status"] == "success"
    assert resolved["result"] == state["issue"]
    assert (tr.directory / "youtrack-events.jsonl").read_text().startswith(journal)
    assert tracking().ensure_youtrack_issue(allow_create=True) == state["issue"]
    assert state["posts"] == 1
