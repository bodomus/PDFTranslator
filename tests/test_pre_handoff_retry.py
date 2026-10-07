"""Explicit operator recovery with positive process-exit evidence, no providers."""

from pathlib import Path

import pytest
import scripts.agent_cycle as validator
import scripts.pi_ticket_cycle as runner
from scripts.pi_ticket_cycle import CommandResult, RunnerError, run_cycle

from tests import test_pi_ticket_cycle as cycle_tests
from tests.test_operational_retry import artifacts
from tests.test_pi_ticket_cycle import TICKET, FakePi, _config, _git

git_repo = cycle_tests.git_repo


def clean_stop(repo: Path, fake: FakePi, monkeypatch: pytest.MonkeyPatch) -> Path:
    def no_handoff() -> CommandResult:
        fake.implementer_runs += 1
        return CommandResult(0, "clarification requested", "")

    with monkeypatch.context() as patch:
        patch.setattr(fake, "_implementer", no_handoff)
        with pytest.raises(RunnerError, match="implementer did not produce"):
            run_cycle(repo, TICKET, executor=fake, config=_config())
    return validator.cycle_directory(repo, TICKET)


def approve(repo: Path) -> dict:
    return validator.retry_pre_handoff_cycle(repo, TICKET)


def test_clean_unknown_retry_preserves_evidence(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakePi(git_repo)
    directory = clean_stop(git_repo, fake, monkeypatch)
    (directory / "implementer.json").write_bytes(b'{"invalid":')
    before = artifacts(directory)
    assert validator.cycle_status(git_repo, TICKET)["pre_handoff_retry_eligible"]
    manifest = approve(git_repo)
    assert manifest["implementation_attempt"] == 2
    assert manifest["review_round"] == 0 and fake.reviewer_runs == 0
    approval = manifest["pre_handoff_retries"][0]
    assert approval["approved_by"] == "human" and approval["retry_kind"] == "pre_handoff"
    assert approval["previous_stop_class"] == "unknown"
    archive = directory / "attempts" / "1"
    assert artifacts(archive) == before
    assert run_cycle(git_repo, TICKET, executor=fake, config=_config()).passed
    assert fake.implementer_runs == 2 and fake.reviewer_runs == 1
    assert artifacts(archive) == before
    assert (directory / "implementer-attempt-1.json").read_bytes() == b'{"invalid":'
    assert (directory / "pi-implementer-round-1.log").read_bytes() == before[
        "pi-implementer-round-1.log"
    ]
    assert validator.cycle_status(git_repo, TICKET)["implementation_attempt"] == 2
    with pytest.raises(validator.CycleError, match="retry_not_stopped"):
        approve(git_repo)


@pytest.mark.parametrize(
    "violation",
    [
        "dirty",
        "head",
        "branch",
        "identity",
        "active",
        "review",
        "accepted",
        "candidate",
        "marker_missing",
        "marker_launching",
        "round",
        "uncertain",
        "pending",
        "tracking_corrupt",
        "attempt",
        "safety",
        "review_stdout",
        "review_log",
        "review_progress",
    ],
)
def test_rejection_preserves_state(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, violation: str
) -> None:
    fake = FakePi(git_repo)
    directory = clean_stop(git_repo, fake, monkeypatch)
    manifest = runner._read_manifest(git_repo, TICKET)
    marker = directory / "implementer-launch-attempt-1.json"
    if violation == "dirty":
        (git_repo / "untracked.txt").write_text("WIP")
    elif violation == "head":
        _git(git_repo, "commit", "--allow-empty", "-m", "changed HEAD")
    elif violation == "branch":
        _git(git_repo, "switch", "-c", "foreign")
    elif violation == "identity":
        manifest["repository_fingerprint"] = "0" * 64
    elif violation == "active":
        manifest["active_agent"] = "implementer"
    elif violation == "review":
        (directory / "review-1.json").write_text("{}")
    elif violation == "review_stdout":
        (directory / "reviewer-stdout-round-1.txt").write_text("evidence")
    elif violation == "review_log":
        (directory / "pi-reviewer-round-1.log").write_text("evidence")
    elif violation == "review_progress":
        (directory / "reviewer-progress.log").write_text("evidence")
    elif violation == "accepted":
        (directory / "implementation-1.json").write_text("{}")
    elif violation == "candidate":
        (directory / "handoff.json").write_text("{}")
    elif violation == "marker_missing":
        marker.unlink()
    elif violation == "marker_launching":
        runner._write_json(marker, validator.implementer_launch_record(manifest, "launching"))
    elif violation == "round":
        manifest["review_round"] = 1
    elif violation in {"uncertain", "pending"}:
        runner._write_json(
            directory / "youtrack.json",
            {
                "ticket": TICKET,
                "operations": {"0" * 64: {"status": violation, "conflicting_write": False}},
            },
        )
    elif violation == "tracking_corrupt":
        (directory / "youtrack.json").write_text("{")
    elif violation == "attempt":
        manifest["implementation_attempt"] = 2
    elif violation == "safety":
        manifest["stop_class"] = "safety"
    runner._write_json(directory / "manifest.json", manifest)
    before = artifacts(directory)
    with pytest.raises(validator.CycleError):
        approve(git_repo)
    assert artifacts(directory) == before
    assert not (directory / "attempts").exists()
    assert fake.implementer_runs == 1 and fake.reviewer_runs == 0


def test_stop_text_cannot_authorize_and_exited_proof_is_required(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakePi(git_repo)
    directory = clean_stop(git_repo, fake, monkeypatch)
    validator.stop_cycle(git_repo, TICKET, "unrelated unknown operator prose")
    assert validator.cycle_status(git_repo, TICKET)["pre_handoff_retry_eligible"]
    (directory / "implementer-launch-attempt-1.json").unlink()
    validator.stop_cycle(git_repo, TICKET, "implementer did not produce implementer.json")
    with pytest.raises(validator.CycleError, match="retry_process_outcome_unproven"):
        approve(git_repo)


@pytest.mark.parametrize(
    "reason", ["clean clarification before handoff", "implementer process failed"]
)
def test_operational_stop_requires_budgeted_retry(git_repo: Path, reason: str) -> None:
    from tests.test_operational_retry import fail

    fake = FakePi(git_repo)
    directory = fail(git_repo, fake)
    validator.stop_cycle(
        git_repo,
        TICKET,
        reason,
        stop_class=validator.StopClass.OPERATIONAL,
        stop_code="implementer_process_failed",
    )
    before = artifacts(directory)
    with pytest.raises(validator.CycleError, match="retry_stop_class_ineligible"):
        approve(git_repo)
    assert artifacts(directory) == before
    status = validator.cycle_status(git_repo, TICKET)
    assert status["stop_class"] == "operational"
    assert status["stop_code"] == "implementer_process_failed"
    assert not status["pre_handoff_retry_eligible"]
    assert status["operational_retry_eligible"]

    approved = validator.retry_operational_cycle(git_repo, TICKET, "human operational approval")
    assert approved["state"] == "HUMAN_APPROVED_OPERATIONAL_RETRY"
    assert len(approved["operational_retries"]) == 1
    assert not approved.get("pre_handoff_retries")
    assert approved["review_round"] == 0
    assert fake.implementer_runs == 1 and fake.reviewer_runs == 0


def test_alternating_retry_commands_cannot_bypass_operational_budget(git_repo: Path) -> None:
    from tests.test_operational_retry import fail

    fake = FakePi(git_repo)
    for index in range(validator.MAX_OPERATIONAL_RETRIES):
        directory = fail(git_repo, fake)
        before = artifacts(directory)
        with pytest.raises(validator.CycleError, match="retry_stop_class_ineligible"):
            approve(git_repo)
        assert artifacts(directory) == before
        approved = validator.retry_operational_cycle(git_repo, TICKET, "human operational approval")
        assert len(approved["operational_retries"]) == index + 1
        assert not approved.get("pre_handoff_retries")

    directory = fail(git_repo, fake)
    stopped = runner._read_manifest(git_repo, TICKET)
    assert stopped["stop_code"] == "operational_retry_limit"
    assert len(stopped["operational_retries"]) == validator.MAX_OPERATIONAL_RETRIES
    before = artifacts(directory)
    with pytest.raises(validator.CycleError, match="retry_operational_limit"):
        approve(git_repo)
    with pytest.raises(validator.CycleError, match="operational_retry_limit"):
        validator.retry_operational_cycle(git_repo, TICKET, "human operational approval")
    assert artifacts(directory) == before
    assert not stopped.get("pre_handoff_retries")
    assert stopped["review_round"] == 0 and fake.reviewer_runs == 0
    assert fake.implementer_runs == validator.MAX_OPERATIONAL_RETRIES + 1


@pytest.mark.parametrize("stage", ["approval", "prepared", "begin_projection", "launching"])
def test_crash_restart_same_attempt(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    fake = FakePi(git_repo)
    directory = clean_stop(git_repo, fake, monkeypatch)
    write = validator._atomic_write_json
    if stage == "approval":

        def crash(path: Path, document: dict) -> None:
            if path.name == "handoff.json":
                raise validator.CycleError("simulated approval crash")
            write(path, document)

        with monkeypatch.context() as patch:
            patch.setattr(validator, "_atomic_write_json", crash)
            with pytest.raises(validator.CycleError, match="simulated"):
                approve(git_repo)
    else:
        approve(git_repo)

        def crash_launch(path: Path, document: dict) -> None:
            write(path, document)
            if document.get("phase") == stage:
                raise SystemExit("simulated process crash")

        def crash_begin(path: Path, document: dict) -> None:
            if path.name == "handoff.json" and document["system"]["state"] == "IMPLEMENTING":
                raise SystemExit("simulated process crash")
            write(path, document)

        with monkeypatch.context() as patch:
            if stage == "begin_projection":
                patch.setattr(validator, "_atomic_write_json", crash_begin)
            else:
                patch.setattr(runner, "_atomic_write_json", crash_launch)
            with pytest.raises(SystemExit, match="simulated process crash"):
                run_cycle(git_repo, TICKET, executor=fake, config=_config())
    assert len(runner._read_manifest(git_repo, TICKET)["pre_handoff_retries"]) == 1
    with pytest.raises(validator.CycleError):
        approve(git_repo)
    if stage == "launching":
        with pytest.raises(RunnerError):
            run_cycle(git_repo, TICKET, executor=fake, config=_config())
        assert fake.implementer_runs == 1
    else:
        assert run_cycle(git_repo, TICKET, executor=fake, config=_config()).passed
        assert fake.implementer_runs == 2
    assert (directory / "attempts" / "1" / "manifest.json").exists()


def test_crash_after_dispatch_never_relaunches(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakePi(git_repo)
    directory = clean_stop(git_repo, fake, monkeypatch)
    approve(git_repo)
    execute = runner._execute_child

    def crash(*args, **kwargs):
        execute(*args, **kwargs)
        raise SystemExit("crashed after dispatch")

    with monkeypatch.context() as patch:
        patch.setattr(runner, "_execute_child", crash)
        with pytest.raises(SystemExit, match="crashed after dispatch"):
            run_cycle(git_repo, TICKET, executor=fake, config=_config())
    assert fake.implementer_runs == 2 and fake.reviewer_runs == 0
    before = artifacts(directory)
    with pytest.raises(RunnerError):
        run_cycle(git_repo, TICKET, executor=fake, config=_config())
    assert artifacts(directory) == before
    assert fake.implementer_runs == 2 and fake.reviewer_runs == 0


def test_history_and_dispatch_fence(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakePi(git_repo)
    directory = clean_stop(git_repo, fake, monkeypatch)
    approve(git_repo)
    tracking = directory / "youtrack.json"
    runner._write_json(
        tracking,
        {
            "ticket": TICKET,
            "operations": {"0" * 64: {"status": "uncertain", "conflicting_write": False}},
        },
    )
    with pytest.raises(RunnerError, match="retry_remote_mutation_uncertain"):
        run_cycle(git_repo, TICKET, executor=fake, config=_config())
    assert fake.implementer_runs == 1
    (directory / "attempts" / "1" / "manifest.json").write_text("{}")
    with pytest.raises(validator.CycleError, match="metadata_inconsistent"):
        validator.cycle_status(git_repo, TICKET)


@pytest.mark.parametrize("first", ["operational", "pre_handoff"])
def test_mixed_retry_attempt_continuity(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, first: str
) -> None:
    from tests.test_operational_retry import fail

    fake = FakePi(git_repo)
    if first == "operational":
        fail(git_repo, fake)
        validator.retry_operational_cycle(git_repo, TICKET, "operator operational approval")
        clean_stop(git_repo, fake, monkeypatch)
        approve(git_repo)
    else:
        clean_stop(git_repo, fake, monkeypatch)
        approve(git_repo)
        fail(git_repo, fake)
        validator.retry_operational_cycle(git_repo, TICKET, "operator operational approval")
    assert validator.implementation_attempt(runner._read_manifest(git_repo, TICKET)) == 3
    outcome = run_cycle(git_repo, TICKET, executor=fake, config=_config())
    assert outcome.passed and outcome.implementation_attempt == 3
    assert fake.implementer_runs == 3 and fake.reviewer_runs == 1


def test_definite_tracking_success_not_dispatched_again(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.project_tracking import ProjectTracking

    mutations = []

    class Tracking:
        def __init__(self, root, ticket, text, warn):
            self.adapter = ProjectTracking(root, ticket, text, config={}, warn=warn)
            self.data = self.adapter.data

        def call(self, action, *args):
            if action == "bootstrap":
                manifest = args[0]
                self.adapter.operation(
                    "system",
                    "create",
                    manifest["current_head_sha"],
                    0,
                    lambda: mutations.append("create"),
                    prepare=lambda: True,
                )

    monkeypatch.setattr(runner, "TrackingHooks", Tracking)
    fake = FakePi(git_repo)
    clean_stop(git_repo, fake, monkeypatch)
    assert mutations == ["create"]
    approve(git_repo)
    assert run_cycle(git_repo, TICKET, executor=fake, config=_config()).passed
    assert mutations == ["create"]


@pytest.mark.parametrize(
    "field", ["missing_archive", "attempt_gap", "boolean", "bad_approval", "contradictory_state"]
)
def test_malformed_retry_history_fails_closed(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    fake = FakePi(git_repo)
    directory = clean_stop(git_repo, fake, monkeypatch)
    manifest = approve(git_repo)
    if field == "missing_archive":
        (directory / "attempts" / "1" / "manifest.json").unlink()
    elif field == "attempt_gap":
        manifest["pre_handoff_retries"][0]["implementation_attempt"] = 3
    elif field == "boolean":
        manifest["pre_handoff_retries"][0]["previous_attempt_id"] = True
    elif field == "bad_approval":
        manifest["pre_handoff_retries"][0]["approved_by"] = "implementer"
    else:
        manifest["state"] = "HUMAN_APPROVED_OPERATIONAL_RETRY"
    runner._write_json(directory / "manifest.json", manifest)
    before = artifacts(directory)
    with pytest.raises(validator.CycleError):
        run_cycle(git_repo, TICKET, executor=fake, config=_config())
    assert artifacts(directory) == before and fake.implementer_runs == 1


def test_operator_lock_and_cli(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakePi(git_repo)
    clean_stop(git_repo, fake, monkeypatch)
    with (
        runner._runner_ownership(git_repo, TICKET),
        pytest.raises(validator.CycleError, match="retry_agent_still_active"),
    ):
        approve(git_repo)
    assert validator.main(["retry-pre-handoff", TICKET], repo_root=git_repo) == 0
    assert validator.main(["retry-pre-handoff", TICKET], repo_root=git_repo) == 2
    assert fake.implementer_runs == 1
