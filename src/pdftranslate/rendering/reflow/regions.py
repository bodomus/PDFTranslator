"""Conservative production eligibility and single-column region discovery."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, replace
from pathlib import Path

import pymupdf

from pdftranslate.domain.document import ExtractedDocument
from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox
from pdftranslate.list_markers import detect_list_marker
from pdftranslate.reconstruction import LogicalParagraph, ParagraphKind
from pdftranslate.rendering.inline_styles import InlineStyleMapping, map_inline_styles
from pdftranslate.rendering.reflow.models import (
    ContentDisposition,
    FlowParagraph,
    Rect,
    ReflowStyle,
)
from pdftranslate.rendering.reflow.typography import (
    body_reflow_style,
    heading_reflow_style,
    list_reflow_style,
)
from pdftranslate.repeated import RepeatedElementPolicy
from pdftranslate.typography import ResolvedParagraphStyle


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
    style_by_occurrence: dict[int, ResolvedParagraphStyle] | None = None,
    font_path: Path | None = None,
) -> ReflowPage | None:
    """Return a page only when structured and PDF evidence proves a safe body region."""
    if document.schema_version != "1.3" or page_model.classification is not PageClassification.TEXT:
        return None
    flow_candidates: list[tuple[int, LogicalParagraph]] = []
    list_candidates: list[tuple[int, LogicalParagraph, str]] = []
    for index, paragraph in enumerate(document.paragraphs):
        if paragraph.anchor_page_number != page_model.page_number:
            continue
        marker = detect_list_marker(paragraph.text)
        is_list = marker is not None and paragraph.kind in {
            ParagraphKind.BODY,
            ParagraphKind.HEADING,
            ParagraphKind.LIST_ITEM,
        }
        if not is_list and paragraph.kind not in {ParagraphKind.BODY, ParagraphKind.HEADING}:
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
        if is_list:
            translated_text = paragraph.translated_text
            if not translated_text or not translated_text.strip():
                continue
            list_candidates.append((index, paragraph, translated_text))
            continue
        flow_candidates.append((index, paragraph))
    body = [item for item in flow_candidates if item[1].kind is ParagraphKind.BODY]
    list_structural = [
        (index, paragraph)
        for index, paragraph, _ in list_candidates
        if paragraph.kind in {ParagraphKind.BODY, ParagraphKind.LIST_ITEM}
    ]
    if body:
        if len(body) < 2 or not _stable_single_column(body, page_model):
            return None
        if list_structural and not _stable_list_column(list_structural, page_model):
            return None
    elif not list_structural or not _stable_list_column(list_structural, page_model):
        return None
    ambiguity_candidates = [
        *flow_candidates,
        *((index, paragraph) for index, paragraph, _ in list_candidates),
    ]
    if not _ambiguity_resolved_by_page_evidence(ambiguity_candidates, body):
        return None
    if body:
        x_rects = [rect_from_bbox(item.bbox) for _, item in body]
    else:
        x_rects = [rect_from_bbox(item.bbox) for _, item in list_structural]
    flow_rects = [rect_from_bbox(item.bbox) for _, item in flow_candidates]
    flow_rects.extend(rect_from_bbox(item.bbox) for _, item, _ in list_candidates)
    x0 = min(item.x0 for item in x_rects)
    x1 = max(item.x1 for item in x_rects)
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
    selected = {index for index, _ in flow_candidates} | {index for index, _, _ in list_candidates}
    if intersects_unselected(document, page_model.page_number, selected, region):
        return None
    if _intersects_pdf_objects(page, region):
        return None

    list_by_index = {
        index: (paragraph, reconstructed) for index, paragraph, reconstructed in list_candidates
    }
    ordered = sorted(
        (*flow_candidates, *((index, paragraph) for index, paragraph, _ in list_candidates)),
        key=lambda item: item[0],
    )
    flow: list[FlowParagraph] = []
    for index, paragraph in ordered:
        if index in list_by_index:
            list_item = _list_flow_paragraph(
                page_model,
                index,
                paragraph,
                list_by_index[index][1],
                region,
                default_font_size,
                min_font_size,
                line_height,
                style_by_occurrence,
                font_path,
            )
            if list_item is None:
                return None
            flow.append(list_item)
            continue
        source_rect = rect_from_bbox(paragraph.bbox)
        if not region.contains(source_rect):
            return None
        source_size = paragraph_font_size(paragraph, default_font_size)
        is_heading = paragraph.kind is ParagraphKind.HEADING
        font_size = max(min_font_size, source_size)
        resolved_style: ResolvedParagraphStyle | None = None
        if is_heading:
            if style_by_occurrence is None:
                font_size = max(font_size, default_font_size * 1.15)
                style = ReflowStyle(
                    font_size=font_size,
                    line_height=line_height,
                    space_before=0.0,
                    space_after=font_size * 0.65,
                    heading=True,
                )
                color = paragraph_color(paragraph)
            else:
                resolved = _resolved_occurrence(style_by_occurrence, index, paragraph)
                if resolved is None:
                    return None
                resolved_style = resolved
                try:
                    style, color = heading_reflow_style(resolved)
                except ValueError:
                    return None
        else:
            if style_by_occurrence is None:
                style = ReflowStyle(
                    font_size=font_size,
                    line_height=line_height,
                    space_before=0.0,
                    space_after=font_size * 0.45,
                )
                color = paragraph_color(paragraph)
            else:
                resolved = _resolved_occurrence(style_by_occurrence, index, paragraph)
                if resolved is None:
                    return None
                resolved_style = resolved
                try:
                    style, color = body_reflow_style(resolved)
                except ValueError:
                    return None
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


def _stable_list_column(items: list[tuple[int, LogicalParagraph]], page: ExtractedPage) -> bool:
    rects = [item.bbox for _, item in items]
    if len(rects) < 2:
        # A single confident item has no sibling to contradict a single column. Its
        # marker/content geometry is validated later against the flow region.
        return True
    x0_spread = max(item.x0 for item in rects) - min(item.x0 for item in rects)
    x1_spread = max(item.x1 for item in rects) - min(item.x1 for item in rects)
    # List items are intentionally narrower than a full body column, so the body width
    # guard does not apply. Only the shared left/right edges evidence one list column.
    return x0_spread <= max(14.0, page.width * 0.04) and x1_spread <= max(24.0, page.width * 0.14)


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


def _list_flow_paragraph(
    page_model: ExtractedPage,
    index: int,
    paragraph: LogicalParagraph,
    reconstructed_text: str,
    region: Rect,
    default_font_size: float,
    min_font_size: float,
    line_height: float,
    style_by_occurrence: dict[int, ResolvedParagraphStyle] | None,
    font_path: Path | None,
) -> FlowParagraph | None:
    source_rect = rect_from_bbox(paragraph.bbox)
    if not region.contains(source_rect):
        return None
    source_size = paragraph_font_size(paragraph, default_font_size)
    font_size = max(min_font_size, source_size)
    is_heading = paragraph.kind is ParagraphKind.HEADING
    if style_by_occurrence is not None:
        resolved = _resolved_occurrence(style_by_occurrence, index, paragraph)
        if resolved is None:
            return None
        try:
            if is_heading:
                style, color = heading_reflow_style(resolved)
            elif paragraph.kind is ParagraphKind.LIST_ITEM:
                style, color = list_reflow_style(resolved)
            else:
                style, color = body_reflow_style(resolved)
        except ValueError:
            return None
    elif is_heading:
        font_size = max(font_size, default_font_size * 1.15)
        style = ReflowStyle(
            font_size=font_size,
            line_height=line_height,
            space_before=0.0,
            space_after=font_size * 0.65,
            heading=True,
        )
        color = paragraph_color(paragraph)
    else:
        style = ReflowStyle(
            font_size=font_size,
            line_height=line_height,
            space_before=0.0,
            space_after=font_size * 0.45,
        )
        color = paragraph_color(paragraph)
    list_style = _list_item_style(style, paragraph, region, font_path, font_size)
    if list_style is None:
        return None
    return FlowParagraph(
        occurrence_index=index,
        paragraph_id=paragraph.id,
        source_page_number=page_model.page_number,
        kind=paragraph.kind.value,
        disposition=(
            ContentDisposition.FLOWABLE_HEADING if is_heading else ContentDisposition.FLOWABLE_BODY
        ),
        text=reconstructed_text,
        source_rect=source_rect,
        source_fragment_rects=tuple(
            rect_from_bbox(fragment.bbox) for fragment in paragraph.fragments
        ),
        style=list_style,
        color=color,
        inline_styles=InlineStyleMapping(),
    )


def _list_item_style(
    style: ReflowStyle,
    paragraph: LogicalParagraph,
    region: Rect,
    font_path: Path | None,
    font_size: float,
) -> ReflowStyle | None:
    marker = detect_list_marker(paragraph.text)
    if marker is None:
        return None
    marker_x = min(fragment.bbox.x0 for fragment in paragraph.fragments)
    if marker_x < region.x0 - 1e-6:
        return None
    content_x = _source_content_x(paragraph, marker_x, region, font_path, font_size)
    if content_x <= marker_x:
        return None
    # The marker is a separate source-backed run at marker_x, and the semantic content begins
    # at the same source content edge on every line, so the first line has no hanging indent.
    return replace(
        style,
        left_indent=max(0.0, content_x - region.x0),
        first_line_indent=0.0,
        list_marker=marker.marker_text,
        list_marker_offset=content_x - marker_x,
    )


def _source_content_x(
    paragraph: LogicalParagraph,
    marker_x: float,
    region: Rect,
    font_path: Path | None,
    font_size: float,
) -> float:
    if len(paragraph.fragments) >= 2:
        content_x = float(
            statistics.median(fragment.bbox.x0 for fragment in paragraph.fragments[1:])
        )
        if content_x > marker_x and content_x <= region.x1:
            return content_x
    if font_path is not None:
        marker = detect_list_marker(paragraph.text)
        if marker is not None:
            font = pymupdf.Font(fontfile=str(font_path))  # type: ignore[no-untyped-call]
            content_x = marker_x + float(
                font.text_length(  # type: ignore[no-untyped-call]
                    f"{marker.marker_text}{marker.separation}",
                    fontsize=font_size,
                )
            )
            if content_x > marker_x and content_x <= region.x1:
                return content_x
    return marker_x


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
