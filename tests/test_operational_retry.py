"""Human-approved pre-review retry: deterministic local Git/adapter tests."""

import json
from pathlib import Path

import pytest
import scripts.agent_cycle as validator
import scripts.pi_ticket_cycle as runner
from scripts.agent_cycle import CycleError, cycle_directory, cycle_status
from scripts.pi_ticket_cycle import CommandResult, RunnerError, run_cycle

from tests import test_pi_ticket_cycle as cycle_tests
from tests.test_pi_cycle_resume import prepare
from tests.test_pi_ticket_cycle import TICKET, FakePi, _config, _git

# Existing repository-local fixture; no network, provider, or system temp files.
git_repo = cycle_tests.git_repo


def fail(repo: Path, fake: FakePi) -> Path:
    fake.implementer_exit = 1
    with pytest.raises(RunnerError, match="implementer exited with code 1"):
        run_cycle(repo, TICKET, executor=fake, config=_config())
    fake.implementer_exit = 0
    return cycle_directory(repo, TICKET)


def artifacts(directory: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}


def approve(repo: Path) -> dict[str, object]:
    return validator.retry_operational_cycle(repo, TICKET, "Limits reset; human retry approved")


def test_operational_retry_end_to_end(git_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakePi(git_repo)
    directory = fail(git_repo, fake)
    before = artifacts(directory)
    head = _git(git_repo, "rev-parse", "HEAD")
    status = cycle_status(git_repo, TICKET)
    assert status["operational_retry_eligible"]
    assert status["implementation_attempt"] == 1
    assert status["review_round"] == 0
    assert status["stop_class"] == "operational"
    assert status["stop_code"] == "implementer_process_failed"
    partial = directory / "implementer.json"
    partial.write_text('{"partial":', encoding="utf-8")
    outcome = run_cycle(
        git_repo,
        TICKET,
        executor=fake,
        config=_config(),
        recover_operational=True,
        reason="Limits reset; human retry approved",
    )
    assert outcome.passed and outcome.review_rounds == 1
    assert outcome.implementation_attempt == 2 and outcome.operational_retries == 1
    manifest = runner._read_manifest(git_repo, TICKET)
    assert manifest["operational_retries"] == [
        {
            "type": "operational_retry",
            "reason": "Limits reset; human retry approved",
            "previous_stop_code": "implementer_process_failed",
            "previous_stop_reason": "implementer exited with code 1",
            "head_sha": head,
            "branch": manifest["branch"],
            "review_round": 0,
            "implementation_attempt": 2,
        }
    ]
    assert (directory / "implementer-attempt-1.json").read_text() == '{"partial":'
    assert (directory / "pi-implementer-round-1.log").read_bytes() == before[
        "pi-implementer-round-1.log"
    ]
    assert (directory / "pi-implementer-round-2.log").exists()
    assert (
        (directory / "implementer-progress.log")
        .read_bytes()
        .startswith(before["implementer-progress.log"])
    )
    assert "operational retry started" in (directory / "implementer-progress.log").read_text()
    assert "Recovery type: operational implementer retry" in capsys.readouterr().out
    assert cycle_status(git_repo, TICKET)["implementation_attempt"] == 2
    assert (
        json.loads((directory / "implementation-2.json").read_text())["implementation_attempt"] == 2
    )


@pytest.mark.parametrize(
    "violation",
    [
        "dirty",
        "head",
        "branch",
        "active",
        "invalid_active",
        "invalid_attempt",
        "null_attempt",
        "malformed_handoff",
        "safety",
        "unknown",
        "code",
        "fingerprint",
        "ticket",
        "corrupt",
        "duplicate",
        "review_artifact",
        "implementation_artifact",
    ],
)
def test_rejected_retry_never_mutates(git_repo: Path, violation: str) -> None:
    fake = FakePi(git_repo)
    directory = fail(git_repo, fake)
    path = directory / "manifest.json"
    manifest = runner._read_manifest(git_repo, TICKET)
    if violation == "dirty":
        (git_repo / "tracked.txt").write_text("WIP")
    elif violation == "head":
        _git(git_repo, "commit", "--allow-empty", "-m", "outside cycle")
    elif violation == "branch":
        _git(git_repo, "switch", "-c", "unexpected-branch")
    elif violation == "active":
        manifest["active_agent"] = "implementer"
    elif violation == "invalid_active":
        manifest["active_agent"] = []
    elif violation == "invalid_attempt":
        manifest["implementation_attempt"] = True
    elif violation == "null_attempt":
        manifest["implementation_attempt"] = None
    elif violation == "malformed_handoff":
        (directory / "handoff.json").write_text("{}")
    elif violation in {"safety", "unknown"}:
        manifest["stop_class"] = violation
    elif violation == "code":
        manifest["stop_code"] = "unexpected_code"
    elif violation == "fingerprint":
        manifest["repository_fingerprint"] = "0" * 64
    elif violation == "ticket":
        manifest["ticket"] = "PDFTR-999"
    elif violation == "review_artifact":
        (directory / "review-1.json").write_text("{}")
    elif violation == "implementation_artifact":
        (directory / "implementation-1.json").write_text("{}")
    if violation == "corrupt":
        path.write_text("{")
    elif violation == "duplicate":
        path.write_text(
            path.read_text().replace('"review_round": 0', '"review_round": 0, "review_round": 0')
        )
    else:
        runner._write_json(path, manifest)
    before = artifacts(directory)
    with pytest.raises(CycleError):
        approve(git_repo)
    assert artifacts(directory) == before
    assert fake.implementer_runs == 1


def test_approval_idempotency_and_ready_for_review(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    directory = fail(git_repo, fake)
    manifest = approve(git_repo)
    assert manifest["state"] == "HUMAN_APPROVED_OPERATIONAL_RETRY"
    assert manifest["review_round"] == 0
    assert validator.implementation_attempt(manifest) == 2
    before = artifacts(directory)
    with pytest.raises(CycleError, match="requires STOPPED"):
        approve(git_repo)
    assert artifacts(directory) == before
    validator.begin_implementation(git_repo, TICKET)
    fake._implementer()
    result = validator.record_handoff(git_repo, TICKET, directory / "implementer.json")
    assert result["state"] == "READY_FOR_REVIEW" and result["review_round"] == 0
    assert not cycle_status(git_repo, TICKET)["operational_retry_eligible"]


@pytest.mark.parametrize("stage", ["before_launch", "between_atomic_writes"])
def test_approved_crash_resumes_same_attempt(
    git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    fake = FakePi(git_repo)
    directory = fail(git_repo, fake)
    if stage == "before_launch":

        def unavailable() -> None:
            raise RunnerError("simulated crash before child launch")

        with monkeypatch.context() as patch:
            patch.setattr(fake, "ensure_available", unavailable)
            with pytest.raises(RunnerError, match="simulated crash"):
                run_cycle(
                    git_repo,
                    TICKET,
                    executor=fake,
                    config=_config(),
                    recover_operational=True,
                    reason="operator approval",
                )
    else:
        write = validator._atomic_write_json

        def crash(path: Path, document: dict[str, object]) -> None:
            if path.name == "handoff.json":
                raise CycleError("simulated crash between writes")
            write(path, document)

        with monkeypatch.context() as patch:
            patch.setattr(validator, "_atomic_write_json", crash)
            with pytest.raises(CycleError, match="between writes"):
                approve(git_repo)
    assert fake.implementer_runs == 1
    assert cycle_status(git_repo, TICKET)["state"] == "HUMAN_APPROVED_OPERATIONAL_RETRY"
    outcome = run_cycle(git_repo, TICKET, executor=fake, config=_config())
    assert outcome.passed and outcome.implementation_attempt == 2
    assert len(runner._read_manifest(git_repo, TICKET)["operational_retries"]) == 1
    assert (directory / "pi-implementer-round-1.log").exists()


def test_retry_bound_never_spends_review_budget(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    directory = fail(git_repo, fake)
    fake.implementer_exit = 1
    for index in range(validator.MAX_OPERATIONAL_RETRIES):
        with pytest.raises(RunnerError, match="implementer exited"):
            run_cycle(
                git_repo,
                TICKET,
                executor=fake,
                config=_config(),
                recover_operational=True,
                reason=f"human approval {index + 1}",
            )
        manifest = runner._read_manifest(git_repo, TICKET)
        assert manifest["review_round"] == 0
        assert len(manifest["operational_retries"]) == index + 1
        assert validator.implementation_attempt(manifest) == index + 2
    assert manifest["stop_code"] == "operational_retry_limit"
    before = artifacts(directory)
    with pytest.raises(CycleError):
        approve(git_repo)
    assert before == artifacts(directory)
    assert len(list(directory.glob("pi-implementer-round-*.log"))) == 4
    assert fake.reviewer_runs == 0


@pytest.mark.parametrize("state", ["READY_FOR_REVIEW", "STOPPED"])
def test_review_flow_not_operational_retry(git_repo: Path, state: str) -> None:
    fake = FakePi(git_repo)
    prepare(git_repo, fake, state)
    before = artifacts(cycle_directory(git_repo, TICKET))
    with pytest.raises(CycleError):
        approve(git_repo)
    assert artifacts(cycle_directory(git_repo, TICKET)) == before
    if state == "READY_FOR_REVIEW":
        fake.verdicts = ["PASS"]
        assert run_cycle(git_repo, TICKET, executor=fake, config=_config()).passed
        assert not fake.invocations[0][1].startswith("You are the implementer")


@pytest.mark.parametrize("code", sorted(validator.OPERATIONAL_CODES) + ["uncertain"])
def test_trusted_adapter_classification(git_repo: Path, code: str) -> None:
    fake = FakePi(git_repo)
    fake._implementer = lambda: CommandResult(1, "usage limits exhausted", "", failure_code=code)
    with pytest.raises(RunnerError):
        run_cycle(git_repo, TICKET, executor=fake, config=_config())
    status = cycle_status(git_repo, TICKET)
    assert status["operational_retry_eligible"] == (code in validator.OPERATIONAL_CODES)


@pytest.mark.parametrize("error", [OSError("launch failed"), ValueError("uncertain failure")])
def test_runtime_failures_fail_closed_when_uncertain(git_repo: Path, error: Exception) -> None:
    fake = FakePi(git_repo)
    fake.run_raises = error
    with pytest.raises(RunnerError):
        run_cycle(git_repo, TICKET, executor=fake, config=_config())
    status = cycle_status(git_repo, TICKET)
    assert status["operational_retry_eligible"] == isinstance(error, OSError)


def test_termination_classification(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    fake.cancel_implementer = True
    with pytest.raises(RunnerError):
        run_cycle(git_repo, TICKET, executor=fake, config=_config())
    assert cycle_status(git_repo, TICKET)["stop_code"] == "implementer_terminated"


def test_status_and_legacy_pdftr44_shape(
    git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Same round-zero/unchanged HEAD/clean-tree failure as PDFTR-44, no text inference.
    fake = FakePi(git_repo)
    directory = fail(git_repo, fake)
    capsys.readouterr()
    assert validator.main(["status", TICKET], repo_root=git_repo) == 0
    output = capsys.readouterr().out
    for text in [
        "Implementation attempt: 1",
        "Operational retries: 0",
        "Review round: 0",
        "Stop class: operational",
        "Stop code: implementer_process_failed",
        "Operational retry eligible: yes",
        "Active agent: none",
        "Working tree: clean",
    ]:
        assert text in output
    (git_repo / "tracked.txt").write_text("WIP")
    validator.main(["status", TICKET], repo_root=git_repo)
    assert "Reason: working tree is dirty" in capsys.readouterr().out
    path = directory / "manifest.json"
    manifest = runner._read_manifest(git_repo, TICKET)
    for field in ("stop_class", "stop_code", "operational_retries"):
        manifest.pop(field)
    runner._write_json(path, manifest)
    assert cycle_status(git_repo, TICKET)["stop_class"] == "unknown"
    before = artifacts(directory)
    with pytest.raises(CycleError, match="not operational"):
        approve(git_repo)
    assert before == artifacts(directory)


@pytest.mark.parametrize("reason", [None, "", "\n", "x" * 201])
def test_operational_cli_requires_reason(git_repo: Path, reason: str | None) -> None:
    fake = FakePi(git_repo)
    directory = fail(git_repo, fake)
    before = artifacts(directory)
    with pytest.raises(RunnerError, match="reason"):
        run_cycle(
            git_repo,
            TICKET,
            executor=fake,
            config=_config(),
            recover_operational=True,
            reason=reason,
        )
    assert before == artifacts(directory)


def test_recovery_flags_are_exclusive(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    directory = fail(git_repo, fake)
    before = artifacts(directory)
    with pytest.raises(RunnerError, match="mutually exclusive"):
        run_cycle(
            git_repo,
            TICKET,
            executor=fake,
            config=_config(),
            recover=True,
            recover_operational=True,
            reason="approval",
        )
    assert before == artifacts(directory)
    args = runner._parser().parse_args([TICKET, "--recover-operational", "--reason", "approved"])
    assert args.recover_operational and not args.recover


def test_previous_implementation_report_preserved(git_repo: Path) -> None:
    report = git_repo / f".implementation-reports/implementation-report-{TICKET}.md"
    report.parent.mkdir()
    report.write_text("Previous failed attempt report\n", encoding="utf-8")
    _git(git_repo, "add", ".implementation-reports")
    _git(git_repo, "commit", "-m", "prior report")
    fake = FakePi(git_repo)
    directory = fail(git_repo, fake)
    run_cycle(
        git_repo,
        TICKET,
        executor=fake,
        config=_config(),
        recover_operational=True,
        reason="human approval",
    )
    assert (directory / "implementation-report-attempt-1.md").read_bytes() == report.read_bytes()


def test_review_recovery_after_operational_retry(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    fail(git_repo, fake)
    fake.verdicts = ["CHANGES_REQUIRED"]
    fake.findings = [[cycle_tests._finding("R1")]]
    outcome = run_cycle(
        git_repo,
        TICKET,
        executor=fake,
        config=_config(),
        recover_operational=True,
        reason="human approval",
    )
    assert outcome.state == "STOPPED" and outcome.review_rounds == 2
    assert len(runner._read_manifest(git_repo, TICKET)["operational_retries"]) == 1
    fake.verdicts = ["PASS"]
    outcome = run_cycle(
        git_repo,
        TICKET,
        executor=fake,
        config=_config(),
        recover=True,
        reason="human review rework approval",
    )
    assert outcome.passed and outcome.review_rounds == 3
    assert outcome.implementation_attempt == 4


@pytest.mark.parametrize("boundary", ["symlink", "junction"])
def test_filesystem_boundary_rejects_without_mutation(
    git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    fake = FakePi(git_repo)
    directory = fail(git_repo, fake)
    before = artifacts(directory)
    method = "is_symlink" if boundary == "symlink" else "is_junction"
    original = getattr(Path, method)

    def redirected(path: Path) -> bool:
        return path == directory / "manifest.json" or original(path)

    monkeypatch.setattr(Path, method, redirected)
    with pytest.raises(CycleError, match="symbolic links"):
        approve(git_repo)
    assert before == artifacts(directory)


def test_legacy_review_recovery_uses_review_evidence(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    prepare(git_repo, fake, "STOPPED")
    manifest = runner._read_manifest(git_repo, TICKET)
    for field in ("stop_class", "stop_code", "operational_retries"):
        manifest.pop(field)
    # Free text cannot control review recovery decisions.
    manifest["stop_reason"] = "arbitrary old text"
    runner._write_json(cycle_directory(git_repo, TICKET) / "manifest.json", manifest)
    validator.reopen_cycle(git_repo, TICKET, "human approval")
    fake.verdicts = ["PASS"]
    assert run_cycle(git_repo, TICKET, executor=fake, config=_config()).passed
