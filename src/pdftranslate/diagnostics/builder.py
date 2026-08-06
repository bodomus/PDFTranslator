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
from pdftranslate.reconstruction import DecisionAction
from pdftranslate.rendering.models import RenderResult
from pdftranslate.repeated import (
    RepeatedBlockClassification,
    RepeatedElementKind,
    RepeatedElementPolicy,
)


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
    glossary = translated.translation.glossary if translated.translation is not None else None
    glossary_by_id = (
        {item.paragraph_id: item for item in glossary.paragraphs} if glossary is not None else {}
    )
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
    if translated.reconstruction is not None:
        findings.extend(
            DiagnosticFinding(
                code=DiagnosticCode.READING_ORDER_AMBIGUOUS,
                severity="warning",
                stage="extract",
                message=(
                    f"Ambiguous boundary between {decision.previous_fragment_id} "
                    f"and {decision.current_fragment_id}: "
                    + ", ".join(reason.value for reason in decision.reasons)
                ),
                page_number=decision.page_number,
                block_id=decision.current_fragment_id,
            )
            for decision in translated.reconstruction.decisions
            if decision.action is DecisionAction.AMBIGUOUS
        )
    if translated.repeated_elements is not None:
        findings.extend(
            DiagnosticFinding(
                code=DiagnosticCode.REPEATED_ELEMENT_AMBIGUOUS,
                severity="warning",
                stage="extract",
                message=(f"Ambiguous repeated element {item.block_id}: " + ", ".join(item.reasons)),
                page_number=item.page_number,
                block_id=item.block_id,
            )
            for item in translated.repeated_elements.blocks
            if item.ambiguous
        )
    if glossary is not None:
        findings.extend(
            DiagnosticFinding(
                code=DiagnosticCode.GLOSSARY_ENTRY_UNUSED,
                severity="info",
                stage="translate",
                message=f"Glossary entry {entry_id} was not matched",
            )
            for entry_id in glossary.unmatched_entry_ids
        )
    pages: list[PageDiagnostic] = []
    for page in translated.pages:
        blocks: list[BlockDiagnostic] = []
        units = (
            tuple(
                paragraph
                for paragraph in translated.paragraphs
                if paragraph.anchor_page_number == page.page_number
            )
            if translated.schema_version == "1.3"
            else page.text_blocks
        )
        for block in units:
            repeated = _repeated_for_unit(translated, block)
            layout = render_by_id.get(block.id)
            glossary_unit = glossary_by_id.get(block.id)
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
                    repeated_classification=(
                        repeated.kind if repeated is not None else RepeatedElementKind.BODY
                    ),
                    repeated_confidence=repeated.confidence if repeated is not None else 1.0,
                    repeated_group_id=repeated.group_id if repeated is not None else None,
                    repeated_policy=(
                        repeated.policy if repeated is not None else RepeatedElementPolicy.TRANSLATE
                    ),
                    repeated_ambiguous=repeated.ambiguous if repeated is not None else False,
                    glossary_entry_ids=(
                        glossary_unit.entry_ids if glossary_unit is not None else ()
                    ),
                    glossary_occurrences=(
                        len(glossary_unit.occurrences) if glossary_unit is not None else 0
                    ),
                    glossary_modes=(
                        tuple(sorted({item.mode.value for item in glossary_unit.occurrences}))
                        if glossary_unit is not None
                        else ()
                    ),
                    glossary_compliance=(
                        glossary_unit.compliance
                        if glossary_unit is not None and glossary_unit.compliance != "not_matched"
                        else "not_applicable"
                    ),
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
            raw_lines=translated.reconstruction.metrics.raw_lines
            if translated.reconstruction
            else sum(len(block.lines) for page in translated.pages for block in page.text_blocks),
            logical_paragraphs=len(translated.paragraphs),
            ambiguous_decisions=translated.reconstruction.metrics.ambiguous_decisions
            if translated.reconstruction
            else 0,
            cross_page_merges=translated.reconstruction.metrics.cross_page_merges
            if translated.reconstruction
            else 0,
            ocr_pages=len(ocr_pages),
            repeated_elements=(
                translated.repeated_elements.metrics.counts
                if translated.repeated_elements is not None
                else {}
            ),
            ambiguous_repeated_elements=(
                translated.repeated_elements.metrics.ambiguous_blocks
                if translated.repeated_elements is not None
                else 0
            ),
            font_reductions=render.font_reductions if render else 0,
            expanded_blocks=render.expanded_blocks if render else 0,
            glossary_enabled=glossary is not None,
            glossary_schema_version=glossary.schema_version if glossary is not None else None,
            glossary_version=glossary.glossary_version if glossary is not None else None,
            glossary_fingerprint=glossary.fingerprint if glossary is not None else None,
            glossary_total_entries=(
                glossary.statistics.total_entries if glossary is not None else 0
            ),
            glossary_matched_entries=(
                glossary.statistics.matched_entries if glossary is not None else 0
            ),
            glossary_unmatched_entries=(
                glossary.statistics.unmatched_entries if glossary is not None else 0
            ),
            glossary_applied_occurrences=(
                glossary.statistics.applied_occurrences if glossary is not None else 0
            ),
            glossary_preserved_occurrences=(
                glossary.statistics.preserved_occurrences if glossary is not None else 0
            ),
            glossary_translation_occurrences=(
                glossary.statistics.mandatory_translation_occurrences if glossary is not None else 0
            ),
            glossary_violations=(glossary.statistics.violations if glossary is not None else 0),
            glossary_conflicts=(glossary.statistics.conflicts if glossary is not None else 0),
            glossary_ambiguous_matches=(
                glossary.statistics.ambiguous_matches if glossary is not None else 0
            ),
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
        reconstruction=translated.reconstruction,
    )


def _repeated_for_unit(
    document: ExtractedDocument,
    unit: object,
) -> RepeatedBlockClassification | None:
    evidence = document.repeated_elements
    if evidence is None:
        return None
    by_id = evidence.by_block_id()
    fragments = getattr(unit, "fragments", None)
    if fragments is None:
        return by_id.get(str(getattr(unit, "id", "")))
    values = [
        item
        for fragment in fragments
        if (item := by_id.get(fragment.mapping.source_block_id)) is not None
    ]
    if not values:
        return None
    first = values[0]
    if any(item.kind != first.kind or item.policy != first.policy for item in values[1:]):
        return None
    return first


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
            raw_lines=0,
            logical_paragraphs=0,
            ambiguous_decisions=0,
            cross_page_merges=0,
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
