"""Conservative ordered footnote-group discovery for production pagination."""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf

from pdftranslate.domain.document import ExtractedDocument
from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.reconstruction import LogicalParagraph, ParagraphKind
from pdftranslate.rendering.inline_styles import map_inline_styles
from pdftranslate.rendering.reflow.models import (
    ContentDisposition,
    FlowParagraph,
    Rect,
    ReflowStyle,
)
from pdftranslate.rendering.reflow.regions import (
    intersects_unselected,
    paragraph_color,
    paragraph_font_size,
    paragraph_policy,
    rect_from_bbox,
)
from pdftranslate.rendering.reflow.typography import footnote_reflow_style
from pdftranslate.repeated import RepeatedElementPolicy
from pdftranslate.typography import ResolvedParagraphStyle


@dataclass(frozen=True)
class FootnotePage:
    """One ordered, safely classified footnote column on a source page."""

    source_page_number: int
    occurrence_indexes: tuple[int, ...]
    paragraphs: tuple[FlowParagraph, ...]
    source_region_rect: Rect
    continuation_region_rect: Rect
    separator_rect: Rect | None = None


def discover_footnote_page(
    document: ExtractedDocument,
    page_model: ExtractedPage,
    page: pymupdf.Page,
    *,
    body_region: Rect | None,
    default_font_size: float,
    min_font_size: float,
    line_height: float,
    style_by_occurrence: dict[int, ResolvedParagraphStyle] | None = None,
) -> FootnotePage | None:
    """Return a footnote group only when structured and PDF evidence is safe."""
    if document.schema_version != "1.3" or page_model.classification is not PageClassification.TEXT:
        return None
    candidates = tuple(
        (index, paragraph)
        for index, paragraph in enumerate(document.paragraphs)
        if paragraph.anchor_page_number == page_model.page_number
        and paragraph.kind is ParagraphKind.FOOTNOTE
    )
    if not candidates:
        return None
    if any(
        not _eligible_footnote(document, page_model.page_number, item) for _, item in candidates
    ):
        return None
    if not _stable_group_x_range(candidates, page_model.width, body_region):
        return None

    note_top = min(item.bbox.y0 for _, item in candidates)
    note_bottom = max(item.bbox.y1 for _, item in candidates)
    gap = max(4.0, default_font_size * 0.5)
    body_bottom = max(
        (
            item.bbox.y1
            for item in document.paragraphs
            if item.anchor_page_number == page_model.page_number
            and item.kind in {ParagraphKind.BODY, ParagraphKind.HEADING}
            and item.bbox.y1 <= note_top
        ),
        default=0.0,
    )
    if body_region is not None:
        body_bottom = max(body_bottom, body_region.y1)
    if body_bottom + gap > note_top + 0.5:
        return None

    selected = {index for index, _ in candidates}
    lower_anchor_top = min(
        (
            fragment.bbox.y0
            for index, paragraph in enumerate(document.paragraphs)
            if index not in selected
            for fragment in paragraph.fragments
            if fragment.mapping.page_number == page_model.page_number
            and fragment.bbox.y0 >= note_bottom - 0.5
        ),
        default=page_model.height * 0.97 + gap,
    )
    region_bottom = min(page_model.height * 0.97, lower_anchor_top - gap)
    if region_bottom < note_bottom - 0.5:
        return None
    source_x0 = min(item.bbox.x0 for _, item in candidates)
    source_x1 = max(item.bbox.x1 for _, item in candidates)
    if body_region is not None and all(
        item.bbox.x0 >= body_region.x0 - 2.0 and item.bbox.x1 <= body_region.x1 + 2.0
        for _, item in candidates
    ):
        source_x0, source_x1 = body_region.x0, body_region.x1
    source_region = Rect(
        source_x0,
        note_top,
        source_x1,
        region_bottom,
    )
    if intersects_unselected(document, page_model.page_number, selected, source_region):
        return None

    separator = _find_separator(page, note_top, body_bottom)
    if _intersects_unsafe_objects(page, source_region, separator):
        return None

    flow: list[FlowParagraph] = []
    for index, paragraph in candidates:
        resolved_style: ResolvedParagraphStyle | None = None
        if style_by_occurrence is None:
            source_size = paragraph_font_size(paragraph, default_font_size)
            font_size = max(min_font_size, source_size)
            style = ReflowStyle(
                font_size=font_size,
                line_height=line_height,
                space_before=0.0,
                space_after=font_size * 0.25,
            )
            color = paragraph_color(paragraph)
        else:
            resolved = _resolved_occurrence(style_by_occurrence, index, paragraph)
            if resolved is None:
                return None
            resolved_style = resolved
            try:
                style, color = footnote_reflow_style(resolved)
            except ValueError:
                return None
        source_rect = rect_from_bbox(paragraph.bbox)
        flow.append(
            FlowParagraph(
                occurrence_index=index,
                paragraph_id=paragraph.id,
                source_page_number=page_model.page_number,
                kind=ParagraphKind.FOOTNOTE.value,
                disposition=ContentDisposition.FLOWABLE_FOOTNOTE,
                text=paragraph.translated_text or "",
                source_rect=source_rect,
                source_fragment_rects=tuple(
                    rect_from_bbox(fragment.bbox) for fragment in paragraph.fragments
                ),
                style=style,
                color=color,
                inline_styles=map_inline_styles(
                    paragraph,
                    translated_text=paragraph.translated_text or "",
                    base_font_size=style.font_size,
                    base_color=color,
                    base_bold=style.bold_requested,
                    base_italic=style.italic_requested,
                    base_font_family_group=(
                        resolved_style.source_font_family_group
                        if resolved_style is not None
                        else None
                    ),
                ),
            )
        )
    continuation = Rect(
        source_region.x0,
        max(36.0, page_model.height * 0.08),
        source_region.x1,
        page_model.height * 0.90,
    )
    return FootnotePage(
        source_page_number=page_model.page_number,
        occurrence_indexes=tuple(item.occurrence_index for item in flow),
        paragraphs=tuple(flow),
        source_region_rect=source_region,
        continuation_region_rect=continuation,
        separator_rect=separator,
    )


def _resolved_occurrence(
    style_by_occurrence: dict[int, ResolvedParagraphStyle],
    occurrence_index: int,
    paragraph: LogicalParagraph,
) -> ResolvedParagraphStyle | None:
    resolved = style_by_occurrence.get(occurrence_index)
    if (
        resolved is None
        or resolved.occurrence_index != occurrence_index
        or resolved.paragraph_id != paragraph.id
    ):
        return None
    return resolved


def _eligible_footnote(
    document: ExtractedDocument, page_number: int, paragraph: LogicalParagraph
) -> bool:
    return (
        paragraph_policy(document, paragraph) is RepeatedElementPolicy.TRANSLATE
        and paragraph.translated_text is not None
        and bool(paragraph.translated_text.strip())
        and bool(paragraph.fragments)
        and all(
            fragment.mapping.page_number == page_number and fragment.column == 0
            for fragment in paragraph.fragments
        )
    )


def _stable_group_x_range(
    candidates: tuple[tuple[int, LogicalParagraph], ...],
    page_width: float,
    body_region: Rect | None,
) -> bool:
    grouped: dict[str, list[LogicalParagraph]] = {}
    for _, paragraph in candidates:
        grouped.setdefault(paragraph.id, []).append(paragraph)
    unions = tuple(
        (
            min(item.bbox.x0 for item in paragraphs),
            max(item.bbox.x1 for item in paragraphs),
        )
        for paragraphs in grouped.values()
    )
    if len(unions) < 2:
        x0, x1 = unions[0]
        return x1 - x0 >= page_width * 0.15 or (
            body_region is not None and x0 >= body_region.x0 - 2.0 and x1 <= body_region.x1 + 2.0
        )
    if any(x1 - x0 < page_width * 0.40 for x0, x1 in unions):
        return False
    x0s = tuple(item[0] for item in unions)
    x1s = tuple(item[1] for item in unions)
    return max(x0s) - min(x0s) <= max(20.0, page_width * 0.08) and max(x1s) - min(x1s) <= max(
        24.0, page_width * 0.10
    )


def _find_separator(page: pymupdf.Page, note_top: float, body_bottom: float) -> Rect | None:
    candidates: list[Rect] = []
    for drawing in page.get_drawings():
        raw = drawing.get("rect")
        if not isinstance(raw, pymupdf.Rect) or raw.width < page.rect.width * 0.10:
            continue
        if raw.height > 2.5 or raw.y0 < body_bottom - 1.0 or raw.y1 > note_top + 1.0:
            continue
        candidates.append(Rect(float(raw.x0), float(raw.y0), float(raw.x1), float(raw.y1 + 0.1)))
    return max(candidates, key=lambda item: item.width, default=None)


def _intersects_unsafe_objects(page: pymupdf.Page, region: Rect, separator: Rect | None) -> bool:
    for image in page.get_image_info(xrefs=True):
        if region.intersects(Rect(*map(float, image["bbox"]))):
            return True
    for drawing in page.get_drawings():
        raw = drawing.get("rect")
        if not isinstance(raw, pymupdf.Rect) or raw.get_area() <= 1.0:
            continue
        candidate = Rect(float(raw.x0), float(raw.y0), float(raw.x1), float(raw.y1))
        if separator is not None and candidate.intersects(separator):
            continue
        if region.intersects(candidate):
            return True
    return False
