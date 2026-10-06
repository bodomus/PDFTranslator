"""Progress diagnostics never turn console encoding limits into process failures."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts import pi_ticket_cycle as runner
from scripts.agent_progress import JournalMonitor, ProgressConfig

from tests import test_pi_ticket_cycle as cycle

work_dir = cycle.work_dir
git_repo = cycle.git_repo


@pytest.mark.parametrize("encoding", ["cp1251", "ascii"])
@pytest.mark.parametrize("invalid_bytes", [False, True])
def test_heartbeat_encoding_fallback(
    work_dir: Path, monkeypatch: pytest.MonkeyPatch, encoding: str, invalid_bytes: bool
) -> None:
    journal = work_dir / "progress.log"
    message = b"Tests \xff passed" if invalid_bytes else "Tests ✓ Привет passed".encode()
    journal.write_bytes(b"[12:01] " + message + b"\x1b\x00\n")
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding=encoding, errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    monitor = JournalMonitor(journal, ProgressConfig())
    runner.ProgressReporter(cycle.TICKET).heartbeat("reviewer", 300, monitor)
    output = raw.getvalue().decode(encoding)
    assert "reviewer running... 5m - last: [12:01] Tests" in output
    assert "Tests ?" in output
    if not invalid_bytes:
        assert ("Привет" if encoding == "cp1251" else "??????") in output
    assert "passed" in output
    assert "\x1b" not in output and "\x00" not in output


@pytest.mark.parametrize("encoding", ["cp1251", "ascii"])
def test_encoding_fallback_does_not_interrupt_child(
    work_dir: Path, monkeypatch: pytest.MonkeyPatch, encoding: str
) -> None:
    journal = work_dir / "progress.log"
    journal.write_text("[12:01] Running tests ✓\n", encoding="utf-8")
    monitor = JournalMonitor(journal, ProgressConfig())
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding=encoding, errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)

    class Child:
        returncode: int | None = None
        communications = 0

        def communicate(self, **_kwargs: object) -> tuple[str, str]:
            self.communications += 1
            if self.communications == 1:
                raise subprocess.TimeoutExpired("fake-pi", 300)
            self.returncode = 0
            return "complete result", ""

        def poll(self) -> int | None:
            return self.returncode

    child = Child()
    cleanup: list[int] = []

    class Tree:
        def terminate(self, _grace: float) -> bool:
            cleanup.append(child.communications)
            return True

        def close(self) -> None:
            pass

    monkeypatch.setattr(runner, "resolve_executable", lambda _name: "fake-pi.exe")
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *_args, **_kwargs: child)
    monkeypatch.setattr(runner, "_new_process_tree", lambda _child: Tree())
    result = runner.SubprocessExecutor().run(
        ["fake-pi"],
        cwd=work_dir,
        log_path=work_dir / "pi.log",
        stdin_text="prompt",
        heartbeat=lambda elapsed: runner.ProgressReporter(cycle.TICKET).heartbeat(
            "reviewer", elapsed, monitor
        ),
    )
    assert result == runner.CommandResult(0, "complete result", "")
    assert child.communications == 2
    assert cleanup == [2]  # Normal completion cleanup only, never heartbeat failure cleanup.
    assert "Running tests ?" in raw.getvalue().decode(encoding)


@pytest.mark.parametrize("encoding", ["cp1251", "ascii"])
@pytest.mark.parametrize("role", ["implementer", "reviewer"])
def test_original_role_failure_survives_last_activity_output(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, encoding: str, role: str
) -> None:
    fake = cycle.FakePi(git_repo)
    original = getattr(fake, f"_{role}")

    def fail() -> runner.CommandResult:
        journal = git_repo / ".agent-cycle" / cycle.TICKET / f"{role}-progress.log"
        with journal.open("ab") as stream:
            stream.write("[09:11] Network blocked ✓ ".encode() + b"\xff\n")
        return original()

    setattr(fake, f"_{role}", fail)
    setattr(fake, f"{role}_exit", 1)
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding=encoding, errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    with pytest.raises(runner.RunnerError, match=f"{role} exited with code 1"):
        cycle._run(git_repo, fake)
    output = raw.getvalue().decode(encoding)
    assert "Last activity: [09:11] Network blocked ? ?" in output
    assert f"Progress log: .agent-cycle/{cycle.TICKET}/{role}-progress.log" in output
    manifest = json.loads((git_repo / ".agent-cycle" / cycle.TICKET / "manifest.json").read_text())
    assert manifest["state"] == "STOPPED"
    assert f"{role} exited with code 1" in manifest["stop_reason"]


@pytest.mark.parametrize("encoding", ["cp1251", "ascii"])
def test_main_reports_original_error_with_safe_stderr(
    work_dir: Path, monkeypatch: pytest.MonkeyPatch, encoding: str
) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise runner.RunnerError("Original process failure ✓")

    monkeypatch.setattr(runner, "run_cycle", fail)
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding=encoding, errors="strict")
    monkeypatch.setattr(sys, "stderr", stream)
    assert runner.main([cycle.TICKET], repo_root=work_dir) == 1
    assert "ERROR: Original process failure ?" in raw.getvalue().decode(encoding)


def test_argparse_diagnostics_use_encoding_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="ascii", errors="strict")
    monkeypatch.setattr(sys, "stderr", stream)
    with pytest.raises(SystemExit) as error:
        runner.main([cycle.TICKET, "--unknown-✓"])
    assert error.value.code == 2
    assert "unrecognized arguments: --unknown-?" in raw.getvalue().decode("ascii")


def test_console_output_failure_cannot_mask_original_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenConsole(io.StringIO):
        def write(self, _text: str) -> int:
            raise OSError("console unavailable")

    monkeypatch.setattr(sys, "stdout", BrokenConsole())
    monkeypatch.setattr(sys, "stderr", BrokenConsole())
    runner.ProgressReporter(cycle.TICKET).heartbeat("reviewer", 300)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise runner.RunnerError("Original process failure")

    monkeypatch.setattr(runner, "run_cycle", fail)
    assert runner.main([cycle.TICKET]) == 1


@pytest.mark.parametrize("encoding", ["cp1251", "ascii"])
def test_original_process_exception_survives_terminal_diagnostics(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, encoding: str
) -> None:
    fake = cycle.FakePi(git_repo)

    def fail() -> runner.CommandResult:
        journal = git_repo / ".agent-cycle" / cycle.TICKET / "implementer-progress.log"
        with journal.open("a", encoding="utf-8") as stream:
            stream.write("[09:11] Original failure ✓\n")
        raise RuntimeError("Original process exception ✓")

    fake._implementer = fail
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding=encoding, errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    with pytest.raises(
        runner.RunnerError, match="Pi process failure: Original process exception ✓"
    ):
        cycle._run(git_repo, fake)
    assert "Last activity: [09:11] Original failure ?" in raw.getvalue().decode(encoding)


@pytest.mark.parametrize("encoding", ["cp1251", "ascii"])
@pytest.mark.parametrize("state", ["PASSED", "STOPPED"])
def test_final_report_uses_encoding_fallback(
    monkeypatch: pytest.MonkeyPatch, encoding: str, state: str
) -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding=encoding, errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    role = runner.RoleConfig("provider", "model ✓")
    outcome = runner.RunOutcome(
        ticket=cycle.TICKET,
        state=state,
        branch="ticket-branch",
        implementation_sha="a" * 40,
        review_rounds=1,
        implementer=role,
        reviewer=role,
        stop_reason="Original failure ✓",
    )
    runner._report(outcome)
    output = raw.getvalue().decode(encoding)
    assert ("model ?" if state == "PASSED" else "Original failure ?") in output
    assert "HUMAN REVIEW" in output


def test_console_fallback_preserves_activity_character_limit(
    work_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal = work_dir / "progress.log"
    journal.write_text("[12:01] " + "✓" * 300 + "\n", encoding="utf-8")
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="ascii", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    monitor = JournalMonitor(journal, ProgressConfig(max_console_chars=40))
    runner.ProgressReporter(cycle.TICKET).heartbeat("reviewer", 300, monitor)
    text = raw.getvalue().decode("ascii").split(" - last: ", 1)[1].rstrip("\r\n")
    assert text == "[12:01] " + "?" * 29 + "..."
    assert len(text) == 40
