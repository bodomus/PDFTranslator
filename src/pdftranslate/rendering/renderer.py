"""PyMuPDF adapter for safe translated-PDF reconstruction."""

from __future__ import annotations

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
from pdftranslate.rendering.errors import OutputPdfError, RenderingInputError, SourceMismatchError
from pdftranslate.rendering.fonts import discover_font, required_cyrillic_characters, validate_font
from pdftranslate.rendering.layout import (
    font_size_candidates,
    initial_font_size,
    safe_expanded_bbox,
)
from pdftranslate.rendering.models import BlockRenderResult, RenderOptions, RenderResult

_FONT_NAME = "PDFTranslateFont"
_COORDINATE_TOLERANCE = 0.5
_PDF_HYPHENS = str.maketrans(
    {
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "−": "-",
    }
)


@dataclass
class _BlockPlan:
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
        _validate_output_paths(source, output, debug_output, settings.overwrite)
        _validate_document(source, translated, settings.force_source_mismatch)

        translations = tuple(
            cast(str, block.translated_text)
            for page in translated.pages
            for block in page.text_blocks
        )
        selected_font = discover_font(font_path)
        validate_font(selected_font, translations)
        output.parent.mkdir(parents=True, exist_ok=True)

        temporary_output = _temporary_pdf_path(output)
        temporary_debug = _temporary_pdf_path(debug_output) if debug_output is not None else None
        plans: list[_BlockPlan] = []
        warnings: list[str] = []
        expected_cyrillic_text: dict[int, list[str]] = {}
        try:
            document = _open_source(source)
            try:
                for page_model in translated.pages:
                    page = document[page_model.source_index]
                    page_plans, page_warnings = _plan_page(
                        page,
                        page_model.page_number,
                        page_model.text_blocks,
                        selected_font,
                        settings,
                    )
                    plans.extend(page_plans)
                    warnings.extend(page_warnings)
                    _redact_page(page, page_plans, settings.redaction_padding, warnings)
                    _insert_page(page, page_plans, selected_font, settings.line_height)
                    for plan in page_plans:
                        text = cast(str, plan.block.translated_text)
                        if not plan.overflow and required_cyrillic_characters((text,)):
                            expected_cyrillic_text.setdefault(page_model.page_number, []).append(
                                text
                            )
                document.save(str(temporary_output), garbage=4, deflate=True)  # type: ignore[no-untyped-call]
            finally:
                document.close()  # type: ignore[no-untyped-call]

            _validate_saved_pdf(
                temporary_output,
                translated.page_count,
                expected_cyrillic_text,
            )
            if temporary_debug is not None:
                _write_debug_pdf(temporary_output, temporary_debug, plans)
                _validate_saved_pdf(temporary_debug, translated.page_count, expected_cyrillic_text)

            temporary_output.replace(output)
            if temporary_debug is not None and debug_output is not None:
                temporary_debug.replace(debug_output)
        finally:
            for temporary in (temporary_output, temporary_debug):
                if temporary is not None and temporary.exists():
                    temporary.unlink()

        block_results = tuple(_result_from_plan(plan) for plan in plans)
        return RenderResult(
            output_path=output,
            debug_output_path=debug_output,
            font_path=selected_font,
            blocks_rendered=sum(not block.overflow for block in block_results),
            font_reductions=sum(
                block.font_size is not None and block.font_size < block.initial_font_size - 1e-6
                for block in block_results
            ),
            expanded_blocks=sum(block.expanded for block in block_results),
            overflow_blocks=sum(block.overflow for block in block_results),
            file_size=output.stat().st_size,
            warnings=tuple(dict.fromkeys(warnings)),
            blocks=block_results,
        )


def _validate_output_paths(
    source: Path,
    output: Path,
    debug_output: Path | None,
    overwrite: bool,
) -> None:
    if output == source:
        raise OutputPdfError("output path must not be the source PDF")
    if output.suffix.lower() != ".pdf":
        raise OutputPdfError(f"output must have a .pdf extension: {output}")
    for candidate in (output, debug_output):
        if candidate is None:
            continue
        if candidate == source:
            raise OutputPdfError("debug output path must not be the source PDF")
        if candidate.exists() and not overwrite:
            raise OutputPdfError(f"output already exists; use --overwrite: {candidate}")
        if candidate.exists() and not candidate.is_file():
            raise OutputPdfError(f"output path is not a file: {candidate}")


def _validate_document(source: Path, translated: ExtractedDocument, force_mismatch: bool) -> None:
    metadata = translated.translation
    if translated.schema_version != "1.1" or metadata is None:
        raise RenderingInputError("rendering requires translated document schema 1.1")
    if metadata.status != "completed":
        raise RenderingInputError("rendering requires a completed translation")
    missing = tuple(
        block.id
        for page in translated.pages
        for block in page.text_blocks
        if block.translated_text is None or not block.translated_text.strip()
    )
    if missing:
        raise RenderingInputError(
            f"translated text is missing for block(s): {', '.join(missing[:8])}"
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
    current = PdfExtractor().extract(source, selected_range)
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


def _plan_page(
    page: pymupdf.Page,
    page_number: int,
    blocks: tuple[TextBlock, ...],
    font_path: Path,
    options: RenderOptions,
) -> tuple[list[_BlockPlan], list[str]]:
    plans: list[_BlockPlan] = []
    warnings: list[str] = []
    for block in blocks:
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


def _write_debug_pdf(source: Path, output: Path, plans: list[_BlockPlan]) -> None:
    document = pymupdf.open(source)  # type: ignore[no-untyped-call]
    try:
        for plan in plans:
            page = document[plan.page_number - 1]
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
    expected_cyrillic_text: dict[int, list[str]],
) -> None:
    try:
        document = pymupdf.open(path)  # type: ignore[no-untyped-call]
    except (pymupdf.EmptyFileError, pymupdf.FileDataError, RuntimeError) as error:
        raise OutputPdfError(f"generated PDF cannot be reopened: {error}") from error
    try:
        if not document.is_pdf or document.page_count != page_count:
            raise OutputPdfError("generated PDF page count or format is invalid")
        for page_number, expected_values in expected_cyrillic_text.items():
            extracted = str(
                document[page_number - 1].get_text("text")  # type: ignore[no-untyped-call]
            )
            normalized_extracted = _normalize_validation_text(extracted)
            for expected in expected_values:
                normalized_expected = _normalize_validation_text(expected)
                if normalized_expected not in normalized_extracted:
                    raise OutputPdfError(
                        f"generated PDF is missing inserted Cyrillic text on page {page_number}"
                    )
    finally:
        document.close()  # type: ignore[no-untyped-call]


def _normalize_validation_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).translate(_PDF_HYPHENS).split())


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


def _result_from_plan(plan: _BlockPlan) -> BlockRenderResult:
    return BlockRenderResult(
        page_number=plan.page_number,
        block_id=plan.block.id,
        source_bbox=_bbox(plan.source_rect),
        final_bbox=_bbox(plan.final_rect),
        initial_font_size=plan.initial_size,
        font_size=plan.font_size,
        fitting_attempts=plan.fitting_attempts,
        expanded=plan.expanded,
        overflow=plan.overflow,
    )


def _rect(box: BoundingBox) -> pymupdf.Rect:
    return pymupdf.Rect(  # type: ignore[no-untyped-call]
        box.x0, box.y0, box.x1, box.y1
    )


def _bbox(rect: pymupdf.Rect) -> BoundingBox:
    return BoundingBox(x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1)


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
