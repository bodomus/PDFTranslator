"""Trusted return path and at-most-once mutation tests; no live provider calls."""

from __future__ import annotations

import copy
import json
import urllib.error

import pytest
from scripts.github_review_facts import GitHubFactsProvider
from scripts.github_review_publication import (
    GitHubCheckPublisher,
    PublicationOutcome,
    check_payload,
)
from scripts.independent_review import IndependentReviewStore
from scripts.independent_review_dispatch import DispatchReceipt, DispatchRequest, persist_receipt
from scripts.independent_review_policy import IndependentReviewError, request_review
from scripts.independent_review_result import (
    HTTPSReviewResultReceiver,
    IndependentReviewResultService,
)

H, B, OLD = "a" * 40, "b" * 40, "c" * 40


@pytest.fixture
def setup(tmp_path):
    config = {
        "schema_version": "1.0",
        "repository": "owner/repo",
        "ticket": "PDFTR-51",
        "pull_request": 123,
        "required_checks": ["windows", "ubuntu"],
    }
    facts = {
        **{k: v for k, v in config.items() if k != "required_checks"},
        "pr_exists": True,
        "pr_state": "OPEN",
        "pr_draft": False,
        "head_sha": H,
        "base_sha": B,
        "cycle_state": "PASSED",
        "implementation_sha": H,
        "ci_sha": H,
        "checks": {"windows": "SUCCESS", "ubuntu": "SUCCESS"},
    }
    store = IndependentReviewStore(tmp_path, tmp_path / "cycle", config)
    store.initialize()
    state, _ = request_review(facts, store.load(), config)
    store._persist(state)
    persist_receipt(
        tmp_path,
        store.directory,
        DispatchRequest("owner/repo", "PDFTR-51", 123, 1, H, B),
        DispatchReceipt("DISPATCHED", "opaque-123"),
    )
    result = {
        **{k: v for k, v in config.items() if k != "required_checks"},
        "generation": 1,
        "reviewed_sha": H,
        "verdict": "PASS",
        "findings": [],
    }

    class Receiver:
        def receive(self, request_id):
            assert request_id == "opaque-123"
            return copy.deepcopy({"external_request_id": "opaque-123", "result": result})

    class Publisher:
        calls = 0
        outcome = PublicationOutcome("PUBLISHED", 99)
        reconciled = PublicationOutcome("PUBLICATION_UNCERTAIN")
        after_write = None

        def publish(self, repo, payload):
            assert store.load()["reviews"][0]["result"] == result
            ledger = json.loads(service.path.read_text())
            assert ledger["publications"][0]["publication_state"] == "PENDING"
            assert payload["head_sha"] == H
            self.calls += 1
            if self.after_write:
                self.after_write()
            return self.outcome

        def reconcile(self, *_):
            return self.reconciled

    provider = GitHubFactsProvider(config, lambda _: {})
    provider.fetch = lambda _: copy.deepcopy(facts)
    publisher = Publisher()
    service = IndependentReviewResultService(
        store, provider, Receiver(), publisher, lambda *_: {}, secrets=("credential-sentinel",)
    )
    service.initialize()
    return service, store, publisher, facts, result


def changes(result):
    result["verdict"] = "CHANGES_REQUIRED"
    result["findings"] = [
        {
            "id": "IR-1",
            "severity": "HIGH",
            "file": "scripts/foo.py",
            "symbol": "Foo.bar",
            "problem": "Broken binding",
            "required_fix": "Bind",
            "regression_test": "Wrong generation rejects",
        }
    ]


@pytest.mark.parametrize("verdict", ["PASS", "CHANGES_REQUIRED"])
def test_current_duplicate_and_restart(setup, verdict):
    service, store, publisher, _, result = setup
    if verdict == "CHANGES_REQUIRED":
        changes(result)
    for _ in range(3):
        output = service.receive_and_publish(1)
        assert output["publication"]["publication_state"] == "PUBLISHED"
        assert output["ready_for_human_merge"] == (verdict == "PASS")
        assert output["continuation_eligible"] == (verdict == "CHANGES_REQUIRED")
    assert publisher.calls == 1
    assert len(store.load()["reviews"]) == 1
    assert len(json.loads(service.path.read_text())["publications"]) == 1
    restarted = IndependentReviewResultService(
        store, service.provider, service.receiver, publisher, lambda *_: {}
    )
    assert restarted.status(1)["publication"]["github_check_id"] == 99
    assert publisher.calls == 1


@pytest.mark.parametrize("verdict", ["PASS", "CHANGES_REQUIRED"])
@pytest.mark.parametrize("field", ["head_sha", "base_sha"])
def test_late_results_preserved_stale(setup, verdict, field):
    service, store, publisher, facts, result = setup
    if verdict == "CHANGES_REQUIRED":
        changes(result)
    facts[field] = OLD
    output = service.receive_and_publish(1)
    review = store.load()["reviews"][0]
    assert review["result"] == result and review["status"] == "STALE"
    assert output["publication"]["publication_state"] == "STALE"
    assert not output["ready_for_human_merge"] and not output["continuation_eligible"]
    assert publisher.calls == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("generation", 2),
        ("reviewed_sha", OLD),
        ("repository", "evil/repo"),
        ("pull_request", 124),
        ("ticket", "PDFTR-52"),
        ("mutate", "merge"),
    ],
)
def test_result_binding_and_unknown_fields(setup, field, value):
    service, store, publisher, _, result = setup
    result[field] = value
    with pytest.raises(IndependentReviewError):
        service.receive_and_publish(1)
    assert store.load()["reviews"][0]["result"] is None
    assert publisher.calls == 0


def test_receipt_envelope_and_persisted_binding(setup):
    service, store, publisher, _, result = setup
    service.receiver.receive = lambda _: {"external_request_id": "wrong", "result": result}
    with pytest.raises(IndependentReviewError, match="receipt_mismatch"):
        service.receive_and_publish(1)
    path = store.directory / "independent-dispatch-1.json"
    receipt = json.loads(path.read_text())
    receipt["base_sha"] = OLD
    path.write_text(json.dumps(receipt))
    with pytest.raises(IndependentReviewError, match="receipt_mismatch"):
        service.receive_and_publish(1)
    assert publisher.calls == 0


@pytest.mark.parametrize("target", ["result", "intent"])
def test_persist_failures_prevent_mutation(setup, monkeypatch, target):
    service, store, publisher, _, _ = setup

    def fail(*_):
        raise OSError("credential-sentinel")

    monkeypatch.setattr(
        store if target == "result" else service,
        "_persist" if target == "result" else "_save",
        fail,
    )
    with pytest.raises(OSError):
        service.receive_and_publish(1)
    assert publisher.calls == 0


@pytest.mark.parametrize("state", ["PENDING", "PUBLICATION_UNCERTAIN", "FAILED_DEFINITE"])
def test_publication_restart_never_resends(setup, state):
    service, _, publisher, _, _ = setup
    publisher.outcome = PublicationOutcome("PUBLICATION_UNCERTAIN")
    service.receive_and_publish(1)
    ledger = json.loads(service.path.read_text())
    ledger["publications"][0]["publication_state"] = state
    service._save(ledger)
    output = service.receive_and_publish(1)
    assert publisher.calls == 1
    assert output["publication"]["publication_state"] == (
        "PUBLICATION_UNCERTAIN" if state == "PENDING" else state
    )


def test_timeout_and_reconcile(setup):
    service, _, publisher, _, _ = setup

    def timeout(*_):
        publisher.calls += 1
        raise TimeoutError("credential-sentinel")

    publisher.publish = timeout
    assert (
        service.receive_and_publish(1)["publication"]["publication_state"]
        == "PUBLICATION_UNCERTAIN"
    )
    assert (
        service.status(1, reconcile=True)["publication"]["publication_state"]
        == "PUBLICATION_UNCERTAIN"
    )
    publisher.reconciled = PublicationOutcome("PUBLISHED", 101)
    assert service.status(1, reconcile=True)["publication"]["github_check_id"] == 101
    assert publisher.calls == 1
    assert "credential-sentinel" not in service.path.read_text()


@pytest.mark.parametrize("verdict", ["PASS", "CHANGES_REQUIRED"])
def test_refresh_before_publish_and_post_write_race(setup, verdict):
    service, store, publisher, facts, result = setup
    if verdict == "CHANGES_REQUIRED":
        changes(result)
    publisher.after_write = lambda: facts.update(head_sha=OLD)
    output = service.receive_and_publish(1)
    assert publisher.calls == 1  # Check is bound to H, never OLD.
    assert store.load()["reviews"][0]["status"] == "STALE"
    assert not output["ready_for_human_merge"] and not output["continuation_eligible"]


def test_head_changes_between_ingest_and_intent(setup):
    service, _, publisher, facts, _ = setup
    calls = 0

    def refresh(_):
        nonlocal calls
        calls += 1
        if calls == 2:
            facts["base_sha"] = OLD
        return copy.deepcopy(facts)

    service.provider.fetch = refresh
    assert service.receive_and_publish(1)["publication"]["publication_state"] == "STALE"
    assert publisher.calls == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("head_sha", OLD),
        ("base_sha", OLD),
        ("pr_draft", True),
        ("pr_state", "CLOSED"),
        ("cycle_state", "IMPLEMENTING"),
        ("checks", {"windows": "FAILURE", "ubuntu": "SUCCESS"}),
    ],
)
def test_readiness_recomputed(setup, field, value):
    service, _, publisher, facts, _ = setup
    assert service.receive_and_publish(1)["ready_for_human_merge"]
    facts[field] = value
    assert not service.status(1)["ready_for_human_merge"]
    assert publisher.calls == 1


def test_stale_continuation_is_ineligible(setup):
    service, _, _, facts, result = setup
    changes(result)
    assert service.receive_and_publish(1)["continuation_eligible"]
    facts["base_sha"] = OLD
    output = service.status(1)
    assert output["publication"]["continuation"] is not None  # Immutable historical intent.
    assert not output["continuation_eligible"]


def test_artifact_does_not_authenticate_and_corrupt_ledger_rejects(setup):
    service, store, publisher, _, result = setup
    (store.directory / "agent-pass.json").write_text(json.dumps(result))
    assert store.load()["reviews"][0]["result"] is None
    service.path.write_text("{}")
    with pytest.raises(IndependentReviewError):
        service.receive_and_publish(1)
    with pytest.raises(IndependentReviewError):
        service.initialize()
    assert publisher.calls == 0


def test_secret_rejection_and_bounded_findings(setup):
    service, store, publisher, _, result = setup
    changes(result)
    result["findings"][0]["problem"] = "credential-sentinel"
    with pytest.raises(IndependentReviewError, match="contains_secret"):
        service.receive_and_publish(1)
    assert store.load()["reviews"][0]["result"] is None
    result["findings"][0]["problem"] = "x" * 50000
    service.receive_and_publish(1)
    assert (
        "Additional findings omitted"
        in json.loads(service.path.read_text())["publications"][0]["payload"]["output"]["summary"]
    )
    assert len(store.load()["reviews"][0]["result"]["findings"][0]["problem"]) == 50000
    assert publisher.calls == 1


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.test",
        "https://u:p@example.test",
        "file:///x",
        "https://example.test?token=x",
    ],
)
def test_receiver_endpoint_rejects(endpoint):
    with pytest.raises(IndependentReviewError):
        HTTPSReviewResultReceiver(endpoint, "secret")


def test_authenticated_receiver(monkeypatch, setup):
    _, _, _, _, result = setup
    document = {"external_request_id": "opaque-123", "result": result}
    sent = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, _):
            return json.dumps(document).encode()

    class Opener:
        def open(self, outgoing, timeout):
            sent.append(outgoing)
            return Response()

    monkeypatch.setattr("urllib.request.build_opener", lambda *_: Opener())
    receiver = HTTPSReviewResultReceiver(
        "https://connector.example.test/results", "credential-sentinel"
    )
    assert receiver.receive("opaque-123") == document
    assert sent[0].get_method() == "GET"
    assert sent[0].full_url.endswith("/opaque-123")
    document["result"]["ticket"] = "credential-sentinel"
    with pytest.raises(IndependentReviewError):
        receiver.receive("opaque-123")


@pytest.mark.parametrize(
    "code,expected",
    [
        (400, "FAILED_DEFINITE"),
        (401, "FAILED_DEFINITE"),
        (403, "FAILED_DEFINITE"),
        (408, "PUBLICATION_UNCERTAIN"),
        (500, "PUBLICATION_UNCERTAIN"),
        (504, "PUBLICATION_UNCERTAIN"),
    ],
)
def test_github_mutation_errors(monkeypatch, setup, code, expected):
    _, store, _, _, result = setup
    review = store.load()["reviews"][0]
    review["result"] = result
    payload = check_payload(store.config, review)

    class Opener:
        def open(self, *_args, **_kwargs):
            raise urllib.error.HTTPError(
                "https://api.github.com", code, "credential-sentinel", {}, None
            )

    monkeypatch.setattr("urllib.request.build_opener", lambda *_: Opener())
    assert (
        GitHubCheckPublisher("credential-sentinel", 42).publish("owner/repo", payload).state
        == expected
    )


def test_github_success_and_exact_app_reconciliation(monkeypatch, setup):
    _, store, _, _, result = setup
    review = store.load()["reviews"][0]
    review["result"] = result
    payload = check_payload(store.config, review)
    run = {**payload, "id": 99, "app": {"id": 42}}

    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, _):
            return json.dumps(run).encode()

    class Opener:
        def open(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr("urllib.request.build_opener", lambda *_: Opener())
    publisher = GitHubCheckPublisher("credential-sentinel", 42)
    assert publisher.publish("owner/repo", payload) == PublicationOutcome("PUBLISHED", 99)
    document = {"total_count": 1, "check_runs": [run]}
    publisher.read = lambda _: document
    assert publisher.reconcile("owner/repo", payload).state == "PUBLISHED"
    run["app"]["id"] = 43
    assert publisher.reconcile("owner/repo", payload).state == "PUBLICATION_UNCERTAIN"
    run["app"]["id"] = 42
    document["check_runs"].append(copy.deepcopy(run))
    document["total_count"] = 2
    assert publisher.reconcile("owner/repo", payload).state == "PUBLICATION_UNCERTAIN"
    document.update(total_count=0, check_runs=[])
    assert publisher.reconcile("owner/repo", payload).state == "PUBLICATION_UNCERTAIN"


def test_crash_after_mutation_before_outcome_save(setup, monkeypatch):
    service, _, publisher, _, _ = setup
    save = service._save

    def fail_outcome(ledger):
        if ledger["publications"][0]["publication_state"] == "PUBLISHED":
            raise OSError("disk full")
        save(ledger)

    monkeypatch.setattr(service, "_save", fail_outcome)
    with pytest.raises(OSError):
        service.receive_and_publish(1)
    assert publisher.calls == 1
    assert json.loads(service.path.read_text())["publications"][0]["publication_state"] == "PENDING"
    monkeypatch.setattr(service, "_save", save)
    assert (
        service.receive_and_publish(1)["publication"]["publication_state"]
        == "PUBLICATION_UNCERTAIN"
    )
    assert publisher.calls == 1


def test_duplicate_different_evidence_rejects(setup):
    service, store, publisher, _, result = setup
    service.receive_and_publish(1)
    changes(result)
    with pytest.raises(IndependentReviewError, match="immutable"):
        service.receive_and_publish(1)
    assert store.load()["reviews"][0]["result"]["verdict"] == "PASS"
    assert publisher.calls == 1


def test_current_new_generation_cannot_authorize_old_pass(setup):
    service, store, publisher, facts, result = setup
    service.receive_and_publish(1)
    facts.update(head_sha=OLD, implementation_sha=OLD, ci_sha=OLD)
    state, _ = request_review(facts, store.load(), store.config)
    store._persist(state)
    persist_receipt(
        store.root,
        store.directory,
        DispatchRequest("owner/repo", "PDFTR-51", 123, 2, OLD, B),
        DispatchReceipt("DISPATCHED", "opaque-456"),
    )
    result.update(generation=2, reviewed_sha=OLD)
    service.receiver.receive = lambda _: {"external_request_id": "opaque-456", "result": result}
    # This fixture publisher checks H/first generation, replace with exact second generation fake.
    publisher.publish = lambda *_: PublicationOutcome("PUBLISHED", 100)
    assert service.receive_and_publish(2)["ready_for_human_merge"]
    assert not service.status(1)["ready_for_human_merge"]


def test_exclusive_ticket_ownership(setup):
    from scripts.cycle_ownership import CycleOwnershipError, ticket_ownership

    service, store, publisher, _, _ = setup
    with ticket_ownership(store.directory), pytest.raises(CycleOwnershipError):
        service.receive_and_publish(1)
    assert publisher.calls == 0


def test_publication_success_survives_secondary_refresh_failure(setup):
    service, _, publisher, facts, _ = setup
    calls = 0

    def refresh(_):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise IndependentReviewError("github_read_failed")
        return copy.deepcopy(facts)

    service.provider.fetch = refresh
    with pytest.raises(IndependentReviewError):
        service.receive_and_publish(1)
    assert (
        json.loads(service.path.read_text())["publications"][0]["publication_state"] == "PUBLISHED"
    )
    assert publisher.calls == 1


@pytest.mark.parametrize("transport", ["timeout", "malformed", "redirect"])
def test_github_unreadable_writes_remain_uncertain(monkeypatch, setup, transport):
    _, store, _, _, result = setup
    review = store.load()["reviews"][0]
    review["result"] = result
    payload = check_payload(store.config, review)

    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, _):
            return b"not-json credential-sentinel"

    class Opener:
        def open(self, *_args, **_kwargs):
            if transport == "timeout":
                raise TimeoutError("credential-sentinel")
            if transport == "redirect":
                raise urllib.error.HTTPError("https://api.github.com", 302, "secret", {}, None)
            return Response()

    monkeypatch.setattr("urllib.request.build_opener", lambda *_: Opener())
    publisher = GitHubCheckPublisher("credential-sentinel", 42)
    assert publisher.publish("owner/repo", payload).state == "PUBLICATION_UNCERTAIN"


def test_strict_ledger_config_types_and_status_generation(setup):
    service, _, publisher, _, _ = setup
    service.receive_and_publish(1)
    with pytest.raises(IndependentReviewError, match="unknown_generation"):
        service.status(True)
    ledger = json.loads(service.path.read_text())
    ledger["config"]["pull_request"] = 123.0
    service._save(ledger)
    with pytest.raises(IndependentReviewError):
        service.status(1)
    assert publisher.calls == 1


def test_automatically_known_transport_tokens_reject_before_persistence(setup):
    service, store, publisher, _, result = setup
    service.receiver.token = "connector-credential"
    publisher.token = "github-credential"
    protected = IndependentReviewResultService(
        store, service.provider, service.receiver, publisher, lambda *_: {}
    )
    changes(result)
    result["findings"][0]["problem"] = "github-credential"
    with pytest.raises(IndependentReviewError, match="contains_secret"):
        protected.receive_and_publish(1)
    assert store.load()["reviews"][0]["result"] is None
    assert publisher.calls == 0
