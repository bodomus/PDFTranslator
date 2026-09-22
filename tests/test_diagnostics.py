from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pdftranslate.diagnostics import (
    BlockDiagnostic,
    DiagnosticCode,
    ReportSummary,
    TranslationReport,
    write_report,
)
from pdftranslate.domain.text_block import BoundingBox
from pdftranslate.pipeline import PipelineOptions


def test_diagnostic_codes_are_stable() -> None:
    assert {item.value for item in DiagnosticCode} == {
        "READING_ORDER_AMBIGUOUS",
        "TRANSLATION_TOKEN_MISMATCH",
        "FONT_REDUCED",
        "BLOCK_EXPANDED",
        "BLOCK_OVERFLOW",
        "OCR_LOW_TEXT_GAIN",
        "OUTPUT_VALIDATION_FAILED",
        "PIPELINE_STAGE_FAILED",
        "RENDER_WARNING",
        "REPEATED_ELEMENT_AMBIGUOUS",
        "GLOSSARY_CONFLICT",
        "GLOSSARY_MATCH_AMBIGUOUS",
        "GLOSSARY_TARGET_MISSING",
        "GLOSSARY_PRESERVE_VIOLATION",
        "GLOSSARY_PLACEHOLDER_LEAK",
        "GLOSSARY_ENTRY_UNUSED",
    }


def test_report_options_validate_format_and_text_opt_in() -> None:
    base = {"input_path": Path("input.pdf"), "output_path": Path("output.pdf")}
    with pytest.raises(ValueError, match="report format"):
        PipelineOptions(**base, report=True, report_format="xml")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="requires --report"):
        PipelineOptions(**base, include_report_text=True)


def test_report_options_do_not_change_translation_artifact_identity() -> None:
    base = PipelineOptions(input_path=Path("input.pdf"), output_path=Path("output.pdf"))
    diagnostics = PipelineOptions(
        input_path=Path("input.pdf"),
        output_path=Path("output.pdf"),
        report=True,
        report_format="html",
        report_dir=Path("reports"),
        debug_layout=True,
    )

    assert diagnostics.identity_values() == base.identity_values()
    repeated_off = PipelineOptions(
        input_path=Path("input.pdf"),
        output_path=Path("output.pdf"),
        repeated_elements="off",
    )
    assert repeated_off.identity_values() != base.identity_values()


def test_footnote_diagnostic_preserves_occurrence_identity() -> None:
    diagnostic = BlockDiagnostic(
        block_id="footnote-shared-id",
        source_occurrence_index=7,
        page_number=3,
        source_bbox=BoundingBox(x0=40, y0=400, x1=260, y1=450),
        final_state="rendered",
        render_strategy="reflow_footnote",
        target_pages=(3, 4),
        segment_count=2,
        continuation_count=1,
        text_offsets=((0, 20), (20, 38)),
    )

    assert diagnostic.source_occurrence_index == 7
    assert diagnostic.render_strategy == "reflow_footnote"
    assert diagnostic.target_pages == (3, 4)


def test_report_writer_never_replaces_an_existing_artifact(tmp_path: Path) -> None:
    summary = ReportSummary(
        page_count=0,
        pages_by_type={},
        blocks_extracted=0,
        blocks_translated=0,
        blocks_skipped=0,
        cache_hits=0,
        cache_misses=0,
        translated_segments=0,
        ocr_pages=0,
        font_reductions=0,
        expanded_blocks=0,
        overflow_blocks=0,
        input_size=1,
        output_size=1,
        elapsed_seconds=0.1,
        stage_durations={},
    )
    assert summary.footnotes_reflowed == 0
    assert summary.footnote_segments == 0
    assert summary.footnote_continuation_pages == 0
    assert summary.footnote_unplaced_text_count == 0
    populated = summary.model_copy(
        update={
            "footnotes_reflowed": 3,
            "footnote_segments": 5,
            "footnote_continuation_pages": 2,
            "footnote_unplaced_text_count": 0,
        }
    )
    first = TranslationReport(
        run_id="first",
        status="success",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        input_path="input.pdf",
        output_path="output.pdf",
        summary=summary,
        pages=(),
    )
    second = first.model_copy(update={"run_id": "second"})

    (path,) = write_report(first, tmp_path, report_format="json")
    original = path.read_bytes()

    with pytest.raises(FileExistsError, match="already exists"):
        write_report(second, tmp_path, report_format="json")

    assert path.read_bytes() == original
    assert '"run_id": "first"' in path.read_text("utf-8")

    html_report = first.model_copy(update={"run_id": "html", "summary": populated})
    (html_path,) = write_report(html_report, tmp_path / "html", report_format="html")
    html = html_path.read_text("utf-8")
    assert "Footnotes reflowed</th><td>3" in html
    assert "Footnote segments</th><td>5" in html
    assert "Footnote continuation pages</th><td>2" in html
