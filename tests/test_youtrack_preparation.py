"""Preparation reads never reserve an at-most-once mutation action."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError

import pytest
from scripts.project_tracking import ProjectTracking, YouTrack

from tests.test_project_tracking import CONFIG, TEXT, TICKET, FakeGitHub, FakeYouTrack, manifest


def preparation_scenario(
    root: Path, path: str, yt: YouTrack
) -> tuple[Callable[[], ProjectTracking], Callable[[ProjectTracking], None]]:
    gh = FakeGitHub(root) if path == "pr-link" else None

    def tracking() -> ProjectTracking:
        return ProjectTracking(
            root, TICKET, TEXT, config=CONFIG, youtrack=yt, github=gh, warn=lambda _: None
        )

    def invoke(tr: ProjectTracking) -> None:
        if path == "create":
            tr.bootstrap()
        elif path == "comment":
            tr.lifecycle("start", manifest())
        elif path == "attachment":
            tr.attach("preparation.md", "Preparation regression", "harness", "a" * 40, 1)
        else:
            tr.passed(manifest(), None)

    return tracking, invoke


def initialize_scenario(tr: ProjectTracking, path: str) -> None:
    tr.save()
    if path != "create":
        tr.bootstrap()
        assert not tr.sync_failed
    if path == "pr-link":
        (tr.directory / "handoff.json").write_text(
            json.dumps({"implementer": {"focused_tests": "PASS", "full_tests": "PASS"}})
        )


def action_writes(fake: FakeYouTrack, path: str) -> list[Any]:
    return [
        body
        for method, target, body in fake.calls
        if method == "POST"
        and (
            target.startswith("issues?")
            if path == "create"
            else target.endswith("/attachments")
            if path == "attachment"
            else target.endswith("/comments")
        )
    ]


@pytest.mark.parametrize(
    "path,stage",
    [
        ("create", "identity"),
        ("comment", "identity"),
        ("comment", "duplicates"),
        ("attachment", "identity"),
        ("pr-link", "identity"),
        ("pr-link", "duplicates"),
    ],
)
def test_preparation_get_timeout_remains_retryable_after_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str, stage: str
) -> None:
    import scripts.project_tracking as module

    fake = FakeYouTrack(exists=path != "create")
    fake.values["State"] = {"id": "0"}
    entered, release, terminated = threading.Event(), threading.Event(), threading.Event()
    active = False
    identity_reads = 0
    dispatched: list[str] = []
    snapshots: list[dict[str, Any]] = []

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
        nonlocal identity_reads
        assert timeout == 5
        method = request.get_method()
        target = request.full_url.split("/api/", 1)[1]
        dispatched.append(method)
        identity = target == "issues/" + TICKET + "?fields=id,idReadable,project(id,shortName)"
        if active and method == "GET" and identity:
            identity_reads += 1
        delayed = (
            active
            and method == "GET"
            and (
                "/comments?" in target
                if stage == "duplicates"
                else identity and identity_reads == (2 if path in {"create", "comment"} else 1)
            )
        )
        if delayed:
            snapshots.append(json.loads(tr.path.read_text()))
            entered.set()
            try:
                assert release.wait(5)
            finally:
                terminated.set()
        content_type = request.get_header("Content-type")
        body = (
            json.loads(request.data)
            if request.data and content_type == "application/json"
            else (request.data, content_type)
            if request.data
            else None
        )
        result = fake.request(method, target, body)
        if method == "GET" and result is None:
            raise HTTPError(request.full_url, 404, "Absent", {}, None)
        return Response(result)

    monkeypatch.setattr(module, "build_opener", lambda *args: SimpleNamespace(open=open_request))
    yt = YouTrack("https://tracker.example", "fake-token")
    yt.overall_timeout = 0.1
    tracking, invoke = preparation_scenario(tmp_path, path, yt)
    tr = tracking()
    initialize_scenario(tr, path)
    fake.calls.clear()
    dispatched.clear()
    before = json.loads(tr.path.read_text())["operations"]
    active = True
    try:
        invoke(tr)
        assert entered.is_set()
        assert tr.sync_failed
        assert not set(dispatched) & {"POST", "PATCH", "PUT", "DELETE"}
        persisted = json.loads(tr.path.read_text())
        for snapshot in [*snapshots, persisted]:
            assert all(snapshot["operations"].get(key) == op for key, op in before.items())
            assert all(
                op["status"] not in {"pending", "uncertain"} and not op.get("conflicting_write")
                for op in snapshot["operations"].values()
            )
        events = [
            json.loads(line)
            for line in (tr.directory / "youtrack-events.jsonl").read_text().splitlines()
        ]
        failed = [event for event in events if event.get("error_class") == "ReadTimeout"]
        assert len(failed) == 1
        assert all(
            failed[0]["idempotency_key"] not in snapshot["operations"]
            for snapshot in [*snapshots, persisted]
        )
    finally:
        active = False
        release.set()
        assert terminated.wait(5)

    resumed = tracking()
    if path != "create":
        resumed.bootstrap()
        assert not resumed.sync_failed
    invoke(resumed)
    assert not resumed.sync_failed
    assert len(action_writes(fake, path)) == 1
    invoke(resumed)
    again = tracking()
    again.bootstrap()
    invoke(again)
    assert not again.sync_failed
    assert len(action_writes(fake, path)) == 1


@pytest.mark.parametrize("path", ["create", "comment", "attachment", "pr-link"])
def test_post_dispatch_timeout_preserves_nonrepeatable_guard(tmp_path: Path, path: str) -> None:
    fake = FakeYouTrack(exists=path != "create")
    fake.values["State"] = {"id": "0"}
    entered, release, terminated = threading.Event(), threading.Event(), threading.Event()

    class DelayedWrite(YouTrack):
        overall_timeout = 0.1
        active = False
        dispatches = 0

        def _request(self, method: str, target: str, body: Any = None) -> Any:
            if self.active and method == "POST":
                self.dispatches += 1
                pending = json.loads(tr.path.read_text())["operations"]
                assert any(op["status"] == "pending" for op in pending.values())
                entered.set()
                try:
                    assert release.wait(5)
                    return fake.request(method, target, body)
                finally:
                    terminated.set()
            return fake.request(method, target, body)

    yt = DelayedWrite("https://tracker.example", "fake-token")
    tracking, invoke = preparation_scenario(tmp_path, path, yt)
    tr = tracking()
    initialize_scenario(tr, path)
    fake.calls.clear()
    yt.active = True
    try:
        invoke(tr)
        assert entered.is_set()
        persisted = json.loads(tr.path.read_text())
        uncertain = {
            key: op for key, op in persisted["operations"].items() if op["status"] == "uncertain"
        }
        assert len(uncertain) == 1
        resumed = tracking()
        if path != "create":
            # These fixtures already have exact issue identity; avoid unrelated bootstrap writes.
            resumed.issue = resumed.verify(fake.issue)
            resumed.fields = fake.fields
        invoke(resumed)
        assert yt.dispatches == 1
        assert all(resumed.data["operations"][key] == op for key, op in uncertain.items())
    finally:
        yt.active = False
        release.set()
        assert terminated.wait(5)
    assert len(action_writes(fake, path)) == 1
    resumed = tracking()
    resumed.bootstrap()
    invoke(resumed)
    assert len(action_writes(fake, path)) == 1
