"""PyMuPDF measurement, rendering, and validation for the PDFTR-22 PoC."""
# mypy: disable-error-code="no-untyped-call"

from __future__ import annotations

import json
import math
import unicodedata
from dataclasses import replace
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import cast

import pymupdf

from pdftranslate.domain.document import ExtractedDocument
from pdftranslate.domain.text_block import BoundingBox
from pdftranslate.reconstruction import LogicalParagraph, ParagraphKind
from pdftranslate.rendering.fonts import discover_font, validate_font
from pdftranslate.repeated import RepeatedElementPolicy
from pdftranslate.serialization import read_document_json
from scripts.reflow_poc.models import (
    ContentDisposition,
    FlowParagraph,
    FlowRegion,
    LayoutPlan,
    Rect,
)
from scripts.reflow_poc.planner import (
    CapacityError,
    Measurement,
    PlannerOptions,
    UnsupportedLayoutError,
    plan_flow,
)

_FONT_NAME = "PDFTR22ReflowFont"
_PDF_VALIDATION_TEXT = str.maketrans(
    {
        **{character: "-" for character in "‐‑‒–—−"},
        "\ufd3e": "(",
        "\ufd3f": ")",
    }
)


class PocValidationError(RuntimeError):
    """Raised when the diagnostic PDF does not preserve the complete plan."""


class PyMuPdfMeasurer:
    """Probe PyMuPDF textbox layout without committing shapes to a PDF."""

    def __init__(self, page_width: float, page_height: float, font_path: Path) -> None:
        self._document = pymupdf.open()
        self._page = self._document.new_page(width=page_width, height=page_height)
        self._font_path = font_path

    def close(self) -> None:
        self._document.close()

    def __enter__(self) -> PyMuPdfMeasurer:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def measure(
        self,
        text: str,
        *,
        width: float,
        height: float,
        font_size: float,
        line_height: float,
    ) -> Measurement:
        if not text:
            return Measurement(fits=True, used_height=0.0, line_count=0)
        rect = pymupdf.Rect(0, 0, width, height)
        shape = self._page.new_shape()
        remaining = shape.insert_textbox(
            rect,
            text,
            fontname=_FONT_NAME,
            fontfile=str(self._font_path),
            fontsize=font_size,
            lineheight=line_height,
        )
        fits = remaining >= -1e-6
        if not fits:
            return Measurement(fits=False, used_height=height, line_count=0)
        used_height = max(font_size * line_height, height - float(remaining))
        line_count = max(1, math.ceil(used_height / (font_size * line_height)))
        return Measurement(fits=True, used_height=used_height, line_count=line_count)


def run_poc(
    source_path: Path,
    translated_path: Path,
    *,
    source_page_number: int,
    occurrence_indexes: tuple[int, ...],
    region_rect: Rect,
    output_path: Path,
    plan_path: Path,
    debug_output_path: Path | None = None,
    allow_ambiguous_occurrences: tuple[int, ...] = (),
    font_path: Path | None = None,
    planner_options: PlannerOptions | None = None,
    max_new_pages: int = 2,
    overwrite: bool = False,
) -> LayoutPlan:
    """Execute the controlled single-page body-reflow proof of concept."""
    source = source_path.expanduser().resolve()
    translated_file = translated_path.expanduser().resolve()
    output = output_path.expanduser().resolve()
    plan_file = plan_path.expanduser().resolve()
    debug_output = debug_output_path.expanduser().resolve() if debug_output_path else None
    _validate_paths(source, translated_file, output, plan_file, debug_output, overwrite)
    if max_new_pages < 0:
        raise ValueError("max_new_pages cannot be negative")

    document_model = read_document_json(translated_file)
    _validate_document_identity(source, document_model)
    paragraphs = _select_flow_paragraphs(
        document_model,
        source_page_number,
        occurrence_indexes,
        region_rect,
        frozenset(allow_ambiguous_occurrences),
    )
    selected_font = discover_font(font_path)
    validate_font(selected_font, tuple(item.text for item in paragraphs))
    options = planner_options or PlannerOptions()

    source_document = _open_pdf(source)
    try:
        source_page = _source_page(source_document, document_model, source_page_number)
        _validate_controlled_region(source_page, document_model, occurrence_indexes, region_rect)
        regions = [
            FlowRegion(
                target_page_number=1,
                rect=region_rect,
                column_index=0,
                order=0,
            )
        ]
        with PyMuPdfMeasurer(
            float(source_page.rect.width), float(source_page.rect.height), selected_font
        ) as measurer:
            while True:
                try:
                    layout = plan_flow(
                        paragraphs,
                        tuple(regions),
                        measurer,
                        source_page_number=source_page_number,
                        font_path=str(selected_font),
                        options=options,
                    )
                    break
                except CapacityError:
                    if len(regions) - 1 >= max_new_pages:
                        raise
                    regions.append(
                        FlowRegion(
                            target_page_number=len(regions) + 1,
                            rect=region_rect,
                            column_index=0,
                            order=len(regions),
                            created_page=True,
                        )
                    )

        temporary_output = _temporary_path(output, ".tmp.pdf")
        try:
            _render_output(
                source_document,
                source_page,
                source_page_number,
                document_model,
                occurrence_indexes,
                layout,
                selected_font,
                temporary_output,
            )
            extracted_count = _validate_saved_output(temporary_output, layout)
            validated_metrics = replace(
                layout.metrics,
                output_paragraph_count=layout.metrics.input_logical_paragraph_count,
                output_extracted_character_count=extracted_count,
            )
            layout = replace(layout, metrics=validated_metrics)
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary_output.replace(output)
        finally:
            if temporary_output.exists():
                temporary_output.unlink()
    finally:
        source_document.close()

    _write_plan(plan_file, layout, overwrite=overwrite)
    if debug_output is not None:
        _write_debug_output(output, debug_output, layout, overwrite=overwrite)
    return layout


def _select_flow_paragraphs(
    document: ExtractedDocument,
    source_page_number: int,
    occurrence_indexes: tuple[int, ...],
    region: Rect,
    allow_ambiguous: frozenset[int],
) -> tuple[FlowParagraph, ...]:
    if document.schema_version != "1.3" or document.translation is None:
        raise UnsupportedLayoutError("the PoC requires a translated schema 1.3 artifact")
    if document.translation.status != "completed":
        raise UnsupportedLayoutError("the PoC requires a completed translation")
    if occurrence_indexes != tuple(sorted(set(occurrence_indexes))) or not occurrence_indexes:
        raise UnsupportedLayoutError("occurrence indexes must be a non-empty ordered unique tuple")
    if allow_ambiguous - set(occurrence_indexes):
        raise UnsupportedLayoutError("ambiguous overrides must be selected occurrences")

    selected: list[FlowParagraph] = []
    for occurrence_index in occurrence_indexes:
        try:
            paragraph = document.paragraphs[occurrence_index]
        except IndexError as error:
            raise UnsupportedLayoutError(
                f"paragraph occurrence index is out of range: {occurrence_index}"
            ) from error
        if paragraph.anchor_page_number != source_page_number:
            raise UnsupportedLayoutError(
                f"occurrence {occurrence_index} is not anchored to source page {source_page_number}"
            )
        if paragraph.kind is not ParagraphKind.BODY:
            raise UnsupportedLayoutError(
                f"occurrence {occurrence_index} is {paragraph.kind.value}, not body prose"
            )
        if paragraph.ambiguous and occurrence_index not in allow_ambiguous:
            raise UnsupportedLayoutError(
                f"occurrence {occurrence_index} is ambiguous; require an explicit reviewed override"
            )
        if _paragraph_policy(document, paragraph) is not RepeatedElementPolicy.TRANSLATE:
            raise UnsupportedLayoutError(
                f"occurrence {occurrence_index} does not have translate policy"
            )
        if paragraph.translated_text is None or not paragraph.translated_text.strip():
            raise UnsupportedLayoutError(
                f"occurrence {occurrence_index} has no required translated text"
            )
        source_rect = _rect_from_bbox(paragraph.bbox)
        if not region.contains(source_rect):
            raise UnsupportedLayoutError(
                f"occurrence {occurrence_index} is outside the reviewed body-flow region"
            )
        selected.append(
            FlowParagraph(
                occurrence_index=occurrence_index,
                paragraph_id=paragraph.id,
                source_page_number=source_page_number,
                kind=paragraph.kind.value,
                disposition=ContentDisposition.FLOWABLE_NOW,
                text=paragraph.translated_text,
                source_rect=source_rect,
                source_fragment_rects=tuple(
                    _rect_from_bbox(fragment.bbox)
                    for fragment in paragraph.fragments
                    if fragment.mapping.page_number == source_page_number
                ),
            )
        )
    return tuple(selected)


def _validate_controlled_region(
    source_page: pymupdf.Page,
    document: ExtractedDocument,
    selected_occurrences: tuple[int, ...],
    region: Rect,
) -> None:
    selected = set(selected_occurrences)
    for occurrence_index, paragraph in enumerate(document.paragraphs):
        if occurrence_index in selected:
            continue
        for fragment in paragraph.fragments:
            if fragment.mapping.page_number != source_page.number + 1:
                continue
            if region.intersects(_rect_from_bbox(fragment.bbox)):
                raise UnsupportedLayoutError(
                    "reviewed body region intersects an unselected paragraph occurrence: "
                    f"{occurrence_index} ({paragraph.id})"
                )
    for image in source_page.get_image_info(xrefs=True):
        if region.intersects(Rect(*map(float, image["bbox"]))):
            raise UnsupportedLayoutError("body-flow region intersects an image")
    for drawing in source_page.get_drawings():
        drawing_rect = cast(pymupdf.Rect, drawing["rect"])
        if region.intersects(
            Rect(
                float(drawing_rect.x0),
                float(drawing_rect.y0),
                float(drawing_rect.x1),
                float(drawing_rect.y1),
            )
        ):
            raise UnsupportedLayoutError("body-flow region intersects a vector drawing")


def _render_output(
    source_document: pymupdf.Document,
    source_page: pymupdf.Page,
    source_page_number: int,
    document_model: ExtractedDocument,
    occurrence_indexes: tuple[int, ...],
    layout: LayoutPlan,
    font_path: Path,
    destination: Path,
) -> None:
    output = pymupdf.open()
    try:
        output.insert_pdf(source_document, from_page=source_page.number, to_page=source_page.number)
        for _ in range(layout.metrics.new_pages_created):
            output.new_page(width=source_page.rect.width, height=source_page.rect.height)
        first_page = output[0]
        seen: set[tuple[float, float, float, float]] = set()
        for occurrence_index in occurrence_indexes:
            paragraph = document_model.paragraphs[occurrence_index]
            for fragment in paragraph.fragments:
                if fragment.mapping.page_number != source_page_number:
                    continue
                rect = _pymupdf_rect(_rect_from_bbox(fragment.bbox))
                key = (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
                if key in seen:
                    continue
                seen.add(key)
                first_page.add_redact_annot(rect, fill=(1.0, 1.0, 1.0), cross_out=False)
        if seen:
            first_page.apply_redactions(images=0, graphics=0, text=0)

        for segment in layout.segments:
            page = output[segment.target_page_number - 1]
            shape = page.new_shape()
            remaining = shape.insert_textbox(
                _pymupdf_rect(segment.target_rect),
                segment.text,
                fontname=_FONT_NAME,
                fontfile=str(font_path),
                fontsize=segment.font_size,
                lineheight=layout.line_height,
                color=(0.0, 0.0, 0.0),
            )
            if remaining < -0.1:
                raise PocValidationError(
                    "layout changed between measurement and insertion for "
                    f"occurrence {segment.occurrence_index}, "
                    f"continuation {segment.continuation_index}"
                )
            shape.commit(overlay=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        output.save(destination, garbage=4, deflate=True)
    finally:
        output.close()


def _validate_saved_output(path: Path, layout: LayoutPlan) -> int:
    output = _open_pdf(path)
    try:
        if output.page_count != len({region.target_page_number for region in layout.regions}):
            raise PocValidationError("PoC output page count does not match the layout plan")
        region_text: dict[int, str] = {}
        for region in layout.regions:
            page = output[region.target_page_number - 1]
            padding = max(2.0, layout.font_size * 0.8)
            clip = pymupdf.Rect(
                max(page.rect.x0, region.rect.x0 - padding),
                max(page.rect.y0, region.rect.y0 - padding),
                min(page.rect.x1, region.rect.x1 + padding),
                min(page.rect.y1, region.rect.y1 + padding),
            )
            region_text[region.target_page_number] = _normalize_text(
                str(page.get_text("text", clip=clip))
            )
        for segment in layout.segments:
            page = output[segment.target_page_number - 1]
            padding = max(2.0, segment.font_size * 0.8)
            clip = pymupdf.Rect(
                max(page.rect.x0, segment.target_rect.x0 - padding),
                max(page.rect.y0, segment.target_rect.y0 - padding),
                min(page.rect.x1, segment.target_rect.x1 + padding),
                min(page.rect.y1, segment.target_rect.y1 + padding),
            )
            expected_normalized = _normalize_text(segment.text)
            local_extracted_normalized = _normalize_text(str(page.get_text("text", clip=clip)))
            if expected_normalized not in local_extracted_normalized:
                region_extracted_normalized = region_text[segment.target_page_number]
                raise PocValidationError(
                    "saved PoC PDF is missing selectable text for "
                    f"occurrence {segment.occurrence_index}, "
                    f"continuation {segment.continuation_index}; "
                    f"expected={expected_normalized[:160]!r}; "
                    f"local_extracted={local_extracted_normalized[:160]!r}; "
                    f"region_diagnostic={region_extracted_normalized[:160]!r}"
                )
    finally:
        output.close()
    return sum(len(text) for text in region_text.values())


def _write_plan(path: Path, layout: LayoutPlan, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"layout plan already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(path, ".tmp.json")
    try:
        temporary.write_text(
            json.dumps(layout.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_debug_output(
    source: Path, destination: Path, layout: LayoutPlan, *, overwrite: bool
) -> None:
    if destination.exists() and not overwrite:
        raise FileExistsError(f"debug output already exists: {destination}")
    debug = _open_pdf(source)
    temporary = _temporary_path(destination, ".tmp.pdf")
    try:
        for region in layout.regions:
            page = debug[region.target_page_number - 1]
            page.draw_rect(_pymupdf_rect(region.rect), color=(0.1, 0.4, 1.0), width=0.8)
        for segment in layout.segments:
            page = debug[segment.target_page_number - 1]
            page.draw_rect(_pymupdf_rect(segment.target_rect), color=(0.1, 0.7, 0.2), width=0.8)
            label_y = max(7.0, segment.target_rect.y0 - 1.0)
            page.insert_text(
                (segment.target_rect.x0, label_y),
                f"{segment.occurrence_index}:{segment.continuation_index}",
                fontsize=5.0,
                color=(0.0, 0.3, 0.8),
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        debug.save(temporary, garbage=4, deflate=True)
        checked = _open_pdf(temporary)
        checked.close()
        temporary.replace(destination)
    finally:
        debug.close()
        if temporary.exists():
            temporary.unlink()


def _validate_paths(
    source: Path,
    translated: Path,
    output: Path,
    plan: Path,
    debug_output: Path | None,
    overwrite: bool,
) -> None:
    if not source.is_file() or not translated.is_file():
        raise FileNotFoundError("source PDF and translated schema 1.3 artifact must exist")
    destinations = tuple(item for item in (output, plan, debug_output) if item is not None)
    if len(set(destinations)) != len(destinations):
        raise ValueError("output, plan, and debug paths must be distinct")
    if source in destinations or translated in destinations:
        raise ValueError("PoC destinations must not overwrite source inputs")
    for destination in destinations:
        if destination.exists() and not overwrite:
            raise FileExistsError(f"destination already exists: {destination}")
        if destination.exists() and not destination.is_file():
            raise ValueError(f"destination is not a file: {destination}")


def _validate_document_identity(source: Path, document: ExtractedDocument) -> None:
    from pdftranslate.pdf.pymupdf_backend import source_identity

    actual = source_identity(source)
    if actual.file_size != document.source.file_size or actual.sha256 != document.source.sha256:
        raise UnsupportedLayoutError("translated artifact does not belong to the source PDF")


def _source_page(
    source: pymupdf.Document, document: ExtractedDocument, source_page_number: int
) -> pymupdf.Page:
    page_model = next(
        (page for page in document.pages if page.page_number == source_page_number), None
    )
    if page_model is None:
        raise UnsupportedLayoutError("source page is not present in the translated artifact")
    return source[page_model.source_index]


def _paragraph_policy(
    document: ExtractedDocument, paragraph: LogicalParagraph
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


def _rect_from_bbox(bbox: BoundingBox) -> Rect:
    return Rect(
        float(bbox.x0),
        float(bbox.y0),
        float(bbox.x1),
        float(bbox.y1),
    )


def _pymupdf_rect(rect: Rect) -> pymupdf.Rect:
    return pymupdf.Rect(rect.x0, rect.y0, rect.x1, rect.y1)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).translate(_PDF_VALIDATION_TEXT)
    return " ".join(normalized.split())


def _temporary_path(destination: Path, suffix: str) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        prefix=f".{destination.stem}.", suffix=suffix, dir=destination.parent, delete=False
    ) as temporary:
        path = Path(temporary.name)
    path.unlink()
    return path


def _open_pdf(path: Path) -> pymupdf.Document:
    try:
        return pymupdf.open(path)
    except (pymupdf.EmptyFileError, pymupdf.FileDataError, RuntimeError) as error:
        raise PocValidationError(f"cannot open PDF {path}: {error}") from error
