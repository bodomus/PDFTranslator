"""Atomic UTF-8 batch report publication."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from pdftranslate.batch.models import BatchReport


def write_batch_report(report: BatchReport, path: Path) -> Path:
    """Atomically replace the selected JSON report after a complete write."""
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{destination.stem}.",
            suffix=".tmp.json",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            pending = Path(temporary.name)
            temporary.write(report.model_dump_json(indent=2))
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        pending.replace(destination)
    finally:
        if pending is not None and pending.exists():
            pending.unlink()
    return destination
