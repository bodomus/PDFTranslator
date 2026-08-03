"""Conservative deterministic paragraph reconstruction from extracted pages."""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from pdftranslate.domain.page import ExtractedPage
from pdftranslate.domain.text_block import BoundingBox, TextBlock, TextSpan
from pdftranslate.reconstruction.models import (
    DecisionAction,
    DecisionReason,
    LogicalParagraph,
    ParagraphFragment,
    ParagraphKind,
    ParagraphReconstruction,
    ParagraphReconstructionOptions,
    ReconstructionDecision,
    ReconstructionMetrics,
    ReconstructionResult,
    SourceBlockMapping,
)

_LIST_MARKER = re.compile(r"^\s*(?:[•◦▪‣]|[-*+]\s|\(?\d+[.)]\s|[A-Za-z][.)]\s)")
_CAPTION = re.compile(r"^\s*(?:figure|fig\.?|table|chart|image)\s+\d+\b", re.IGNORECASE)
_TERMINAL = frozenset(".?!:;")
_LEGITIMATE_HYPHEN_PREFIXES = frozenset(
    {"well", "ill", "self", "non", "pre", "post", "high", "low", "long", "short"}
)


@dataclass(frozen=True)
class _PageLayout:
    page: ExtractedPage
    fragments: tuple[ParagraphFragment, ...]
    median_font_size: float
    two_columns: bool


def reconstruct_paragraphs(
    pages: Sequence[ExtractedPage],
    options: ParagraphReconstructionOptions | None = None,
) -> ReconstructionResult:
    """Build deterministic logical paragraphs and auditable merge evidence."""
    selected = options or ParagraphReconstructionOptions()
    repeated_margin_text = _repeated_margin_text(pages, selected)
    layouts = tuple(_page_layout(page, selected) for page in pages)
    raw_blocks = sum(len(page.text_blocks) for page in pages)
    raw_lines = sum(max(1, len(block.lines)) for page in pages for block in page.text_blocks)

    if selected.mode == "off":
        off_paragraphs = tuple(
            _paragraph_from_fragments(
                (fragment,),
                _kind(fragment, layout, repeated_margin_text, selected),
                ambiguous=False,
            )
            for layout in layouts
            for fragment in _block_fragments(layout.page)
        )
        return ReconstructionResult(
            paragraphs=off_paragraphs,
            evidence=ParagraphReconstruction(
                mode=selected.mode,
                options=selected,
                metrics=ReconstructionMetrics(
                    raw_blocks=raw_blocks,
                    raw_lines=raw_lines,
                    logical_paragraphs=len(off_paragraphs),
                    merged_fragments=0,
                    ambiguous_decisions=0,
                    cross_page_merges=0,
                    soft_hyphens_removed=0,
                ),
            ),
        )

    paragraphs: list[LogicalParagraph] = []
    decisions: list[ReconstructionDecision] = []
    soft_hyphens_removed = 0
    for layout in layouts:
        page_paragraphs, page_decisions, removed = _reconstruct_page(
            layout, repeated_margin_text, selected
        )
        paragraphs.extend(page_paragraphs)
        decisions.extend(page_decisions)
        soft_hyphens_removed += removed

    paragraphs, cross_page_decisions, removed = _merge_across_pages(paragraphs, layouts, selected)
    decisions.extend(cross_page_decisions)
    soft_hyphens_removed += removed
    return ReconstructionResult(
        paragraphs=tuple(paragraphs),
        evidence=ParagraphReconstruction(
            mode=selected.mode,
            options=selected,
            decisions=tuple(decisions),
            metrics=ReconstructionMetrics(
                raw_blocks=raw_blocks,
                raw_lines=raw_lines,
                logical_paragraphs=len(paragraphs),
                merged_fragments=sum(len(paragraph.fragments) - 1 for paragraph in paragraphs),
                ambiguous_decisions=sum(
                    decision.action is DecisionAction.AMBIGUOUS for decision in decisions
                ),
                cross_page_merges=sum(
                    decision.action is DecisionAction.MERGE and decision.cross_page
                    for decision in decisions
                ),
                soft_hyphens_removed=soft_hyphens_removed,
            ),
        ),
    )


def _page_layout(page: ExtractedPage, options: ParagraphReconstructionOptions) -> _PageLayout:
    fragments = _line_fragments(page)
    font_sizes = [
        size
        for fragment in fragments
        for span in fragment.spans
        if (size := span.font_size) is not None and size > 0
    ]
    median_font_size = statistics.median(font_sizes) if font_sizes else 0.0
    two_columns = _has_two_columns(fragments, page.width, options)
    if two_columns:
        fragments = tuple(
            fragment.model_copy(update={"column": _column(fragment.bbox, page.width)})
            for fragment in fragments
        )
        fragments = tuple(
            sorted(fragments, key=lambda item: (item.column, item.bbox.y0, item.bbox.x0, item.id))
        )
    else:
        fragments = tuple(sorted(fragments, key=lambda item: (item.bbox.y0, item.bbox.x0, item.id)))
    return _PageLayout(
        page=page,
        fragments=fragments,
        median_font_size=median_font_size,
        two_columns=two_columns,
    )


def _line_fragments(page: ExtractedPage) -> tuple[ParagraphFragment, ...]:
    fragments: list[ParagraphFragment] = []
    for block in page.text_blocks:
        mapping = _mapping(block, page.page_number)
        if block.lines:
            for line in block.lines:
                fragments.append(
                    ParagraphFragment(
                        id=line.id,
                        text=line.text,
                        bbox=line.bbox,
                        mapping=mapping,
                        spans=line.spans,
                        column=0,
                    )
                )
        else:
            fragments.append(
                ParagraphFragment(
                    id=f"{block.id}-l0001",
                    text=block.text,
                    bbox=block.bbox,
                    mapping=mapping,
                    spans=block.spans,
                    column=0,
                )
            )
    return tuple(fragments)


def _block_fragments(page: ExtractedPage) -> tuple[ParagraphFragment, ...]:
    return tuple(
        ParagraphFragment(
            id=f"{block.id}-f0001",
            text=block.text,
            bbox=block.bbox,
            mapping=_mapping(block, page.page_number),
            spans=block.spans,
            column=0,
        )
        for block in page.text_blocks
    )


def _mapping(block: TextBlock, page_number: int) -> SourceBlockMapping:
    return SourceBlockMapping(
        source_block_id=block.id,
        page_number=page_number,
        bbox=block.bbox,
        original_order=block.original_order,
        normalized_order=block.normalized_order,
        line_ids=tuple(line.id for line in block.lines),
    )


def _reconstruct_page(
    layout: _PageLayout,
    repeated_margin_text: frozenset[tuple[str, str]],
    options: ParagraphReconstructionOptions,
) -> tuple[list[LogicalParagraph], list[ReconstructionDecision], int]:
    paragraphs: list[LogicalParagraph] = []
    decisions: list[ReconstructionDecision] = []
    removed = 0
    current: list[ParagraphFragment] = []
    current_kind: ParagraphKind | None = None
    current_ambiguous = False
    for fragment in layout.fragments:
        kind = _kind(fragment, layout, repeated_margin_text, options)
        if not current:
            current = [fragment]
            current_kind = kind
            continue
        action, reasons = _decide(current[-1], fragment, current_kind, kind, layout, options)
        decisions.append(
            ReconstructionDecision(
                previous_fragment_id=current[-1].id,
                current_fragment_id=fragment.id,
                action=action,
                reasons=reasons,
                page_number=layout.page.page_number,
            )
        )
        if action is DecisionAction.MERGE:
            if DecisionReason.SOFT_HYPHEN in reasons:
                removed += 1
            current.append(fragment)
            continue
        if action is DecisionAction.AMBIGUOUS:
            current_ambiguous = True
        assert current_kind is not None
        paragraphs.append(
            _paragraph_from_fragments(tuple(current), current_kind, current_ambiguous)
        )
        current = [fragment]
        current_kind = kind
        current_ambiguous = action is DecisionAction.AMBIGUOUS
    if current:
        assert current_kind is not None
        paragraphs.append(
            _paragraph_from_fragments(tuple(current), current_kind, current_ambiguous)
        )
    return paragraphs, decisions, removed


def _decide(
    previous: ParagraphFragment,
    current: ParagraphFragment,
    previous_kind: ParagraphKind | None,
    current_kind: ParagraphKind,
    layout: _PageLayout,
    options: ParagraphReconstructionOptions,
) -> tuple[DecisionAction, tuple[DecisionReason, ...]]:
    if previous_kind in {ParagraphKind.HEADER, ParagraphKind.FOOTER} or current_kind in {
        ParagraphKind.HEADER,
        ParagraphKind.FOOTER,
    }:
        return DecisionAction.KEEP, (DecisionReason.REPEATED_MARGIN_TEXT,)
    boundary_reason = _kind_boundary(previous_kind, current_kind)
    if boundary_reason is not None:
        return DecisionAction.KEEP, (boundary_reason,)
    if previous.column != current.column:
        return DecisionAction.KEEP, (DecisionReason.COLUMN_BOUNDARY,)

    reasons: list[DecisionReason] = [DecisionReason.SAME_COLUMN]
    aligned = abs(previous.bbox.x0 - current.bbox.x0) <= options.left_alignment_tolerance
    indented = abs(previous.bbox.x0 - current.bbox.x0) <= options.indentation_tolerance
    if aligned:
        reasons.append(DecisionReason.ALIGNED)
    elif not indented:
        return DecisionAction.KEEP, (*reasons, DecisionReason.INDENTATION_CHANGE)

    gap = current.bbox.y0 - previous.bbox.y1
    line_height = min(_height(previous.bbox), _height(current.bbox))
    if gap > line_height * options.max_vertical_gap_ratio or gap < -line_height * 0.35:
        return DecisionAction.KEEP, (*reasons, DecisionReason.GAP_TOO_LARGE)
    reasons.append(DecisionReason.CLOSE_VERTICAL_GAP)

    if _style_compatible(previous.spans, current.spans, layout.median_font_size):
        reasons.append(DecisionReason.COMPATIBLE_STYLE)
    else:
        return DecisionAction.KEEP, (*reasons, DecisionReason.STYLE_CHANGE)

    width_ratio = min(_width(previous.bbox), _width(current.bbox)) / max(
        _width(previous.bbox), _width(current.bbox)
    )
    same_source = previous.mapping.source_block_id == current.mapping.source_block_id
    if same_source:
        reasons.append(DecisionReason.SAME_SOURCE_BLOCK)
    elif width_ratio >= options.min_width_ratio:
        reasons.append(DecisionReason.SIMILAR_WIDTH)

    previous_text = previous.text.rstrip()
    current_text = current.text.lstrip()
    if _is_soft_hyphen(previous_text, current_text):
        return DecisionAction.MERGE, (*reasons, DecisionReason.SOFT_HYPHEN)
    if previous_text.endswith("-"):
        reasons.append(DecisionReason.PROTECTED_HYPHEN)
    if current_text and current_text[0].islower():
        reasons.append(DecisionReason.LOWERCASE_CONTINUATION)
    if previous_text and previous_text[-1] not in _TERMINAL:
        reasons.append(DecisionReason.UNFINISHED_SENTENCE)
    else:
        reasons.append(DecisionReason.TERMINAL_PUNCTUATION)

    continuation = any(
        reason in reasons
        for reason in (DecisionReason.LOWERCASE_CONTINUATION, DecisionReason.UNFINISHED_SENTENCE)
    )
    geometry = same_source or width_ratio >= options.min_width_ratio
    if continuation and geometry:
        return DecisionAction.MERGE, tuple(reasons)
    if geometry:
        return DecisionAction.AMBIGUOUS, (*reasons, DecisionReason.AMBIGUOUS_GEOMETRY)
    return DecisionAction.KEEP, tuple(reasons)


def _merge_across_pages(
    paragraphs: list[LogicalParagraph],
    layouts: Sequence[_PageLayout],
    options: ParagraphReconstructionOptions,
) -> tuple[list[LogicalParagraph], list[ReconstructionDecision], int]:
    if len(layouts) < 2 or len(paragraphs) < 2:
        return paragraphs, [], 0
    page_by_number = {layout.page.page_number: layout.page for layout in layouts}
    result: list[LogicalParagraph] = []
    decisions: list[ReconstructionDecision] = []
    removed = 0
    for paragraph in paragraphs:
        if not result:
            result.append(paragraph)
            continue
        previous = result[-1]
        previous_fragment = previous.fragments[-1]
        current_fragment = paragraph.fragments[0]
        cross_page = current_fragment.mapping.page_number != previous_fragment.mapping.page_number
        if not cross_page:
            result.append(paragraph)
            continue
        action, reasons = _decide_cross_page(
            previous,
            paragraph,
            page_by_number[previous_fragment.mapping.page_number],
            page_by_number[current_fragment.mapping.page_number],
            options,
        )
        decisions.append(
            ReconstructionDecision(
                previous_fragment_id=previous_fragment.id,
                current_fragment_id=current_fragment.id,
                action=action,
                reasons=reasons,
                page_number=current_fragment.mapping.page_number,
                cross_page=True,
            )
        )
        if action is DecisionAction.MERGE:
            if DecisionReason.SOFT_HYPHEN in reasons:
                removed += 1
            merged_text, _ = _join_text(previous.text, paragraph.text)
            result[-1] = previous.model_copy(
                update={
                    "text": merged_text,
                    "fragments": previous.fragments + paragraph.fragments,
                    "spans": previous.spans + paragraph.spans,
                    "ambiguous": previous.ambiguous or paragraph.ambiguous,
                }
            )
        else:
            result.append(
                paragraph.model_copy(
                    update={"ambiguous": paragraph.ambiguous or action is DecisionAction.AMBIGUOUS}
                )
            )
    return result, decisions, removed


def _decide_cross_page(
    previous: LogicalParagraph,
    current: LogicalParagraph,
    previous_page: ExtractedPage,
    current_page: ExtractedPage,
    options: ParagraphReconstructionOptions,
) -> tuple[DecisionAction, tuple[DecisionReason, ...]]:
    if current_page.page_number != previous_page.page_number + 1:
        return DecisionAction.KEEP, (DecisionReason.PAGE_BOUNDARY_WEAK,)
    if previous.kind is not ParagraphKind.BODY or current.kind is not ParagraphKind.BODY:
        boundary = _kind_boundary(previous.kind, current.kind) or DecisionReason.PAGE_BOUNDARY_WEAK
        return DecisionAction.KEEP, (boundary,)
    left = previous.fragments[-1]
    right = current.fragments[0]
    near_bottom = left.bbox.y1 >= previous_page.height * (1 - options.cross_page_edge_ratio)
    near_top = right.bbox.y0 <= current_page.height * options.cross_page_edge_ratio
    aligned = abs(left.bbox.x0 - right.bbox.x0) <= options.left_alignment_tolerance
    same_column = left.column == right.column
    text_continues = bool(right.text.lstrip() and right.text.lstrip()[0].islower())
    unfinished = bool(previous.text.rstrip() and previous.text.rstrip()[-1] not in _TERMINAL)
    reasons: list[DecisionReason] = []
    if same_column:
        reasons.append(DecisionReason.SAME_COLUMN)
    if aligned:
        reasons.append(DecisionReason.ALIGNED)
    if text_continues:
        reasons.append(DecisionReason.LOWERCASE_CONTINUATION)
    if unfinished:
        reasons.append(DecisionReason.UNFINISHED_SENTENCE)
    if _is_soft_hyphen(previous.text, current.text):
        reasons.append(DecisionReason.SOFT_HYPHEN)
    if near_bottom and near_top and same_column and aligned and (text_continues or unfinished):
        reasons.append(DecisionReason.CROSS_PAGE_CONTINUATION)
        return DecisionAction.MERGE, tuple(reasons)
    if same_column and aligned and (text_continues or unfinished):
        return DecisionAction.AMBIGUOUS, (*reasons, DecisionReason.PAGE_BOUNDARY_WEAK)
    return DecisionAction.KEEP, (*reasons, DecisionReason.PAGE_BOUNDARY_WEAK)


def _paragraph_from_fragments(
    fragments: tuple[ParagraphFragment, ...],
    kind: ParagraphKind,
    ambiguous: bool,
) -> LogicalParagraph:
    text = fragments[0].text.strip()
    for fragment in fragments[1:]:
        text, _ = _join_text(text, fragment.text)
    anchor_page = fragments[0].mapping.page_number
    anchor_boxes = [
        fragment.bbox for fragment in fragments if fragment.mapping.page_number == anchor_page
    ]
    return LogicalParagraph(
        id=fragments[0].mapping.source_block_id,
        text=text,
        kind=kind,
        anchor_page_number=anchor_page,
        bbox=_union(anchor_boxes),
        fragments=fragments,
        spans=tuple(span for fragment in fragments for span in fragment.spans),
        ambiguous=ambiguous,
    )


def _kind(
    fragment: ParagraphFragment,
    layout: _PageLayout,
    repeated_margin_text: frozenset[tuple[str, str]],
    options: ParagraphReconstructionOptions,
) -> ParagraphKind:
    normalized = _normalized_text(fragment.text)
    position = _margin_position(fragment.bbox, layout.page.height, options)
    if position is not None and (position, normalized) in repeated_margin_text:
        return ParagraphKind.HEADER if position == "top" else ParagraphKind.FOOTER
    if _LIST_MARKER.match(fragment.text):
        return ParagraphKind.LIST_ITEM
    if _CAPTION.match(fragment.text):
        return ParagraphKind.CAPTION
    font_size = _representative_font_size(fragment.spans)
    if (
        layout.median_font_size > 0
        and font_size > 0
        and font_size <= layout.median_font_size * options.footnote_font_ratio
        and fragment.bbox.y0 >= layout.page.height * 0.6
    ):
        return ParagraphKind.FOOTNOTE
    letters = "".join(character for character in fragment.text if character.isalpha())
    bold = any(span.bold for span in fragment.spans)
    larger = (
        layout.median_font_size > 0
        and font_size >= layout.median_font_size * options.heading_font_ratio
    )
    if len(fragment.text.split()) <= 12 and letters and (letters.isupper() or bold or larger):
        return ParagraphKind.HEADING
    return ParagraphKind.BODY


def _kind_boundary(previous: ParagraphKind | None, current: ParagraphKind) -> DecisionReason | None:
    if previous is ParagraphKind.HEADING or current is ParagraphKind.HEADING:
        return DecisionReason.HEADING_BOUNDARY
    if previous is ParagraphKind.LIST_ITEM or current is ParagraphKind.LIST_ITEM:
        return DecisionReason.LIST_BOUNDARY
    if previous is ParagraphKind.CAPTION or current is ParagraphKind.CAPTION:
        return DecisionReason.CAPTION_BOUNDARY
    if previous is ParagraphKind.FOOTNOTE or current is ParagraphKind.FOOTNOTE:
        return DecisionReason.FOOTNOTE_BOUNDARY
    return None


def _repeated_margin_text(
    pages: Sequence[ExtractedPage], options: ParagraphReconstructionOptions
) -> frozenset[tuple[str, str]]:
    occurrences: Counter[tuple[str, str]] = Counter()
    page_occurrences: defaultdict[tuple[str, str], set[int]] = defaultdict(set)
    for page in pages:
        for block in page.text_blocks:
            position = _margin_position(block.bbox, page.height, options)
            normalized = _normalized_text(block.text)
            if position is not None and normalized:
                page_occurrences[(position, normalized)].add(page.page_number)
    for key, page_numbers in page_occurrences.items():
        occurrences[key] = len(page_numbers)
    return frozenset(
        key for key, count in occurrences.items() if count >= options.repeated_margin_min_pages
    )


def _margin_position(
    bbox: BoundingBox, page_height: float, options: ParagraphReconstructionOptions
) -> str | None:
    if bbox.y1 <= page_height * options.margin_region_ratio:
        return "top"
    if bbox.y0 >= page_height * (1 - options.margin_region_ratio):
        return "bottom"
    return None


def _has_two_columns(
    fragments: Sequence[ParagraphFragment],
    page_width: float,
    options: ParagraphReconstructionOptions,
) -> bool:
    middle = page_width / 2
    gutter = page_width * options.column_gutter_ratio
    left = [fragment for fragment in fragments if fragment.bbox.x1 <= middle - gutter / 2]
    right = [fragment for fragment in fragments if fragment.bbox.x0 >= middle + gutter / 2]
    if not left or not right:
        return False
    return any(
        first.bbox.y0 < second.bbox.y1 and second.bbox.y0 < first.bbox.y1
        for first in left
        for second in right
    )


def _column(bbox: BoundingBox, page_width: float) -> int:
    middle = page_width / 2
    if bbox.x1 <= middle:
        return 0
    if bbox.x0 >= middle:
        return 1
    return 0


def _style_compatible(
    previous: Sequence[TextSpan], current: Sequence[TextSpan], median_font_size: float
) -> bool:
    previous_size = _representative_font_size(previous)
    current_size = _representative_font_size(current)
    tolerance = max(0.75, median_font_size * 0.08)
    if previous_size and current_size and abs(previous_size - current_size) > tolerance:
        return False
    previous_bold = any(span.bold for span in previous)
    current_bold = any(span.bold for span in current)
    return previous_bold == current_bold


def _representative_font_size(spans: Sequence[TextSpan]) -> float:
    values = [span.font_size for span in spans if span.font_size is not None and span.font_size > 0]
    return statistics.median(values) if values else 0.0


def _join_text(previous: str, current: str) -> tuple[str, bool]:
    left = previous.rstrip()
    right = current.lstrip()
    if _is_soft_hyphen(left, right):
        return left[:-1] + right, True
    return f"{left} {right}", False


def _is_soft_hyphen(previous: str, current: str) -> bool:
    left = previous.rstrip()
    right = current.lstrip()
    if not left.endswith("-") or not right or not right[0].islower():
        return False
    token = left.split()[-1]
    stem = token[:-1]
    right_token = right.split()[0]
    return not (
        token.startswith("--")
        or "-" in stem
        or "-" in right_token
        or not stem.isalpha()
        or len(stem) < 3
        or stem.casefold() in _LEGITIMATE_HYPHEN_PREFIXES
    )


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _union(boxes: Iterable[BoundingBox]) -> BoundingBox:
    values = tuple(boxes)
    if not values:
        raise ValueError("paragraph requires at least one anchor-page rectangle")
    return BoundingBox(
        x0=min(box.x0 for box in values),
        y0=min(box.y0 for box in values),
        x1=max(box.x1 for box in values),
        y1=max(box.y1 for box in values),
    )


def _width(box: BoundingBox) -> float:
    return max(box.x1 - box.x0, 1.0)


def _height(box: BoundingBox) -> float:
    return max(box.y1 - box.y0, 1.0)
