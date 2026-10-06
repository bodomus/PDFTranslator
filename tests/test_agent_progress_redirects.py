"""Reject hard-linked diagnostic writes without affecting repository files."""

import os
import subprocess
from pathlib import Path

import pytest
from scripts.agent_progress import ProgressConfig, append_boundary
from scripts.pi_ticket_cycle import main

from tests import test_pi_ticket_cycle as cycle

work_dir = cycle.work_dir


def test_hardlinked_journal_rejected(work_dir: Path) -> None:
    directory = work_dir / ".agent-cycle" / "PDFTR-44"
    directory.mkdir(parents=True)
    original = directory / "implementer-progress.log"
    original.write_text("[12:00] Original\n", encoding="utf-8")
    linked = directory / "reviewer-progress.log"
    os.link(original, linked)
    with pytest.raises(OSError, match="Redirected"):
        append_boundary(linked, "Resumed reviewer")
    script = """
import { appendProgress } from './scripts/agent_progress/journal.mjs';
try {
 appendProgress(process.argv[1], 'PDFTR-44', 'reviewer', {message:'Review PASS'});
 process.exit(1);
} catch { process.exit(0); }
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(work_dir)],
        cwd=cycle.REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert original.read_text() == "[12:00] Original\n"


@pytest.mark.parametrize("target_exists", [False, True])
def test_symbolic_journal_rejected_even_when_dangling(work_dir: Path, target_exists: bool) -> None:
    directory = work_dir / ".agent-cycle" / "PDFTR-44"
    directory.mkdir(parents=True)
    target = work_dir / "repository-file.txt"
    if target_exists:
        target.write_text("Unchanged repository content\n", encoding="utf-8")
    journal = directory / "reviewer-progress.log"
    try:
        journal.symlink_to(target)
    except OSError as error:
        if os.name == "nt" and error.winerror == 1314:
            pytest.skip("Windows symlink privilege or Developer Mode required")
        raise
    script = """
import { appendProgress } from './scripts/agent_progress/journal.mjs';
try {
 appendProgress(process.argv[1], 'PDFTR-44', 'reviewer', {message:'Review complete'});
 process.exitCode = 1;
} catch (error) {
 if (!error.message.includes('Redirected progress journal')) throw error;
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
    assert journal.is_symlink()
    if target_exists:
        assert target.read_text() == "Unchanged repository content\n"
    else:
        assert not target.exists()
    assert sorted(p.name for p in directory.iterdir()) == ["reviewer-progress.log"]


def test_absent_and_regular_journal_paths_remain_append_only(work_dir: Path) -> None:
    directory = work_dir / ".agent-cycle" / "PDFTR-44"
    directory.mkdir(parents=True)
    script = """
import { appendProgress } from './scripts/agent_progress/journal.mjs';
for (const message of ['First milestone','Second milestone']) {
 appendProgress(process.argv[1], 'PDFTR-44', 'reviewer', {message},
   new Date('2026-01-01T13:23:00Z'));
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
    assert (directory / "reviewer-progress.log").read_text() == (
        "[13:23] First milestone\n[13:23] Second milestone\n"
    )


@pytest.mark.parametrize("stale,chars", [(0, 180), (-1, 180), (30, 0), (30, 2001)])
def test_invalid_config(stale: int, chars: int) -> None:
    with pytest.raises(ValueError):
        ProgressConfig(stale_minutes=stale, max_console_chars=chars)


def test_invalid_cli_config_fails_before_initialization(work_dir: Path) -> None:
    assert main(["PDFTR-44", "--progress-stale-minutes", "0"], repo_root=work_dir) == 1
    assert not (work_dir / ".agent-cycle").exists()
