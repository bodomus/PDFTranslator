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


@pytest.mark.parametrize("stale,chars", [(0, 180), (-1, 180), (30, 0), (30, 2001)])
def test_invalid_config(stale: int, chars: int) -> None:
    with pytest.raises(ValueError):
        ProgressConfig(stale_minutes=stale, max_console_chars=chars)


def test_invalid_cli_config_fails_before_initialization(work_dir: Path) -> None:
    assert main(["PDFTR-44", "--progress-stale-minutes", "0"], repo_root=work_dir) == 1
    assert not (work_dir / ".agent-cycle").exists()
