"""Credential-free tests of independent exact-SHA review and persistence fences."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from scripts.cycle_ownership import CycleOwnershipError, ticket_ownership
from scripts.independent_review import IndependentReviewStore, main, read_json
from scripts.independent_review_policy import (
    IndependentReviewError,
    empty_state,
    evaluate_independent_review,
    mark_dispatch,
    pass_is_valid,
    record_result,
    refresh_state,
    request_review,
    validate_state,
)

A, B = "a" * 40, "b" * 40


@pytest.fixture
def config():
    return {
        "schema_version": "1.0",
        "repository": "bodomus/PDFTranslator",
        "ticket": "PDFTR-49",
        "pull_request": 123,
        "required_checks": ["windows", "ubuntu"],
    }


@pytest.fixture
def facts(config):
    return {k: v for k, v in config.items() if k != "required_checks"} | {
        "pr_exists": True,
        "pr_state": "OPEN",
        "pr_draft": False,
        "head_sha": A,
        "base_sha": "c" * 40,
        "cycle_state": "PASSED",
        "implementation_sha": A,
        "ci_sha": A,
        "checks": {"windows": "SUCCESS", "ubuntu": "SUCCESS"},
    }


def result(config, generation=1, sha=A, verdict="PASS"):
    finding = {
        "id": "IR-1",
        "severity": "HIGH",
        "file": "scripts/foo.py",
        "symbol": "Foo.bar",
        "problem": "unsafe",
        "required_fix": "reject",
        "regression_test": "test rejection",
    }
    return {k: v for k, v in config.items() if k != "required_checks"} | {
        "generation": generation,
        "reviewed_sha": sha,
        "verdict": verdict,
        "findings": [] if verdict == "PASS" else [finding],
    }


def new_head(facts):
    return facts | {"head_sha": B, "implementation_sha": B, "ci_sha": B}


def test_eligible_pure_idempotent(facts, config):
    state = empty_state(config)
    original = copy.deepcopy((facts, state, config))
    decision = evaluate_independent_review(facts, state, config)
    assert decision == {"decision": "ELIGIBLE", "reason": "eligible", "generation": 1}
    assert evaluate_independent_review(facts, state, config) == decision
    assert (facts, state, config) == original
    state, _ = request_review(facts, state, config)
    for _ in range(4):
        state, duplicate = request_review(facts, state, config)
        assert duplicate["decision"] == "ALREADY_REQUESTED"
        assert len(state["reviews"]) == 1


@pytest.mark.parametrize(
    ("patch", "reason"),
    [
        ({"checks": {"windows": "SUCCESS", "ubuntu": "PENDING"}}, "ci_pending"),
        ({"checks": {"windows": "SUCCESS", "ubuntu": "FAILURE"}}, "ci_failed"),
        ({"checks": {"windows": "SUCCESS", "ubuntu": "UNKNOWN"}}, "ci_unknown"),
        ({"checks": {"windows": "SUCCESS"}}, "ci_unknown"),
        ({"ci_sha": B}, "ci_sha_mismatch"),
        ({"implementation_sha": B}, "sha_mismatch"),
        ({"pr_draft": True}, "pr_draft"),
        ({"pr_state": "CLOSED"}, "pr_closed"),
        ({"pr_state": "MERGED"}, "pr_closed"),
        ({"pr_exists": False}, "pr_missing"),
        ({"cycle_state": "STOPPED"}, "cycle_not_passed"),
    ],
)
def test_not_ready_no_generation(facts, config, patch, reason):
    state, decision = request_review(facts | patch, empty_state(config), config)
    assert decision == {"decision": "NOT_ELIGIBLE", "reason": reason, "generation": None}
    assert state["reviews"] == []


@pytest.mark.parametrize(
    "patch",
    [
        {"repository": "attacker/repo"},
        {"pull_request": 124},
        {"ticket": "PDFTR-50"},
        {"head_sha": "main"},
        {"ci_sha": A.upper()},
        {"base_sha": None},
        {"pr_draft": 0},
        {"pull_request": True},
        {"checks": {"windows": []}},
        {"event": "check_run"},
        {"schema_version": "2.0"},
    ],
)
def test_invalid_facts_fail_closed(facts, config, patch):
    assert (
        evaluate_independent_review(facts | patch, empty_state(config), config)["decision"]
        == "INVALID"
    )
    assert not pass_is_valid(facts | patch, empty_state(config), config)


def test_missing_facts_and_required_config(facts, config):
    for key in facts:
        incomplete = facts.copy()
        del incomplete[key]
        assert (
            evaluate_independent_review(incomplete, empty_state(config), config)["decision"]
            == "INVALID"
        )
    for checks in ([], ["windows", "windows"], [True], None):
        with pytest.raises(IndependentReviewError):
            empty_state(config | {"required_checks": checks})


@pytest.mark.parametrize("verdict", ["PASS", "CHANGES_REQUIRED"])
def test_result_and_head_update(facts, config, verdict):
    state, _ = request_review(facts, empty_state(config), config)
    evidence = result(config, verdict=verdict)
    state = record_result(facts, state, config, evidence)
    assert pass_is_valid(facts, state, config) == (verdict == "PASS")
    assert evaluate_independent_review(facts, state, config)["decision"] == "ALREADY_REVIEWED"
    moved = new_head(facts)
    assert not pass_is_valid(moved, state, config)
    updated, decision = request_review(moved, state, config)
    assert decision["generation"] == 2
    assert updated["reviews"][0]["status"] == "STALE"
    assert updated["reviews"][0]["result"] == evidence
    assert state["reviews"][0]["status"] == verdict  # caller input untouched
    for _ in range(3):
        updated, decision = request_review(moved, updated, config)
        assert decision["decision"] == "ALREADY_REQUESTED"
        assert updated["current_generation"] == 2
    updated = record_result(moved, updated, config, result(config, 2, B))
    assert pass_is_valid(moved, updated, config)
    # Returning to A does not revive its historical PASS or allocate a duplicate SHA.
    reverted, decision = request_review(facts, updated, config)
    assert decision["decision"] == "STALE"
    assert not pass_is_valid(facts, reverted, config)
    assert reverted["current_generation"] == 2


@pytest.mark.parametrize("status", ["REQUESTED", "RUNNING", "DISPATCH_UNCERTAIN"])
def test_late_pass_historical(facts, config, status):
    state, _ = request_review(facts, empty_state(config), config)
    if status != "REQUESTED":
        state = mark_dispatch(state, config, 1, status)
    moved = new_head(facts)
    state, _ = request_review(moved, state, config)
    state = record_result(moved, state, config, result(config))
    assert state["reviews"][0]["status"] == "STALE"
    assert state["reviews"][0]["result"]["verdict"] == "PASS"
    assert not pass_is_valid(moved, state, config)


def test_pass_revoked_by_readiness(facts, config):
    state, _ = request_review(facts, empty_state(config), config)
    state = record_result(facts, state, config, result(config))
    for patch in (
        {"pr_draft": True},
        {"pr_state": "CLOSED"},
        {"cycle_state": "STOPPED"},
        {"ci_sha": B},
        {"checks": {"windows": "FAILURE", "ubuntu": "SUCCESS"}},
    ):
        assert not pass_is_valid(facts | patch, state, config)
    assert pass_is_valid(facts, state, config)


def test_pass_invalid_on_base_only_move_and_pair_return(facts, config):
    state, _ = request_review(facts, empty_state(config), config)
    evidence = result(config)
    state = record_result(facts, state, config, evidence)
    assert pass_is_valid(facts, state, config)
    moved = facts | {"base_sha": "d" * 40}
    assert not pass_is_valid(moved, state, config)
    assert evaluate_independent_review(moved, state, config)["decision"] == "ELIGIBLE"
    updated, decision = request_review(moved, state, config)
    assert decision == {"decision": "ELIGIBLE", "reason": "eligible", "generation": 2}
    assert updated["reviews"][0]["status"] == "STALE"
    assert updated["reviews"][0]["result"] == evidence
    assert updated["reviews"][0]["requested_base_sha"] == "c" * 40
    assert updated["reviews"][1]["requested_base_sha"] == "d" * 40
    assert state["reviews"][0]["status"] == "PASS"
    for _ in range(3):
        updated, duplicate = request_review(moved, updated, config)
        assert duplicate["decision"] == "ALREADY_REQUESTED"
        assert len(updated["reviews"]) == 2
    updated = record_result(moved, updated, config, result(config, 2))
    assert pass_is_valid(moved, updated, config)
    assert evaluate_independent_review(moved, updated, config)["decision"] == "ALREADY_REVIEWED"
    reverted, decision = request_review(facts, updated, config)
    assert decision["decision"] == "STALE"
    assert reverted["current_generation"] == 2
    assert all(review["status"] == "STALE" for review in reverted["reviews"])
    assert not pass_is_valid(facts, reverted, config)
    assert record_result(facts, reverted, config, evidence) == reverted
    with pytest.raises(IndependentReviewError, match="result_immutable"):
        record_result(facts, reverted, config, result(config, verdict="CHANGES_REQUIRED"))


@pytest.mark.parametrize("status", ["REQUESTED", "RUNNING", "DISPATCH_UNCERTAIN"])
@pytest.mark.parametrize("new_request", [False, True])
def test_base_only_move_stales_active_and_late_pass(facts, config, status, new_request):
    state, _ = request_review(facts, empty_state(config), config)
    if status != "REQUESTED":
        state = mark_dispatch(state, config, 1, status)
    moved = facts | {"base_sha": "d" * 40}
    state = refresh_state(moved, state, config)
    assert state["reviews"][0]["status"] == "STALE"
    if new_request:
        state, decision = request_review(moved, state, config)
        assert decision["decision"] == "ELIGIBLE" and decision["generation"] == 2
    state = record_result(moved, state, config, result(config))
    assert state["reviews"][0]["status"] == "STALE"
    assert state["reviews"][0]["result"] == result(config)
    assert state["reviews"][0]["requested_base_sha"] == "c" * 40
    assert not pass_is_valid(moved, state, config)
    assert not pass_is_valid(facts, state, config)


@pytest.mark.parametrize(
    ("patch", "reason"),
    [
        ({"checks": {"windows": "SUCCESS", "ubuntu": "PENDING"}}, "ci_pending"),
        ({"checks": {"windows": "SUCCESS", "ubuntu": "FAILURE"}}, "ci_failed"),
        ({"checks": {"windows": "SUCCESS", "ubuntu": "UNKNOWN"}}, "ci_unknown"),
        ({"ci_sha": B}, "ci_sha_mismatch"),
        ({"implementation_sha": B}, "sha_mismatch"),
        ({"cycle_state": "STOPPED"}, "cycle_not_passed"),
        ({"pr_draft": True}, "pr_draft"),
        ({"pr_state": "CLOSED"}, "pr_closed"),
    ],
)
def test_base_change_revokes_pass_before_readiness(facts, config, patch, reason):
    state, _ = request_review(facts, empty_state(config), config)
    state = record_result(facts, state, config, result(config))
    moved = facts | {"base_sha": "d" * 40}
    updated, decision = request_review(moved | patch, state, config)
    assert decision == {"decision": "NOT_ELIGIBLE", "reason": reason, "generation": None}
    assert updated["reviews"][0]["status"] == "STALE"
    assert updated["current_generation"] == 1
    assert not pass_is_valid(moved | patch, updated, config)
    assert not pass_is_valid(facts, updated, config)
    updated, decision = request_review(moved, updated, config)
    assert decision["decision"] == "ELIGIBLE" and updated["current_generation"] == 2


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_sha",
        "duplicate_number",
        "pass_without_result",
        "wrong_result_sha",
        "generation_bool",
        "current_bool",
        "active_old",
        "unknown_status",
        "binding",
        "checks",
    ],
)
def test_corrupt_generation(facts, config, mutation):
    state, _ = request_review(facts, empty_state(config), config)
    state, _ = request_review(new_head(facts), state, config)
    if mutation == "duplicate_sha":
        state["reviews"][1]["requested_sha"] = A
    elif mutation == "duplicate_number":
        state["reviews"][1]["generation"] = 1
    elif mutation == "pass_without_result":
        state["reviews"][1]["status"] = "PASS"
    elif mutation == "wrong_result_sha":
        state["reviews"][1].update(status="PASS", result=result(config, 2, A))
    elif mutation == "generation_bool":
        state["reviews"][0]["generation"] = True
    elif mutation == "current_bool":
        state["current_generation"] = True
    elif mutation == "active_old":
        state["reviews"][0]["status"] = "RUNNING"
    elif mutation == "unknown_status":
        state["reviews"][1]["status"] = "ELIGIBLE"
    elif mutation == "binding":
        state["repository"] = "wrong/repo"
    else:
        state["required_checks"] = ["windows"]
    assert evaluate_independent_review(new_head(facts), state, config)["decision"] == "INVALID"
    with pytest.raises(IndependentReviewError):
        validate_state(state, config)


@pytest.mark.parametrize(
    "patch",
    [
        {"repository": "wrong/repo"},
        {"pull_request": True},
        {"generation": 2},
        {"generation": True},
        {"reviewed_sha": B},
        {"reviewed_sha": "main"},
        {"verdict": "BLOCKED"},
        {"verdict": "CHANGES_REQUIRED"},
        {"findings": [{}]},
        {"findings": None},
        {"extra": 1},
    ],
)
def test_result_validation(facts, config, patch):
    state, _ = request_review(facts, empty_state(config), config)
    with pytest.raises(IndependentReviewError):
        record_result(facts, state, config, result(config) | patch)
    assert state["reviews"][0]["result"] is None


def test_finding_grammar_and_immutable_result(facts, config):
    state, _ = request_review(facts, empty_state(config), config)
    evidence = result(config, verdict="CHANGES_REQUIRED")
    for patch in ({"severity": "P1"}, {"problem": ""}, {"file": None}, {"extra": 0}):
        invalid = copy.deepcopy(evidence)
        invalid["findings"][0].update(patch)
        with pytest.raises(IndependentReviewError):
            record_result(facts, state, config, invalid)
    accepted = record_result(facts, state, config, evidence)
    assert record_result(facts, accepted, config, evidence) == accepted
    with pytest.raises(IndependentReviewError, match="result_immutable"):
        record_result(facts, accepted, config, result(config))


def test_uncertainty_no_retry(facts, config):
    state, _ = request_review(facts, empty_state(config), config)
    state = mark_dispatch(state, config, 1, "DISPATCH_UNCERTAIN")
    state, decision = request_review(facts, state, config)
    assert decision["decision"] == "ALREADY_REQUESTED"
    with pytest.raises(IndependentReviewError, match="dispatch_uncertain"):
        mark_dispatch(state, config, 1, "RUNNING")


def test_event_name_not_policy_input(facts, config):
    decisions = []
    for _signal in (
        "opened",
        "ready_for_review",
        "synchronize",
        "check_run",
        "workflow_run",
        "manual",
    ):
        # Event adapters must refresh to the same facts, not pass event payloads.
        decisions.append(evaluate_independent_review(facts, empty_state(config), config))
    assert all(d == decisions[0] for d in decisions)


def test_refresh_without_eligibility_preserves_evidence(facts, config):
    state, _ = request_review(facts, empty_state(config), config)
    moved = new_head(facts) | {"checks": {"windows": "PENDING"}}
    refreshed = refresh_state(moved, state, config)
    assert refreshed["reviews"][0]["status"] == "STALE"
    refreshed = record_result(moved, refreshed, config, result(config))
    assert refreshed["reviews"][0]["result"] == result(config)
    assert not pass_is_valid(moved, refreshed, config)


@pytest.fixture
def store(tmp_path, config):
    store = IndependentReviewStore(tmp_path, tmp_path / "coordination" / "PDFTR-49", config)
    store.initialize()
    return store


def test_store_crash_restart_and_exclusive_ownership(store, facts, config):
    assert store.request(lambda: facts)["decision"] == "ELIGIBLE"
    restarted = IndependentReviewStore(store.root, store.directory, config)
    assert restarted.request(lambda: facts)["decision"] == "ALREADY_REQUESTED"
    assert len(restarted.load()["reviews"]) == 1
    with ticket_ownership(store.directory), pytest.raises(CycleOwnershipError):
        restarted.request(lambda: facts)
    restarted.dispatch_status(1, "DISPATCH_UNCERTAIN")
    assert restarted.request(lambda: facts)["decision"] == "ALREADY_REQUESTED"
    restarted.accept_result(lambda: new_head(facts), result(config))
    assert restarted.load()["reviews"][0]["status"] == "STALE"


def test_store_base_pair_binding_survives_restart(store, facts, config):
    assert store.request(lambda: facts)["generation"] == 1
    store.accept_result(lambda: facts, result(config))
    restarted = IndependentReviewStore(store.root, store.directory, config)
    assert pass_is_valid(facts, restarted.load(), config)
    moved = facts | {"base_sha": "d" * 40}
    assert not pass_is_valid(moved, restarted.load(), config)
    assert restarted.request(lambda: moved)["generation"] == 2
    persisted = restarted.load()
    assert persisted["reviews"][0]["status"] == "STALE"
    assert [r["requested_base_sha"] for r in persisted["reviews"]] == ["c" * 40, "d" * 40]
    assert restarted.request(lambda: moved)["decision"] == "ALREADY_REQUESTED"
    restarted.dispatch_status(2, "DISPATCH_UNCERTAIN")
    assert restarted.request(lambda: moved)["decision"] == "ALREADY_REQUESTED"
    assert restarted.request(lambda: facts)["decision"] == "STALE"
    assert restarted.load()["current_generation"] == 2


def test_store_late_base_result_before_new_request(store, facts, config):
    store.request(lambda: facts)
    store.dispatch_status(1, "RUNNING")
    moved = facts | {"base_sha": "d" * 40}
    state = store.accept_result(lambda: moved, result(config))
    assert state["reviews"][0]["status"] == "STALE"
    assert state["reviews"][0]["result"] == result(config)
    assert not pass_is_valid(moved, store.load(), config)
    assert store.request(lambda: moved)["generation"] == 2


@pytest.mark.parametrize("generation", [1, 2])
@pytest.mark.parametrize("base", ["missing", None, "", "main", "c" * 39, "C" * 40, True, [], {}])
def test_persisted_missing_or_malformed_base_fails_closed(store, facts, config, generation, base):
    store.request(lambda: facts)
    store.accept_result(lambda: facts, result(config))
    moved = new_head(facts)
    store.request(lambda: moved)
    store.accept_result(lambda: moved, result(config, 2, B))
    state = store.load()
    review = state["reviews"][generation - 1]
    if base == "missing":
        review.pop("requested_base_sha", None)
    else:
        review["requested_base_sha"] = base
    store.path.write_text(json.dumps(state), encoding="utf-8")
    old = store.path.read_bytes()
    assert evaluate_independent_review(moved, state, config)["decision"] == "INVALID"
    assert not pass_is_valid(moved, state, config)
    with pytest.raises(IndependentReviewError):
        store.load()
    with pytest.raises(IndependentReviewError):
        store.request(lambda: moved)
    assert store.path.read_bytes() == old


def test_store_failed_persist_returns_no_dispatch(store, facts, monkeypatch):
    old = store.path.read_bytes()

    def fail(*_args):
        raise OSError("simulated crash before replacement")

    monkeypatch.setattr("scripts.independent_review.os.replace", fail)
    with pytest.raises(OSError):
        store.request(lambda: facts)
    assert store.path.read_bytes() == old
    assert list((store.root / "temp" / "independent-review").iterdir()) == []


def test_missing_corrupt_history_not_reinitialized(store, facts):
    with pytest.raises(IndependentReviewError, match="state_already_exists"):
        store.initialize()
    store.path.write_text('{"schema_version": "1.0"}', encoding="utf-8")
    old = store.path.read_bytes()
    with pytest.raises(IndependentReviewError):
        store.request(lambda: facts)
    assert store.path.read_bytes() == old
    store.path.unlink()
    with pytest.raises(IndependentReviewError):
        store.request(lambda: facts)


def test_cli_read_only(store, facts, config, capsys, tmp_path):
    config_path, facts_path = tmp_path / "config.json", tmp_path / "facts.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    facts_path.write_text(json.dumps(facts), encoding="utf-8")
    args = ["PDFTR-49", "--config", str(config_path), "--state", str(store.path)]
    old = store.path.read_bytes()
    for _ in range(3):
        assert main(["evaluate", *args, "--facts", str(facts_path)]) == 0
        output = json.loads(capsys.readouterr().out)
        assert output["decision"] == "ELIGIBLE" and output["inspection_only"]
    assert main(["status", *args]) == 0
    assert json.loads(capsys.readouterr().out)["state"]["current_generation"] == 0
    assert store.path.read_bytes() == old
    with pytest.raises(SystemExit):
        main(["record-result", *args])


def test_json_duplicate_keys_reject(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"verdict":"PASS","verdict":"CHANGES_REQUIRED"}', encoding="utf-8")
    with pytest.raises(IndependentReviewError):
        read_json(path)


def test_cli_missing_default_inspection_only(config, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    path = Path("config.json")
    path.write_text(json.dumps(config), encoding="utf-8")
    assert main(["status", "PDFTR-49", "--config", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["state"]["reviews"] == []
    assert not Path(".agent-cycle").exists()
