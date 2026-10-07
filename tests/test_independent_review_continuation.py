"""No models, live APIs or real agents; source-bound policy and existing runner tests."""

import copy
import json

import pytest
from scripts import agent_cycle as cycle
from scripts.cycle_ownership import CycleOwnershipError, ticket_ownership
from scripts.github_review_facts import GitHubFactsProvider
from scripts.github_review_publication import PublicationOutcome
from scripts.independent_review import IndependentReviewStore
from scripts.independent_review_continuation import IndependentReviewContinuationService
from scripts.independent_review_continuation_policy import evaluate_continuation
from scripts.independent_review_dispatch import DispatchReceipt, DispatchRequest, persist_receipt
from scripts.independent_review_policy import IndependentReviewError, request_review
from scripts.independent_review_result import IndependentReviewResultService
from scripts.pi_ticket_cycle import run_cycle

from tests.test_pi_ticket_cycle import TICKET, FakePi, _config, _finding, _git
from tests.test_pi_ticket_cycle import git_repo as continuation_repo  # noqa: F401


@pytest.fixture
def setup(continuation_repo):  # noqa: F811
    git_repo = continuation_repo
    (git_repo / ".gitignore").write_text("/.agent-cycle/\n/temp/\n", encoding="utf-8")
    _git(git_repo, "add", ".gitignore")
    _git(git_repo, "commit", "-m", "ignore runtime temp")
    fake = FakePi(git_repo)
    assert run_cycle(git_repo, TICKET, executor=fake, config=_config()).passed
    config = {
        "schema_version": "1.0",
        "repository": "owner/repo",
        "ticket": TICKET,
        "pull_request": 123,
        "required_checks": ["windows", "ubuntu"],
    }
    directory = cycle.cycle_directory(git_repo, TICKET)
    store = IndependentReviewStore(git_repo, directory, config)
    store.initialize()
    facts = {
        **{k: v for k, v in config.items() if k != "required_checks"},
        "pr_exists": True,
        "pr_state": "OPEN",
        "pr_draft": False,
        "head_sha": _git(git_repo, "rev-parse", "HEAD"),
        "base_sha": _git(git_repo, "rev-parse", "master"),
        "cycle_state": "PASSED",
        "implementation_sha": _git(git_repo, "rev-parse", "HEAD"),
        "ci_sha": _git(git_repo, "rev-parse", "HEAD"),
        "checks": {"windows": "SUCCESS", "ubuntu": "SUCCESS"},
    }
    result = {}

    class Receiver:
        def receive(self, request_id):
            return {"external_request_id": request_id, "result": copy.deepcopy(result)}

    class Publisher:
        def publish(self, *_):
            return PublicationOutcome("PUBLISHED", 123)

    provider = GitHubFactsProvider(config, lambda _: {})
    provider.fetch = lambda _: copy.deepcopy(facts)
    results = IndependentReviewResultService(
        store,
        provider,
        Receiver(),
        Publisher(),
        lambda *_: {},
    )
    results.initialize()

    def publish(verdict="CHANGES_REQUIRED"):
        state, decision = request_review(facts, store.load(), config)
        store._persist(state)
        generation = decision["generation"]
        persist_receipt(
            git_repo,
            directory,
            DispatchRequest(
                "owner/repo", TICKET, 123, generation, facts["head_sha"], facts["base_sha"]
            ),
            DispatchReceipt("DISPATCHED", f"opaque-{generation}"),
        )
        result.clear()
        result.update(
            {
                **{k: v for k, v in config.items() if k != "required_checks"},
                "generation": generation,
                "reviewed_sha": facts["head_sha"],
                "verdict": verdict,
                "findings": [_finding("IR-1")] if verdict == "CHANGES_REQUIRED" else [],
            }
        )
        results.receive_and_publish(generation)

    publish()
    service = IndependentReviewContinuationService(results)
    service.initialize()
    return service, fake, facts, publish


def inputs(service, facts):
    state = service.store.load()
    ledger = service.results._load(state)
    previous = cycle._load_json(service.store.directory / "manifest.json")
    safety = service._safety(previous)
    return previous, state, ledger["publications"][-1], [], copy.deepcopy(facts), safety


def invoke(service, fake):
    return service.continue_cycle(executor=fake, config=_config(), ticket_text="# correction")


def test_happy_path_and_duplicate(setup):
    service, fake, facts, _ = setup
    before = copy.deepcopy(service.store.load()["reviews"][0])
    assert evaluate_continuation(*inputs(service, facts))["decision"] == "AUTHORIZED"
    output = invoke(service, fake)
    assert output == {"decision": "COMPLETED", "continuation_id": 1}
    assert fake.implementer_runs == fake.reviewer_runs == 2
    prompt = fake.invocations[2][1]
    assert "independent-review correction cycle" in prompt
    assert facts["head_sha"] in prompt and facts["base_sha"] in prompt
    assert '"required_fix": "Correct the defect"' in prompt
    assert service.store.load()["reviews"][0] == before
    history = json.loads(service.path.read_text())["continuations"]
    assert history[0]["implementation_attempt"] == 2
    assert history[0]["resulting_implementation_sha"] != facts["head_sha"]
    assert invoke(service, fake)["reason"] == "continuation_already_used"
    assert fake.implementer_runs == 2
    assert cycle.cycle_status(service.store.root, TICKET)["state"] == "PASSED"


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("head_sha", "a" * 40, "head_mismatch"),
        ("base_sha", "b" * 40, "base_mismatch"),
        ("ci_sha", "c" * 40, "reference_facts_invalid"),
        ("pr_draft", True, "reference_facts_invalid"),
        ("pr_state", "CLOSED", "reference_facts_invalid"),
    ],
)
def test_authoritative_drift_no_launch(setup, field, value, reason):
    service, fake, facts, _ = setup
    facts[field] = value
    assert invoke(service, fake)["reason"] == "continuation_" + reason
    assert fake.implementer_runs == 1
    assert json.loads(service.path.read_text())["continuations"] == []


@pytest.mark.parametrize(
    "field,reason",
    [
        ("repository_matches", "repository_mismatch"),
        ("branch_matches", "branch_mismatch"),
        ("head_matches", "head_mismatch"),
        ("clean", "dirty_tree"),
        ("no_operation", "repository_operation"),
        ("no_active_agent", "agent_active"),
        ("publication_resolved", "publication_uncertain"),
    ],
)
def test_safety_policy(setup, field, reason):
    service, _, facts, _ = setup
    args = inputs(service, facts)
    args[-1][field] = False
    assert evaluate_continuation(*args)["reason"] == "continuation_" + reason


@pytest.mark.parametrize(
    "state", ["IMPLEMENTING", "REVIEWING", "READY_FOR_REVIEW", "STOPPED", "FAILED"]
)
def test_invalid_cycle_states(setup, state):
    service, _, facts, _ = setup
    args = inputs(service, facts)
    args[0]["state"] = state
    assert evaluate_continuation(*args)["reason"] == "continuation_cycle_state_invalid"


def test_policy_rejections(setup):
    service, _, facts, _ = setup
    args = inputs(service, facts)
    args[2]["publication_state"] = "PUBLICATION_UNCERTAIN"
    assert evaluate_continuation(*args)["reason"] == "continuation_publication_uncertain"
    args[2]["publication_state"] = "FAILED_DEFINITE"
    assert evaluate_continuation(*args)["reason"] == "continuation_not_published"
    args = inputs(service, facts)
    args[1]["reviews"][0]["status"] = "STALE"
    assert evaluate_continuation(*args)["reason"] == "continuation_stale"
    args = inputs(service, facts)
    args[2]["continuation"] = {"comment": "fix it"}
    assert evaluate_continuation(*args)["reason"] == "continuation_generation_mismatch"
    args = inputs(service, facts)
    args[2]["continuation"]["generation"] = 99
    assert evaluate_continuation(*args)["reason"] == "continuation_generation_mismatch"
    args = inputs(service, facts)
    args[0]["active_agent"] = "implementer"
    assert evaluate_continuation(*args)["reason"] == "continuation_agent_active"
    args = inputs(service, facts)
    args[3].append({"source_generation": 1})
    assert evaluate_continuation(*args)["reason"] == "continuation_already_used"
    args[3][:] = [{"source_generation": 98}, {"source_generation": 99}]
    assert evaluate_continuation(*args)["reason"] == "continuation_budget_exhausted"


@pytest.mark.parametrize("operation", ["MERGE_HEAD", "rebase-merge", "CHERRY_PICK_HEAD"])
def test_operation_state_no_launch(setup, operation):
    service, fake, _, _ = setup
    path = service.store.root / ".git" / operation
    if operation == "rebase-merge":
        path.mkdir()
    else:
        path.write_text("a" * 40)
    assert invoke(service, fake)["reason"] == "continuation_repository_operation"
    assert fake.implementer_runs == 1


def test_dirty_no_launch(setup):
    service, fake, _, _ = setup
    (service.store.root / "tracked.txt").write_text("dirty")
    assert invoke(service, fake)["reason"] == "continuation_dirty_tree"
    assert fake.implementer_runs == 1


@pytest.mark.parametrize("crash_state", ["AUTHORIZED", "PREPARED", "LAUNCHING"])
def test_restart_same_identity_and_uncertainty(setup, monkeypatch, crash_state):
    service, fake, _, _ = setup
    save = service._save

    def crash(ledger):
        save(ledger)
        if ledger["continuations"] and ledger["continuations"][-1]["state"] == crash_state:
            raise SystemExit("simulated parent crash")

    monkeypatch.setattr(service, "_save", crash)
    with pytest.raises(SystemExit):
        invoke(service, fake)
    assert fake.implementer_runs == 1
    restarted = IndependentReviewContinuationService(service.results)
    output = invoke(restarted, fake)
    if crash_state == "LAUNCHING":
        assert output["reason"] == "continuation_launch_uncertain"
        assert invoke(restarted, fake)["reason"] == "continuation_launch_uncertain"
        assert fake.implementer_runs == 1
    else:
        assert output["decision"] == "COMPLETED"
        assert fake.implementer_runs == 2
    assert len(json.loads(service.path.read_text())["continuations"]) == 1


def test_tampered_findings_reject(setup, monkeypatch):
    service, fake, _, _ = setup
    project = service._project

    def tamper(entry):
        project(entry)
        path = service._input_path(entry)
        artifact = json.loads(path.read_text())
        artifact["findings"][0]["required_fix"] = "untrusted"
        path.write_text(json.dumps(artifact))

    monkeypatch.setattr(service, "_project", tamper)
    with pytest.raises(IndependentReviewError, match="findings_mismatch"):
        invoke(service, fake)
    assert fake.implementer_runs == 1


def test_concurrent_owner_rejects(setup):
    service, fake, _, _ = setup
    with ticket_ownership(service.store.directory), pytest.raises(CycleOwnershipError):
        invoke(service, fake)
    assert invoke(service, fake)["decision"] == "COMPLETED"
    assert fake.implementer_runs == 2


def test_budget_new_sha_new_review_and_immutable_history(setup):
    service, fake, facts, publish = setup
    original = copy.deepcopy(service.store.load()["reviews"][0]["result"])
    for generation in (1, 2):
        assert invoke(service, fake)["decision"] == "COMPLETED"
        head = _git(service.store.root, "rev-parse", "HEAD")
        facts.update(head_sha=head, implementation_sha=head, ci_sha=head)
        # Old generation has no authority for the new SHA, even before next review.
        assert invoke(service, fake)["reason"] == "continuation_already_used"
        publish()
        assert service.store.load()["current_generation"] == generation + 1
    assert invoke(service, fake)["reason"] == "continuation_budget_exhausted"
    assert fake.implementer_runs == fake.reviewer_runs == 3
    assert service.store.load()["reviews"][0]["result"] == original
    manifest = cycle._load_json(service.store.directory / "manifest.json")
    assert manifest["operational_retries"] == []
    assert not manifest.get("pre_handoff_retries")


def test_internal_review_changes_remain_budgeted(setup):
    service, fake, _, _ = setup
    fake.verdicts = ["PASS", "CHANGES_REQUIRED", "CHANGES_REQUIRED"]
    fake.findings = [[], [_finding("R2")], [_finding("R3")]]
    assert invoke(service, fake)["decision"] == "RUNNING"
    status = cycle.cycle_status(service.store.root, TICKET)
    assert status["state"] == "STOPPED"
    assert status["stop_reason"] == "review_round_limit"
    assert fake.implementer_runs == fake.reviewer_runs == 3
    assert len(json.loads(service.path.read_text())["continuations"]) == 1
    with pytest.raises(cycle.CycleError):
        cycle.retry_operational_cycle(service.store.root, TICKET, "operator")
    with pytest.raises(cycle.CycleError):
        cycle.retry_pre_handoff_cycle(service.store.root, TICKET)


def test_pass_and_missing_intent_do_not_authorize(setup):
    service, fake, facts, _ = setup
    args = inputs(service, facts)
    args[1]["reviews"][0]["status"] = "PASS"
    args[1]["reviews"][0]["result"].update(verdict="PASS", findings=[])
    assert evaluate_continuation(*args)["reason"] == "continuation_not_changes_required"
    args = inputs(service, facts)
    args[2]["continuation"] = None
    assert evaluate_continuation(*args)["reason"] == "continuation_intent_missing"
    path = service.results.path
    ledger = json.loads(path.read_text())
    ledger["publications"][0]["continuation"] = None
    path.write_text(json.dumps(ledger))
    assert invoke(service, fake)["reason"] == "continuation_intent_missing"
    assert fake.implementer_runs == 1


@pytest.mark.parametrize("drift", ["branch", "head", "repository"])
def test_real_local_identity_drift(setup, drift):
    service, fake, _, _ = setup
    if drift == "branch":
        _git(service.store.root, "switch", "-c", "wrong-branch")
    elif drift == "head":
        _git(service.store.root, "commit", "--allow-empty", "-m", "head drift")
    else:
        path = service.store.directory / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["repository_fingerprint"] = "0" * 64
        path.write_text(json.dumps(manifest))
    assert invoke(service, fake)["reason"] == "continuation_" + drift + "_mismatch"
    assert fake.implementer_runs == 1


def test_revalidate_immediately_before_launch(setup, monkeypatch):
    service, fake, facts, _ = setup
    fetch = service.results.provider.fetch
    calls = 0

    def drift(previous):
        nonlocal calls
        calls += 1
        if calls == 2:
            facts["base_sha"] = "b" * 40
        return fetch(previous)

    monkeypatch.setattr(service.results.provider, "fetch", drift)
    with pytest.raises(IndependentReviewError, match="continuation_base_mismatch"):
        invoke(service, fake)
    assert fake.implementer_runs == 1
    assert json.loads(service.path.read_text())["continuations"][0]["state"] == "STALE"
    assert invoke(service, fake)["reason"] == "continuation_already_used"


def test_resume_prepared_after_begin_without_duplicate(setup, monkeypatch):
    import scripts.pi_ticket_cycle as runner

    service, fake, _, _ = setup
    begin = runner.begin_implementation

    def crash(*args):
        begin(*args)
        raise SystemExit("crash after begin")

    with monkeypatch.context() as patch:
        patch.setattr(runner, "begin_implementation", crash)
        with pytest.raises(SystemExit):
            invoke(service, fake)
    assert fake.implementer_runs == 1
    assert invoke(service, fake)["decision"] == "COMPLETED"
    assert fake.implementer_runs == 2


def test_crash_after_owned_process_exit_no_relaunch(setup, monkeypatch):
    service, fake, _, _ = setup
    save = service._save

    def crash(ledger):
        save(ledger)
        if ledger["continuations"][-1]["state"] == "RUNNING":
            raise SystemExit("crash after owned process exit")

    monkeypatch.setattr(service, "_save", crash)
    with pytest.raises(SystemExit):
        invoke(service, fake)
    restarted = IndependentReviewContinuationService(service.results)
    assert invoke(restarted, fake)["reason"] == "continuation_launch_uncertain"
    assert fake.implementer_runs == 2
    assert fake.reviewer_runs == 1


def test_older_generation_and_dispatch_receipt_fences(setup):
    service, fake, facts, publish = setup
    assert invoke(service, fake)["decision"] == "COMPLETED"
    head = _git(service.store.root, "rev-parse", "HEAD")
    facts.update(head_sha=head, implementation_sha=head, ci_sha=head)
    publish()
    assert (
        service.continue_cycle(executor=fake, config=_config(), expected_generation=1)["reason"]
        == "continuation_generation_mismatch"
    )
    receipt = service.store.directory / "independent-dispatch-2.json"
    data = json.loads(receipt.read_text())
    data["outcome"] = "DISPATCH_UNCERTAIN"
    receipt.write_text(json.dumps(data))
    with pytest.raises(IndependentReviewError, match="dispatch_receipt_mismatch"):
        invoke(service, fake)
    assert fake.implementer_runs == 2


def test_missing_youtrack_does_not_block_return_path(setup, monkeypatch):
    import scripts.pi_ticket_cycle as runner

    service, fake, _, _ = setup

    class MissingTicket:
        data = {"warnings": ["Issue not found"]}

        def __init__(self, *args, **kwargs):
            pass

        def call(self, *args):
            pass

    monkeypatch.setattr(runner, "TrackingHooks", MissingTicket)
    assert (
        service.receive_and_continue(1, executor=fake, config=_config())["decision"] == "COMPLETED"
    )
    assert fake.implementer_runs == fake.reviewer_runs == 2


def test_result_evidence_tampering_reject(setup):
    service, fake, _, _ = setup
    assert invoke(service, fake)["decision"] == "COMPLETED"
    state = service.store.load()
    state["reviews"][0]["result"]["findings"][0]["problem"] = "changed evidence"
    service.store._persist(state)
    with pytest.raises(IndependentReviewError, match="continuation_state_corrupt"):
        invoke(service, fake)
    assert fake.implementer_runs == 2


def test_new_sha_ci_is_not_bypassed(setup):
    service, fake, facts, _ = setup
    assert invoke(service, fake)["decision"] == "COMPLETED"
    head = _git(service.store.root, "rev-parse", "HEAD")
    facts.update(head_sha=head, implementation_sha=head, ci_sha=head)
    facts["checks"]["ubuntu"] = "PENDING"
    _, decision = request_review(facts, service.store.load(), service.store.config)
    assert decision["reason"] == "ci_pending"
    assert service.store.load()["current_generation"] == 1


def test_normal_runner_cannot_dispatch_policy_projection(setup, monkeypatch):
    service, fake, _, _ = setup
    project = service._project

    def crash(entry):
        project(entry)
        raise SystemExit("prepared projection")

    monkeypatch.setattr(service, "_project", crash)
    with pytest.raises(SystemExit):
        invoke(service, fake)
    from scripts.pi_ticket_cycle import RunnerError

    with pytest.raises(RunnerError):
        run_cycle(service.store.root, TICKET, executor=fake, config=_config())
    assert fake.implementer_runs == 1
