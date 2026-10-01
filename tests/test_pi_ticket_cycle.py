from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from uuid import uuid4

import pytest
import scripts.pi_ticket_cycle as pi_runner
from scripts.agent_cycle import CycleError, cycle_directory, cycle_status
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
    _load_ticket_text,
    _new_process_tree,
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


@pytest.fixture
def work_dir() -> Iterator[Path]:
    root = REPOSITORY_ROOT / "temp" / "pi-cycle-tests" / str(uuid4())
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _config(executable: str = "pi") -> RunnerConfig:
    return RunnerConfig(base_branch=BASE_BRANCH, executable=executable)


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


def _run(repo: Path, fake: FakePi) -> object:
    return run_cycle(repo, TICKET, executor=fake, config=_config())


# --- Core cycle behavior --------------------------------------------------------------------


def test_one_round_pass(git_repo: Path) -> None:
    fake = FakePi(git_repo)

    outcome = _run(git_repo, fake)

    assert outcome.passed
    assert outcome.state == "PASSED"
    assert fake.implementer_runs == 1
    assert fake.reviewer_runs == 1
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


def test_reviewer_invocation_is_read_only_and_configured(git_repo: Path) -> None:
    fake = FakePi(git_repo)

    _run(git_repo, fake)

    reviewer_command = next(c for c in fake.commands if _provider(c) == "openai-codex")
    assert _model(reviewer_command) == "gpt-6.1-sol"
    tools = reviewer_command[reviewer_command.index("--tools") + 1].split(",")
    assert tools == ["read", "grep", "find", "ls"]


def test_implementer_invocation_is_configured(git_repo: Path) -> None:
    fake = FakePi(git_repo)

    _run(git_repo, fake)

    implementer_command = next(c for c in fake.commands if _provider(c) == "deepseek")
    assert _model(implementer_command) == "deepseek-v4-pro"
    assert "--tools" not in implementer_command


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
    assert _state(git_repo) == "STOPPED"


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
    handoff = json.loads((cycle_directory(git_repo, TICKET) / "handoff.json").read_text("utf-8"))
    assert handoff["system"]["state"] == outcome.state
    assert handoff["reviewer"]["reviewed_sha"] == outcome.implementation_sha


# --- R2: consistent handoff ownership -------------------------------------------------------


def test_prompts_permit_only_the_handoff_input(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    fake.verdicts = ["CHANGES_REQUIRED", "PASS"]
    fake.findings = [[_finding("R1")], []]

    _run(git_repo, fake)

    handoff_path = str(cycle_directory(git_repo, TICKET) / "implementer.json")
    implementer_prompts = [
        stdin for command, stdin in fake.invocations if _provider(command) == "deepseek"
    ]
    assert len(implementer_prompts) == 2
    for prompt in implementer_prompts:
        assert handoff_path in prompt
        assert "Do NOT modify manifest.json, handoff.json" in prompt
        assert "Do NOT run scripts/agent_cycle.py" in prompt
        assert "Do NOT modify anything under .agent-cycle/" not in prompt
    reviewer_prompt = next(
        stdin for command, stdin in fake.invocations if _provider(command) == "openai-codex"
    )
    assert "read-only" in reviewer_prompt.lower()
    assert "persists that output" in reviewer_prompt
    assert "create that ignored coordination input" not in reviewer_prompt


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


# --- Process helpers ------------------------------------------------------------------------


def _spawn_tree_script(directory: Path, *, ignore_sigterm: bool = False) -> Path:
    script = directory / "spawn_tree.py"
    grandchild = (
        "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(300)"
        if ignore_sigterm
        else "import time; time.sleep(300)"
    )
    script.write_text(
        "import os, subprocess, sys, time\n"
        "self_file, child_file, mode = sys.argv[1], sys.argv[2], sys.argv[3]\n"
        f"grandchild = subprocess.Popen([sys.executable, '-c', {grandchild!r}])\n"
        "open(self_file, 'w').write(str(os.getpid()))\n"
        "open(child_file, 'w').write(str(grandchild.pid))\n"
        "if mode == 'stay':\n"
        "    time.sleep(300)\n",
        encoding="utf-8",
    )
    return script


def _make_tree_shim(directory: Path, script: Path, self_file: Path, child_file: Path) -> str:
    if os.name == "nt":
        shim = directory / "tree-fake.cmd"
        shim.write_text(
            f'@ECHO off\r\n"{sys.executable}" "{script}" "{self_file}" "{child_file}" stay %*\r\n',
            encoding="utf-8",
        )
        return str(shim)
    shim = directory / "tree-fake.sh"
    shim.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" "{script}" "{self_file}" "{child_file}" stay "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return str(shim)


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


def _wait_for_files(files: Sequence[Path], timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while not all(path.exists() for path in files) and time.time() < deadline:
        time.sleep(0.05)
    assert all(path.exists() for path in files)


def _wait_until_dead(pid: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while _pid_exists(pid) and time.time() < deadline:
        time.sleep(0.1)
    return not _pid_exists(pid)


def _inject_communicate_failure(
    monkeypatch: pytest.MonkeyPatch,
    files: Sequence[Path],
    error_factory: Callable[[], BaseException],
    marker: str,
) -> None:
    original = subprocess.Popen.communicate

    def fake_communicate(
        self: subprocess.Popen, input: object = None, timeout: object = None
    ) -> object:
        joined = " ".join(str(part) for part in (getattr(self, "args", None) or []))
        if marker not in joined:
            return original(self, input=input, timeout=timeout)
        deadline = time.time() + 30
        while not all(path.exists() for path in files) and time.time() < deadline:
            time.sleep(0.05)
        raise error_factory()

    monkeypatch.setattr(subprocess.Popen, "communicate", fake_communicate)


# --- R4: process tree independent of parent lifetime ----------------------------------------


def test_process_tree_kills_descendant_after_parent_exit(work_dir: Path) -> None:
    script = _spawn_tree_script(work_dir)
    self_file = work_dir / "self.pid"
    child_file = work_dir / "child.pid"
    process = subprocess.Popen(
        [sys.executable, str(script), str(self_file), str(child_file), "exit"],
        **_group_popen_kwargs(),
    )
    tree = _new_process_tree(process)
    try:
        _wait_for_files([self_file, child_file])
        child_pid = int(child_file.read_text(encoding="utf-8"))
        process.wait(timeout=30)
        assert _pid_exists(child_pid)
        assert tree.terminate(10.0) is True
        assert _wait_until_dead(child_pid)
    finally:
        tree.close()
        if process.poll() is None:
            process.kill()


def test_cancellation_kills_child_and_descendant(
    work_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _spawn_tree_script(work_dir)
    self_file = work_dir / "self.pid"
    child_file = work_dir / "child.pid"
    shim = _make_tree_shim(work_dir, script, self_file, child_file)
    _inject_communicate_failure(
        monkeypatch, [self_file, child_file], KeyboardInterrupt, "tree-fake"
    )

    executor = SubprocessExecutor(shim, grace_seconds=2.0)
    with pytest.raises(RunnerCancelled):
        executor.run(
            [shim, "--provider", "deepseek", "--model", "deepseek-v4-pro", "-p"],
            cwd=work_dir,
            log_path=work_dir / "log.txt",
            stdin_text="prompt",
        )

    self_pid = int(self_file.read_text(encoding="utf-8"))
    child_pid = int(child_file.read_text(encoding="utf-8"))
    assert _wait_until_dead(self_pid)
    assert _wait_until_dead(child_pid)


# --- R5: strict single-envelope extraction --------------------------------------------------


def _valid_review(verdict: str = "PASS") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "ticket": TICKET,
        "review_round": 1,
        "reviewed_sha": "b" * 40,
        "verdict": verdict,
        "findings": [_finding("R1")] if verdict == "CHANGES_REQUIRED" else [],
        "blocked_reason": None,
    }


def test_extract_review_json_accepts_single_envelope() -> None:
    document = _valid_review()
    stdout = f"{REVIEW_SENTINEL_BEGIN}\n{json.dumps(document)}\n{REVIEW_SENTINEL_END}\n"

    assert extract_review_json(stdout) == document


def test_extract_review_json_accepts_single_fence() -> None:
    document = _valid_review()
    stdout = f"```json\n{json.dumps(document)}\n```\n"

    assert extract_review_json(stdout) == document


def test_extract_review_json_accepts_whole_stdout_object() -> None:
    document = _valid_review()

    assert extract_review_json(json.dumps(document)) == document


@pytest.mark.parametrize(
    "stdout",
    [
        "no json here",
        "",
        f"{REVIEW_SENTINEL_BEGIN}\n{{bad json}}\n{REVIEW_SENTINEL_END}",
        f"{REVIEW_SENTINEL_BEGIN}\n{json.dumps(_valid_review())}\n",  # unmatched
        (  # reversed
            f"{REVIEW_SENTINEL_END}\n{json.dumps(_valid_review())}\n{REVIEW_SENTINEL_BEGIN}"
        ),
        (
            f"{REVIEW_SENTINEL_BEGIN}\n{json.dumps(_valid_review())}\n{REVIEW_SENTINEL_END}\n"
            f"{REVIEW_SENTINEL_BEGIN}\n{json.dumps(_valid_review())}\n{REVIEW_SENTINEL_END}"
        ),
        f"{REVIEW_SENTINEL_BEGIN}\n[{json.dumps(_valid_review())}]\n{REVIEW_SENTINEL_END}",  # array
        (  # extra conflicting object outside the sentinel envelope
            f"{REVIEW_SENTINEL_BEGIN}\n{json.dumps(_valid_review())}\n{REVIEW_SENTINEL_END}\n"
            f"Note: {json.dumps(_valid_review('CHANGES_REQUIRED'))}\n"
        ),
        (  # unterminated outer object containing a valid inner object
            f"{REVIEW_SENTINEL_BEGIN}\n"
            f'{{"broken": {json.dumps(_valid_review())}'
            f"\n{REVIEW_SENTINEL_END}"
        ),
        f'{{"broken": {json.dumps(_valid_review())}',  # unterminated whole stdout
        "[1, 2, 3]",
    ],
)
def test_extract_review_json_fails_closed(stdout: str) -> None:
    with pytest.raises(RunnerError):
        extract_review_json(stdout)


def test_ambiguous_reviewer_output_stops_without_pass_artifact(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    sha = _git(git_repo, "rev-parse", "HEAD")
    passing = dict(_valid_review(), ticket=TICKET, reviewed_sha=sha)
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


@pytest.mark.parametrize("override", [{"ticket": "PDFTR-99"}, {"reviewed_sha": "a" * 40}])
def test_wrong_reviewer_payload_fails_closed(git_repo: Path, override: dict[str, object]) -> None:
    fake = FakePi(git_repo)
    fake.reviewer_payload_overrides = {0: override}

    with pytest.raises(RunnerError, match="review validation failed"):
        _run(git_repo, fake)

    assert _state(git_repo) == "STOPPED"


# --- R6: cleanup on post-spawn I/O failure --------------------------------------------------


def test_missing_pi_executable_is_actionable() -> None:
    with pytest.raises(RunnerError, match="not found on PATH"):
        resolve_executable("pdftr-missing-pi-executable")


def test_missing_executable_does_not_claim_active_role(git_repo: Path) -> None:
    with pytest.raises(RunnerError, match="not found on PATH"):
        run_cycle(
            git_repo,
            TICKET,
            executor=SubprocessExecutor("pdftr-missing-pi-executable"),
            config=_config(),
        )

    assert not (git_repo / ".agent-cycle").exists()


def test_io_failure_kills_child_and_descendant(
    work_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _spawn_tree_script(work_dir)
    self_file = work_dir / "self.pid"
    child_file = work_dir / "child.pid"
    shim = _make_tree_shim(work_dir, script, self_file, child_file)
    _inject_communicate_failure(
        monkeypatch, [self_file, child_file], lambda: OSError("injected pipe failure"), "tree-fake"
    )

    executor = SubprocessExecutor(shim, grace_seconds=2.0)
    with pytest.raises(OSError):
        executor.run(
            [shim, "--provider", "deepseek", "--model", "deepseek-v4-pro", "-p"],
            cwd=work_dir,
            log_path=work_dir / "log.txt",
            stdin_text="prompt",
        )

    self_pid = int(self_file.read_text(encoding="utf-8"))
    child_pid = int(child_file.read_text(encoding="utf-8"))
    assert _wait_until_dead(self_pid)
    assert _wait_until_dead(child_pid)


def test_io_failure_releases_active_role_and_cleans_tree(
    git_repo: Path, work_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _spawn_tree_script(work_dir)
    self_file = work_dir / "self.pid"
    child_file = work_dir / "child.pid"
    shim = _make_tree_shim(work_dir, script, self_file, child_file)
    _inject_communicate_failure(
        monkeypatch, [self_file, child_file], lambda: OSError("injected pipe failure"), "tree-fake"
    )

    with pytest.raises(RunnerError, match="Pi process failure"):
        run_cycle(
            git_repo,
            TICKET,
            executor=SubprocessExecutor(shim, grace_seconds=2.0),
            config=_config(executable=shim),
        )

    assert _state(git_repo) == "STOPPED"
    assert not (cycle_directory(git_repo, TICKET) / "review-1.json").exists()
    self_pid = int(self_file.read_text(encoding="utf-8"))
    child_pid = int(child_file.read_text(encoding="utf-8"))
    assert _wait_until_dead(self_pid)
    assert _wait_until_dead(child_pid)


# --- R4-WIN: race-free Windows containment --------------------------------------------------


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object semantics")
def test_windows_child_is_suspended_until_job_assignment(work_dir: Path) -> None:
    script = _spawn_tree_script(work_dir)
    self_file = work_dir / "self.pid"
    child_file = work_dir / "child.pid"
    process = subprocess.Popen(
        [sys.executable, str(script), str(self_file), str(child_file), "stay"],
        **_group_popen_kwargs(),
    )
    tree = None
    try:
        time.sleep(1.0)
        assert not self_file.exists()
        assert not child_file.exists()
        tree = _new_process_tree(process)
        _wait_for_files([self_file, child_file])
    finally:
        if tree is not None:
            tree.terminate(2.0)
            tree.close()
        if process.poll() is None:
            process.kill()


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object semantics")
def test_windows_job_creation_failure_fails_closed(
    work_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _spawn_tree_script(work_dir)
    self_file = work_dir / "self.pid"
    child_file = work_dir / "child.pid"
    shim = _make_tree_shim(work_dir, script, self_file, child_file)
    monkeypatch.setattr(pi_runner, "_create_job_object", lambda process: None)

    executor = SubprocessExecutor(shim, grace_seconds=2.0)
    with pytest.raises(RunnerError, match="Job Object"):
        executor.run(
            [shim, "--provider", "deepseek", "--model", "deepseek-v4-pro", "-p"],
            cwd=work_dir,
            log_path=work_dir / "log.txt",
            stdin_text="prompt",
        )

    assert not self_file.exists()
    assert not child_file.exists()


# --- R4-POSIX: reap order and forced group termination ---------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group semantics")
def test_posix_terminate_reaps_sigterm_child(work_dir: Path) -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(300)"],
        **_group_popen_kwargs(),
    )
    tree = _new_process_tree(process)
    try:
        assert tree.terminate(5.0) is True
        assert process.poll() is not None
    finally:
        tree.close()


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group semantics")
def test_posix_terminate_force_kills_sigterm_ignoring_descendant(work_dir: Path) -> None:
    script = _spawn_tree_script(work_dir, ignore_sigterm=True)
    self_file = work_dir / "self.pid"
    child_file = work_dir / "child.pid"
    process = subprocess.Popen(
        [sys.executable, str(script), str(self_file), str(child_file), "stay"],
        **_group_popen_kwargs(),
    )
    tree = _new_process_tree(process)
    try:
        _wait_for_files([self_file, child_file])
        child_pid = int(child_file.read_text(encoding="utf-8"))
        assert tree.terminate(2.0) is True
        assert _wait_until_dead(child_pid)
    finally:
        tree.close()
        if process.poll() is None:
            process.kill()


# --- R5: duplicate JSON keys ----------------------------------------------------------------


@pytest.mark.parametrize(
    "fragment",
    [
        '"verdict":"PASS"',
        '"reviewed_sha":"' + "c" * 40 + '"',
        '"ticket":"PDFTR-99"',
        '"review_round":2',
    ],
)
def test_extract_review_json_rejects_duplicate_keys(fragment: str) -> None:
    valid = json.dumps(_valid_review("CHANGES_REQUIRED"))
    body = valid[:-1] + "," + fragment + "}"
    stdout = f"{REVIEW_SENTINEL_BEGIN}\n{body}\n{REVIEW_SENTINEL_END}"

    with pytest.raises(RunnerError, match="duplicate JSON key"):
        extract_review_json(stdout)


def test_extract_review_json_rejects_duplicate_nested_keys() -> None:
    finding = _finding("R1")
    finding_with_duplicate = json.dumps(finding)[:-1] + ',"id":"R2"}'
    base = json.dumps(_valid_review("CHANGES_REQUIRED"))
    body = base.replace(json.dumps([finding]), "[" + finding_with_duplicate + "]")
    stdout = f"{REVIEW_SENTINEL_BEGIN}\n{body}\n{REVIEW_SENTINEL_END}"

    with pytest.raises(RunnerError, match="duplicate JSON key"):
        extract_review_json(stdout)


def test_duplicate_verdict_output_stops_cycle(git_repo: Path) -> None:
    fake = FakePi(git_repo)
    sha = _git(git_repo, "rev-parse", "HEAD")
    document = dict(_valid_review("CHANGES_REQUIRED"), ticket=TICKET, reviewed_sha=sha)
    body = json.dumps(document)[:-1] + ',"verdict":"PASS"}'
    fake.reviewer_stdout_override = f"{REVIEW_SENTINEL_BEGIN}\n{body}\n{REVIEW_SENTINEL_END}"

    with pytest.raises(RunnerError, match="reviewer output rejected"):
        _run(git_repo, fake)

    assert _state(git_repo) == "STOPPED"
    assert not (cycle_directory(git_repo, TICKET) / "review-1.json").exists()


# --- R6-SPAWN: guard acquisition failure after spawn -----------------------------------------


def test_tree_guard_failure_after_spawn_terminates_child(
    work_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _spawn_tree_script(work_dir)
    self_file = work_dir / "self.pid"
    child_file = work_dir / "child.pid"
    shim = _make_tree_shim(work_dir, script, self_file, child_file)
    captured: dict[str, int] = {}

    def failing_tree(process: subprocess.Popen) -> None:
        captured["pid"] = process.pid
        raise OSError("injected tree-guard failure")

    monkeypatch.setattr(pi_runner, "_new_process_tree", failing_tree)
    executor = SubprocessExecutor(shim, grace_seconds=2.0)

    with pytest.raises(OSError, match="tree-guard failure"):
        executor.run(
            [shim, "--provider", "deepseek", "--model", "deepseek-v4-pro", "-p"],
            cwd=work_dir,
            log_path=work_dir / "log.txt",
            stdin_text="prompt",
        )

    assert _wait_until_dead(captured["pid"])
    if os.name == "nt":
        assert not self_file.exists()
        assert not child_file.exists()


# --- R6-PERSIST: runner-side persistence and active-phase I/O --------------------------------


def test_reviewer_result_persistence_failure_stops_cycle(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakePi(git_repo)

    def failing_write(path: Path, document: dict) -> None:
        raise OSError("injected persistence failure")

    monkeypatch.setattr(pi_runner, "_write_json", failing_write)

    with pytest.raises(RunnerError, match="failed to persist reviewer result"):
        _run(git_repo, fake)

    assert _state(git_repo) == "STOPPED"
    assert not (cycle_directory(git_repo, TICKET) / "review-1.json").exists()
    manifest = json.loads((cycle_directory(git_repo, TICKET) / "manifest.json").read_text("utf-8"))
    assert manifest["active_agent"] is None


# --- T1: exact ticket-ID file matching -------------------------------------------------------


def test_load_ticket_text_matches_exact_id(work_dir: Path) -> None:
    tickets = work_dir / "Tickets"
    tickets.mkdir()
    for name in ("PDFTR-35.md", "PDFTR-35A.md", "PDFTR-35AB.md", "PDFTR-350.md"):
        (tickets / name).write_text(name, encoding="utf-8")

    for ticket in ("PDFTR-35", "PDFTR-35A", "PDFTR-35AB", "PDFTR-350"):
        assert _load_ticket_text(work_dir, ticket) == f"{ticket}.md"


def test_load_ticket_text_accepts_slug_form(work_dir: Path) -> None:
    tickets = work_dir / "Tickets"
    tickets.mkdir()
    (tickets / "PDFTR-35-real-ticket.md").write_text("base", encoding="utf-8")
    (tickets / "PDFTR-35A-other-ticket.md").write_text("follow-up", encoding="utf-8")

    assert _load_ticket_text(work_dir, "PDFTR-35") == "base"
    assert _load_ticket_text(work_dir, "PDFTR-35A") == "follow-up"


def test_load_ticket_text_fails_on_duplicate_exact_id(work_dir: Path) -> None:
    tickets = work_dir / "Tickets"
    tickets.mkdir()
    (tickets / "PDFTR-35-a.md").write_text("a", encoding="utf-8")
    (tickets / "PDFTR-35-b.md").write_text("b", encoding="utf-8")

    with pytest.raises(RunnerError, match="exactly one ticket file"):
        _load_ticket_text(work_dir, "PDFTR-35")


@pytest.mark.parametrize("ticket", ["../PDFTR-35", "PDFTR/35", "PDFTR-35A-", "PDFTR-0A"])
def test_load_ticket_text_rejects_unsafe_ids(work_dir: Path, ticket: str) -> None:
    with pytest.raises(CycleError):
        _load_ticket_text(work_dir, ticket)
