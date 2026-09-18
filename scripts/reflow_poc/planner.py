"""Pure forward-only paragraph-to-region planner for the PDFTR-22 PoC."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from scripts.reflow_poc.models import (
    ContentDisposition,
    FlowParagraph,
    FlowRegion,
    LayoutMetrics,
    LayoutPlan,
    PlacementSegment,
    PlacementState,
    Rect,
)


class UnsupportedLayoutError(ValueError):
    """Raised when content or region evidence is unsafe for this PoC."""


class CapacityError(ValueError):
    """Raised rather than returning a plan with unplaced translated text."""

    def __init__(self, paragraph: FlowParagraph, unplaced_text_count: int) -> None:
        self.paragraph = paragraph
        self.unplaced_text_count = unplaced_text_count
        super().__init__(
            "configured flow regions are exhausted for "
            f"occurrence {paragraph.occurrence_index} ({paragraph.paragraph_id}); "
            f"unplaced translated characters={unplaced_text_count}"
        )


@dataclass(frozen=True)
class Measurement:
    fits: bool
    used_height: float
    line_count: int


class TextMeasurer(Protocol):
    """Adapter boundary for side-effect-free text measurement."""

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
    font_size: float = 12.0
    line_height: float = 1.2
    paragraph_spacing: float = 6.0
    minimum_usable_height: float = 2.0

    def __post_init__(self) -> None:
        if self.font_size <= 0 or self.line_height <= 0:
            raise ValueError("font size and line height must be positive")
        if self.paragraph_spacing < 0 or self.minimum_usable_height <= 0:
            raise ValueError("spacing cannot be negative and minimum height must be positive")


def plan_flow(
    paragraphs: tuple[FlowParagraph, ...],
    regions: tuple[FlowRegion, ...],
    measurer: TextMeasurer,
    *,
    source_page_number: int,
    font_path: str,
    options: PlannerOptions | None = None,
) -> LayoutPlan:
    """Plan every character into ordered continuation segments without PDF mutation."""
    selected = options or PlannerOptions()
    _validate_inputs(paragraphs, regions, source_page_number)
    ordered_regions = tuple(sorted(regions, key=lambda item: item.order))
    region_index = 0
    cursor_y = ordered_regions[0].rect.y0
    segments: list[PlacementSegment] = []

    for paragraph in paragraphs:
        text_offset = 0
        continuation_index = 0
        while text_offset < len(paragraph.text):
            if region_index >= len(ordered_regions):
                raise CapacityError(paragraph, len(paragraph.text) - text_offset)
            region = ordered_regions[region_index]
            available_height = region.rect.y1 - cursor_y
            if available_height < selected.minimum_usable_height:
                region_index += 1
                if region_index < len(ordered_regions):
                    cursor_y = ordered_regions[region_index].rect.y0
                continue

            remaining_text = paragraph.text[text_offset:]
            measurement = measurer.measure(
                remaining_text,
                width=region.rect.width,
                height=available_height,
                font_size=selected.font_size,
                line_height=selected.line_height,
            )
            if measurement.fits:
                consumed = len(remaining_text)
                segment_measurement = measurement
            else:
                consumed, segment_measurement = _largest_fitting_prefix(
                    remaining_text,
                    region.rect.width,
                    available_height,
                    measurer,
                    selected,
                )
                if consumed == 0:
                    if cursor_y > region.rect.y0 + 1e-6:
                        region_index += 1
                        if region_index < len(ordered_regions):
                            cursor_y = ordered_regions[region_index].rect.y0
                        continue
                    raise UnsupportedLayoutError(
                        "a non-empty translated token cannot fit in an empty flow region"
                    )

            end_offset = text_offset + consumed
            completes = end_offset == len(paragraph.text)
            baseline_safety = selected.font_size * selected.line_height
            segment_height = min(
                available_height,
                max(
                    selected.minimum_usable_height,
                    segment_measurement.used_height + baseline_safety,
                ),
            )
            segment_rect = Rect(
                region.rect.x0,
                cursor_y,
                region.rect.x1,
                cursor_y + segment_height,
            )
            segments.append(
                PlacementSegment(
                    occurrence_index=paragraph.occurrence_index,
                    paragraph_id=paragraph.paragraph_id,
                    source_page_number=paragraph.source_page_number,
                    target_page_number=region.target_page_number,
                    target_rect=segment_rect,
                    continuation_index=continuation_index,
                    font_size=selected.font_size,
                    measured_height=segment_measurement.used_height,
                    line_count=segment_measurement.line_count,
                    text_start=text_offset,
                    text_end=end_offset,
                    text=paragraph.text[text_offset:end_offset],
                    state=PlacementState.COMPLETE if completes else PlacementState.CONTINUED,
                )
            )
            text_offset = end_offset
            continuation_index += 1
            if completes:
                cursor_y = segment_rect.y1 + selected.paragraph_spacing
            else:
                region_index += 1
                if region_index < len(ordered_regions):
                    cursor_y = ordered_regions[region_index].rect.y0

    _validate_exact_accounting(paragraphs, tuple(segments))
    metrics = LayoutMetrics(
        input_logical_paragraph_count=len(paragraphs),
        input_translated_character_count=sum(len(item.text) for item in paragraphs),
        planned_paragraph_count=len({item.occurrence_index for item in segments}),
        planned_continuation_count=len(segments) - len(paragraphs),
        output_paragraph_count=0,
        output_extracted_character_count=0,
        unplaced_text_count=0,
        new_pages_created=sum(region.created_page for region in ordered_regions),
    )
    return LayoutPlan(
        schema_version="0.1",
        source_page_number=source_page_number,
        font_path=font_path,
        font_size=selected.font_size,
        line_height=selected.line_height,
        paragraph_spacing=selected.paragraph_spacing,
        regions=ordered_regions,
        paragraphs=paragraphs,
        segments=tuple(segments),
        metrics=metrics,
    )


def _validate_inputs(
    paragraphs: tuple[FlowParagraph, ...],
    regions: tuple[FlowRegion, ...],
    source_page_number: int,
) -> None:
    if not paragraphs or not regions:
        raise UnsupportedLayoutError("at least one paragraph and one flow region are required")
    if source_page_number < 1:
        raise UnsupportedLayoutError("source page number must be one-based")
    occurrences = tuple(item.occurrence_index for item in paragraphs)
    if occurrences != tuple(sorted(set(occurrences))):
        raise UnsupportedLayoutError("paragraph occurrences must be unique and ordered")
    for paragraph in paragraphs:
        if paragraph.disposition is not ContentDisposition.FLOWABLE_NOW:
            raise UnsupportedLayoutError(
                f"occurrence {paragraph.occurrence_index} is not explicitly flowable"
            )
        if paragraph.source_page_number != source_page_number:
            raise UnsupportedLayoutError("the PoC supports one controlled source page at a time")
        if paragraph.kind != "body":
            raise UnsupportedLayoutError(
                f"the PoC supports body prose only, got {paragraph.kind!r}"
            )
    orders = tuple(item.order for item in regions)
    if orders != tuple(sorted(set(orders))):
        raise UnsupportedLayoutError("flow-region order values must be unique and increasing")
    target_pages = tuple(item.target_page_number for item in regions)
    if target_pages != tuple(sorted(target_pages)):
        raise UnsupportedLayoutError("flow regions must move forward through target pages")
    if any(region.column_index != 0 for region in regions):
        raise UnsupportedLayoutError("the PoC supports one column only")


def _largest_fitting_prefix(
    text: str,
    width: float,
    height: float,
    measurer: TextMeasurer,
    options: PlannerOptions,
) -> tuple[int, Measurement]:
    boundaries = [match.end() for match in re.finditer(r"\S+\s*", text)]
    if not boundaries or boundaries[-1] != len(text):
        boundaries.append(len(text))
    best_index, best_measurement = _binary_search_boundaries(
        text, boundaries, width, height, measurer, options
    )
    if best_index > 0:
        return best_index, best_measurement
    return _binary_search_boundaries(
        text, list(range(1, len(text) + 1)), width, height, measurer, options
    )


def _binary_search_boundaries(
    text: str,
    boundaries: list[int],
    width: float,
    height: float,
    measurer: TextMeasurer,
    options: PlannerOptions,
) -> tuple[int, Measurement]:
    low = 0
    high = len(boundaries) - 1
    best_index = 0
    best = Measurement(fits=False, used_height=0.0, line_count=0)
    while low <= high:
        middle = (low + high) // 2
        boundary = boundaries[middle]
        measured = measurer.measure(
            text[:boundary],
            width=width,
            height=height,
            font_size=options.font_size,
            line_height=options.line_height,
        )
        if measured.fits:
            best_index = boundary
            best = measured
            low = middle + 1
        else:
            high = middle - 1
    return best_index, best


def _validate_exact_accounting(
    paragraphs: tuple[FlowParagraph, ...], segments: tuple[PlacementSegment, ...]
) -> None:
    by_occurrence: dict[int, list[PlacementSegment]] = {}
    for segment in segments:
        by_occurrence.setdefault(segment.occurrence_index, []).append(segment)
    for paragraph in paragraphs:
        paragraph_segments = by_occurrence.get(paragraph.occurrence_index, [])
        reconstructed = "".join(item.text for item in paragraph_segments)
        offsets = tuple((item.text_start, item.text_end) for item in paragraph_segments)
        expected_offsets: list[tuple[int, int]] = []
        cursor = 0
        for segment in paragraph_segments:
            expected_offsets.append((cursor, cursor + len(segment.text)))
            cursor += len(segment.text)
        if reconstructed != paragraph.text or offsets != tuple(expected_offsets):
            raise AssertionError(
                "planner lost, duplicated, or reordered text for occurrence "
                f"{paragraph.occurrence_index}"
            )
