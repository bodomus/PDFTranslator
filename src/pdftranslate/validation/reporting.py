"""Atomic JSON and Markdown publication for validation evidence."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import BaseModel

from pdftranslate.validation.models import DocumentValidationResult, ValidationSummary


def write_json(model: BaseModel, path: Path) -> Path:
    """Atomically write one UTF-8 JSON model."""
    return _atomic_write(path, model.model_dump_json(indent=2) + "\n")


def write_markdown(
    summary: ValidationSummary,
    documents: tuple[DocumentValidationResult, ...],
    path: Path,
) -> Path:
    """Write a compact compatibility matrix and defect list."""
    lines = [
        "# Real PDF validation summary",
        "",
        f"- Status: **{summary.status}**",
        f"- Dry run: `{str(summary.dry_run).lower()}`",
        f"- Documents: {summary.selected_documents} selected / "
        f"{summary.discovered_documents} discovered",
        f"- Passed: {summary.passed_documents}",
        f"- Failed: {summary.failed_documents}",
        f"- Planned: {summary.planned_documents}",
        f"- Source integrity failures: {summary.source_integrity_failures}",
        f"- Manual reviews pending: {summary.manual_reviews_pending}",
        "",
        "## Compatibility matrix",
        "",
        "| Document | Categories | Status | Pages | OCR | Device | Source unchanged | Manual |",
        "| --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for item in documents:
        categories = ", ".join(item.categories)
        pages = str(item.page_count) if item.page_count is not None else "—"
        device = item.effective_device or item.requested_device
        unchanged = "yes" if item.source_unchanged else "NO"
        lines.append(
            f"| `{item.document_id}` | {categories} | {item.status} | {pages} | "
            f"{item.ocr_decision} | {device} | {unchanged} | {item.manual_review.status} |"
        )

    lines.extend(["", "## Defects", ""])
    if not summary.defects:
        lines.append("No deterministic defects were recorded.")
    else:
        lines.append("| Severity | Document | Stage | Summary | Follow-up |")
        lines.append("| --- | --- | --- | --- | --- |")
        for defect in summary.defects:
            lines.append(
                f"| {defect.severity} | `{defect.document_id}` | {defect.stage} | "
                f"{defect.summary} | {defect.recommended_follow_up} |"
            )

    lines.extend(
        [
            "",
            "## Manual review",
            "",
            "Fill `manual-review-template.json` after checking outputs in PDF-XChange Editor, "
            "then rerun with `--manual-results` to merge the observations.",
            "",
        ]
    )
    return _atomic_write(path, "\n".join(lines))


def _atomic_write(path: Path, content: str) -> Path:
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{destination.stem}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            pending = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        pending.replace(destination)
    finally:
        if pending is not None and pending.exists():
            pending.unlink()
    return destination
