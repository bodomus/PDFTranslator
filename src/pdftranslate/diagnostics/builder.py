"""Convert pipeline evidence into stable diagnostic reports."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

from pdftranslate.diagnostics.models import (
    BlockDiagnostic,
    DiagnosticCode,
    DiagnosticFinding,
    PageDiagnostic,
    ReportSummary,
    TranslationReport,
)
from pdftranslate.domain.document import ExtractedDocument, TranslationStatistics
from pdftranslate.rendering.models import RenderResult


def build_success_report(
    *,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    input_path: Path,
    output_path: Path,
    translated: ExtractedDocument,
    render: RenderResult | None,
    ocr_pages: tuple[int, ...],
    ocr_warnings: tuple[str, ...],
    elapsed_seconds: float,
    stage_durations: dict[str, float],
    peak_ram_bytes: int | None,
    include_text: bool,
    debug_layout_path: Path | None,
    block_evidence: dict[str, tuple[int | None, str]],
) -> TranslationReport:
    statistics = _statistics(translated)
    render_by_id = {item.block_id: item for item in render.blocks} if render else {}
    findings: list[DiagnosticFinding] = [
        DiagnosticFinding(
            code=DiagnosticCode.OCR_LOW_TEXT_GAIN, severity="warning", stage="ocr", message=warning
        )
        for warning in ocr_warnings
    ]
    if render is not None:
        findings.extend(
            DiagnosticFinding(
                code=DiagnosticCode.RENDER_WARNING,
                severity="warning",
                stage="render",
                message=warning,
            )
            for warning in render.warnings
        )
    pages: list[PageDiagnostic] = []
    for page in translated.pages:
        blocks: list[BlockDiagnostic] = []
        for block in page.text_blocks:
            layout = render_by_id.get(block.id)
            codes: list[DiagnosticCode] = []
            state = "unknown"
            if layout is not None:
                state = "rendered"
                if layout.font_size is not None and layout.font_size < layout.initial_font_size:
                    codes.append(DiagnosticCode.FONT_REDUCED)
                if layout.expanded:
                    state = "expanded"
                    codes.append(DiagnosticCode.BLOCK_EXPANDED)
                if layout.overflow:
                    state = "overflow"
                    codes.append(DiagnosticCode.BLOCK_OVERFLOW)
                for code in codes:
                    findings.append(
                        DiagnosticFinding(
                            code=code,
                            severity="error"
                            if code is DiagnosticCode.BLOCK_OVERFLOW
                            else "warning",
                            stage="render",
                            message=f"Block {block.id}: {code.value.lower()}",
                            page_number=page.page_number,
                            block_id=block.id,
                        )
                    )
            blocks.append(
                BlockDiagnostic(
                    block_id=block.id,
                    page_number=page.page_number,
                    source_bbox=block.bbox,
                    final_bbox=layout.final_bbox if layout else None,
                    initial_font_size=layout.initial_font_size if layout else None,
                    final_font_size=layout.font_size if layout else None,
                    fitting_attempts=layout.fitting_attempts if layout else None,
                    segmentation_count=block_evidence.get(block.id, (None, "unknown"))[0],
                    cache_status=block_evidence.get(block.id, (None, "unknown"))[1],  # type: ignore[arg-type]
                    final_state=state,  # type: ignore[arg-type]
                    warning_codes=tuple(codes),
                    source_text=block.text if include_text else None,
                    translated_text=block.translated_text if include_text else None,
                )
            )
        page_codes = (
            (DiagnosticCode.READING_ORDER_AMBIGUOUS,)
            if any("reading order" in warning.casefold() for warning in page.warnings)
            else ()
        )
        for code in page_codes:
            findings.append(
                DiagnosticFinding(
                    code=code,
                    severity="warning",
                    stage="extract",
                    message="Reading order is ambiguous",
                    page_number=page.page_number,
                )
            )
        pages.append(
            PageDiagnostic(
                page_number=page.page_number,
                classification=page.classification.value,
                width=page.width,
                height=page.height,
                ocr_status="processed" if page.page_number in ocr_pages else "not_processed",
                warning_codes=page_codes,
                blocks=tuple(blocks),
            )
        )
    by_type = Counter(page.classification.value for page in translated.pages)
    return TranslationReport(
        run_id=run_id,
        status="success",
        started_at=started_at,
        finished_at=finished_at,
        input_path=str(input_path),
        output_path=str(output_path),
        summary=ReportSummary(
            page_count=translated.page_count,
            pages_by_type=dict(sorted(by_type.items())),
            blocks_extracted=statistics.total_blocks,
            blocks_translated=statistics.completed_blocks,
            blocks_skipped=statistics.skipped_blocks,
            cache_hits=statistics.cache_hits,
            cache_misses=statistics.cache_misses,
            translated_segments=statistics.translated_segments,
            ocr_pages=len(ocr_pages),
            font_reductions=render.font_reductions if render else 0,
            expanded_blocks=render.expanded_blocks if render else 0,
            overflow_blocks=render.overflow_blocks if render else 0,
            input_size=translated.source.file_size,
            output_size=output_path.stat().st_size,
            elapsed_seconds=elapsed_seconds,
            stage_durations=stage_durations,
            peak_ram_bytes=peak_ram_bytes,
            selected_font=str(render.font_path) if render else None,
        ),
        pages=tuple(pages),
        findings=tuple(findings),
        text_included=include_text,
        debug_layout_path=str(debug_layout_path) if debug_layout_path else None,
    )


def build_failure_report(
    *,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    input_path: Path,
    output_path: Path,
    failed_stage: str,
    message: str,
    input_size: int,
    elapsed_seconds: float,
    stage_durations: dict[str, float],
    peak_ram_bytes: int | None,
    interrupted: bool,
) -> TranslationReport:
    return TranslationReport(
        run_id=run_id,
        status="interrupted" if interrupted else "failed",
        started_at=started_at,
        finished_at=finished_at,
        input_path=str(input_path),
        output_path=str(output_path),
        failed_stage=failed_stage,
        summary=ReportSummary(
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
            input_size=input_size,
            output_size=0,
            elapsed_seconds=elapsed_seconds,
            stage_durations=stage_durations,
            peak_ram_bytes=peak_ram_bytes,
        ),
        pages=(),
        findings=(
            DiagnosticFinding(
                code=(
                    DiagnosticCode.OUTPUT_VALIDATION_FAILED
                    if failed_stage == "validate"
                    else DiagnosticCode.PIPELINE_STAGE_FAILED
                ),
                severity="error",
                stage=failed_stage,
                message=message,
            ),
        ),
    )


def _statistics(document: ExtractedDocument) -> TranslationStatistics:
    assert document.translation is not None
    return document.translation.statistics
