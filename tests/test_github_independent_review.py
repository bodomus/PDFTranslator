"""Deterministic GitHub/connector integration; no live credentials or mutations."""

from __future__ import annotations

import copy
import json
import threading
from dataclasses import asdict

import pytest
from scripts.cycle_ownership import CycleOwnershipError
from scripts.github_independent_review import (
    SUPPORTED_EVENTS,
    github_event_signal,
    handle_signal,
    load_cycle,
    main,
)
from scripts.github_review_facts import GitHubFactsProvider, GitHubReader, normalize_checks
from scripts.independent_review import IndependentReviewStore
from scripts.independent_review_dispatch import (
    DispatchReceipt,
    DispatchRequest,
    HTTPSReviewDispatcher,
)
from scripts.independent_review_policy import IndependentReviewError

H, B, OLD = "a" * 40, "b" * 40, "c" * 40


@pytest.fixture
def setup(tmp_path):
    config = {
        "schema_version": "1.0",
        "repository": "owner/repo",
        "ticket": "PDFTR-50",
        "pull_request": 123,
        "required_checks": ["windows", "ubuntu"],
    }
    cycle = {"ticket": "PDFTR-50", "branch": "task", "state": "PASSED", "current_head_sha": H}
    pr = {
        "number": 123,
        "draft": False,
        "merged": False,
        "state": "open",
        "head": {"sha": H, "ref": "task", "repo": {"full_name": "owner/repo"}},
        "base": {"sha": B, "repo": {"full_name": "owner/repo"}},
    }
    checks = {
        "total_count": 2,
        "check_runs": [
            {"name": name, "head_sha": H, "status": "completed", "conclusion": "success"}
            for name in config["required_checks"]
        ],
    }
    observations = []

    def read(path):
        observations.append(path)
        if "/pulls/" in path:
            return copy.deepcopy(pr)
        if "/check-runs" in path:
            return copy.deepcopy(checks)
        return {"full_name": "owner/repo"}

    store = IndependentReviewStore(tmp_path, tmp_path / "cycle", config)
    store.initialize()
    provider = GitHubFactsProvider(config, read)

    class Dispatcher:
        calls = []
        receipt = DispatchReceipt("DISPATCHED", "opaque-123")
        error = None

        def dispatch(self, request):
            # State must already be durable before any transport invocation.
            state = store.load()
            assert state["reviews"][request.generation - 1]["status"] == "REQUESTED"
            self.calls.append(request)
            if self.error:
                raise self.error
            return self.receipt

    dispatcher = Dispatcher()

    def signal(event="manual", payload=None):
        return handle_signal(event, payload or {}, store, provider, dispatcher, lambda *_: cycle)

    return store, provider, dispatcher, cycle, pr, checks, observations, signal


@pytest.mark.parametrize("event", sorted(SUPPORTED_EVENTS))
def test_event_claims_never_authorize(setup, event):
    store, provider, dispatch, cycle, pr, checks, reads, signal = setup
    checks["check_runs"][0]["status"] = "in_progress"
    decision = signal(event, {"head_sha": OLD, "ci": "success", "draft": False})
    assert decision["decision"] == "NOT_ELIGIBLE"
    assert decision["reason"] == "ci_pending"
    assert not dispatch.calls
    assert provider.fetch(cycle)["head_sha"] == H
    assert len(reads) >= 4


@pytest.mark.parametrize(
    "change,reason",
    [
        ("old_ci", "ci_unknown"),
        ("missing", "ci_unknown"),
        ("failed", "ci_failed"),
        ("draft", "pr_draft"),
        ("closed", "pr_closed"),
        ("cycle", "cycle_not_passed"),
        ("sha", "sha_mismatch"),
        ("duplicate", "ci_unknown"),
    ],
)
def test_not_eligible(setup, change, reason):
    store, _, dispatch, cycle, pr, checks, _, signal = setup
    if change == "old_ci":
        checks["check_runs"][0]["head_sha"] = OLD
    elif change == "missing":
        checks["check_runs"].pop()
        checks["total_count"] = 1
    elif change == "failed":
        checks["check_runs"][0]["conclusion"] = "failure"
    elif change == "draft":
        pr["draft"] = True
    elif change == "closed":
        pr["state"] = "closed"
    elif change == "cycle":
        cycle["state"] = "REVIEWING"
    elif change == "sha":
        cycle["current_head_sha"] = OLD
    elif change == "duplicate":
        checks["check_runs"].append(copy.deepcopy(checks["check_runs"][0]))
        checks["total_count"] = 3
    assert signal()["reason"] == reason
    assert store.load()["current_generation"] == 0
    assert not dispatch.calls


def test_duplicate_restart_and_pinned_receipt(setup):
    store, provider, dispatch, cycle, _, _, _, signal = setup
    assert signal("opened")["dispatch_state"] == "RUNNING"
    for event in SUPPORTED_EVENTS:
        assert signal(event)["decision"] == "ALREADY_REQUESTED"
    restarted = IndependentReviewStore(store.root, store.directory, store.config)
    assert (
        handle_signal("manual", {}, restarted, provider, dispatch, lambda *_: cycle)["decision"]
        == "ALREADY_REQUESTED"
    )
    assert len(dispatch.calls) == 1
    request = dispatch.calls[0]
    assert (request.head_sha, request.base_sha, request.generation) == (H, B, 1)
    assert "Do not mutate" in request.instructions()
    assert "Do not merge" in request.instructions()
    assert H in request.instructions() and B in request.instructions()
    receipt = json.loads((store.directory / "independent-dispatch-1.json").read_text())
    assert receipt["external_request_id"] == "opaque-123"
    assert store.load()["reviews"][0]["status"] == "RUNNING"


def test_base_only_movement(setup):
    store, _, dispatch, _, pr, _, _, signal = setup
    signal()
    pr["base"]["sha"] = OLD
    assert signal()["generation"] == 2
    assert store.load()["reviews"][0]["status"] == "STALE"
    assert dispatch.calls[-1].base_sha == OLD
    signal()
    assert len(dispatch.calls) == 2


def test_race_rejects_mixed_snapshot(setup):
    store, provider, dispatch, _, pr, _, _, signal = setup
    read = provider.read

    def raced(path):
        result = read(path)
        if "/check-runs" in path:
            pr["head"]["sha"] = OLD
        return result

    provider.read = raced
    with pytest.raises(IndependentReviewError, match="snapshot_changed"):
        signal()
    assert not dispatch.calls
    assert store.load()["current_generation"] == 0


@pytest.mark.parametrize("field", ["repo", "pr", "fork", "branch", "ticket", "corrupt"])
def test_bindings_and_corrupt_history(setup, field):
    store, provider, dispatch, cycle, pr, _, _, signal = setup
    if field == "repo":
        read = provider.read
        provider.read = lambda path: (
            {"full_name": "evil/repo"} if "/pulls/" not in path else read(path)
        )
    elif field == "pr":
        pr["number"] = 124
    elif field == "fork":
        pr["head"]["repo"]["full_name"] = "fork/repo"
    elif field == "branch":
        cycle["branch"] = "other"
    elif field == "ticket":
        cycle["ticket"] = "PDFTR-49"
    else:
        store.path.write_text("{}")
    with pytest.raises(IndependentReviewError):
        signal()
    assert not dispatch.calls


def test_persist_failure_prevents_dispatch(setup, monkeypatch):
    store, _, dispatch, _, _, _, _, signal = setup

    def fail(state):
        raise OSError("disk full")

    monkeypatch.setattr(store, "_persist", fail)
    with pytest.raises(OSError):
        signal()
    assert not dispatch.calls


@pytest.mark.parametrize("outcome", ["DEFINITE_NOT_DISPATCHED", "DISPATCH_UNCERTAIN", "exception"])
def test_failure_is_never_retried(setup, outcome):
    store, _, dispatch, _, _, _, _, signal = setup
    if outcome == "exception":
        dispatch.error = TimeoutError("secret must not be persisted")
    else:
        dispatch.receipt = DispatchReceipt(outcome)
    signal()
    signal()
    assert len(dispatch.calls) == 1
    assert store.load()["current_generation"] == 1
    assert store.load()["reviews"][0]["status"] == "DISPATCH_UNCERTAIN"
    assert "secret" not in store.path.read_text()


def test_crash_after_requested_no_dispatch_on_restart(setup):
    store, provider, dispatch, cycle, _, _, _, signal = setup
    store.request(lambda: provider.fetch(cycle))
    assert signal()["decision"] == "ALREADY_REQUESTED"
    assert not dispatch.calls
    assert store.load()["reviews"][0]["status"] == "DISPATCH_UNCERTAIN"


def test_concurrent_signal_uses_existing_ticket_lock(setup):
    store, provider, dispatch, _, _, _, _, signal = setup
    entered, release = threading.Event(), threading.Event()
    read = provider.read

    def blocked(path):
        entered.set()
        assert release.wait(5)
        return read(path)

    provider.read = blocked
    errors = []

    def worker():
        try:
            signal()
        except Exception as error:
            errors.append(error)

    thread = threading.Thread(target=worker)
    thread.start()
    assert entered.wait(5)
    try:
        with pytest.raises(CycleOwnershipError):
            signal("synchronize")
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and not errors
    assert len(dispatch.calls) == 1
    assert store.load()["current_generation"] == 1


@pytest.mark.parametrize(
    "status,conclusion,expected",
    [
        ("queued", None, "PENDING"),
        ("waiting", None, "PENDING"),
        ("completed", "cancelled", "FAILURE"),
        ("completed", "timed_out", "FAILURE"),
        ("completed", "action_required", "FAILURE"),
        ("completed", "neutral", "UNKNOWN"),
        ("completed", "skipped", "UNKNOWN"),
        ("unknown", "success", "UNKNOWN"),
    ],
)
def test_normalization(status, conclusion, expected):
    doc = {
        "total_count": 1,
        "check_runs": [
            {
                "name": "ci",
                "head_sha": H,
                "status": status,
                "conclusion": conclusion,
            }
        ],
    }
    assert normalize_checks(doc, H, ["ci"]) == {"ci": expected}


@pytest.mark.parametrize(
    "event", ["pull_request", "check_run", "check_suite", "status", "workflow_run"]
)
def test_real_github_event_adapter(setup, event):
    _, _, dispatcher, _, _, _, _, signal = setup
    payload = {"action": "ready_for_review", "head_sha": OLD, "ci": "success"}
    normalized = github_event_signal(event, payload)
    assert signal(normalized, payload)["decision"] == "ELIGIBLE"
    assert dispatcher.calls[0].head_sha == H


@pytest.mark.parametrize(
    "name,payload",
    [
        ("push", {}),
        ("pull_request", {"action": "deleted"}),
        ("pull_request", []),
        ("pull_request", {"action": []}),
    ],
)
def test_unsupported_events_reject(name, payload):
    with pytest.raises(IndependentReviewError):
        github_event_signal(name, payload)


def test_cycle_reader_uses_harness_validation(monkeypatch, tmp_path):
    from types import SimpleNamespace

    manifest = {"current_head_sha": H, "state": "PASSED"}
    git = SimpleNamespace(head_sha=H, clean=True)
    calls = []

    def validated(root, ticket):
        calls.append((root, ticket))
        return None, manifest, {}, git

    monkeypatch.setattr("scripts.github_independent_review._load_cycle", validated)
    assert load_cycle(tmp_path, "PDFTR-50") is manifest
    assert calls == [(tmp_path, "PDFTR-50")]
    git.head_sha = OLD
    with pytest.raises(IndependentReviewError, match="cycle_git_mismatch"):
        load_cycle(tmp_path, "PDFTR-50")
    git.head_sha, git.clean = H, False
    with pytest.raises(IndependentReviewError):
        load_cycle(tmp_path, "PDFTR-50")


def test_truncated_check_collection_rejects():
    with pytest.raises(IndependentReviewError):
        normalize_checks({"total_count": 101, "check_runs": []}, H, ["ci"])


@pytest.mark.parametrize(
    "endpoint", ["http://example.test", "https://user:pass@example.test", "file:///x"]
)
def test_connector_rejects_unsafe_endpoint(endpoint):
    with pytest.raises(IndependentReviewError):
        HTTPSReviewDispatcher(endpoint, "secret")


def test_connector_contract_and_secret_isolation(monkeypatch):
    request = DispatchRequest("owner/repo", "PDFTR-50", 123, 1, H, B)
    response_document = {**asdict(request), "external_request_id": "opaque-123"}
    sent = []

    class Response:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, size):
            return json.dumps(response_document).encode()

    class Opener:
        def open(self, outgoing, timeout):
            sent.append(outgoing)
            return Response()

    monkeypatch.setattr("urllib.request.build_opener", lambda *_: Opener())
    transport = HTTPSReviewDispatcher(
        "https://connector.example.test/review", "credential-sentinel"
    )
    assert transport.dispatch(request) == DispatchReceipt("DISPATCHED", "opaque-123")
    assert "credential-sentinel" not in sent[0].data.decode()
    response_document["external_request_id"] = "credential-sentinel"
    assert transport.dispatch(request).outcome == "DISPATCH_UNCERTAIN"
    response_document["external_request_id"] = "opaque-123"
    response_document["head_sha"] = OLD
    assert transport.dispatch(request).outcome == "DISPATCH_UNCERTAIN"
    assert HTTPSReviewDispatcher("https://example.test", "").dispatch(request).outcome == (
        "DEFINITE_NOT_DISPATCHED"
    )


def test_github_reader_safe_error_and_manual_missing_config(monkeypatch, capsys):
    class Opener:
        def open(self, *_args, **_kwargs):
            raise OSError("credential-sentinel")

    monkeypatch.setattr("urllib.request.build_opener", lambda *_: Opener())
    with pytest.raises(IndependentReviewError, match="github_read_failed"):
        GitHubReader("credential-sentinel")("/repos/owner/repo")
    monkeypatch.delenv("PDFTR_REVIEW_CONFIG", raising=False)
    assert main(["evaluate", "PDFTR-50"]) == 1
    assert "credential-sentinel" not in capsys.readouterr().out
