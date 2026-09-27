from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from scripts.agent_cycle import (
    CycleError,
    begin_implementation,
    begin_review,
    cycle_directory,
    cycle_status,
    initialize_cycle,
    main,
    record_handoff,
    record_review,
    validate_ticket_id,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BASE_BRANCH = "master"
TASK_BRANCH = "agent/PDFTR-33-test"
TICKET = "PDFTR-33"


def _git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


@pytest.fixture
def git_repo() -> Iterator[Path]:
    root = REPOSITORY_ROOT / "temp" / "agent-cycle-tests" / str(uuid4())
    root.mkdir(parents=True)
    try:
        _git(root, "init", "-b", BASE_BRANCH)
        _git(root, "config", "user.name", "Agent Cycle Tests")
        _git(root, "config", "user.email", "agent-cycle@example.invalid")
        (root / ".gitignore").write_text("/.agent-cycle/\n", encoding="utf-8")
        (root / "tracked.txt").write_text("initial\n", encoding="utf-8")
        _git(root, "add", ".gitignore", "tracked.txt")
        _git(root, "commit", "-m", "initial")
        _git(root, "switch", "-c", TASK_BRANCH)
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _write_json(path: Path, document: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _implementer_input(repo: Path, attempt: int) -> Path:
    return _write_json(
        cycle_directory(repo, TICKET) / f"implementer-{attempt}.json",
        {
            "schema_version": "1.0",
            "ticket": TICKET,
            "implementation_attempt": attempt,
            "status": "COMPLETE",
            "implementation_report": (".implementation-reports/implementation-report-PDFTR-33.md"),
            "focused_tests": "PASS",
            "full_tests": "PASS",
            "check_ps1": "PASS",
            "known_limitations": [],
            "notes": [],
        },
    )


def _finding(identifier: str = "R1") -> dict[str, str]:
    return {
        "id": identifier,
        "severity": "HIGH",
        "file": "scripts/agent_cycle.py",
        "symbol": "record_review",
        "problem": "Concrete defect",
        "required_fix": "Correct the defect",
        "regression_test": "Add a deterministic test",
    }


def _review_input(
    repo: Path,
    *,
    review_round: int,
    sha: str,
    verdict: str,
    findings: list[dict[str, str]] | None = None,
    blocked_reason: str | None = None,
) -> Path:
    return _write_json(
        cycle_directory(repo, TICKET) / f"reviewer-input-{review_round}.json",
        {
            "schema_version": "1.0",
            "ticket": TICKET,
            "review_round": review_round,
            "reviewed_sha": sha,
            "verdict": verdict,
            "findings": findings or [],
            "blocked_reason": blocked_reason,
        },
    )


def _commit_attempt(repo: Path, attempt: int) -> str:
    (repo / "tracked.txt").write_text(f"attempt {attempt}\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", f"attempt {attempt}")
    return _git(repo, "rev-parse", "HEAD")


def _ready_for_review(repo: Path, attempt: int = 1) -> str:
    begin_implementation(repo, TICKET)
    sha = _commit_attempt(repo, attempt)
    record_handoff(repo, TICKET, _implementer_input(repo, attempt))
    return sha


@pytest.mark.parametrize("ticket", ("PDFTR-33", "ABC-123"))
def test_ticket_id_accepts_conservative_form(ticket: str) -> None:
    assert validate_ticket_id(ticket) == ticket


@pytest.mark.parametrize(
    "ticket",
    ("../PDFTR-33", "PDFTR/33", "PDFTR\\33", ".", "..", "", "C:\\PDFTR-33", "ABC-0"),
)
def test_ticket_id_rejects_path_unsafe_values(ticket: str) -> None:
    with pytest.raises(CycleError, match="invalid ticket ID"):
        validate_ticket_id(ticket)


def test_initialization_records_derived_git_facts_and_three_sections(git_repo: Path) -> None:
    manifest = initialize_cycle(git_repo, TICKET)
    directory = cycle_directory(git_repo, TICKET)
    handoff = json.loads((directory / "handoff.json").read_text(encoding="utf-8"))

    assert directory.is_dir()
    assert manifest["branch"] == TASK_BRANCH
    assert manifest["base_sha"] == _git(git_repo, "merge-base", BASE_BRANCH, "HEAD")
    assert manifest["current_head_sha"] == _git(git_repo, "rev-parse", "HEAD")
    assert manifest["review_round"] == 0
    assert manifest["active_agent"] is None
    assert manifest["working_tree_clean"] is True
    assert set(handoff) == {"schema_version", "system", "implementer", "reviewer"}
    assert handoff["system"]["ticket"] == TICKET
    assert handoff["implementer"] is None
    assert handoff["reviewer"] is None


def test_legacy_product_named_handoff_sections_are_rejected(git_repo: Path) -> None:
    initialize_cycle(git_repo, TICKET)
    handoff_path = cycle_directory(git_repo, TICKET) / "handoff.json"
    current = json.loads(handoff_path.read_text(encoding="utf-8"))
    _write_json(
        handoff_path,
        {
            "schema_version": "1.0",
            "shared": current["system"],
            "deepseek": None,
            "codex": None,
        },
    )

    with pytest.raises(CycleError, match="invalid handoff fields"):
        cycle_status(git_repo, TICKET)


@pytest.mark.parametrize("legacy_name", ("deepseek", "codex"))
def test_legacy_product_named_active_agents_are_rejected(git_repo: Path, legacy_name: str) -> None:
    initialize_cycle(git_repo, TICKET)
    manifest_path = cycle_directory(git_repo, TICKET) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["active_agent"] = legacy_name
    _write_json(manifest_path, manifest)

    with pytest.raises(CycleError, match="invalid active_agent"):
        cycle_status(git_repo, TICKET)


def test_dirty_tree_rejects_handoff_without_advancing_state(git_repo: Path) -> None:
    initialize_cycle(git_repo, TICKET)
    begin_implementation(git_repo, TICKET)
    (git_repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(CycleError, match="clean working tree"):
        record_handoff(git_repo, TICKET, _implementer_input(git_repo, 1))

    manifest = json.loads(
        (cycle_directory(git_repo, TICKET) / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["state"] == "IMPLEMENTING"
    assert manifest["active_agent"] == "implementer"


def test_sha_binding_rejects_review_for_another_commit(git_repo: Path) -> None:
    initialize_cycle(git_repo, TICKET)
    sha = _ready_for_review(git_repo)
    begin_review(git_repo, TICKET, sha)
    wrong_sha = "a" * 40 if sha != "a" * 40 else "b" * 40

    with pytest.raises(CycleError, match="reviewed_sha"):
        record_review(
            git_repo,
            TICKET,
            _review_input(
                git_repo,
                review_round=1,
                sha=wrong_sha,
                verdict="CHANGES_REQUIRED",
                findings=[_finding()],
            ),
        )


def test_new_commit_invalidates_prior_pass(git_repo: Path) -> None:
    initialize_cycle(git_repo, TICKET)
    sha = _ready_for_review(git_repo)
    begin_review(git_repo, TICKET, sha)
    record_review(
        git_repo,
        TICKET,
        _review_input(git_repo, review_round=1, sha=sha, verdict="PASS"),
    )
    _commit_attempt(git_repo, 2)

    status = cycle_status(git_repo, TICKET)

    assert status["review_valid_for_head"] is False
    assert "Git HEAD differs" in status["errors"][0]


def test_two_changes_required_reviews_stop_and_third_round_cannot_start(
    git_repo: Path,
) -> None:
    initialize_cycle(git_repo, TICKET)
    sha_1 = _ready_for_review(git_repo, 1)
    begin_review(git_repo, TICKET, sha_1)
    record_review(
        git_repo,
        TICKET,
        _review_input(
            git_repo,
            review_round=1,
            sha=sha_1,
            verdict="CHANGES_REQUIRED",
            findings=[_finding("R1")],
        ),
    )
    sha_2 = _ready_for_review(git_repo, 2)
    begin_review(git_repo, TICKET, sha_2)
    manifest = record_review(
        git_repo,
        TICKET,
        _review_input(
            git_repo,
            review_round=2,
            sha=sha_2,
            verdict="CHANGES_REQUIRED",
            findings=[_finding("R2")],
        ),
    )

    assert manifest["state"] == "STOPPED"
    assert manifest["stop_reason"] == "review_round_limit"
    with pytest.raises(CycleError, match="cannot begin review"):
        begin_review(git_repo, TICKET, sha_2)


def test_review_window_detects_repository_mutation(git_repo: Path) -> None:
    initialize_cycle(git_repo, TICKET)
    sha = _ready_for_review(git_repo)
    begin_review(git_repo, TICKET, sha)
    (git_repo / "tracked.txt").write_text("reviewer mutation\n", encoding="utf-8")

    with pytest.raises(CycleError, match="working tree changed"):
        record_review(
            git_repo,
            TICKET,
            _review_input(git_repo, review_round=1, sha=sha, verdict="PASS"),
        )


def test_invalid_verdict_fails_closed(git_repo: Path) -> None:
    initialize_cycle(git_repo, TICKET)
    sha = _ready_for_review(git_repo)
    begin_review(git_repo, TICKET, sha)

    with pytest.raises(CycleError, match="invalid review verdict"):
        record_review(
            git_repo,
            TICKET,
            _review_input(git_repo, review_round=1, sha=sha, verdict="MAYBE"),
        )


def test_repeated_exact_finding_stops_for_human_inspection(git_repo: Path) -> None:
    initialize_cycle(git_repo, TICKET)
    sha_1 = _ready_for_review(git_repo, 1)
    begin_review(git_repo, TICKET, sha_1)
    record_review(
        git_repo,
        TICKET,
        _review_input(
            git_repo,
            review_round=1,
            sha=sha_1,
            verdict="CHANGES_REQUIRED",
            findings=[_finding()],
        ),
    )
    sha_2 = _ready_for_review(git_repo, 2)
    begin_review(git_repo, TICKET, sha_2)
    manifest = record_review(
        git_repo,
        TICKET,
        _review_input(
            git_repo,
            review_round=2,
            sha=sha_2,
            verdict="CHANGES_REQUIRED",
            findings=[_finding()],
        ),
    )

    assert manifest["state"] == "STOPPED"
    assert manifest["stop_reason"] == "repeated_finding"


def test_active_agent_exclusivity_rejects_reviewer(git_repo: Path) -> None:
    initialize_cycle(git_repo, TICKET)
    manifest = begin_implementation(git_repo, TICKET)
    sha = _git(git_repo, "rev-parse", "HEAD")

    assert manifest["active_agent"] == "implementer"
    with pytest.raises(CycleError, match="already active"):
        begin_review(git_repo, TICKET, sha)


def test_begin_review_assigns_generic_reviewer_role(git_repo: Path) -> None:
    initialize_cycle(git_repo, TICKET)
    sha = _ready_for_review(git_repo)

    manifest = begin_review(git_repo, TICKET, sha)

    assert manifest["active_agent"] == "reviewer"


def test_corrupt_manifest_is_not_recreated(git_repo: Path) -> None:
    initialize_cycle(git_repo, TICKET)
    manifest_path = cycle_directory(git_repo, TICKET) / "manifest.json"
    manifest_path.write_text("{corrupt", encoding="utf-8")

    with pytest.raises(CycleError, match="valid JSON"):
        cycle_status(git_repo, TICKET)

    assert manifest_path.read_text(encoding="utf-8") == "{corrupt"


def test_command_from_repository_subdirectory_is_rejected(git_repo: Path) -> None:
    initialize_cycle(git_repo, TICKET)
    subdirectory = git_repo / "nested"
    subdirectory.mkdir()

    with pytest.raises(CycleError, match="run from repository root"):
        cycle_status(subdirectory, TICKET)


def test_changes_required_handoff_requires_a_new_sha(git_repo: Path) -> None:
    initialize_cycle(git_repo, TICKET)
    sha = _ready_for_review(git_repo)
    begin_review(git_repo, TICKET, sha)
    record_review(
        git_repo,
        TICKET,
        _review_input(
            git_repo,
            review_round=1,
            sha=sha,
            verdict="CHANGES_REQUIRED",
            findings=[_finding()],
        ),
    )
    begin_implementation(git_repo, TICKET)

    with pytest.raises(CycleError, match="new implementation SHA"):
        record_handoff(git_repo, TICKET, _implementer_input(git_repo, 2))


def test_manual_commit_between_phases_requires_human_recovery(git_repo: Path) -> None:
    initialize_cycle(git_repo, TICKET)
    _commit_attempt(git_repo, 1)

    with pytest.raises(CycleError, match="outside a validated implementation phase"):
        begin_implementation(git_repo, TICKET)


def test_optional_remote_tip_verification_is_local_and_exact(git_repo: Path) -> None:
    initialize_cycle(git_repo, TICKET)
    head = _git(git_repo, "rev-parse", "HEAD")
    _git(git_repo, "update-ref", f"refs/remotes/origin/{TASK_BRANCH}", head)

    status = cycle_status(git_repo, TICKET, verify_remote="origin")

    assert status["remote_tip"] == head
    assert status["errors"] == []


def test_cli_returns_nonzero_for_invalid_ticket(
    git_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = main(["status", "../PDFTR-33"], repo_root=git_repo)

    assert result == 2
    assert "invalid ticket ID" in capsys.readouterr().err
