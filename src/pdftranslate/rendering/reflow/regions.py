"""Conservative production eligibility and single-column region discovery."""

from __future__ import annotations

import statistics
from dataclasses import dataclass

import pymupdf

from pdftranslate.domain.document import ExtractedDocument
from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox
from pdftranslate.reconstruction import LogicalParagraph, ParagraphKind
from pdftranslate.rendering.reflow.models import (
    ContentDisposition,
    FlowParagraph,
    Rect,
    ReflowStyle,
)
from pdftranslate.repeated import RepeatedElementPolicy


@dataclass(frozen=True)
class ReflowPage:
    source_page_number: int
    occurrence_indexes: tuple[int, ...]
    paragraphs: tuple[FlowParagraph, ...]
    region_rect: Rect


def discover_reflow_page(
    document: ExtractedDocument,
    page_model: ExtractedPage,
    page: pymupdf.Page,
    *,
    default_font_size: float,
    min_font_size: float,
    line_height: float,
) -> ReflowPage | None:
    """Return a page only when structured and PDF evidence proves a safe body region."""
    if document.schema_version != "1.3" or page_model.classification is not PageClassification.TEXT:
        return None
    candidates: list[tuple[int, LogicalParagraph]] = []
    for index, paragraph in enumerate(document.paragraphs):
        if paragraph.anchor_page_number != page_model.page_number:
            continue
        if paragraph.kind not in {ParagraphKind.BODY, ParagraphKind.HEADING}:
            continue
        # Reconstruction can label short running titles and page numbers as body
        # when a selected artifact has too few pages for repeated-element evidence.
        # Margin geometry is therefore an anchored exclusion, never flow evidence.
        if (
            paragraph.bbox.y0 < page_model.height * 0.07
            or paragraph.bbox.y1 > page_model.height * 0.92
        ):
            continue
        if (
            paragraph_policy(document, paragraph) is not RepeatedElementPolicy.TRANSLATE
            or paragraph.translated_text is None
            or not paragraph.translated_text.strip()
            or any(
                fragment.mapping.page_number != page_model.page_number or fragment.column != 0
                for fragment in paragraph.fragments
            )
        ):
            return None
        candidates.append((index, paragraph))
    body = [item for item in candidates if item[1].kind is ParagraphKind.BODY]
    headings = [item for item in candidates if item[1].kind is ParagraphKind.HEADING]
    if len(body) < 2 or not _stable_single_column(body, page_model):
        return None
    if not _ambiguity_resolved_by_page_evidence(candidates, body):
        return None
    if headings and not _single_heading_style(headings):
        return None

    body_rects = [rect_from_bbox(item.bbox) for _, item in body]
    flow_rects = [rect_from_bbox(item.bbox) for _, item in candidates]
    x0 = min(item.x0 for item in body_rects)
    x1 = max(item.x1 for item in body_rects)
    y0 = min(item.y0 for item in flow_rects)
    if y0 < page_model.height * 0.07:
        return None
    footnote_top = min(
        (
            item.bbox.y0
            for item in document.paragraphs
            if item.anchor_page_number == page_model.page_number
            and item.kind is ParagraphKind.FOOTNOTE
            and item.bbox.y0 > y0
        ),
        default=page_model.height * 0.90,
    )
    separator_top = _nearest_horizontal_separator_top(
        page,
        footnote_top,
        max(item.y1 for item in flow_rects),
    )
    footnote_boundary = min(footnote_top, separator_top or footnote_top)
    y1 = min(
        page_model.height * 0.90,
        footnote_boundary - max(4.0, default_font_size * 0.5),
    )
    y1 = max(y1, max(item.y1 for item in flow_rects))
    if y1 <= y0 or x1 <= x0:
        return None
    region = Rect(x0, y0, x1, y1)
    selected = {index for index, _ in candidates}
    if intersects_unselected(document, page_model.page_number, selected, region):
        return None
    if _intersects_pdf_objects(page, region):
        return None

    flow: list[FlowParagraph] = []
    for index, paragraph in sorted(candidates, key=lambda item: item[0]):
        source_rect = rect_from_bbox(paragraph.bbox)
        if not region.contains(source_rect):
            return None
        source_size = paragraph_font_size(paragraph, default_font_size)
        is_heading = paragraph.kind is ParagraphKind.HEADING
        font_size = max(min_font_size, source_size)
        if is_heading:
            font_size = max(font_size, default_font_size * 1.15)
        flow.append(
            FlowParagraph(
                occurrence_index=index,
                paragraph_id=paragraph.id,
                source_page_number=page_model.page_number,
                kind=paragraph.kind.value,
                disposition=(
                    ContentDisposition.FLOWABLE_HEADING
                    if is_heading
                    else ContentDisposition.FLOWABLE_BODY
                ),
                text=paragraph.translated_text or "",
                source_rect=source_rect,
                source_fragment_rects=tuple(
                    rect_from_bbox(fragment.bbox) for fragment in paragraph.fragments
                ),
                style=ReflowStyle(
                    font_size=font_size,
                    line_height=line_height,
                    paragraph_spacing=font_size * (0.65 if is_heading else 0.45),
                    heading=is_heading,
                ),
                color=paragraph_color(paragraph),
            )
        )
    return ReflowPage(
        source_page_number=page_model.page_number,
        occurrence_indexes=tuple(item.occurrence_index for item in flow),
        paragraphs=tuple(flow),
        region_rect=region,
    )


def _stable_single_column(body: list[tuple[int, LogicalParagraph]], page: ExtractedPage) -> bool:
    rects = [item.bbox for _, item in body]
    if any((item.x1 - item.x0) < page.width * 0.42 for item in rects):
        return False
    x0_spread = max(item.x0 for item in rects) - min(item.x0 for item in rects)
    x1_spread = max(item.x1 for item in rects) - min(item.x1 for item in rects)
    # A justified/left-aligned body has a stable left edge; ragged-right lines may
    # legitimately leave a wider final-line spread without indicating another column.
    return x0_spread <= max(14.0, page.width * 0.04) and x1_spread <= max(24.0, page.width * 0.14)


def _single_heading_style(headings: list[tuple[int, LogicalParagraph]]) -> bool:
    sizes = [paragraph_font_size(item, 11.0) for _, item in headings]
    return max(sizes) - min(sizes) <= 1.0


def _ambiguity_resolved_by_page_evidence(
    candidates: list[tuple[int, LogicalParagraph]],
    body: list[tuple[int, LogicalParagraph]],
) -> bool:
    ambiguous = [item for item in candidates if item[1].ambiguous]
    if not ambiguous:
        return True
    # A partial or isolated ambiguity remains unsafe. Some book artifacts mark every
    # boundary in a homogeneous body column ambiguous; at least three same-column,
    # stable-width body occurrences provide stronger page-level evidence than those
    # local boundary flags. Other safety checks still run before eligibility succeeds.
    return len(body) >= 3 and len(ambiguous) == len(candidates)


def intersects_unselected(
    document: ExtractedDocument,
    page_number: int,
    selected: set[int],
    region: Rect,
) -> bool:
    for index, paragraph in enumerate(document.paragraphs):
        if index in selected:
            continue
        for fragment in paragraph.fragments:
            if fragment.mapping.page_number == page_number and region.intersects(
                rect_from_bbox(fragment.bbox)
            ):
                return True
    return False


def _intersects_pdf_objects(page: pymupdf.Page, region: Rect) -> bool:
    for image in page.get_image_info(xrefs=True):
        if region.intersects(Rect(*map(float, image["bbox"]))):
            return True
    for drawing in page.get_drawings():
        drawing_rect = drawing.get("rect")
        if (
            isinstance(drawing_rect, pymupdf.Rect)
            and drawing_rect.get_area() > 1.0
            and region.intersects(
                Rect(
                    float(drawing_rect.x0),
                    float(drawing_rect.y0),
                    float(drawing_rect.x1),
                    float(drawing_rect.y1),
                )
            )
        ):
            return True
    return False


def _nearest_horizontal_separator_top(
    page: pymupdf.Page, footnote_top: float, body_bottom: float
) -> float | None:
    candidates = tuple(
        float(raw.y0)
        for drawing in page.get_drawings()
        if isinstance((raw := drawing.get("rect")), pymupdf.Rect)
        and raw.width >= page.rect.width * 0.10
        and raw.height <= 2.5
        and raw.y0 >= body_bottom
        and raw.y1 <= footnote_top + 1.0
    )
    return max(candidates, default=None)


def paragraph_policy(
    document: ExtractedDocument, paragraph: LogicalParagraph
) -> RepeatedElementPolicy:
    if document.repeated_elements is None:
        return RepeatedElementPolicy.TRANSLATE
    by_id = document.repeated_elements.by_block_id()
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


def paragraph_font_size(paragraph: LogicalParagraph, default: float) -> float:
    sizes = [span.font_size for span in paragraph.spans if span.font_size and span.font_size > 0]
    return float(statistics.median(sizes)) if sizes else default


def paragraph_color(paragraph: LogicalParagraph) -> tuple[float, float, float]:
    packed = next((span.text_color for span in paragraph.spans if span.text_color is not None), 0)
    return (
        float((packed >> 16) & 0xFF) / 255.0,
        float((packed >> 8) & 0xFF) / 255.0,
        float(packed & 0xFF) / 255.0,
    )


def rect_from_bbox(box: BoundingBox) -> Rect:
    return Rect(float(box.x0), float(box.y0), float(box.x1), float(box.y1))
