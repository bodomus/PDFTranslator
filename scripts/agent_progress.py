"""Non-authoritative, bounded operational journal diagnostics for Pi roles."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_LINE = re.compile(r"^\[(?:[01]\d|2[0-3]):[0-5]\d\] (.+)$")
TAIL_BYTES = 64 * 1024


@dataclass(frozen=True)
class ProgressConfig:
    enabled: bool = True
    stale_minutes: int = 30
    max_console_chars: int = 180

    def __post_init__(self) -> None:
        if self.stale_minutes < 1 or not 20 <= self.max_console_chars <= 2000:
            raise ValueError("progress requires stale_minutes >= 1 and console chars 20..2000")


@dataclass(frozen=True)
class Activity:
    text: str
    identity: tuple[int, str]


def last_activity(path: Path, max_chars: int = 180) -> Activity | None:
    """Read only a bounded tail; ignore incomplete/malformed lines and I/O failures."""
    try:
        if path.is_symlink() or not path.is_file():
            return None
        with path.open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            start = max(0, size - TAIL_BYTES)
            stream.seek(start)
            tail = stream.read(TAIL_BYTES)
    except OSError:
        return None
    # Split on LF only: embedded control characters must not become journal boundaries.
    lines = tail.split(b"\n")[:-1]
    if start:
        start += len(lines.pop(0)) + 1 if lines else 0
    offset = start + sum(len(line) + 1 for line in lines)
    for raw in reversed(lines):
        offset -= len(raw) + 1
        decoded = raw.decode("utf-8", errors="replace").rstrip("\r")
        if not _LINE.fullmatch(decoded):
            continue
        safe = "".join(" " if unicodedata.category(c).startswith("C") else c for c in decoded)
        safe = " ".join(safe.split())
        if not safe[8:]:
            continue
        if len(safe) > max_chars:
            safe = safe[: max_chars - 3] + "..."
        return Activity(safe, (offset, hashlib.sha256(raw).hexdigest()))
    return None


def append_boundary(path: Path, message: str) -> None:
    """Runner lifecycle boundary only; never truncate previous execution history."""
    for location in (path.parent.parent, path.parent, path):
        if location.is_symlink():
            raise OSError("Redirected progress path is unsupported")
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise OSError("Redirected progress journal is unsupported")
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        # Separate a previous interrupted write from the new valid boundary.
        stream.write(f"\n[{datetime.now(UTC):%H:%M}] {message}\n")


def progress_policy(path: Path | None) -> str:
    if path is None:
        return ""
    return (
        "\n## Operational progress (diagnostic exception to file-writing restrictions)\n"
        f"Maintain a concise operational progress log at: {path}\n"
        "Use progress_append(message) only; the harness binds it to your own journal.\n"
        "This is NOT a reasoning journal or authoritative state. UTC timestamps are automatic.\n"
        "Append short factual milestones: major steps started/completed, tests started/result,\n"
        "meaningful blockers, external failures, commit/push/completion (usually 5–20 lines).\n"
        "No chain-of-thought, detailed reasoning, raw prompts, every file read/minor edit,\n"
        "periodic heartbeat, report duplication, secrets, credentials, tokens, auth headers,\n"
        "OAuth codes, environment dumps or secret-bearing URLs. Summarize failures safely.\n"
        "One short line per event. Reviewer: fewer entries; this does not permit repository\n"
        "mutations or replace the stdout review verdict. Never write another role's journal.\n"
    )


class JournalMonitor:
    """Per-execution stale clock, measured from locally observed valid activity changes."""

    def __init__(self, path: Path, config: ProgressConfig) -> None:
        self.path = path
        self.config = config
        current = last_activity(path, config.max_console_chars)
        self.identity = current.identity if current else None
        self.changed_at = 0.0

    def observe(self, elapsed: float) -> tuple[str | None, float]:
        current = last_activity(self.path, self.config.max_console_chars)
        identity = current.identity if current else None
        if identity is not None and identity != self.identity:
            self.identity = identity
            self.changed_at = elapsed
        return current.text if current else None, max(0.0, elapsed - self.changed_at)
