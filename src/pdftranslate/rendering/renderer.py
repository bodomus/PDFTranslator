"""PyMuPDF adapter for safe translated-PDF reconstruction."""

from __future__ import annotations

import shutil
import statistics
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import cast

import pymupdf

from pdftranslate.domain.document import ExtractedDocument
from pdftranslate.domain.text_block import BoundingBox, TextBlock
from pdftranslate.pdf import PdfExtractor
from pdftranslate.pdf.pymupdf_backend import source_identity
from pdftranslate.reconstruction import LogicalParagraph, ParagraphKind
from pdftranslate.rendering.errors import (
    OutputPdfError,
    RenderCompletenessError,
    RenderingInputError,
    SourceMismatchError,
)
from pdftranslate.rendering.fonts import discover_font, required_cyrillic_characters, validate_font
from pdftranslate.rendering.layout import (
    font_size_candidates,
    initial_font_size,
    safe_expanded_bbox,
)
from pdftranslate.rendering.models import (
    BlockRenderResult,
    RenderOptions,
    RenderResult,
    RenderState,
    RenderStrategy,
)
from pdftranslate.rendering.reflow.footnotes import discover_footnote_page
from pdftranslate.rendering.reflow.models import (
    ContentDisposition,
    DocumentLayoutPlan,
    FlowParagraph,
    FlowRegion,
    LayoutPlan,
    Rect,
    ReflowContentKind,
)
from pdftranslate.rendering.reflow.planner import CapacityError, plan_flow
from pdftranslate.rendering.reflow.pymupdf_layout import (
    PyMuPdfMeasurer,
    insert_continuation_pages,
    insert_reflow_segments,
    validate_saved_segments,
)
from pdftranslate.rendering.reflow.regions import discover_reflow_page
from pdftranslate.repeated import RepeatedElementPolicy
from pdftranslate.typography import (
    ResolvedParagraphStyle,
    extract_typography_evidence,
    reconstruct_styles,
)

_FONT_NAME = "PDFTranslateFont"
_COORDINATE_TOLERANCE = 0.5
_PDF_VALIDATION_TEXT = str.maketrans(
    {
        **{character: "-" for character in "‐‑‒–—−"},
        "\ufd3e": "(",
        "\ufd3f": ")",
    }
)


@dataclass
class _BlockPlan:
    unit_index: int
    block: TextBlock
    page_number: int
    source_rect: pymupdf.Rect
    final_rect: pymupdf.Rect
    initial_size: float
    font_size: float | None
    fitting_attempts: int
    color: tuple[float, float, float]
    background: tuple[float, float, float]
    expanded: bool
    overflow: bool


@dataclass(frozen=True)
class _ExpectedText:
    page_number: int
    block_id: str
    source_text: str
    translated_text: str
    source_rect: pymupdf.Rect
    final_rect: pymupdf.Rect
    font_path: Path
    font_size: float | None
    overflow: bool
    expanded: bool


class PdfRenderer:
    """Validate, render, verify, and atomically publish translated PDFs."""

    def render(
        self,
        source_path: Path,
        translated: ExtractedDocument,
        output_path: Path,
        *,
        font_path: Path | None = None,
        options: RenderOptions | None = None,
    ) -> RenderResult:
        settings = options or RenderOptions()
        source = source_path.expanduser().resolve()
        output = output_path.expanduser().resolve()
        debug_output = _debug_output_path(output) if settings.debug_layout else None
        failed_output = _failed_render_output_path(output) if settings.debug_layout else None
        _validate_output_paths(source, output, debug_output, failed_output, settings.overwrite)
        _validate_document(source, translated, settings.force_source_mismatch)

        paragraph_mode = translated.schema_version == "1.3"
        translations = (
            tuple(
                cast(str, paragraph.translated_text)
                for paragraph in translated.paragraphs
                if _paragraph_policy(translated, paragraph)
                not in {
                    RepeatedElementPolicy.PRESERVE,
                    RepeatedElementPolicy.SKIP,
                    RepeatedElementPolicy.REMOVE,
                }
            )
            if translated.schema_version == "1.3"
            else tuple(
                cast(str, block.translated_text)
                for page in translated.pages
                for block in page.text_blocks
            )
        )
        selected_font = discover_font(font_path)
        validate_font(selected_font, translations)
        style_by_occurrence: dict[int, ResolvedParagraphStyle] = {}
        if translated.schema_version == "1.3":
            resolved_styles = reconstruct_styles(extract_typography_evidence(translated))
            style_by_occurrence = {
                style.occurrence_index: style for style in resolved_styles.paragraphs
            }
        output.parent.mkdir(parents=True, exist_ok=True)

        temporary_output = _temporary_pdf_path(output)
        temporary_debug = _temporary_pdf_path(debug_output) if debug_output is not None else None
        plans: list[_BlockPlan] = []
        warnings: list[str] = []
        expected_cyrillic_text: list[_ExpectedText] = []
        try:
            document = _open_source(source)
            try:
                layout = _plan_reflow_document(
                    document,
                    translated,
                    selected_font,
                    settings,
                    style_by_occurrence=style_by_occurrence,
                )
                reflow_plans = layout.plans
                reflow_occurrences = layout.selected_occurrences
                final_page_by_source = layout.page_map
                units_by_page = _render_units_by_page(
                    translated, excluded_occurrences=reflow_occurrences
                )
                plans_by_source_index: dict[int, list[_BlockPlan]] = {}
                for page_model in translated.pages:
                    page = document[page_model.source_index]
                    render_units = units_by_page.get(page_model.page_number, ())
                    page_plans, page_warnings = _plan_page(
                        page,
                        page_model.page_number,
                        tuple(unit[1] for unit in render_units),
                        selected_font,
                        settings,
                        unit_indices=tuple(unit[0] for unit in render_units),
                    )
                    plans.extend(page_plans)
                    plans_by_source_index[page_model.source_index] = page_plans
                    warnings.extend(page_warnings)

                _validate_layout_collisions(translated, layout, plans)

                block_results = _render_results(
                    translated,
                    plans,
                    settings.min_font_size,
                    reflow_plans,
                    final_page_by_source,
                )
                _ensure_render_complete(block_results, source, failed_output, plans)

                if paragraph_mode:
                    _redact_paragraph_fragments(document, translated, settings, warnings)
                for page_model in translated.pages:
                    page = document[page_model.source_index]
                    page_plans = plans_by_source_index[page_model.source_index]
                    if not paragraph_mode:
                        _redact_page(page, page_plans, settings.redaction_padding, warnings)
                    _insert_page(page, page_plans, selected_font, settings.line_height)
                    for plan in page_plans:
                        text = cast(str, plan.block.translated_text)
                        if not plan.overflow and required_cyrillic_characters((text,)):
                            expected_cyrillic_text.append(
                                _ExpectedText(
                                    page_number=final_page_by_source[page_model.page_number],
                                    block_id=plan.block.id,
                                    source_text=plan.block.text,
                                    translated_text=text,
                                    source_rect=plan.source_rect,
                                    final_rect=plan.final_rect,
                                    font_path=selected_font,
                                    font_size=plan.font_size,
                                    overflow=plan.overflow,
                                    expanded=plan.expanded,
                                )
                            )
                insert_continuation_pages(document, reflow_plans)
                insert_reflow_segments(document, reflow_plans, selected_font)
                document.save(str(temporary_output), garbage=4, deflate=True)  # type: ignore[no-untyped-call]
            finally:
                document.close()  # type: ignore[no-untyped-call]

            _validate_saved_pdf(
                temporary_output,
                translated.page_count + layout.inserted_pages,
                expected_cyrillic_text,
                failed_output=failed_output,
            )
            validate_saved_segments(temporary_output, reflow_plans)
            if temporary_debug is not None:
                _write_debug_pdf(
                    temporary_output,
                    temporary_debug,
                    plans,
                    page_numbers=final_page_by_source,
                )
                _validate_saved_pdf(
                    temporary_debug,
                    translated.page_count + layout.inserted_pages,
                    expected_cyrillic_text,
                    failed_output=None,
                )
                validate_saved_segments(temporary_debug, reflow_plans)

            temporary_output.replace(output)
            if temporary_debug is not None and debug_output is not None:
                temporary_debug.replace(debug_output)
        finally:
            for temporary in (temporary_output, temporary_debug):
                if temporary is not None and temporary.exists():
                    temporary.unlink()

        return RenderResult(
            output_path=output,
            debug_output_path=debug_output,
            font_path=selected_font,
            blocks_rendered=sum(block.state is RenderState.RENDERED for block in block_results),
            font_reductions=sum(
                block.font_size is not None
                and block.initial_font_size is not None
                and block.font_size < block.initial_font_size - 1e-6
                for block in block_results
            ),
            expanded_blocks=sum(block.expanded for block in block_results),
            overflow_blocks=sum(block.overflow for block in block_results),
            file_size=output.stat().st_size,
            warnings=tuple(dict.fromkeys(warnings)),
            blocks=block_results,
            reflowed_paragraphs=sum(len(item.paragraphs) for item in layout.body_plans),
            reflow_segments=sum(len(item.segments) for item in layout.body_plans),
            continued_paragraphs=sum(item.continued_occurrences for item in layout.body_plans),
            inserted_pages=layout.inserted_pages,
            fixed_layout_paragraphs=sum(
                item.strategy is RenderStrategy.FIXED_LAYOUT for item in block_results
            ),
            unsupported_pages=layout.unsupported_body_pages,
            unplaced_text_count=sum(item.unplaced_text_count for item in reflow_plans),
            footnotes_reflowed=sum(len(item.paragraphs) for item in layout.footnote_plans),
            footnote_segments=sum(len(item.segments) for item in layout.footnote_plans),
            continued_footnotes=sum(item.continued_occurrences for item in layout.footnote_plans),
            footnote_continuation_pages=sum(item.inserted_pages for item in layout.footnote_plans),
            footnote_fixed_layout_units=sum(
                block_results[index].strategy is RenderStrategy.FIXED_LAYOUT
                for index, paragraph in enumerate(translated.paragraphs)
                if paragraph.kind is ParagraphKind.FOOTNOTE
            ),
            footnote_unsupported_pages=layout.unsupported_footnote_pages,
            footnote_unplaced_text_count=sum(
                item.unplaced_text_count for item in layout.footnote_plans
            ),
        )


def _plan_reflow_document(
    document: pymupdf.Document,
    translated: ExtractedDocument,
    font_path: Path,
    options: RenderOptions,
    *,
    style_by_occurrence: dict[int, ResolvedParagraphStyle] | None = None,
) -> DocumentLayoutPlan:
    if translated.schema_version != "1.3":
        return DocumentLayoutPlan(
            plans=(),
            final_page_by_source=tuple(
                (page.page_number, page.source_index + 1) for page in translated.pages
            ),
        )
    plans: list[LayoutPlan] = []
    final_page_by_source: list[tuple[int, int]] = []
    inserted_before = 0
    inserted_body_pages = 0
    inserted_footnote_pages = 0
    unsupported_body_pages = 0
    unsupported_footnote_pages = 0
    for page_model in translated.pages:
        final_page = page_model.source_index + 1 + inserted_before
        final_page_by_source.append((page_model.page_number, final_page))
        source_page = document[page_model.source_index]
        body = discover_reflow_page(
            translated,
            page_model,
            source_page,
            default_font_size=options.default_font_size,
            min_font_size=options.min_font_size,
            line_height=options.line_height,
            style_by_occurrence=style_by_occurrence,
        )
        body_plan: LayoutPlan | None = None
        if body is None:
            if _page_has_flow_candidate(translated, page_model.page_number):
                unsupported_body_pages += 1
        else:
            remaining_pages = options.max_reflow_pages - inserted_body_pages
            with PyMuPdfMeasurer(
                float(source_page.rect.width), float(source_page.rect.height), font_path
            ) as measurer:
                body_plan = _plan_bounded_flow(
                    body.paragraphs,
                    body.region_rect,
                    body.region_rect,
                    final_page,
                    final_page + 1,
                    remaining_pages,
                    page_model.page_number,
                    measurer,
                    ReflowContentKind.BODY,
                )
            plans.append(body_plan)
            inserted_before += body_plan.inserted_pages
            inserted_body_pages += body_plan.inserted_pages

        footnotes = discover_footnote_page(
            translated,
            page_model,
            source_page,
            body_region=body.region_rect if body is not None else None,
            default_font_size=options.default_font_size,
            min_font_size=options.min_font_size,
            line_height=options.line_height,
            style_by_occurrence=style_by_occurrence,
        )
        if footnotes is None:
            if _page_has_footnote_candidate(translated, page_model.page_number):
                unsupported_footnote_pages += 1
            continue
        remaining_pages = options.max_footnote_pages - inserted_footnote_pages
        first_continuation_page = final_page + (body_plan.inserted_pages if body_plan else 0) + 1
        with PyMuPdfMeasurer(
            float(source_page.rect.width), float(source_page.rect.height), font_path
        ) as measurer:
            footnote_plan = _plan_bounded_flow(
                footnotes.paragraphs,
                footnotes.source_region_rect,
                footnotes.continuation_region_rect,
                final_page,
                first_continuation_page,
                remaining_pages,
                page_model.page_number,
                measurer,
                ReflowContentKind.FOOTNOTE,
            )
        plans.append(footnote_plan)
        inserted_before += footnote_plan.inserted_pages
        inserted_footnote_pages += footnote_plan.inserted_pages
    return DocumentLayoutPlan(
        plans=tuple(plans),
        final_page_by_source=tuple(final_page_by_source),
        unsupported_body_pages=unsupported_body_pages,
        unsupported_footnote_pages=unsupported_footnote_pages,
    )


def _plan_bounded_flow(
    paragraphs: tuple[FlowParagraph, ...],
    source_region: Rect,
    continuation_region: Rect,
    source_target_page: int,
    first_continuation_page: int,
    max_added_pages: int,
    source_page_number: int,
    measurer: PyMuPdfMeasurer,
    content_kind: ReflowContentKind,
) -> LayoutPlan:
    last_capacity_error: CapacityError | None = None
    for added_pages in range(max_added_pages + 1):
        regions = (
            FlowRegion(
                target_page_number=source_target_page,
                rect=source_region,
                column_index=0,
                order=0,
                source_page_number=source_page_number,
            ),
            *(
                FlowRegion(
                    target_page_number=first_continuation_page + offset,
                    rect=continuation_region,
                    column_index=0,
                    order=offset + 1,
                    source_page_number=source_page_number,
                    created_page=True,
                )
                for offset in range(added_pages)
            ),
        )
        try:
            return plan_flow(
                paragraphs,
                regions,
                measurer,
                content_kind=content_kind,
            )
        except CapacityError as error:
            last_capacity_error = error
    assert last_capacity_error is not None
    raise RenderCompletenessError(str(last_capacity_error)) from last_capacity_error


def _page_has_flow_candidate(document: ExtractedDocument, page_number: int) -> bool:
    return any(
        paragraph.anchor_page_number == page_number
        and paragraph.kind.value in {"body", "heading"}
        and _paragraph_policy(document, paragraph) is RepeatedElementPolicy.TRANSLATE
        for paragraph in document.paragraphs
    )


def _page_has_footnote_candidate(document: ExtractedDocument, page_number: int) -> bool:
    return any(
        paragraph.anchor_page_number == page_number
        and paragraph.kind is ParagraphKind.FOOTNOTE
        and _paragraph_policy(document, paragraph) is RepeatedElementPolicy.TRANSLATE
        for paragraph in document.paragraphs
    )


def _validate_layout_collisions(
    translated: ExtractedDocument,
    layout: DocumentLayoutPlan,
    fixed_plans: list[_BlockPlan],
) -> None:
    body_segments = tuple(item for plan in layout.body_plans for item in plan.segments)
    footnote_segments = tuple(item for plan in layout.footnote_plans for item in plan.segments)
    for footnote in footnote_segments:
        for body in body_segments:
            if (
                footnote.target_page_number == body.target_page_number
                and footnote.target_rect.intersects(body.target_rect)
            ):
                raise RenderCompletenessError(
                    "body and footnote reflow segments overlap before PDF mutation"
                )

    page_map = layout.page_map
    for footnote in footnote_segments:
        for fixed in fixed_plans:
            if page_map.get(fixed.page_number, fixed.page_number) != footnote.target_page_number:
                continue
            fixed_rect = Rect(
                float(fixed.final_rect.x0),
                float(fixed.final_rect.y0),
                float(fixed.final_rect.x1),
                float(fixed.final_rect.y1),
            )
            if footnote.target_rect.intersects(fixed_rect):
                raise RenderCompletenessError(
                    "footnote reflow segment overlaps a fixed-layout render unit "
                    "before PDF mutation"
                )

    selected = layout.selected_occurrences
    for index, paragraph in enumerate(translated.paragraphs):
        if index in selected:
            continue
        anchor_page = page_map.get(paragraph.anchor_page_number, paragraph.anchor_page_number)
        anchor_rect = Rect(
            float(paragraph.bbox.x0),
            float(paragraph.bbox.y0),
            float(paragraph.bbox.x1),
            float(paragraph.bbox.y1),
        )
        if any(
            segment.target_page_number == anchor_page
            and segment.target_rect.intersects(anchor_rect)
            for segment in footnote_segments
        ):
            raise RenderCompletenessError(
                "footnote reflow segment overlaps an anchored paragraph before PDF mutation"
            )


def _paragraph_block(paragraph: LogicalParagraph) -> TextBlock:
    first = paragraph.fragments[0]
    return TextBlock(
        id=paragraph.id,
        text=paragraph.text,
        translated_text=paragraph.translated_text,
        bbox=paragraph.bbox,
        original_order=first.mapping.original_order,
        normalized_order=first.mapping.normalized_order,
        spans=paragraph.spans,
    )


def _render_units_by_page(
    translated: ExtractedDocument,
    *,
    excluded_occurrences: frozenset[int] = frozenset(),
) -> dict[int, tuple[tuple[int, TextBlock], ...]]:
    grouped: dict[int, list[tuple[int, TextBlock]]] = {}
    if translated.schema_version == "1.3":
        for unit_index, paragraph in enumerate(translated.paragraphs):
            if unit_index in excluded_occurrences:
                continue
            if _paragraph_policy(translated, paragraph) in {
                RepeatedElementPolicy.PRESERVE,
                RepeatedElementPolicy.SKIP,
                RepeatedElementPolicy.REMOVE,
            }:
                continue
            grouped.setdefault(paragraph.anchor_page_number, []).append(
                (unit_index, _paragraph_block(paragraph))
            )
        return {page: tuple(blocks) for page, blocks in grouped.items()}

    unit_index = 0
    for page in translated.pages:
        for block in page.text_blocks:
            grouped.setdefault(page.page_number, []).append((unit_index, block))
            unit_index += 1
    return {page: tuple(blocks) for page, blocks in grouped.items()}


def _redact_paragraph_fragments(
    document: pymupdf.Document,
    translated: ExtractedDocument,
    options: RenderOptions,
    warnings: list[str],
) -> None:
    page_indices = {page.page_number: page.source_index for page in translated.pages}
    seen: set[tuple[int, float, float, float, float]] = set()
    for paragraph in translated.paragraphs:
        if _paragraph_policy(translated, paragraph) in {
            RepeatedElementPolicy.PRESERVE,
            RepeatedElementPolicy.SKIP,
        }:
            continue
        for fragment in paragraph.fragments:
            box = fragment.bbox
            key = (fragment.mapping.page_number, box.x0, box.y0, box.x1, box.y1)
            if key in seen:
                warnings.append(
                    f"paragraph {paragraph.id}: duplicate source fragment was redacted once"
                )
                continue
            seen.add(key)
            page = document[page_indices[fragment.mapping.page_number]]
            rect = _padded_rect(_rect(box), page.rect, options.redaction_padding)
            background = _sample_background(page, _rect(box))
            page.add_redact_annot(rect, fill=background, cross_out=False)
    for page_number in {item[0] for item in seen}:
        page = document[page_indices[page_number]]
        page.apply_redactions(images=0, graphics=0, text=0)


def _validate_output_paths(
    source: Path,
    output: Path,
    debug_output: Path | None,
    failed_output: Path | None,
    overwrite: bool,
) -> None:
    if output == source:
        raise OutputPdfError("output path must not be the source PDF")
    if output.suffix.lower() != ".pdf":
        raise OutputPdfError(f"output must have a .pdf extension: {output}")
    for candidate in (output, debug_output, failed_output):
        if candidate is None:
            continue
        if candidate == source:
            raise OutputPdfError("diagnostic output path must not be the source PDF")
        if candidate.exists() and not overwrite:
            raise OutputPdfError(f"output already exists; use --overwrite: {candidate}")
        if candidate.exists() and not candidate.is_file():
            raise OutputPdfError(f"output path is not a file: {candidate}")


def _validate_document(source: Path, translated: ExtractedDocument, force_mismatch: bool) -> None:
    metadata = translated.translation
    if translated.schema_version not in {"1.1", "1.3"} or metadata is None:
        raise RenderingInputError("rendering requires translated document schema 1.1 or 1.3")
    if metadata.status != "completed":
        raise RenderingInputError("rendering requires a completed translation")
    if translated.schema_version == "1.3":
        missing = tuple(
            paragraph.id
            for paragraph in translated.paragraphs
            if (
                paragraph.translated_text is None
                or (
                    not paragraph.translated_text.strip()
                    and _paragraph_policy(translated, paragraph)
                    not in {RepeatedElementPolicy.SKIP, RepeatedElementPolicy.REMOVE}
                )
            )
        )
        label = "paragraph"
    else:
        missing = tuple(
            block.id
            for page in translated.pages
            for block in page.text_blocks
            if block.translated_text is None or not block.translated_text.strip()
        )
        label = "block"
    if missing:
        raise RenderingInputError(
            f"translated text is missing for {label}(s): {', '.join(missing[:8])}"
        )

    actual_identity = source_identity(source)
    identity_mismatch = (
        actual_identity.file_size != translated.source.file_size
        or actual_identity.sha256 != translated.source.sha256
    )
    if identity_mismatch and not force_mismatch:
        raise SourceMismatchError(
            "source PDF size or SHA-256 does not match translated JSON; "
            "use --force-source-mismatch only after verifying the layout"
        )

    selected_range = ",".join(str(number) for number in translated.selected_pages)
    reconstruction_options = (
        translated.reconstruction.options if translated.reconstruction is not None else None
    )
    repeated_options = (
        translated.repeated_elements.options if translated.repeated_elements is not None else None
    )
    current = PdfExtractor().extract(
        source, selected_range, reconstruction_options, repeated_options
    )
    if current.page_count != translated.page_count:
        raise SourceMismatchError("source PDF page count does not match translated JSON")
    if len(current.pages) != len(translated.pages):
        raise SourceMismatchError("selected page structure does not match translated JSON")
    for actual_page, expected_page in zip(current.pages, translated.pages, strict=True):
        if actual_page.page_number != expected_page.page_number:
            raise SourceMismatchError("source page numbers do not match translated JSON")
        if actual_page.source_index != expected_page.source_index:
            raise SourceMismatchError(f"source index mismatch on page {expected_page.page_number}")
        if not _close(actual_page.width, expected_page.width) or not _close(
            actual_page.height, expected_page.height
        ):
            raise SourceMismatchError(
                f"page dimensions mismatch on page {expected_page.page_number}"
            )
        if len(actual_page.text_blocks) != len(expected_page.text_blocks):
            raise SourceMismatchError(
                f"text block count mismatch on page {expected_page.page_number}"
            )
        for actual_block, expected_block in zip(
            actual_page.text_blocks, expected_page.text_blocks, strict=True
        ):
            if actual_block.id != expected_block.id or actual_block.text != expected_block.text:
                raise SourceMismatchError(
                    f"block {expected_block.id} does not match source page "
                    f"{expected_page.page_number}"
                )
            if not _bbox_close(actual_block.bbox, expected_block.bbox):
                raise SourceMismatchError(f"bounding box mismatch for block {expected_block.id}")
            _validate_bbox(expected_block.bbox, expected_page.width, expected_page.height)
    if translated.schema_version == "1.3":
        actual_paragraphs = tuple(
            (item.id, item.text, item.fragments) for item in current.paragraphs
        )
        expected_paragraphs = tuple(
            (item.id, item.text, item.fragments) for item in translated.paragraphs
        )
        if actual_paragraphs != expected_paragraphs:
            raise SourceMismatchError(
                "paragraph reconstruction or source mapping does not match the source PDF"
            )


def _paragraph_policy(
    document: ExtractedDocument,
    paragraph: LogicalParagraph,
) -> RepeatedElementPolicy:
    evidence = document.repeated_elements
    if evidence is None:
        return RepeatedElementPolicy.TRANSLATE
    by_id = evidence.by_block_id()
    policies = {
        item.policy
        for fragment in paragraph.fragments
        if (item := by_id.get(fragment.mapping.source_block_id)) is not None
    }
    if not policies:
        return RepeatedElementPolicy.TRANSLATE
    if len(policies) > 1:
        return RepeatedElementPolicy.PRESERVE
    return next(iter(policies))


def _plan_page(
    page: pymupdf.Page,
    page_number: int,
    blocks: tuple[TextBlock, ...],
    font_path: Path,
    options: RenderOptions,
    *,
    unit_indices: tuple[int, ...] | None = None,
) -> tuple[list[_BlockPlan], list[str]]:
    plans: list[_BlockPlan] = []
    warnings: list[str] = []
    indices = unit_indices if unit_indices is not None else tuple(range(len(blocks)))
    if len(indices) != len(blocks):
        raise ValueError("render unit indexes must align with blocks")
    for unit_index, block in zip(indices, blocks, strict=True):
        text = cast(str, block.translated_text)
        source_rect = _rect(block.bbox)
        start_size = initial_font_size(block, options.default_font_size)
        color = _block_color(block)
        background = _sample_background(page, source_rect)
        chosen_size, fitting_attempts = _fit(
            page, source_rect, text, font_path, start_size, options, color
        )
        final_rect = source_rect
        expanded = False
        if chosen_size is None and options.allow_expand:
            expanded_bbox = safe_expanded_bbox(
                block,
                blocks,
                float(page.rect.height),
                max(options.redaction_padding, 1.0),
            )
            expanded_rect = _rect(expanded_bbox)
            if expanded_rect.height > source_rect.height + 1e-6:
                final_rect = expanded_rect
                chosen_size, expansion_attempts = _fit(
                    page,
                    final_rect,
                    text,
                    font_path,
                    start_size,
                    options,
                    color,
                )
                fitting_attempts += expansion_attempts
                expanded = chosen_size is not None
        overflow = chosen_size is None
        if overflow:
            warnings.append(
                f"block {block.id} on page {page_number} overflows at minimum font size "
                f"{options.min_font_size:g}"
            )
        elif expanded:
            warnings.append(f"block {block.id} on page {page_number} expanded downward")
        plans.append(
            _BlockPlan(
                unit_index=unit_index,
                block=block,
                page_number=page_number,
                source_rect=source_rect,
                final_rect=final_rect,
                initial_size=start_size,
                font_size=chosen_size,
                fitting_attempts=fitting_attempts,
                color=color,
                background=background,
                expanded=expanded,
                overflow=overflow,
            )
        )
    return plans, warnings


def _fit(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    text: str,
    font_path: Path,
    start_size: float,
    options: RenderOptions,
    color: tuple[float, float, float],
) -> tuple[float | None, int]:
    attempts = 0
    for size in font_size_candidates(start_size, options.min_font_size, options.font_size_step):
        attempts += 1
        shape = page.new_shape()  # type: ignore[no-untyped-call]
        remaining = shape.insert_textbox(
            rect,
            text,
            fontname=_FONT_NAME,
            fontfile=str(font_path),
            fontsize=size,
            lineheight=options.line_height,
            color=color,
        )
        if remaining >= -1e-6:
            return size, attempts
    return None, attempts


def _redact_page(
    page: pymupdf.Page,
    plans: list[_BlockPlan],
    padding: float,
    warnings: list[str],
) -> None:
    for plan in plans:
        redaction_rect = _safe_redaction_rect(plan, plans, page.rect, padding)
        if padding > 0 and redaction_rect == plan.source_rect:
            padded = _padded_rect(plan.source_rect, page.rect, padding)
            if padded != plan.source_rect:
                warnings.append(f"block {plan.block.id}: redaction padding reduced near other text")
        page.add_redact_annot(redaction_rect, fill=plan.background, cross_out=False)
    if plans:
        page.apply_redactions(
            images=0,  # preserve overlapping image objects
            graphics=0,  # preserve overlapping vector objects
            text=0,  # remove overlapping text
        )


def _insert_page(
    page: pymupdf.Page,
    plans: list[_BlockPlan],
    font_path: Path,
    line_height: float,
) -> None:
    for plan in plans:
        if plan.font_size is None:
            continue
        shape = page.new_shape()  # type: ignore[no-untyped-call]
        remaining = shape.insert_textbox(
            plan.final_rect,
            cast(str, plan.block.translated_text),
            fontname=_FONT_NAME,
            fontfile=str(font_path),
            fontsize=plan.font_size,
            lineheight=line_height,
            color=plan.color,
        )
        if remaining < -1e-6:
            raise OutputPdfError(f"layout changed while inserting block {plan.block.id}")
        shape.commit(overlay=True)


def _safe_redaction_rect(
    plan: _BlockPlan,
    plans: list[_BlockPlan],
    page_rect: pymupdf.Rect,
    padding: float,
) -> pymupdf.Rect:
    candidate = _padded_rect(plan.source_rect, page_rect, padding)
    for other in plans:
        if other is plan:
            continue
        candidate_overlaps = candidate.intersects(  # type: ignore[no-untyped-call]
            other.source_rect
        )
        source_overlaps = plan.source_rect.intersects(  # type: ignore[no-untyped-call]
            other.source_rect
        )
        if candidate_overlaps and not source_overlaps:
            return plan.source_rect
    return candidate


def _padded_rect(rect: pymupdf.Rect, page_rect: pymupdf.Rect, padding: float) -> pymupdf.Rect:
    return pymupdf.Rect(  # type: ignore[no-untyped-call]
        max(page_rect.x0, rect.x0 - padding),
        max(page_rect.y0, rect.y0 - padding),
        min(page_rect.x1, rect.x1 + padding),
        min(page_rect.y1, rect.y1 + padding),
    )


def _sample_background(page: pymupdf.Page, rect: pymupdf.Rect) -> tuple[float, float, float]:
    try:
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(0.25, 0.25),  # type: ignore[no-untyped-call]
            clip=rect,
            colorspace=pymupdf.csRGB,
            alpha=False,
        )
    except (RuntimeError, ValueError):
        return (1.0, 1.0, 1.0)
    samples = pixmap.samples
    channels = pixmap.n
    if not samples or channels < 3:
        return (1.0, 1.0, 1.0)
    return (
        float(statistics.median(samples[0::channels])) / 255.0,
        float(statistics.median(samples[1::channels])) / 255.0,
        float(statistics.median(samples[2::channels])) / 255.0,
    )


def _block_color(block: TextBlock) -> tuple[float, float, float]:
    packed = next(
        (span.text_color for span in block.spans if span.text_color is not None),
        0,
    )
    return (
        float((packed >> 16) & 0xFF) / 255.0,
        float((packed >> 8) & 0xFF) / 255.0,
        float(packed & 0xFF) / 255.0,
    )


def _write_debug_pdf(
    source: Path,
    output: Path,
    plans: list[_BlockPlan],
    *,
    page_numbers: dict[int, int] | None = None,
) -> None:
    document = pymupdf.open(source)  # type: ignore[no-untyped-call]
    try:
        for plan in plans:
            target_page = (
                page_numbers.get(plan.page_number, plan.page_number)
                if page_numbers
                else plan.page_number
            )
            page = document[target_page - 1]
            page.draw_rect(plan.source_rect, color=(0.1, 0.4, 1.0), width=0.8, overlay=True)
            final_color = (1.0, 0.1, 0.1) if plan.overflow else (0.1, 0.7, 0.2)
            if plan.expanded:
                final_color = (1.0, 0.55, 0.0)
            page.draw_rect(plan.final_rect, color=final_color, width=1.2, overlay=True)
            state = "overflow" if plan.overflow else "expanded" if plan.expanded else "rendered"
            page.insert_text(
                (plan.final_rect.x0, max(6.0, plan.final_rect.y0 - 2.0)),
                f"{plan.block.id} [{state}]",
                fontsize=6.0,
                color=final_color,
                overlay=True,
            )
        document.save(str(output), garbage=4, deflate=True)  # type: ignore[no-untyped-call]
    finally:
        document.close()  # type: ignore[no-untyped-call]


def _validate_saved_pdf(
    path: Path,
    page_count: int,
    expected_cyrillic_text: list[_ExpectedText],
    *,
    failed_output: Path | None = None,
) -> None:
    try:
        document = pymupdf.open(path)  # type: ignore[no-untyped-call]
    except (pymupdf.EmptyFileError, pymupdf.FileDataError, RuntimeError) as error:
        raise OutputPdfError(f"generated PDF cannot be reopened: {error}") from error
    try:
        if not document.is_pdf or document.page_count != page_count:
            raise OutputPdfError("generated PDF page count or format is invalid")
        page_text: dict[int, str] = {}
        for expected in expected_cyrillic_text:
            page = document[expected.page_number - 1]
            normalized_page = page_text.setdefault(
                expected.page_number,
                _normalize_validation_text(str(page.get_text("text"))),  # type: ignore[no-untyped-call]
            )
            normalized_expected = _normalize_validation_text(expected.translated_text)
            clip = _validation_clip(expected.final_rect, page.rect, expected.font_size)
            clipped = str(page.get_text("text", clip=clip))  # type: ignore[no-untyped-call]
            normalized_clipped = _normalize_validation_text(clipped)
            if normalized_expected in normalized_clipped:
                continue
            if failed_output is not None:
                failed_output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, failed_output)
            raise OutputPdfError(
                _validation_failure_message(expected, normalized_clipped, normalized_page)
            )
    finally:
        document.close()  # type: ignore[no-untyped-call]


def _normalize_validation_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).translate(_PDF_VALIDATION_TEXT).split())


def _validation_clip(
    rect: pymupdf.Rect,
    page_rect: pymupdf.Rect,
    font_size: float | None,
) -> pymupdf.Rect:
    padding = max(2.0, (font_size or 0.0) * 0.8)
    return pymupdf.Rect(  # type: ignore[no-untyped-call]
        max(page_rect.x0, rect.x0 - padding),
        max(page_rect.y0, rect.y0 - padding),
        min(page_rect.x1, rect.x1 + padding),
        min(page_rect.y1, rect.y1 + padding),
    )


def _validation_failure_message(
    expected: _ExpectedText,
    normalized_clipped: str,
    normalized_page: str,
) -> str:
    return (
        "generated PDF is missing inserted Cyrillic text "
        f"for block {expected.block_id} on page {expected.page_number}; "
        f"expected={_snippet(_normalize_validation_text(expected.translated_text))!r}; "
        f"extracted_clip={_snippet(normalized_clipped)!r}; "
        f"extracted_page={_snippet(normalized_page)!r}; "
        f"source_bbox={_rect_tuple(expected.source_rect)}; "
        f"final_bbox={_rect_tuple(expected.final_rect)}; "
        f"font_path={expected.font_path}; "
        f"font_size={expected.font_size}; "
        f"overflow={expected.overflow}; "
        f"expanded={expected.expanded}"
    )


def _snippet(value: str, limit: int = 240) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def _open_source(path: Path) -> pymupdf.Document:
    try:
        return pymupdf.open(path)  # type: ignore[no-untyped-call]
    except (pymupdf.EmptyFileError, pymupdf.FileDataError, RuntimeError) as error:
        raise RenderingInputError(f"cannot open source PDF {path}: {error}") from error


def _temporary_pdf_path(destination: Path | None) -> Path:
    if destination is None:
        raise ValueError("temporary destination is required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        prefix=f".{destination.stem}.",
        suffix=".tmp.pdf",
        dir=destination.parent,
        delete=False,
    ) as temporary:
        path = Path(temporary.name)
    path.unlink()
    return path


def _debug_output_path(output: Path) -> Path:
    return output.with_name(f"{output.stem}.debug.pdf")


def _failed_render_output_path(output: Path) -> Path:
    return output.with_name(f"{output.stem}.failed-render.pdf")


def _render_results(
    translated: ExtractedDocument,
    plans: list[_BlockPlan],
    min_font_size: float,
    reflow_plans: tuple[LayoutPlan, ...] = (),
    final_page_by_source: dict[int, int] | None = None,
) -> tuple[BlockRenderResult, ...]:
    results = {
        plan.unit_index: _result_from_plan(
            plan,
            min_font_size,
            target_page=(final_page_by_source or {}).get(plan.page_number, plan.page_number),
        )
        for plan in plans
    }
    for layout in reflow_plans:
        for flow_paragraph in layout.paragraphs:
            segments = tuple(
                item
                for item in layout.segments
                if item.occurrence_index == flow_paragraph.occurrence_index
            )
            has_applied_typography = (
                layout.content_kind is ReflowContentKind.BODY
                and flow_paragraph.disposition
                in {ContentDisposition.FLOWABLE_BODY, ContentDisposition.FLOWABLE_HEADING}
            ) or (
                layout.content_kind is ReflowContentKind.FOOTNOTE
                and flow_paragraph.disposition is ContentDisposition.FLOWABLE_FOOTNOTE
            )
            results[flow_paragraph.occurrence_index] = BlockRenderResult(
                unit_index=flow_paragraph.occurrence_index,
                page_number=flow_paragraph.source_page_number,
                block_id=flow_paragraph.paragraph_id,
                policy=RepeatedElementPolicy.TRANSLATE,
                state=RenderState.RENDERED,
                source_bbox=_bbox(_reflow_rect(flow_paragraph.source_rect)),
                final_bbox=_bbox(_reflow_rect(segments[0].target_rect)),
                initial_font_size=flow_paragraph.style.font_size,
                font_size=flow_paragraph.style.font_size,
                min_font_size=min_font_size,
                fitting_attempts=1,
                expanded=False,
                overflow=False,
                translated_character_count=len(flow_paragraph.text),
                strategy=(
                    RenderStrategy.REFLOW_FOOTNOTE
                    if layout.content_kind is ReflowContentKind.FOOTNOTE
                    else RenderStrategy.REFLOW_LAYOUT
                ),
                target_pages=tuple(dict.fromkeys(item.target_page_number for item in segments)),
                segment_count=len(segments),
                continuation_count=max(0, len(segments) - 1),
                target_rects=tuple(_bbox(_reflow_rect(item.target_rect)) for item in segments),
                text_offsets=tuple((item.text_start, item.text_end) for item in segments),
                applied_line_height=(
                    flow_paragraph.style.line_height if has_applied_typography else None
                ),
                applied_alignment=(
                    flow_paragraph.style.alignment.value if has_applied_typography else None
                ),
                applied_first_line_indent=(
                    flow_paragraph.style.first_line_indent if has_applied_typography else None
                ),
                applied_left_indent=(
                    flow_paragraph.style.left_indent if has_applied_typography else None
                ),
                applied_right_indent=(
                    flow_paragraph.style.right_indent if has_applied_typography else None
                ),
                applied_space_before=(
                    flow_paragraph.style.space_before if has_applied_typography else None
                ),
                applied_space_after=(
                    flow_paragraph.style.space_after if has_applied_typography else None
                ),
                applied_color=flow_paragraph.color if has_applied_typography else None,
                bold_requested=(
                    flow_paragraph.style.bold_requested if has_applied_typography else None
                ),
                bold_applied=(
                    flow_paragraph.style.bold_applied if has_applied_typography else None
                ),
                italic_requested=(
                    flow_paragraph.style.italic_requested if has_applied_typography else None
                ),
                italic_applied=(
                    flow_paragraph.style.italic_applied if has_applied_typography else None
                ),
                mixed_style=(flow_paragraph.style.mixed_style if has_applied_typography else None),
                style_fallback_count=(
                    flow_paragraph.style.fallback_count if has_applied_typography else None
                ),
            )
    if translated.schema_version == "1.3":
        for unit_index, paragraph in enumerate(translated.paragraphs):
            policy = _paragraph_policy(translated, paragraph)
            if policy is RepeatedElementPolicy.TRANSLATE:
                if unit_index not in results:
                    results[unit_index] = _unplanned_result(
                        unit_index,
                        paragraph.anchor_page_number,
                        paragraph.id,
                        paragraph.bbox,
                        len(paragraph.translated_text or ""),
                        min_font_size,
                    )
                continue
            state = (
                RenderState.PRESERVED
                if policy is RepeatedElementPolicy.PRESERVE
                else RenderState.EXCLUDED_BY_POLICY
            )
            results[unit_index] = BlockRenderResult(
                unit_index=unit_index,
                page_number=paragraph.anchor_page_number,
                block_id=paragraph.id,
                policy=policy,
                state=state,
                source_bbox=paragraph.bbox,
                final_bbox=paragraph.bbox,
                initial_font_size=None,
                font_size=None,
                min_font_size=min_font_size,
                fitting_attempts=0,
                expanded=False,
                overflow=False,
                translated_character_count=len(paragraph.translated_text or ""),
                strategy=RenderStrategy.ANCHORED_PRESERVED,
                target_pages=(
                    (final_page_by_source or {}).get(
                        paragraph.anchor_page_number, paragraph.anchor_page_number
                    ),
                ),
            )
    else:
        unit_index = 0
        for page in translated.pages:
            for block in page.text_blocks:
                if unit_index not in results:
                    results[unit_index] = _unplanned_result(
                        unit_index,
                        page.page_number,
                        block.id,
                        block.bbox,
                        len(block.translated_text or ""),
                        min_font_size,
                    )
                unit_index += 1
    return tuple(results[index] for index in sorted(results))


def _unplanned_result(
    unit_index: int,
    page_number: int,
    block_id: str,
    bbox: BoundingBox,
    translated_character_count: int,
    min_font_size: float,
) -> BlockRenderResult:
    return BlockRenderResult(
        unit_index=unit_index,
        page_number=page_number,
        block_id=block_id,
        policy=RepeatedElementPolicy.TRANSLATE,
        state=RenderState.FAILED,
        source_bbox=bbox,
        final_bbox=bbox,
        initial_font_size=None,
        font_size=None,
        min_font_size=min_font_size,
        fitting_attempts=0,
        expanded=False,
        overflow=False,
        translated_character_count=translated_character_count,
        strategy=RenderStrategy.UNSUPPORTED,
    )


def _ensure_render_complete(
    results: tuple[BlockRenderResult, ...],
    source: Path,
    failed_output: Path | None,
    plans: list[_BlockPlan],
) -> None:
    failures = tuple(
        result
        for result in results
        if result.policy is RepeatedElementPolicy.TRANSLATE
        and result.state is not RenderState.RENDERED
    )
    if not failures:
        return
    if failed_output is not None:
        failed_output.parent.mkdir(parents=True, exist_ok=True)
        temporary_failed = _temporary_pdf_path(failed_output)
        try:
            _write_debug_pdf(source, temporary_failed, plans)
            temporary_failed.replace(failed_output)
        finally:
            if temporary_failed.exists():
                temporary_failed.unlink()
    details = "\n".join(_completeness_failure_detail(result) for result in failures)
    raise RenderCompletenessError(
        "render completeness failed: "
        f"{len(failures)} required paragraph(s) could not be rendered completely\n{details}"
    )


def _completeness_failure_detail(result: BlockRenderResult) -> str:
    return (
        f"{result.block_id} occurrence={result.unit_index + 1} "
        f"page={result.page_number} state={result.state.value} "
        f"source_bbox={_bbox_tuple(result.source_bbox)} "
        f"final_bbox={_bbox_tuple(result.final_bbox)} "
        f"font_size={result.font_size} min_font_size={result.min_font_size:g} "
        f"attempts={result.fitting_attempts} expanded={result.expanded} "
        f"translated_chars={result.translated_character_count}"
    )


def _result_from_plan(
    plan: _BlockPlan, min_font_size: float, *, target_page: int | None = None
) -> BlockRenderResult:
    return BlockRenderResult(
        unit_index=plan.unit_index,
        page_number=plan.page_number,
        block_id=plan.block.id,
        policy=RepeatedElementPolicy.TRANSLATE,
        state=RenderState.OVERFLOW if plan.overflow else RenderState.RENDERED,
        source_bbox=_bbox(plan.source_rect),
        final_bbox=_bbox(plan.final_rect),
        initial_font_size=plan.initial_size,
        font_size=plan.font_size,
        min_font_size=min_font_size,
        fitting_attempts=plan.fitting_attempts,
        expanded=plan.expanded,
        overflow=plan.overflow,
        translated_character_count=len(cast(str, plan.block.translated_text)),
        strategy=RenderStrategy.FIXED_LAYOUT,
        target_pages=(target_page or plan.page_number,),
        segment_count=0 if plan.overflow else 1,
        target_rects=() if plan.overflow else (_bbox(plan.final_rect),),
        text_offsets=(() if plan.overflow else ((0, len(cast(str, plan.block.translated_text))),)),
    )


def _reflow_rect(rect: Rect) -> pymupdf.Rect:
    return pymupdf.Rect(rect.x0, rect.y0, rect.x1, rect.y1)  # type: ignore[no-untyped-call]


def _rect(box: BoundingBox) -> pymupdf.Rect:
    return pymupdf.Rect(  # type: ignore[no-untyped-call]
        box.x0, box.y0, box.x1, box.y1
    )


def _bbox(rect: pymupdf.Rect) -> BoundingBox:
    return BoundingBox(x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1)


def _rect_tuple(rect: pymupdf.Rect) -> tuple[float, float, float, float]:
    return (round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2))


def _bbox_tuple(box: BoundingBox) -> tuple[float, float, float, float]:
    return (round(box.x0, 2), round(box.y0, 2), round(box.x1, 2), round(box.y1, 2))


def _validate_bbox(box: BoundingBox, width: float, height: float) -> None:
    if (
        box.x0 < 0
        or box.y0 < 0
        or box.x1 > width + _COORDINATE_TOLERANCE
        or box.y1 > height + _COORDINATE_TOLERANCE
    ):
        raise SourceMismatchError("translated JSON contains a block outside its source page")
    if box.x1 - box.x0 <= 0 or box.y1 - box.y0 <= 0:
        raise SourceMismatchError("translated JSON contains an empty block rectangle")


def _bbox_close(left: BoundingBox, right: BoundingBox) -> bool:
    return all(
        _close(first, second)
        for first, second in zip(
            (left.x0, left.y0, left.x1, left.y1),
            (right.x0, right.y0, right.x1, right.y1),
            strict=True,
        )
    )


def _close(left: float, right: float) -> bool:
    return abs(left - right) <= _COORDINATE_TOLERANCE
