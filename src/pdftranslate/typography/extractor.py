"""Deterministic typography evidence extraction from retained source geometry."""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from collections.abc import Callable, Hashable, Iterable, Sequence
from dataclasses import dataclass

from pdftranslate.domain.document import ExtractedDocument
from pdftranslate.domain.text_block import TextSpan
from pdftranslate.reconstruction import LogicalParagraph, ParagraphFragment, ParagraphKind
from pdftranslate.typography.models import (
    MixedStyleEvidence,
    ParagraphTypographyEvidence,
    RgbColor,
    TextAlignment,
    TypographyBaseline,
    TypographyConfidence,
    TypographyFallback,
    TypographyProperty,
    TypographyProvenance,
    TypographyRole,
)

_SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")
_PREVIEW_LIMIT = 120


@dataclass(frozen=True)
class _Region:
    x0: float
    x1: float


def normalize_source_font_name(name: str) -> str:
    """Remove only the canonical six-uppercase-letter PDF subset prefix."""
    return _SUBSET_PREFIX.sub("", name.strip())


def extract_typography_evidence(document: ExtractedDocument) -> TypographyBaseline:
    """Derive compact typography evidence without reopening or mutating the source PDF."""
    page_widths = {page.page_number: page.width for page in document.pages}
    regions = _role_regions(document.paragraphs)
    evidence = tuple(
        _paragraph_evidence(index, paragraph, document.paragraphs, page_widths, regions)
        for index, paragraph in enumerate(document.paragraphs)
    )
    return TypographyBaseline(source_sha256=document.source.sha256, paragraphs=evidence)


def _paragraph_evidence(
    index: int,
    paragraph: LogicalParagraph,
    paragraphs: Sequence[LogicalParagraph],
    page_widths: dict[int, float],
    regions: dict[tuple[int, int, TypographyRole], _Region],
) -> ParagraphTypographyEvidence:
    spans = tuple(span for span in paragraph.spans if _span_weight(span) > 0)
    role = _role(paragraph.kind)
    font_name, mixed_font = _font_name_property(spans)
    font_size, mixed_size = _font_size_property(spans)
    bold, mixed_weight = _boolean_property(
        spans, lambda span: span.bold, TypographyFallback.REGULAR
    )
    italic, mixed_italic = _boolean_property(
        spans, lambda span: span.italic, TypographyFallback.NON_ITALIC
    )
    color, mixed_color = _color_property(spans)
    fragments = _anchor_fragments(paragraph)
    column = _single_column(fragments)
    region = (
        regions.get((paragraph.anchor_page_number, column, role)) if column is not None else None
    )
    page_width = page_widths.get(paragraph.anchor_page_number, paragraph.bbox.x1)
    alignment = _alignment_property(fragments, region, page_width, font_size.value)
    line_height_points, line_height_ratio = _line_height_properties(fragments, font_size.value)
    first_indent, left_indent, right_indent = _indent_properties(fragments, region)
    space_before = _space_before_property(index, paragraph, paragraphs)
    return ParagraphTypographyEvidence(
        occurrence_index=index,
        paragraph_id=paragraph.id,
        source_page_number=paragraph.anchor_page_number,
        text_preview=_preview(paragraph.text),
        role=TypographyProperty(
            value=role,
            confidence=TypographyConfidence.HIGH,
            provenance=(TypographyProvenance.PARAGRAPH_KIND,),
            fallback=TypographyFallback.OTHER_ROLE,
        ),
        source_font_name=font_name,
        font_size_points=font_size,
        bold=bold,
        italic=italic,
        color_rgb=color,
        alignment=alignment,
        line_height_points=line_height_points,
        line_height_ratio=line_height_ratio,
        first_line_indent_points=first_indent,
        left_indent_points=left_indent,
        right_indent_points=right_indent,
        space_before_points=space_before,
        space_after_points=_unknown(TypographyFallback.ZERO_SPACING),
        mixed_styles=MixedStyleEvidence(
            mixed_font_family=mixed_font,
            mixed_font_size=mixed_size,
            mixed_weight=mixed_weight,
            mixed_italic=mixed_italic,
            mixed_color=mixed_color,
        ),
    )


def _role(kind: ParagraphKind) -> TypographyRole:
    if kind is ParagraphKind.BODY:
        return TypographyRole.BODY
    if kind is ParagraphKind.HEADING:
        return TypographyRole.HEADING
    if kind is ParagraphKind.FOOTNOTE:
        return TypographyRole.FOOTNOTE
    return TypographyRole.OTHER


def _role_regions(
    paragraphs: Sequence[LogicalParagraph],
) -> dict[tuple[int, int, TypographyRole], _Region]:
    edges: dict[tuple[int, int, TypographyRole], list[tuple[float, float]]] = {}
    for paragraph in paragraphs:
        role = _role(paragraph.kind)
        region_role = TypographyRole.BODY if role is TypographyRole.HEADING else role
        for fragment in paragraph.fragments:
            edges.setdefault(
                (fragment.mapping.page_number, fragment.column, region_role), []
            ).append((fragment.bbox.x0, fragment.bbox.x1))
    regions = {
        key: _Region(min(item[0] for item in values), max(item[1] for item in values))
        for key, values in edges.items()
    }
    return regions | {
        (page, column, TypographyRole.HEADING): region
        for (page, column, role), region in regions.items()
        if role is TypographyRole.BODY
    }


def _font_name_property(
    spans: Sequence[TextSpan],
) -> tuple[TypographyProperty[str], bool]:
    values = [
        (normalize_source_font_name(span.font_name), _span_weight(span))
        for span in spans
        if span.font_name
    ]
    dominant, mixed = _dominant(values)
    if dominant is None:
        return _unknown(TypographyFallback.RENDERER_DEFAULT_FONT), False
    dominant_share = _dominant_share(values, dominant)
    return (
        TypographyProperty(
            value=dominant,
            confidence=(
                TypographyConfidence.HIGH if dominant_share >= 0.8 else TypographyConfidence.MEDIUM
            ),
            provenance=(TypographyProvenance.SOURCE_FONT,),
            fallback=TypographyFallback.RENDERER_DEFAULT_FONT,
        ),
        mixed,
    )


def _font_size_property(
    spans: Sequence[TextSpan],
) -> tuple[TypographyProperty[float], bool]:
    values = [
        (round(span.font_size, 3), _span_weight(span))
        for span in spans
        if span.font_size is not None and math.isfinite(span.font_size) and span.font_size > 0
    ]
    dominant, mixed = _dominant(values)
    if dominant is None:
        return _unknown(TypographyFallback.RENDERER_DEFAULT_FONT_SIZE), False
    dominant_share = _dominant_share(values, dominant)
    return (
        TypographyProperty(
            value=dominant,
            confidence=(
                TypographyConfidence.HIGH if dominant_share >= 0.8 else TypographyConfidence.MEDIUM
            ),
            provenance=(TypographyProvenance.SOURCE_SPAN,),
            fallback=TypographyFallback.RENDERER_DEFAULT_FONT_SIZE,
        ),
        mixed,
    )


def _boolean_property(
    spans: Sequence[TextSpan],
    selector: Callable[[TextSpan], bool | None],
    fallback: TypographyFallback,
) -> tuple[TypographyProperty[bool], bool]:
    values = [
        (value, _span_weight(span)) for span in spans if (value := selector(span)) is not None
    ]
    dominant, mixed = _dominant(values)
    if dominant is None:
        return _unknown(fallback), False
    counts = Counter[bool]()
    for value, weight in values:
        counts[value] += weight
    if mixed and counts[True] == counts[False]:
        return (
            TypographyProperty(
                value=None,
                confidence=TypographyConfidence.LOW,
                provenance=(TypographyProvenance.SPAN_FLAGS,),
                fallback=fallback,
            ),
            True,
        )
    return (
        TypographyProperty(
            value=dominant,
            confidence=TypographyConfidence.HIGH if not mixed else TypographyConfidence.MEDIUM,
            provenance=(TypographyProvenance.SPAN_FLAGS,),
            fallback=fallback,
        ),
        mixed,
    )


def _color_property(
    spans: Sequence[TextSpan],
) -> tuple[TypographyProperty[RgbColor], bool]:
    values = [
        (span.text_color, _span_weight(span)) for span in spans if span.text_color is not None
    ]
    packed, mixed = _dominant(values)
    if packed is None:
        return _unknown(TypographyFallback.BLACK), False
    return (
        TypographyProperty(
            value=RgbColor(
                red=(packed >> 16) & 0xFF,
                green=(packed >> 8) & 0xFF,
                blue=packed & 0xFF,
            ),
            confidence=TypographyConfidence.HIGH if not mixed else TypographyConfidence.MEDIUM,
            provenance=(TypographyProvenance.SOURCE_SPAN,),
            fallback=TypographyFallback.BLACK,
        ),
        mixed,
    )


def _alignment_property(
    fragments: Sequence[ParagraphFragment],
    region: _Region | None,
    page_width: float,
    font_size: float | None,
) -> TypographyProperty[TextAlignment]:
    if not fragments:
        return _unknown(TypographyFallback.LEFT)
    tolerance = max(2.0, (font_size or 10.0) * 0.35)
    if len(fragments) == 1:
        line = fragments[0].bbox
        line_width = line.x1 - line.x0
        line_center = (line.x0 + line.x1) / 2
        if (
            abs(line_center - page_width / 2) <= page_width * 0.05
            and line_width <= page_width * 0.60
        ):
            return _geometry(TextAlignment.CENTER, TypographyConfidence.MEDIUM)
        if (
            region is not None
            and region.x1 - region.x0 > line_width + tolerance
            and abs(line.x0 - region.x0) <= tolerance
        ):
            return _geometry(TextAlignment.LEFT, TypographyConfidence.LOW)
        return _alignment_unknown()

    lefts = [fragment.bbox.x0 for fragment in fragments]
    rights = [fragment.bbox.x1 for fragment in fragments]
    centers = [(left + right) / 2 for left, right in zip(lefts, rights, strict=True)]
    alignment_lefts = lefts[1:] if len(lefts) >= 3 else lefts
    left_stable = _spread(alignment_lefts) <= tolerance
    right_stable = _spread(rights) <= tolerance
    centers_stable = _spread(centers) <= tolerance
    nonfinal_right_stable = len(rights) >= 3 and _spread(rights[:-1]) <= tolerance * 1.5
    final_is_short = len(rights) >= 3 and statistics.median(rights[:-1]) - rights[-1] > max(
        tolerance * 2, ((region.x1 - region.x0) if region else page_width) * 0.08
    )
    if left_stable and nonfinal_right_stable and final_is_short:
        return _geometry(TextAlignment.JUSTIFIED, TypographyConfidence.MEDIUM)
    if centers_stable and not left_stable and not right_stable:
        return _geometry(TextAlignment.CENTER, TypographyConfidence.MEDIUM)
    if right_stable and not left_stable:
        return _geometry(TextAlignment.RIGHT, TypographyConfidence.MEDIUM)
    if left_stable:
        return _geometry(TextAlignment.LEFT, TypographyConfidence.MEDIUM)
    return _alignment_unknown()


def _line_height_properties(
    fragments: Sequence[ParagraphFragment], font_size: float | None
) -> tuple[TypographyProperty[float], TypographyProperty[float]]:
    baselines = [_fragment_baseline(fragment) for fragment in fragments]
    distances = [
        right - left
        for left, right in zip(baselines, baselines[1:], strict=False)
        if left is not None and right is not None and right - left > 0.1
    ]
    confidence = TypographyConfidence.MEDIUM
    if not distances and len(fragments) >= 2:
        tops = [fragment.bbox.y0 for fragment in fragments]
        distances = [
            right - left for left, right in zip(tops, tops[1:], strict=False) if right - left > 0.1
        ]
        confidence = TypographyConfidence.LOW
    if not distances:
        unknown: TypographyProperty[float] = _unknown(TypographyFallback.DEFAULT_LINE_HEIGHT)
        return unknown, unknown
    line_height = round(float(statistics.median(distances)), 3)
    points = TypographyProperty(
        value=line_height,
        confidence=confidence,
        provenance=(TypographyProvenance.LINE_GEOMETRY,),
        fallback=TypographyFallback.DEFAULT_LINE_HEIGHT,
    )
    if font_size is None or font_size <= 0:
        return points, _unknown(TypographyFallback.DEFAULT_LINE_HEIGHT)
    return points, TypographyProperty(
        value=round(line_height / font_size, 3),
        confidence=confidence,
        provenance=(TypographyProvenance.LINE_GEOMETRY,),
        fallback=TypographyFallback.DEFAULT_LINE_HEIGHT,
    )


def _indent_properties(
    fragments: Sequence[ParagraphFragment], region: _Region | None
) -> tuple[TypographyProperty[float], TypographyProperty[float], TypographyProperty[float]]:
    if not fragments or region is None:
        unknown: TypographyProperty[float] = _unknown(TypographyFallback.ZERO_INDENT)
        return unknown, unknown, unknown
    provenance = (TypographyProvenance.PARAGRAPH_GEOMETRY,)
    left = TypographyProperty(
        value=round(max(0.0, min(item.bbox.x0 for item in fragments) - region.x0), 3),
        confidence=TypographyConfidence.MEDIUM,
        provenance=provenance,
        fallback=TypographyFallback.ZERO_INDENT,
    )
    right = TypographyProperty(
        value=round(max(0.0, region.x1 - max(item.bbox.x1 for item in fragments)), 3),
        confidence=TypographyConfidence.MEDIUM,
        provenance=provenance,
        fallback=TypographyFallback.ZERO_INDENT,
    )
    if len(fragments) < 2:
        return _unknown(TypographyFallback.ZERO_INDENT), left, right
    following_left = float(statistics.median(item.bbox.x0 for item in fragments[1:]))
    first = TypographyProperty(
        value=round(fragments[0].bbox.x0 - following_left, 3),
        confidence=TypographyConfidence.MEDIUM,
        provenance=provenance,
        fallback=TypographyFallback.ZERO_INDENT,
    )
    return first, left, right


def _space_before_property(
    index: int, paragraph: LogicalParagraph, paragraphs: Sequence[LogicalParagraph]
) -> TypographyProperty[float]:
    if index == 0:
        return _unknown(TypographyFallback.ZERO_SPACING)
    current_fragments = _anchor_fragments(paragraph)
    if not current_fragments:
        return _unknown(TypographyFallback.ZERO_SPACING)
    current_column = _single_column(current_fragments)
    if current_column is None:
        return _unknown(TypographyFallback.ZERO_SPACING)
    current_top = min(item.bbox.y0 for item in current_fragments)
    previous = paragraphs[index - 1]
    previous_fragments = tuple(
        item
        for item in previous.fragments
        if item.mapping.page_number == paragraph.anchor_page_number
    )
    if not previous_fragments:
        return _unknown(TypographyFallback.ZERO_SPACING)
    if _single_column(previous_fragments) != current_column:
        return _unknown(TypographyFallback.ZERO_SPACING)
    previous_bottom = max(item.bbox.y1 for item in previous_fragments)
    gap = current_top - previous_bottom
    if gap < -0.5:
        return _unknown(TypographyFallback.ZERO_SPACING)
    return TypographyProperty(
        value=round(max(0.0, gap), 3),
        confidence=TypographyConfidence.LOW,
        provenance=(TypographyProvenance.NEIGHBOR_GEOMETRY,),
        fallback=TypographyFallback.ZERO_SPACING,
    )


def _fragment_baseline(fragment: ParagraphFragment) -> float | None:
    values = [
        (span.origin[1], _span_weight(span))
        for span in fragment.spans
        if span.origin is not None and math.isfinite(span.origin[1])
    ]
    return _weighted_median(values)


def _weighted_median(values: Sequence[tuple[float, int]]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = sum(weight for _, weight in ordered) / 2
    cumulative = 0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= midpoint:
            return value
    return ordered[-1][0]


def _anchor_fragments(paragraph: LogicalParagraph) -> tuple[ParagraphFragment, ...]:
    return tuple(
        fragment
        for fragment in paragraph.fragments
        if fragment.mapping.page_number == paragraph.anchor_page_number
    )


def _single_column(fragments: Sequence[ParagraphFragment]) -> int | None:
    columns = {fragment.column for fragment in fragments}
    return next(iter(columns)) if len(columns) == 1 else None


def _dominant[K: Hashable](values: Iterable[tuple[K, int]]) -> tuple[K | None, bool]:
    counts = Counter[K]()
    for value, weight in values:
        counts[value] += weight
    if not counts:
        return None, False
    dominant = sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))[0][0]
    return dominant, len(counts) > 1


def _dominant_share[K: Hashable](values: Sequence[tuple[K, int]], dominant: K) -> float:
    total = sum(weight for _, weight in values)
    if total <= 0:
        return 0.0
    return sum(weight for value, weight in values if value == dominant) / total


def _span_weight(span: TextSpan) -> int:
    return sum(not character.isspace() for character in span.text)


def _spread(values: Sequence[float]) -> float:
    return max(values) - min(values) if values else 0.0


def _preview(text: str) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= _PREVIEW_LIMIT else compact[: _PREVIEW_LIMIT - 1] + "…"


def _geometry(
    value: TextAlignment, confidence: TypographyConfidence
) -> TypographyProperty[TextAlignment]:
    return TypographyProperty(
        value=value,
        confidence=confidence,
        provenance=(TypographyProvenance.LINE_GEOMETRY,),
        fallback=TypographyFallback.LEFT,
    )


def _alignment_unknown() -> TypographyProperty[TextAlignment]:
    return TypographyProperty(
        value=TextAlignment.UNKNOWN,
        confidence=TypographyConfidence.UNKNOWN,
        provenance=(TypographyProvenance.LINE_GEOMETRY,),
        fallback=TypographyFallback.LEFT,
    )


def _unknown[T](fallback: TypographyFallback) -> TypographyProperty[T]:
    return TypographyProperty(
        value=None,
        confidence=TypographyConfidence.UNKNOWN,
        provenance=(TypographyProvenance.FALLBACK,),
        fallback=fallback,
    )
