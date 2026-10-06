"""Regressions for durable transport uncertainty and invalid configured values."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError, URLError

import pytest
from scripts.project_tracking import (
    APIError,
    IdentityError,
    ProjectTracking,
    TrackingError,
    UncertainTransport,
    YouTrack,
    validate_live,
)

from tests.test_project_tracking import CONFIG, TEXT, TICKET, FakeYouTrack, manifest, mutations


@pytest.mark.parametrize("kind", ["state", "definition"])
def test_timed_out_write_fences_later_sync_and_restart(tmp_path: Path, kind: str) -> None:
    fake = FakeYouTrack()
    entered, release, terminated = threading.Event(), threading.Event(), threading.Event()

    class Delayed(YouTrack):
        overall_timeout = 0.03
        delayed = False

        def _request(self, method: str, path: str, body: Any = None) -> Any:
            should_delay = (
                method == "POST"
                and isinstance(body, dict)
                and (
                    ("customFields" in body and body["customFields"][0]["name"] == "State")
                    if kind == "state"
                    else "summary" in body
                )
            )
            if self.delayed and should_delay:
                entered.set()
                assert release.wait(5)
                try:
                    return fake.request(method, path, body)
                finally:
                    terminated.set()
            return fake.request(method, path, body)

    yt = Delayed("https://tracker.example", "fake-token")
    messages: list[str] = []

    def tracking() -> ProjectTracking:
        return ProjectTracking(
            tmp_path, TICKET, TEXT, config=CONFIG, youtrack=yt, warn=messages.append
        )

    tr = tracking()
    tr.bootstrap()
    yt.delayed = True
    try:
        if kind == "state":
            tr.lifecycle("start", manifest())
        else:
            fake.issue["summary"] = "Remote divergence"
            tr.bootstrap()
        assert entered.is_set()
        assert tr.sync_failed
        persisted = json.loads(tr.path.read_text())
        assert any(op["status"] == "uncertain" for op in persisted["operations"].values())
        before = len(mutations(fake))
        tr.lifecycle("handoff", manifest())
        resumed = tracking()
        assert validate_live(resumed, state="handoff") == 1
        assert len(mutations(fake)) == before
        assert not any("Idempotent second" in message for message in messages)
    finally:
        release.set()
        assert terminated.wait(5)
    # Even after completion, a read alone is not authorization to remove the durable fence.
    resumed = tracking()
    resumed.bootstrap()
    resumed.lifecycle("handoff", manifest())
    assert resumed.sync_failed
    assert resumed.data["last_sync_status"] == "failed"
    assert any("operator reconciliation required" in w for w in resumed.data["warnings"])
    if kind == "state":
        assert fake.values["State"] == {"id": "0"}  # No newer write was falsely verified.


@pytest.mark.parametrize(
    "failure", [TimeoutError, ConnectionResetError, URLError, 408, 500, 502, 503, 504]
)
def test_transport_failure_fences_dispatched_state_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: type[Exception] | int
) -> None:
    import scripts.project_tracking as module

    fake = FakeYouTrack()
    fake.values["State"] = {"id": "4"}  # Existing Open state.
    release, terminated = threading.Event(), threading.Event()
    dispatched = False
    messages: list[str] = []

    class Response:
        def __init__(self, result: Any) -> None:
            self.payload = json.dumps(result).encode()

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def read(self) -> bytes:
            return self.payload

    def open_request(request: Any, *, timeout: int) -> Response:
        nonlocal dispatched
        assert timeout == 5
        method = request.get_method()
        path = request.full_url.split("/api/", 1)[1]
        body: Any = None
        if request.data:
            content_type = request.get_header("Content-type")
            body = (
                json.loads(request.data)
                if content_type == "application/json"
                else (request.data, content_type)
            )
        if (
            method == "POST"
            and isinstance(body, dict)
            and body.get("customFields", [{}])[0].get("value") == {"id": "0"}
        ):
            dispatched = True

            def remote_completion() -> None:
                try:
                    assert release.wait(5)
                    fake.request(method, path, body)
                finally:
                    terminated.set()

            threading.Thread(target=remote_completion, daemon=True).start()
            # Real request/_request path: the client sees a socket failure or gateway
            # error while the upstream server continues processing the dispatched POST.
            if isinstance(failure, int):
                raise HTTPError(request.full_url, failure, "fake-token private details", {}, None)
            raise failure("fake-token private transport details")
        return Response(fake.request(method, path, body))

    monkeypatch.setattr(module, "build_opener", lambda *args: SimpleNamespace(open=open_request))
    yt = YouTrack("https://tracker.example", "fake-token")

    def tracking() -> ProjectTracking:
        return ProjectTracking(
            tmp_path, TICKET, TEXT, config=CONFIG, youtrack=yt, warn=messages.append
        )

    tr = tracking()
    tr.bootstrap()
    assert not tr.sync_failed
    try:
        tr.lifecycle("start", manifest())
        assert dispatched
        assert tr.sync_failed
        persisted = json.loads(tr.path.read_text())
        assert any(
            op["status"] == "uncertain" and op.get("conflicting_write")
            for op in persisted["operations"].values()
        )
        before = len(mutations(fake))
        tr.lifecycle("handoff", manifest())
        resumed = tracking()
        assert validate_live(resumed, state="handoff") == 1
        assert resumed.data["last_sync_status"] == "failed"
        assert len(mutations(fake)) == before
        assert fake.values["State"] == {"id": "4"}  # Still Open, no newer write.
        assert not any("Idempotent second" in message for message in messages)
    finally:
        release.set()
        assert terminated.wait(5)
    assert fake.values["State"] == {"id": "0"}  # Delayed In Progress completed.
    resumed = tracking()
    resumed.lifecycle("handoff", manifest())
    assert validate_live(tracking(), state="handoff") == 1
    assert resumed.sync_failed
    assert resumed.data["last_sync_status"] == "failed"
    assert len(mutations(fake)) == before + 1  # Only the original dispatched POST.
    evidence = tr.path.read_text() + (tr.directory / "youtrack-events.jsonl").read_text()
    assert "fake-token" not in evidence + "".join(messages)
    assert "private transport details" not in evidence + "".join(messages)


@pytest.mark.parametrize("payload", [b"not json", b"{"])
def test_lost_mutation_response_is_uncertain(
    monkeypatch: pytest.MonkeyPatch, payload: bytes
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
    yt = YouTrack("https://tracker.example", "fake-token")
    with pytest.raises(UncertainTransport):
        yt.request("POST", "issues/1-43", {})
    with pytest.raises(TrackingError) as error:
        yt.request("GET", "issues/1-43")
    assert not isinstance(error.value, UncertainTransport)


@pytest.mark.parametrize("status", [401, 403, 400, 404, 409, 422, 429])
def test_definite_http_rejection_and_pre_dispatch_validation_are_not_uncertain(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    import scripts.project_tracking as module

    def rejected(*args: Any, **kwargs: Any) -> Any:
        raise HTTPError("https://tracker.example", status, "private", {}, None)

    monkeypatch.setattr(module, "build_opener", lambda *args: SimpleNamespace(open=rejected))
    yt = YouTrack("https://tracker.example", "fake-token")
    with pytest.raises(APIError) as error:
        yt.request("POST", "issues/1-43", {})
    assert error.value.status == status
    with pytest.raises(IdentityError):
        yt.request("POST", "https://other.example/api/issues/1-43", {})


@pytest.mark.parametrize("status", [408, 500, 502, 503, 504, 599])
def test_ambiguous_http_read_failure_is_not_absence_or_write_uncertainty(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    import scripts.project_tracking as module

    def rejected(*args: Any, **kwargs: Any) -> Any:
        raise HTTPError("https://tracker.example", status, "fake-token private details", {}, None)

    monkeypatch.setattr(module, "build_opener", lambda *args: SimpleNamespace(open=rejected))
    yt = YouTrack("https://tracker.example", "fake-token")
    with pytest.raises(APIError) as error:
        yt.request("GET", "issues/1-43")
    assert error.value.status == status
    assert "fake-token" not in str(error.value)
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    "key,value,diagnostic",
    [
        ("estimation", 4, "unsupported estimation; expected string"),
        ("estimation", "4", "unsupported estimation; expected unit-bearing period string"),
        ("due_date", 20270101, "unsupported due_date; expected string"),
        ("due_date", "2027-02-30", "unsupported due date; expected ISO YYYY-MM-DD"),
        ("assignee", 42, "unsupported assignee; expected string"),
        ("priority", False, "unsupported priority; expected string"),
    ],
)
def test_malformed_defaults_fail_before_mutation(
    tmp_path: Path, key: str, value: Any, diagnostic: str
) -> None:
    fake = FakeYouTrack()
    messages: list[str] = []
    tr = ProjectTracking(
        tmp_path,
        TICKET,
        TEXT,
        config={"youtrack": {**CONFIG["youtrack"], "defaults": {key: value}}},
        youtrack=fake,
        warn=messages.append,
    )
    assert validate_live(tr, apply_fields=True) == 1
    assert tr.sync_failed
    assert tr.data["last_sync_status"] == "failed"
    assert not mutations(fake)
    assert any(diagnostic in message for message in messages)
    assert not any("Idempotent second" in message for message in messages)


def test_second_state_validation_failure_omits_completion_claim(tmp_path: Path) -> None:
    messages: list[str] = []

    class FailedSecondState(ProjectTracking):
        state_calls = 0

        def apply_fields(self, *args: Any, **kwargs: Any) -> None:
            super().apply_fields(*args, **kwargs)
            self.state_calls += 1
            if self.state_calls == 2:
                self.sync_failed = True

    tr = FailedSecondState(
        tmp_path, TICKET, TEXT, config=CONFIG, youtrack=FakeYouTrack(), warn=messages.append
    )
    assert validate_live(tr, state="handoff") == 1
    assert tr.state_calls == 2
    assert not any("Idempotent second" in message for message in messages)


def test_bootstrap_exception_after_issue_resolution_is_aggregate_failure(tmp_path: Path) -> None:
    messages: list[str] = []

    class FailedBootstrap(ProjectTracking):
        def _apply_fields(self, *args: Any, **kwargs: Any) -> None:
            raise TypeError("unexpected local failure")

    tr = FailedBootstrap(
        tmp_path, TICKET, TEXT, config=CONFIG, youtrack=FakeYouTrack(), warn=messages.append
    )
    assert validate_live(tr, apply_fields=True) == 1
    assert tr.issue is not None
    assert tr.sync_failed
    assert tr.data["last_sync_status"] == "failed"
    assert not any("Idempotent second" in message for message in messages)


def test_pending_repeatable_write_survives_restart(tmp_path: Path) -> None:
    fake = FakeYouTrack()
    tr = ProjectTracking(tmp_path, TICKET, TEXT, config=CONFIG, youtrack=fake)
    tr.data["operations"]["interrupted"] = {"status": "pending", "conflicting_write": True}
    tr.save()
    resumed = ProjectTracking(tmp_path, TICKET, TEXT, config=CONFIG, youtrack=fake)
    assert validate_live(resumed, apply_fields=True) == 1
    assert not mutations(fake)
    assert resumed.data["operations"]["interrupted"]["status"] == "pending"
