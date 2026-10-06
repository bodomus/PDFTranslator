"""Attempt-two regressions for durable uncertainty and invalid configured values."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest
from scripts.project_tracking import ProjectTracking, YouTrack, validate_live

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
