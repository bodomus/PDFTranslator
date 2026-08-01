from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pdftranslate.diagnostics import (
    DiagnosticCode,
    ReportSummary,
    TranslationReport,
    write_report,
)
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
