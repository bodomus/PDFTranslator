from __future__ import annotations

from pathlib import Path

import pytest

from pdftranslate.diagnostics import DiagnosticCode
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
