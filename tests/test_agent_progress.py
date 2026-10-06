"""Deterministic local journal and role-capability regressions; no providers/network."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from scripts.agent_progress import (
    JournalMonitor,
    ProgressConfig,
    append_boundary,
    last_activity,
)
from scripts.pi_ticket_cycle import ProgressReporter, RunnerConfig, RunnerError, run_cycle

from tests import test_pi_ticket_cycle as cycle

work_dir = cycle.work_dir
git_repo = cycle.git_repo


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (None, None),
        ("", None),
        ("[10:01] Inspecting scope\n[10:02] Tests PASS\n", "[10:02] Tests PASS"),
        ("[10:01] Inspecting scope\nmalformed\n", "[10:01] Inspecting scope"),
        ("[10:01] Inspecting scope\n[10:02] Partial", "[10:01] Inspecting scope"),
        ("[99:99] Bad time\n", None),
        ("[10:00] \x00 \t\n", None),
        ("[10:01] Tests\x00\x1b\x7f\u202e PASS\n", "[10:01] Tests PASS"),
        ("[10:01] " + "x" * 10000 + "\n", "[10:01] " + "x" * 29 + "..."),
        ("[10:01] Test\r\n", "[10:01] Test"),
    ],
)
def test_parser(work_dir: Path, content: str | None, expected: str | None) -> None:
    path = work_dir / "progress.log"
    if content is not None:
        path.write_text(content, encoding="utf-8", newline="")
    result = last_activity(path, 40)
    assert (result.text if result else None) == expected


def test_bounded_tail_and_io_failure(work_dir: Path) -> None:
    path = work_dir / "progress.log"
    path.write_bytes(b"x" * 100000 + b"\n[12:00] Latest\n")
    assert last_activity(path).text == "[12:00] Latest"  # type: ignore[union-attr]
    assert last_activity(work_dir) is None


def test_heartbeat_update_and_stale_clock(work_dir: Path) -> None:
    path = work_dir / "progress.log"
    output: list[str] = []
    reporter = ProgressReporter("PDFTR-44", output.append)
    monitor = JournalMonitor(path, ProgressConfig())
    reporter.heartbeat("implementer", 60, monitor)
    assert output == ["[PDFTR-44] implementer running... 1m"]
    reporter.heartbeat("implementer", 1799, monitor)
    assert not any("WARNING" in line for line in output)
    reporter.heartbeat("implementer", 1800, monitor)
    assert "WARNING: no new meaningful activity for 30m" in output[-1]
    path.write_text("[12:00] Focused tests\n", encoding="utf-8")
    reporter.heartbeat("implementer", 1801, monitor)
    assert output[-1].endswith("last: [12:00] Focused tests")
    with path.open("a", encoding="utf-8") as stream:
        stream.write("[12:01] Tests PASS\n")
    reporter.heartbeat("implementer", 2000, monitor)
    assert output[-1].endswith("last: [12:01] Tests PASS")
    reporter.heartbeat("implementer", 3799, monitor)
    assert "WARNING" not in output[-1]
    reporter.heartbeat("implementer", 3800, monitor)
    assert "WARNING" in output[-1]


def test_new_identical_or_truncated_entry_counts_as_activity(work_dir: Path) -> None:
    path = work_dir / "progress.log"
    line = "[12:01] " + "x" * 300 + "\n"
    path.write_text(line, encoding="utf-8")
    monitor = JournalMonitor(path, ProgressConfig())
    with path.open("a", encoding="utf-8") as stream:
        stream.write(line)
    assert monitor.observe(1800)[1] == 0
    with path.open("a", encoding="utf-8") as stream:
        stream.write("[12:01] " + "x" * 299 + "y\n")
    assert monitor.observe(3600)[1] == 0


def test_boundary_preserves_partial_previous_history(work_dir: Path) -> None:
    path = work_dir / "progress.log"
    path.write_text("[12:00] Previous\n[12:01] interrupted", encoding="utf-8")
    old = path.read_bytes()
    append_boundary(path, "Resumed implementer execution (attempt/round 2)")
    assert path.read_bytes().startswith(old)
    assert "Resumed implementer" in last_activity(path).text  # type: ignore[union-attr]


@pytest.mark.parametrize("role", ["implementer", "reviewer"])
@pytest.mark.parametrize("cancel", [False, True])
def test_failure_keeps_journal_and_reports_activity(
    git_repo: Path, role: str, cancel: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = cycle.FakePi(git_repo)
    original = getattr(fake, f"_{role}")

    def fail() -> cycle.CommandResult:
        journal = git_repo / ".agent-cycle" / cycle.TICKET / f"{role}-progress.log"
        with journal.open("a", encoding="utf-8") as stream:
            stream.write("[09:11] Network blocked\n")
        return original()

    setattr(fake, f"_{role}", fail)
    setattr(fake, f"cancel_{role}", cancel)
    setattr(fake, f"{role}_exit", 1)
    with pytest.raises(RunnerError, match="cancelled" if cancel else "exited with code 1"):
        cycle._run(git_repo, fake)
    output = capsys.readouterr().out
    assert "Last activity: [09:11] Network blocked" in output
    assert f"Progress log: .agent-cycle/{cycle.TICKET}/{role}-progress.log" in output
    manifest = json.loads((git_repo / ".agent-cycle" / cycle.TICKET / "manifest.json").read_text())
    assert manifest["state"] == "STOPPED"
    assert last_activity(git_repo / ".agent-cycle" / cycle.TICKET / f"{role}-progress.log")


def test_role_paths_and_retry_boundaries(git_repo: Path) -> None:
    fake = cycle.FakePi(git_repo)
    fake.verdicts = ["CHANGES_REQUIRED", "PASS"]
    fake.findings = [[cycle._finding("R1")], []]
    cycle._run(git_repo, fake)
    for command, prompt in fake.invocations:
        role = command[command.index("--progress-role") + 1]
        assert f"{role}-progress.log" in prompt
        assert "Use progress_append(message) only" in prompt
        assert command[command.index("--progress-ticket") + 1] == cycle.TICKET
    for role in ["implementer", "reviewer"]:
        text = (git_repo / ".agent-cycle" / cycle.TICKET / f"{role}-progress.log").read_text()
        assert f"Started {role} execution (attempt/round 1)" in text
        assert f"Resumed {role} execution (attempt/round 2)" in text


def test_disabled_progress(git_repo: Path) -> None:
    fake = cycle.FakePi(git_repo)
    run_cycle(
        git_repo,
        cycle.TICKET,
        executor=fake,
        config=RunnerConfig(progress=ProgressConfig(enabled=False)),
    )
    assert not list((git_repo / ".agent-cycle" / cycle.TICKET).glob("*-progress.log"))
    for command, prompt in fake.invocations:
        assert "--progress-role" not in command
        assert "Operational progress" not in prompt


def test_append_capability_isolated_and_safe(work_dir: Path) -> None:
    directory = work_dir / ".agent-cycle" / "PDFTR-44"
    directory.mkdir(parents=True)
    implementer = directory / "implementer-progress.log"
    implementer.write_text("[12:00] Existing\n", encoding="utf-8")
    script = r"""
import fs from 'node:fs';
import { appendProgress } from './scripts/agent_progress/journal.mjs';
const root = process.argv[1];
for (const message of ['Tests PASS', 'Review PASS']) {
  appendProgress(root, 'PDFTR-44', 'reviewer', {message}, new Date('2026-01-01T13:23:00Z'));
}
for (const params of [
  {message:'overwrite', path:'implementer-progress.log'},
  {message:'multiple\nlines'}, {message:'\u001b[31m'}, {message:'x'.repeat(241)},
  {message:'Authorization: Bearer secret'}, {message:'https://host/?token=secret'},
]) {
  let rejected = false;
  try { appendProgress(root, 'PDFTR-44', 'reviewer', params); } catch { rejected = true; }
  if (!rejected) throw new Error('unsafe entry accepted');
}
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(work_dir)],
        cwd=cycle.REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert implementer.read_text() == "[12:00] Existing\n"
    assert (directory / "reviewer-progress.log").read_text() == (
        "[13:23] Tests PASS\n[13:23] Review PASS\n"
    )
    assert sorted(p.name for p in directory.iterdir()) == [
        "implementer-progress.log",
        "reviewer-progress.log",
    ]


def test_extension_uses_runner_binding_and_guard(work_dir: Path) -> None:
    script = r"""
import fs from 'node:fs';
let source = fs.readFileSync('./scripts/agent_progress/extension.ts', 'utf8')
 .replace(/^import .*;\r?\n/gm, '').replace('export default function', 'function')
 .replace(': ExtensionAPI', '').replace(/: string/g, '');
const Type = new Proxy({}, {get: () => (...args) => args});
const handlers = {}; let tool; const calls = [];
const flags = {'progress-ticket':'PDFTR-44','progress-role':'reviewer'};
const pi = {registerFlag: () => {}, getFlag: name => flags[name],
 on: (name, cb) => handlers[name] = cb, registerTool: value => tool = value};
const factory = new Function('Type','appendProgress','return (' + source + ')');
factory(Type, (...args) => calls.push(args))(pi);
let failed = false;
try { await tool.execute('id', {message:'Review PASS'}); } catch { failed = true; }
if (!failed) throw new Error('unbound tool accepted');
handlers.session_start({}, {cwd:process.argv[1]});
await tool.execute('id', {message:'Review PASS'});
console.log(JSON.stringify(calls));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(work_dir)],
        cwd=cycle.REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        [str(work_dir), "PDFTR-44", "reviewer", {"message": "Review PASS"}]
    ]
