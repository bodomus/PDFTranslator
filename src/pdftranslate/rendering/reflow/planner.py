"""Pure forward-only paragraph-to-region planner."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from pdftranslate.rendering.reflow.models import (
    ContentDisposition,
    FlowParagraph,
    FlowRegion,
    LayoutPlan,
    PlacementSegment,
    PlacementState,
    Rect,
    ReflowContentKind,
)


class UnsupportedLayoutError(ValueError):
    """Raised when classified evidence is unsafe for production reflow."""


class CapacityError(ValueError):
    """Raised instead of returning a plan with unplaced translated text."""

    def __init__(self, paragraph: FlowParagraph, unplaced_text_count: int) -> None:
        self.paragraph = paragraph
        self.unplaced_text_count = unplaced_text_count
        super().__init__(
            "reflow capacity exhausted for occurrence "
            f"{paragraph.occurrence_index} ({paragraph.paragraph_id}); "
            f"unplaced translated characters={unplaced_text_count}"
        )


@dataclass(frozen=True)
class Measurement:
    fits: bool
    used_height: float
    line_count: int


class TextMeasurer(Protocol):
    def measure(
        self,
        text: str,
        *,
        width: float,
        height: float,
        font_size: float,
        line_height: float,
    ) -> Measurement: ...


@dataclass(frozen=True)
class PlannerOptions:
    minimum_usable_height: float = 2.0
    minimum_body_after_heading_lines: int = 1

    def __post_init__(self) -> None:
        if self.minimum_usable_height <= 0 or self.minimum_body_after_heading_lines < 1:
            raise ValueError("planner minimums must be positive")


def plan_flow(
    paragraphs: tuple[FlowParagraph, ...],
    regions: tuple[FlowRegion, ...],
    measurer: TextMeasurer,
    *,
    options: PlannerOptions | None = None,
    content_kind: ReflowContentKind = ReflowContentKind.BODY,
) -> LayoutPlan:
    selected = options or PlannerOptions()
    _validate_inputs(paragraphs, regions, content_kind)
    ordered_regions = tuple(sorted(regions, key=lambda item: item.order))
    region_index = 0
    cursor_y = ordered_regions[0].rect.y0
    segments: list[PlacementSegment] = []

    for paragraph_index, paragraph in enumerate(paragraphs):
        text_offset = 0
        continuation_index = 0
        while text_offset < len(paragraph.text):
            if region_index >= len(ordered_regions):
                raise CapacityError(paragraph, len(paragraph.text) - text_offset)
            region = ordered_regions[region_index]
            available_height = region.rect.y1 - cursor_y
            baseline_reserve = paragraph.style.font_size * paragraph.style.line_height
            layout_height = available_height - baseline_reserve
            if layout_height < selected.minimum_usable_height:
                region_index, cursor_y = _advance_region(ordered_regions, region_index)
                continue

            remaining = paragraph.text[text_offset:]
            measurement = measurer.measure(
                remaining,
                width=region.rect.width,
                height=layout_height,
                font_size=paragraph.style.font_size,
                line_height=paragraph.style.line_height,
            )
            if (
                text_offset == 0
                and paragraph.style.heading
                and measurement.fits
                and paragraph_index + 1 < len(paragraphs)
                and _would_orphan_heading(
                    paragraph,
                    paragraphs[paragraph_index + 1],
                    measurement,
                    available_height,
                    selected,
                )
                and cursor_y > region.rect.y0 + 1e-6
            ):
                region_index, cursor_y = _advance_region(ordered_regions, region_index)
                continue
            if measurement.fits:
                consumed = len(remaining)
                segment_measurement = measurement
            else:
                consumed, segment_measurement = _largest_fitting_prefix(
                    remaining, region.rect.width, layout_height, measurer, paragraph
                )
                if consumed == 0:
                    if cursor_y > region.rect.y0 + 1e-6:
                        region_index, cursor_y = _advance_region(ordered_regions, region_index)
                        continue
                    raise UnsupportedLayoutError(
                        "a non-empty translated token cannot fit in an empty flow region"
                    )

            text_end = text_offset + consumed
            completes = text_end == len(paragraph.text)
            segment_height = min(
                available_height,
                max(
                    selected.minimum_usable_height,
                    segment_measurement.used_height + baseline_reserve,
                ),
            )
            target = Rect(region.rect.x0, cursor_y, region.rect.x1, cursor_y + segment_height)
            segments.append(
                PlacementSegment(
                    occurrence_index=paragraph.occurrence_index,
                    paragraph_id=paragraph.paragraph_id,
                    source_page_number=paragraph.source_page_number,
                    target_page_number=region.target_page_number,
                    target_rect=target,
                    continuation_index=continuation_index,
                    text_start=text_offset,
                    text_end=text_end,
                    text=paragraph.text[text_offset:text_end],
                    font_size=paragraph.style.font_size,
                    line_height=paragraph.style.line_height,
                    measured_height=segment_measurement.used_height,
                    line_count=segment_measurement.line_count,
                    color=paragraph.color,
                    state=PlacementState.COMPLETE if completes else PlacementState.CONTINUED,
                )
            )
            text_offset = text_end
            continuation_index += 1
            if completes:
                cursor_y = target.y1 + paragraph.style.paragraph_spacing
            else:
                region_index, cursor_y = _advance_region(ordered_regions, region_index)

    _validate_exact_accounting(paragraphs, tuple(segments))
    return LayoutPlan(
        regions=ordered_regions,
        paragraphs=paragraphs,
        segments=tuple(segments),
        inserted_pages=sum(item.created_page for item in ordered_regions),
        content_kind=content_kind,
    )


def _would_orphan_heading(
    heading: FlowParagraph,
    following: FlowParagraph,
    measurement: Measurement,
    available_height: float,
    options: PlannerOptions,
) -> bool:
    if following.disposition is not ContentDisposition.FLOWABLE_BODY:
        return False
    needed = (
        measurement.used_height
        + heading.style.font_size * heading.style.line_height
        + heading.style.paragraph_spacing
        + following.style.font_size
        * following.style.line_height
        * options.minimum_body_after_heading_lines
    )
    return needed > available_height


def _advance_region(regions: tuple[FlowRegion, ...], index: int) -> tuple[int, float]:
    next_index = index + 1
    return next_index, regions[next_index].rect.y0 if next_index < len(regions) else 0.0


def _largest_fitting_prefix(
    text: str,
    width: float,
    height: float,
    measurer: TextMeasurer,
    paragraph: FlowParagraph,
) -> tuple[int, Measurement]:
    boundaries = [match.end() for match in re.finditer(r"\S+\s*", text)]
    if not boundaries or boundaries[-1] != len(text):
        boundaries.append(len(text))
    best = _binary_search(text, boundaries, width, height, measurer, paragraph)
    if best[0] > 0:
        return best
    return _binary_search(text, list(range(1, len(text) + 1)), width, height, measurer, paragraph)


def _binary_search(
    text: str,
    boundaries: list[int],
    width: float,
    height: float,
    measurer: TextMeasurer,
    paragraph: FlowParagraph,
) -> tuple[int, Measurement]:
    low, high, best_index = 0, len(boundaries) - 1, 0
    best = Measurement(False, 0.0, 0)
    while low <= high:
        middle = (low + high) // 2
        boundary = boundaries[middle]
        measured = measurer.measure(
            text[:boundary],
            width=width,
            height=height,
            font_size=paragraph.style.font_size,
            line_height=paragraph.style.line_height,
        )
        if measured.fits:
            best_index, best, low = boundary, measured, middle + 1
        else:
            high = middle - 1
    return best_index, best


def _validate_inputs(
    paragraphs: tuple[FlowParagraph, ...],
    regions: tuple[FlowRegion, ...],
    content_kind: ReflowContentKind,
) -> None:
    if not paragraphs or not regions:
        raise UnsupportedLayoutError("reflow requires paragraphs and regions")
    occurrences = tuple(item.occurrence_index for item in paragraphs)
    if occurrences != tuple(sorted(set(occurrences))):
        raise UnsupportedLayoutError("paragraph occurrences must be unique and ordered")
    allowed = (
        {ContentDisposition.FLOWABLE_FOOTNOTE}
        if content_kind is ReflowContentKind.FOOTNOTE
        else {ContentDisposition.FLOWABLE_BODY, ContentDisposition.FLOWABLE_HEADING}
    )
    if any(item.disposition not in allowed for item in paragraphs):
        raise UnsupportedLayoutError("content kind and flowable paragraph disposition disagree")
    orders = tuple(item.order for item in regions)
    if orders != tuple(sorted(set(orders))):
        raise UnsupportedLayoutError("region order must be unique and increasing")
    pages = tuple(item.target_page_number for item in regions)
    if pages != tuple(sorted(pages)) or any(item.column_index != 0 for item in regions):
        raise UnsupportedLayoutError("regions must move forward through one column")


def _validate_exact_accounting(
    paragraphs: tuple[FlowParagraph, ...], segments: tuple[PlacementSegment, ...]
) -> None:
    grouped: dict[int, list[PlacementSegment]] = {}
    for segment in segments:
        grouped.setdefault(segment.occurrence_index, []).append(segment)
    for paragraph in paragraphs:
        selected = grouped.get(paragraph.occurrence_index, [])
        cursor = 0
        for segment in selected:
            if segment.text_start != cursor or segment.text_end != cursor + len(segment.text):
                raise AssertionError("reflow segment offsets are not contiguous")
            cursor = segment.text_end
        if "".join(item.text for item in selected) != paragraph.text or cursor != len(
            paragraph.text
        ):
            raise AssertionError(
                f"reflow lost, duplicated, or reordered occurrence {paragraph.occurrence_index}"
            )
