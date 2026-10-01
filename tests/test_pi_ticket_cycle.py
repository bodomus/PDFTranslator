from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from uuid import uuid4

import pytest
from scripts.agent_cycle import cycle_directory, cycle_status
from scripts.pi_ticket_cycle import (
    REVIEW_SENTINEL_BEGIN,
    REVIEW_SENTINEL_END,
    CommandResult,
    RoleConfig,
    RunnerCancelled,
    RunnerConfig,
    RunnerError,
    SubprocessExecutor,
    _group_popen_kwargs,
    _terminate_process_tree,
    extract_review_json,
    main,
    resolve_executable,
    run_cycle,
    validate_reviewer_config,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_SOURCE = REPOSITORY_ROOT / ".agents" / "skills" / "two-agent-ticket-workflow"
BASE_BRANCH = "master"
TASK_BRANCH = "pi/PDFTR-35-test"
TICKET = "PDFTR-35"


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
    root = REPOSITORY_ROOT / "temp" / "pi-cycle-tests" / str(uuid4())
    root.mkdir(parents=True)
    try:
        _git(root, "init", "-b", BASE_BRANCH)
        _git(root, "config", "user.name", "Pi Cycle Tests")
        _git(root, "config", "user.email", "pi-cycle@example.invalid")
        (root / ".gitignore").write_text("/.agent-cycle/\n", encoding="utf-8")
        (root / "tracked.txt").write_text("initial\n", encoding="utf-8")
        tickets = root / "Tickets"
        tickets.mkdir()
        (tickets / f"{TICKET}-test-ticket.md").write_text(
            "# Ticket\n\nAcceptance criteria: the cycle stops for human review.\n",
            encoding="utf-8",
        )
        contract_dir = root / ".agents" / "skills" / "two-agent-ticket-workflow"
        contract_dir.mkdir(parents=True)
        for name in ("IMPLEMENTER_CONTRACT.md", "REVIEWER_CONTRACT.md"):
            shutil.copyfile(CONTRACT_SOURCE / name, contract_dir / name)
        _git(root, "add", ".")
        _git(root, "commit", "-m", "initial")
        _git(root, "switch", "-c", TASK_BRANCH)
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _config() -> RunnerConfig:
    return RunnerConfig(base_branch=BASE_BRANCH)


def _state(repo: Path) -> str:
    manifest = json.loads((cycle_directory(repo, TICKET) / "manifest.json").read_text("utf-8"))
    return manifest["state"]


def _provider(command: Sequence[str]) -> str:
    return command[command.index("--provider") + 1]


def _model(command: Sequence[str]) -> str:
    return command[command.index("--model") + 1]


def _finding(identifier: str) -> dict[str, str]:
    return {
        "id": identifier,
        "severity": "HIGH",
        "file": "scripts/pi_ticket_cycle.py",
        "symbol": "run_cycle",
        "problem": "Concrete defect",
        "required_fix": "Correct the defect",
        "regression_test": "Add a deterministic test",
    }


class FakePi:
    """Deterministic stand-in for the real Pi executable; never contacts providers."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.invocations: list[tuple[tuple[str, ...], str]] = []
        self.implementer_runs = 0
        self.reviewer_runs = 0
        self.implementer_exit = 0
        self.reviewer_exit = 0
        self.verdicts: list[str] = ["PASS"]
        self.findings: list[list[dict[str, str]]] = [[]]
        self.blocked_reason = "external blocker"
        self.no_new_commit_on_attempt = 0
        self.dirty_after_implementer = False
        self.cancel_implementer = False
        self.cancel_reviewer = False
        self.run_raises: Exception | None = None
        self.reviewer_stdout_override: str | None = None
        self.reviewer_payload_overrides: dict[int, dict[str, object]] = {}

    @property
    def commands(self) -> list[tuple[str, ...]]:
        return [command for command, _stdin in self.invocations]

    def ensure_available(self) -> None:
        return None

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        log_path: Path,
        stdin_text: str,
    ) -> CommandResult:
        captured = tuple(str(part) for part in command)
        self.invocations.append((captured, stdin_text))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("fake pi log\n", encoding="utf-8")
        if self.run_raises is not None:
            raise self.run_raises
        role = _provider(captured)
        if role == "deepseek":
            return self._implementer()
        if role == "openai-codex":
            return self._reviewer()
        raise AssertionError(f"unexpected provider: {role}")

    def _implementer(self) -> CommandResult:
        self.implementer_runs += 1
        attempt = self.implementer_runs
        if self.cancel_implementer:
            raise RunnerCancelled("simulated implementer cancellation")
        if self.implementer_exit:
            return CommandResult(self.implementer_exit, "", "")
        if attempt != self.no_new_commit_on_attempt:
            (self.repo / "tracked.txt").write_text(f"attempt {attempt}\n", encoding="utf-8")
            _git(self.repo, "add", "tracked.txt")
            _git(self.repo, "commit", "-m", f"attempt {attempt}")
        if self.dirty_after_implementer:
            (self.repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")
            return CommandResult(0, "", "")
        self._write_handoff(attempt)
        return CommandResult(0, "", "")

    def _reviewer(self) -> CommandResult:
        index = self.reviewer_runs
        self.reviewer_runs += 1
        if self.cancel_reviewer:
            raise RunnerCancelled("simulated reviewer cancellation")
        if self.reviewer_exit:
            return CommandResult(self.reviewer_exit, "", "")
        if self.reviewer_stdout_override is not None:
            return CommandResult(0, self.reviewer_stdout_override, "")
        verdict = self.verdicts[min(index, len(self.verdicts) - 1)]
        findings = (
            self.findings[min(index, len(self.findings) - 1)]
            if verdict == "CHANGES_REQUIRED"
            else []
        )
        document: dict[str, object] = {
            "schema_version": "1.0",
            "ticket": TICKET,
            "review_round": index + 1,
            "reviewed_sha": _git(self.repo, "rev-parse", "HEAD"),
            "verdict": verdict,
            "findings": findings,
            "blocked_reason": self.blocked_reason if verdict == "BLOCKED" else None,
        }
        document.update(self.reviewer_payload_overrides.get(index, {}))
        stdout = f"{REVIEW_SENTINEL_BEGIN}\n{json.dumps(document)}\n{REVIEW_SENTINEL_END}\n"
        return CommandResult(0, stdout, "")

    def _write_handoff(self, attempt: int) -> None:
        path = cycle_directory(self.repo, TICKET) / "implementer.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "ticket": TICKET,
                    "implementation_attempt": attempt,
                    "status": "COMPLETE",
                    "implementation_report": (
                        f".implementation-reports/implementation-report-{TICKET}.md"
                    ),
                    "focused_tests": "PASS",
                    "full_tests": "PASS",
                    "check_ps1": "PASS",
                    "known_limitations": [],
                    "notes": [],
                }
            ),
            encoding="utf-8",
        )


def _run(repo: Path, fake: FakePi):
    return run_cycle(repo, TICKET, executor=fake, config=_config())


# --- Required ticket test cases -------------------------------------------------------------


def test_one_round_pass(git_repo: Path) -> None:
    fake = FakePi(git_repo)

    outcome = _run(git_repo, fake)

    assert outcome.passed
    assert outcome.state == "PASSED"
    assert fake.implementer_runs == 1
    assert fake.reviewer_runs == 1
    assert outcome.review_rounds == 1
    review = json.loads((cycle_directory(git_repo, TICKET) / "review-1.json").read_text("utf-8"))
    assert review["verdict"] == "PASS"
    assert review["reviewed_sha"] == outcome.implementation_sha


def test_changes_required_then_new_sha_then_round_two_pass(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    fake.verdicts = ["CHANGES_REQUIRED", "PASS"]
    fake.findings = [[_finding("R1")], []]

    outcome = _run(git_repo, fake)

    assert outcome.state == "PASSED"
    assert fake.implementer_runs == 2
    assert fake.reviewer_runs == 2
    implementer_prompts = [
        stdin for command, stdin in fake.invocations if _provider(command) == "deepseek"
    ]
    assert "R1" in implementer_prompts[1]
    review_1 = json.loads((cycle_directory(git_repo, TICKET) / "review-1.json").read_text("utf-8"))
    review_2 = json.loads((cycle_directory(git_repo, TICKET) / "review-2.json").read_text("utf-8"))
    assert review_1["reviewed_sha"] != review_2["reviewed_sha"]


def test_round_two_changes_required_stops_without_a_third_review(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    fake.verdicts = ["CHANGES_REQUIRED", "CHANGES_REQUIRED"]
    fake.findings = [[_finding("R1")], [_finding("R2")]]

    outcome = _run(git_repo, fake)

    assert outcome.state == "STOPPED"
    assert outcome.stop_reason == "review_round_limit"
    assert fake.reviewer_runs == 2
    assert fake.implementer_runs == 2


def test_reviewer_invocation_is_read_only_and_configured(git_repo: Path) -> None:
    fake = FakePi(git_repo)

    _run(git_repo, fake)

    reviewer_command = next(c for c in fake.commands if _provider(c) == "openai-codex")
    assert _model(reviewer_command) == "gpt-6.1-sol"
    tools = reviewer_command[reviewer_command.index("--tools") + 1].split(",")
    assert tools == ["read", "grep", "find", "ls"]
    assert "write" not in tools
    assert "edit" not in tools
    assert "bash" not in tools


def test_implementer_invocation_is_configured(git_repo: Path) -> None:
    fake = FakePi(git_repo)

    _run(git_repo, fake)

    implementer_command = next(c for c in fake.commands if _provider(c) == "deepseek")
    assert _model(implementer_command) == "deepseek-v4-pro"
    assert "--tools" not in implementer_command


def test_malformed_reviewer_json_fails_closed(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    fake.reviewer_stdout_override = "this is not json"

    with pytest.raises(RunnerError, match="reviewer output rejected"):
        _run(git_repo, fake)

    assert fake.reviewer_runs == 1
    assert _state(git_repo) == "STOPPED"


@pytest.mark.parametrize(
    "override",
    [
        {"reviewed_sha": "a" * 40},
        {"ticket": "PDFTR-99"},
        {"review_round": 2},
        {"verdict": "MAYBE"},
        {"verdict": "PASS", "findings": [_finding("R1")]},
        {"verdict": "CHANGES_REQUIRED", "findings": []},
        {"verdict": "BLOCKED", "blocked_reason": None},
    ],
)
def test_wrong_or_invalid_reviewer_payload_fails_closed(
    git_repo: Path, override: dict[str, object]
) -> None:
    fake = FakePi(git_repo)
    fake.reviewer_payload_overrides = {0: override}

    with pytest.raises(RunnerError, match="review validation failed"):
        _run(git_repo, fake)

    assert fake.reviewer_runs == 1
    assert _state(git_repo) == "STOPPED"


def test_implementer_abnormal_exit_never_starts_reviewer(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    fake.implementer_exit = 3

    with pytest.raises(RunnerError, match="implementer exited with code 3"):
        _run(git_repo, fake)

    assert fake.reviewer_runs == 0
    assert _state(git_repo) == "STOPPED"


def test_reviewer_abnormal_exit_never_starts_another_role(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    fake.reviewer_exit = 4

    with pytest.raises(RunnerError, match="reviewer exited with code 4"):
        _run(git_repo, fake)

    assert fake.implementer_runs == 1
    assert fake.reviewer_runs == 1
    assert _state(git_repo) == "STOPPED"


def test_dirty_tree_after_implementer_never_starts_reviewer(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    fake.dirty_after_implementer = True

    with pytest.raises(RunnerError, match="dirty working tree"):
        _run(git_repo, fake)

    assert fake.reviewer_runs == 0
    assert _state(git_repo) == "STOPPED"


def test_no_new_sha_after_changes_required_prevents_round_two_review(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    fake.verdicts = ["CHANGES_REQUIRED", "PASS"]
    fake.findings = [[_finding("R1")], []]
    fake.no_new_commit_on_attempt = 2

    with pytest.raises(RunnerError, match="handoff validation failed"):
        _run(git_repo, fake)

    assert fake.reviewer_runs == 1
    assert fake.implementer_runs == 2
    assert _state(git_repo) == "STOPPED"


def test_missing_pi_executable_is_actionable() -> None:
    with pytest.raises(RunnerError, match="not found on PATH"):
        resolve_executable("pdftr-missing-pi-executable")


def test_cancellation_during_implementer_never_launches_reviewer(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    fake.cancel_implementer = True

    with pytest.raises(RunnerError, match="cancelled"):
        _run(git_repo, fake)

    assert fake.reviewer_runs == 0
    assert _state(git_repo) == "STOPPED"


def test_cancellation_during_reviewer_never_launches_next_round(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    fake.cancel_reviewer = True

    with pytest.raises(RunnerError, match="cancelled"):
        _run(git_repo, fake)

    assert fake.implementer_runs == 1
    assert fake.reviewer_runs == 1
    assert _state(git_repo) == "STOPPED"


def test_agent_cycle_remains_the_transition_authority(git_repo: Path) -> None:
    fake = FakePi(git_repo)

    outcome = _run(git_repo, fake)

    status = cycle_status(git_repo, TICKET)
    assert status["state"] == "PASSED"
    assert status["review_valid_for_head"] is True
    assert status["errors"] == []
    handoff = json.loads((cycle_directory(git_repo, TICKET) / "handoff.json").read_text("utf-8"))
    assert handoff["system"]["state"] == outcome.state
    assert handoff["implementer"]["status"] == "COMPLETE"
    assert handoff["reviewer"]["verdict"] == "PASS"
    assert handoff["reviewer"]["reviewed_sha"] == outcome.implementation_sha


# --- R2: prompts supersede manual transitions ----------------------------------------------


def test_prompts_supersede_manual_transitions(git_repo: Path) -> None:
    fake = FakePi(git_repo)

    outcome = _run(git_repo, fake)

    implementer_prompt = fake.invocations[0][1]
    reviewer_prompt = fake.invocations[1][1]
    assert "Automated runner override" in implementer_prompt
    assert "Automated runner override" in reviewer_prompt
    assert "Do NOT run scripts/agent_cycle.py" in implementer_prompt
    assert "Do NOT run scripts/agent_cycle.py" in reviewer_prompt
    assert "begin-implementation" in implementer_prompt
    assert "record-review" in reviewer_prompt
    assert "read-only" in reviewer_prompt.lower()
    assert outcome.review_rounds == 1
    assert fake.implementer_runs == 1
    assert fake.reviewer_runs == 1
    assert cycle_status(git_repo, TICKET)["review_round"] == 1


# --- R3: reviewer read-only configuration ---------------------------------------------------


@pytest.mark.parametrize(
    "tools",
    [(), ("read", "bash"), ("write",), ("read", "unknown"), ("",), ("read", "edit", "write")],
)
def test_unsafe_reviewer_tools_rejected_before_state(
    git_repo: Path, tools: tuple[str, ...]
) -> None:
    config = RunnerConfig(
        reviewer=RoleConfig("openai-codex", "gpt-6.1-sol", tools), base_branch=BASE_BRANCH
    )
    fake = FakePi(git_repo)

    with pytest.raises(RunnerError, match="reviewer tools"):
        run_cycle(git_repo, TICKET, executor=fake, config=config)

    assert fake.invocations == []
    assert not (git_repo / ".agent-cycle").exists()


def test_safe_reviewer_config_is_accepted() -> None:
    validate_reviewer_config(_config())


@pytest.mark.parametrize("value", ["", "read,bash", "read,write,edit", "unknown"])
def test_cli_rejects_unsafe_reviewer_tools(git_repo: Path, value: str) -> None:
    code = main(
        [TICKET, "--reviewer-tools", value, "--repo-root", str(git_repo), "--base-branch", "master"]
    )

    assert code == 1
    assert not (git_repo / ".agent-cycle").exists()


# --- R1: prompt transport -------------------------------------------------------------------


def _make_stdin_capture_shim(directory: Path, capture: Path) -> str:
    script = directory / "capture.py"
    script.write_text(
        "import pathlib, sys\npathlib.Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        shim = directory / "pi-fake.cmd"
        shim.write_text(
            f'@ECHO off\r\n"{sys.executable}" "{script}" "{capture}" %*\r\n',
            encoding="utf-8",
        )
        return str(shim)
    shim = directory / "pi-fake.sh"
    shim.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" "{script}" "{capture}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return str(shim)


def test_subprocess_executor_preserves_large_multiline_prompt(tmp_path: Path) -> None:
    capture = tmp_path / "captured.txt"
    shim = _make_stdin_capture_shim(tmp_path, capture)
    prompt = "Quotes 'single' \"double\" metacharacters & | < > ^ %PATH% $VAR `tick`\n" + (
        "Юникод-строка проверки транспорта промпта. " * 400
    )
    assert len(prompt) > 8191

    executor = SubprocessExecutor(shim)
    result = executor.run(
        [shim, "--provider", "deepseek", "--model", "deepseek-v4-pro", "-p"],
        cwd=tmp_path,
        log_path=tmp_path / "log.txt",
        stdin_text=prompt,
    )

    assert result.returncode == 0
    assert capture.read_text(encoding="utf-8") == prompt


# --- R4: process-tree cancellation ----------------------------------------------------------


def _pid_exists(pid: int) -> bool:
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in result.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def test_terminate_process_tree_reaps_descendants(tmp_path: Path) -> None:
    child_pid_file = tmp_path / "child.pid"
    parent_script = tmp_path / "parent.py"
    parent_script.write_text(
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        "open(sys.argv[1], 'w').write(str(child.pid))\n"
        "time.sleep(120)\n",
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [sys.executable, str(parent_script), str(child_pid_file)],
        **_group_popen_kwargs(),
    )
    try:
        deadline = time.time() + 30
        while not child_pid_file.exists() and time.time() < deadline:
            time.sleep(0.05)
        assert child_pid_file.exists()
        child_pid = int(child_pid_file.read_text(encoding="utf-8"))

        _terminate_process_tree(process, 5.0)

        assert process.poll() is not None
        deadline = time.time() + 15
        while _pid_exists(child_pid) and time.time() < deadline:
            time.sleep(0.1)
        assert not _pid_exists(child_pid)
    finally:
        if process.poll() is None:
            _terminate_process_tree(process, 1.0)


# --- R5: single unambiguous reviewer result -------------------------------------------------


def test_extract_review_json_rejects_sentinel_and_fence_conflict() -> None:
    passing = {"schema_version": "1.0", "verdict": "PASS"}
    failing = {"schema_version": "1.0", "verdict": "CHANGES_REQUIRED"}
    stdout = (
        f"{REVIEW_SENTINEL_BEGIN}\n{json.dumps(passing)}\n{REVIEW_SENTINEL_END}\n"
        f"```json\n{json.dumps(failing)}\n```\n"
    )

    with pytest.raises(RunnerError, match="exactly one reviewer JSON"):
        extract_review_json(stdout)


def test_extract_review_json_rejects_unmatched_delimiters() -> None:
    passing = {"schema_version": "1.0", "verdict": "PASS"}
    stdout = f"{REVIEW_SENTINEL_BEGIN}\n{json.dumps(passing)}\n"

    with pytest.raises(RunnerError, match="unmatched review delimiters"):
        extract_review_json(stdout)


def test_extract_review_json_rejects_bare_extra_object() -> None:
    passing = {"schema_version": "1.0", "verdict": "PASS"}
    failing = {"schema_version": "1.0", "verdict": "CHANGES_REQUIRED"}
    stdout = (
        f"{REVIEW_SENTINEL_BEGIN}\n{json.dumps(passing)}\n{REVIEW_SENTINEL_END}\n"
        f"Also consider: {json.dumps(failing)}\n"
    )

    with pytest.raises(RunnerError, match="exactly one reviewer JSON"):
        extract_review_json(stdout)


def test_ambiguous_reviewer_output_stops_without_pass_artifact(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    passing = {
        "schema_version": "1.0",
        "ticket": TICKET,
        "review_round": 1,
        "reviewed_sha": _git(git_repo, "rev-parse", "HEAD"),
        "verdict": "PASS",
        "findings": [],
        "blocked_reason": None,
    }
    failing = dict(passing, verdict="CHANGES_REQUIRED", findings=[_finding("R1")])
    fake.reviewer_stdout_override = (
        f"{REVIEW_SENTINEL_BEGIN}\n{json.dumps(passing)}\n{REVIEW_SENTINEL_END}\n"
        f"```json\n{json.dumps(failing)}\n```\n"
    )

    with pytest.raises(RunnerError, match="reviewer output rejected"):
        _run(git_repo, fake)

    assert fake.reviewer_runs == 1
    assert _state(git_repo) == "STOPPED"
    assert not (cycle_directory(git_repo, TICKET) / "review-1.json").exists()


# --- R6: operational failures fail closed ---------------------------------------------------


def test_missing_executable_does_not_claim_active_role(git_repo: Path) -> None:
    with pytest.raises(RunnerError, match="not found on PATH"):
        run_cycle(
            git_repo,
            TICKET,
            executor=SubprocessExecutor("pdftr-missing-pi-executable"),
            config=_config(),
        )

    assert not (git_repo / ".agent-cycle").exists()


def test_executor_operational_failure_stops_active_phase(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    fake.run_raises = OSError("spawn failed")

    with pytest.raises(RunnerError, match="Pi process failure"):
        _run(git_repo, fake)

    assert fake.reviewer_runs == 0
    assert _state(git_repo) == "STOPPED"


# --- Extraction unit coverage ---------------------------------------------------------------


def test_extract_review_json_accepts_sentinel_block() -> None:
    document = {"schema_version": "1.0", "verdict": "PASS"}
    stdout = f"prefix\n{REVIEW_SENTINEL_BEGIN}\n{json.dumps(document)}\n{REVIEW_SENTINEL_END}\n"

    assert extract_review_json(stdout) == document


def test_extract_review_json_accepts_single_fence() -> None:
    document = {"schema_version": "1.0", "verdict": "PASS"}
    stdout = f"review:\n```json\n{json.dumps(document)}\n```\n"

    assert extract_review_json(stdout) == document


def test_extract_review_json_accepts_whole_stdout_object() -> None:
    document = {"schema_version": "1.0", "verdict": "PASS"}

    assert extract_review_json(json.dumps(document)) == document


@pytest.mark.parametrize(
    "stdout",
    [
        "no json here",
        f"{REVIEW_SENTINEL_BEGIN}\n{{bad json}}\n{REVIEW_SENTINEL_END}",
        "[1, 2, 3]",
        (
            f"{REVIEW_SENTINEL_BEGIN}\n{{}}\n{REVIEW_SENTINEL_END}\n"
            f"{REVIEW_SENTINEL_BEGIN}\n{{}}\n{REVIEW_SENTINEL_END}"
        ),
    ],
)
def test_extract_review_json_fails_closed(stdout: str) -> None:
    with pytest.raises(RunnerError):
        extract_review_json(stdout)
