"""Atomic JSON and self-contained offline HTML diagnostic reports."""

from __future__ import annotations

import html
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from pdftranslate.diagnostics.models import TranslationReport

ReportFormat = Literal["json", "html", "both"]


def write_report(
    report: TranslationReport,
    directory: Path,
    *,
    report_format: ReportFormat = "both",
) -> tuple[Path, ...]:
    """Atomically publish selected report formats below one directory."""
    if report_format not in {"json", "html", "both"}:
        raise ValueError("report format must be one of: json, html, both")
    root = directory.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if report_format in {"json", "both"}:
        target = root / "translation-report.json"
        _atomic_write(target, report.model_dump_json(indent=2) + "\n")
        written.append(target)
    if report_format in {"html", "both"}:
        target = root / "translation-report.html"
        _atomic_write(target, _render_html(report))
        written.append(target)
    return tuple(written)


def _render_html(report: TranslationReport) -> str:
    payload = html.escape(report.model_dump_json(indent=2))
    title = html.escape(f"PDFTranslate report — {report.status}")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{title}</title><style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:2rem;line-height:1.45;color:#18212f}}
h1{{margin-bottom:.25rem}} .status{{font-weight:700}} pre{{white-space:pre-wrap;background:#f3f5f7;
padding:1rem;border-radius:.5rem;overflow:auto}} table{{border-collapse:collapse}}
td,th{{border:1px solid #ccd3db;padding:.4rem .65rem;text-align:left}}
</style></head><body><h1>{title}</h1>
<p class="status">Run {html.escape(report.run_id)} · {html.escape(report.status)}</p>
<table><tr><th>Pages</th><td>{report.summary.page_count}</td></tr>
<tr><th>Blocks</th><td>{report.summary.blocks_translated}/{report.summary.blocks_extracted}</td></tr>
<tr><th>Cache</th><td>{report.summary.cache_hits} hit / {report.summary.cache_misses} miss</td></tr>
<tr><th>Overflow</th><td>{report.summary.overflow_blocks}</td></tr></table>
<h2>Machine-readable details</h2><pre>{payload}</pre></body></html>
"""


def _atomic_write(path: Path, payload: str) -> None:
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
