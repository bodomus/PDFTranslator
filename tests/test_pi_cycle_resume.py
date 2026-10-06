"""Deterministic resume and human-approved recovery integration tests."""

import json
from pathlib import Path

import pytest
import scripts.pi_ticket_cycle as runner
from scripts.agent_cycle import CycleError, cycle_directory, reopen_cycle
from scripts.agent_cycle import main as validator_main
from scripts.pi_ticket_cycle import RunnerError, extract_review_json, run_cycle

from tests import test_pi_ticket_cycle as cycle_tests
from tests.test_pi_ticket_cycle import TICKET, FakePi, _config, _finding, _git, _state

# Reuse the repository-local isolated Git fixture.
git_repo = cycle_tests.git_repo


def prepare(repo: Path, fake: FakePi, state: str) -> None:
    runner.initialize_cycle(repo, TICKET)
    if state == "NEW":
        return
    for attempt in (1, 2):
        runner.begin_implementation(repo, TICKET)
        fake._implementer()
        runner.record_handoff(repo, TICKET, runner._handoff_path(cycle_directory(repo, TICKET)))
        if state == ("READY_FOR_REVIEW" if attempt == 1 else "READY_FOR_REVIEW_2"):
            return
        runner.begin_review(repo, TICKET, _git(repo, "rev-parse", "HEAD"))
        fake.verdicts = [
            state if state == "BLOCKED" else "PASS" if state == "PASSED" else "CHANGES_REQUIRED"
        ]
        fake.findings = [[_finding("R1")]]
        document = extract_review_json(fake._reviewer().stdout)
        path = cycle_directory(repo, TICKET) / "seed-review.json"
        runner._write_json(path, document)
        runner.record_review(repo, TICKET, path)
        if _state(repo) == state:
            return
    assert _state(repo) == state


@pytest.mark.parametrize(
    ("state", "implementations"),
    [("NEW", 1), ("READY_FOR_REVIEW", 0), ("CHANGES_REQUIRED", 1), ("READY_FOR_REVIEW_2", 0)],
)
def test_resume_dispatch(git_repo: Path, state: str, implementations: int) -> None:
    fake = FakePi(git_repo)
    prepare(git_repo, fake, state)
    journals = {
        role: cycle_directory(git_repo, TICKET) / f"{role}-progress.log"
        for role in ("implementer", "reviewer")
    }
    for path in journals.values():
        path.write_text("[12:00] Previous execution\n", encoding="utf-8")
    before_impl, before_review = fake.implementer_runs, fake.reviewer_runs
    fake.verdicts = ["PASS"]
    outcome = run_cycle(git_repo, TICKET, executor=fake, config=_config())
    assert outcome.passed
    assert fake.implementer_runs - before_impl == implementations
    assert fake.reviewer_runs - before_review == 1
    for role, path in journals.items():
        text = path.read_text(encoding="utf-8")
        assert text.startswith("[12:00] Previous execution\n")
        if role == "reviewer" or implementations:
            assert f"Resumed {role} execution" in text
        else:
            assert text == "[12:00] Previous execution\n"
    if state == "CHANGES_REQUIRED":
        assert '"id": "R1"' in fake.invocations[0][1]
        assert "attempt 2" in fake.invocations[0][1]


@pytest.mark.parametrize("state", ["PASSED", "BLOCKED", "STOPPED"])
def test_terminal_resume_never_launches_children(git_repo: Path, state: str) -> None:
    fake = FakePi(git_repo)
    prepare(git_repo, fake, state)
    directory = cycle_directory(git_repo, TICKET)
    before = {p.name: p.read_bytes() for p in directory.glob("*.json")}
    if state == "PASSED":
        assert run_cycle(git_repo, TICKET, executor=fake, config=_config()).passed
    else:
        with pytest.raises(RunnerError, match=f"cycle is {state}") as error:
            run_cycle(git_repo, TICKET, executor=fake, config=_config())
        for label in ("current HEAD", "manifest HEAD", "review round", "human-approved"):
            assert label in str(error.value)
    assert not fake.invocations
    assert before == {p.name: p.read_bytes() for p in directory.glob("*.json")}


def test_human_recovery_preserves_history_and_exact_sha(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    prepare(git_repo, fake, "STOPPED")
    directory = cycle_directory(git_repo, TICKET)
    before = {p.name: p.read_bytes() for p in directory.glob("review-*.json")}
    attempts = {p.name: p.read_bytes() for p in directory.glob("implementation-*.json")}
    journals = [directory / f"{role}-progress.log" for role in ("implementer", "reviewer")]
    for path in journals:
        path.write_text("[12:00] Interrupted history\n", encoding="utf-8")
    old_sha = _git(git_repo, "rev-parse", "HEAD")
    fake.verdicts = ["PASS"]
    outcome = run_cycle(
        git_repo,
        TICKET,
        executor=fake,
        config=_config(),
        recover=True,
        reason="human-approved follow-up for R1",
    )
    assert outcome.passed and outcome.review_rounds == 3
    assert outcome.implementation_sha != old_sha
    for path in journals:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("[12:00] Interrupted history\n")
        assert "attempt/round 3" in text
    for name, content in (before | attempts).items():
        assert (directory / name).read_bytes() == content
    approval = runner._read_manifest(git_repo, TICKET)["human_recoveries"][0]
    assert approval["reason"] == "human-approved follow-up for R1"
    assert approval["stop_reason"] == "repeated_finding"
    assert approval["reviewed_sha"] == old_sha
    assert approval["implementation_attempt"] == 3
    assert approval["previous_handoff"]["implementer"]["implementation_attempt"] == 2
    review = json.loads((directory / "review-3.json").read_text())
    assert review["reviewed_sha"] == outcome.implementation_sha
    assert len(fake.invocations) == 2
    assert "bash" not in fake.commands[1]


@pytest.mark.parametrize("violation", ["dirty", "branch", "head", "no_sha", "wrong_review_sha"])
def test_recovery_safety_guards(git_repo: Path, violation: str) -> None:
    fake = FakePi(git_repo)
    prepare(git_repo, fake, "STOPPED")
    directory = cycle_directory(git_repo, TICKET)
    old_sha = _git(git_repo, "rev-parse", "HEAD")
    before = {p.name: p.read_bytes() for p in directory.glob("review-*.json")}
    if violation == "dirty":
        (git_repo / "tracked.txt").write_text("dirty")
    elif violation == "branch":
        _git(git_repo, "switch", "-c", "wrong-branch")
    elif violation == "head":
        _git(git_repo, "commit", "--allow-empty", "-m", "outside implementation")
    elif violation == "no_sha":
        fake.no_new_commit_on_attempt = 3
    else:
        fake.reviewer_payload_overrides[2] = {"reviewed_sha": old_sha}
    fake.verdicts = ["PASS"]
    with pytest.raises(RunnerError):
        run_cycle(
            git_repo, TICKET, executor=fake, config=_config(), recover=True, reason="human approval"
        )
    for name, content in before.items():
        assert (directory / name).read_bytes() == content
    assert not (directory / "review-3.json").exists()


@pytest.mark.parametrize(("recover", "reason"), [(True, None), (False, "approval"), (True, "")])
def test_recovery_requires_explicit_action_and_reason(
    git_repo: Path, recover: bool, reason: str | None
) -> None:
    fake = FakePi(git_repo)
    prepare(git_repo, fake, "STOPPED")
    with pytest.raises(RunnerError, match="reason"):
        run_cycle(git_repo, TICKET, executor=fake, config=_config(), recover=recover, reason=reason)
    assert not fake.invocations


def test_separate_human_approval_then_normal_resume(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    prepare(git_repo, fake, "STOPPED")
    assert (
        validator_main(["reopen", TICKET, "--reason", "operator approval"], repo_root=git_repo) == 0
    )
    assert _state(git_repo) == "HUMAN_APPROVED_REWORK"
    fake.verdicts = ["PASS"]
    assert run_cycle(git_repo, TICKET, executor=fake, config=_config()).passed


@pytest.mark.parametrize("state", ["NEW", "PASSED", "BLOCKED", "CHANGES_REQUIRED"])
def test_recovery_rejects_ineligible_states(git_repo: Path, state: str) -> None:
    fake = FakePi(git_repo)
    prepare(git_repo, fake, state)
    with pytest.raises(CycleError, match="exhausted"):
        reopen_cycle(git_repo, TICKET, "human approval")
    assert _state(git_repo) == state


def test_recovery_round_limit_and_schema_fail_closed(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    prepare(git_repo, fake, "READY_FOR_REVIEW_2")
    fake.findings = [[_finding("R2")]]
    outcome = run_cycle(git_repo, TICKET, executor=fake, config=_config())
    assert outcome.stop_reason == "review_round_limit"
    reopen_cycle(git_repo, TICKET, "operator approval")
    path = cycle_directory(git_repo, TICKET) / "manifest.json"
    manifest = runner._read_manifest(git_repo, TICKET)
    manifest["human_recoveries"][0]["unexpected"] = True
    runner._write_json(path, manifest)
    with pytest.raises(CycleError, match="unknown"):
        runner.cycle_status(git_repo, TICKET)


@pytest.mark.parametrize("role", ["IMPLEMENTING", "REVIEWING"])
def test_active_phases_require_manual_inspection(git_repo: Path, role: str) -> None:
    fake = FakePi(git_repo)
    prepare(git_repo, fake, "NEW" if role == "IMPLEMENTING" else "READY_FOR_REVIEW")
    if role == "IMPLEMENTING":
        runner.begin_implementation(git_repo, TICKET)
    else:
        runner.begin_review(git_repo, TICKET, _git(git_repo, "rev-parse", "HEAD"))
    with pytest.raises(RunnerError, match=role):
        run_cycle(git_repo, TICKET, executor=fake, config=_config())
    assert not fake.invocations
    assert _state(git_repo) == role


def test_recovery_never_adds_automatic_retries(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    prepare(git_repo, fake, "STOPPED")
    outcome = run_cycle(
        git_repo, TICKET, executor=fake, config=_config(), recover=True, reason="human approval"
    )
    assert outcome.state == "STOPPED" and outcome.review_rounds == 3
    assert outcome.stop_reason == "repeated_finding"
    assert len(fake.invocations) == 2
    with pytest.raises(RunnerError, match="STOPPED"):
        run_cycle(git_repo, TICKET, executor=fake, config=_config())
    fake.verdicts = ["PASS"]
    outcome = run_cycle(
        git_repo,
        TICKET,
        executor=fake,
        config=_config(),
        recover=True,
        reason="second human approval",
    )
    assert outcome.passed and outcome.review_rounds == 4
    assert len(runner._read_manifest(git_repo, TICKET)["human_recoveries"]) == 2
