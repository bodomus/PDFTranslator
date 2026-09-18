"""Typed contracts for production single-column reflow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ContentDisposition(StrEnum):
    FLOWABLE_BODY = "flowable_body"
    FLOWABLE_HEADING = "flowable_heading"
    ANCHORED_PRESERVE = "anchored_preserve"
    FIXED_LAYOUT = "fixed_layout"
    DEFERRED_UNSUPPORTED = "deferred_unsupported"


class PlacementState(StrEnum):
    CONTINUED = "continued"
    COMPLETE = "complete"


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("rectangle must have positive width and height")

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    def intersects(self, other: Rect) -> bool:
        return (
            self.x0 < other.x1 and self.x1 > other.x0 and self.y0 < other.y1 and self.y1 > other.y0
        )

    def contains(self, other: Rect, *, tolerance: float = 0.5) -> bool:
        return (
            other.x0 >= self.x0 - tolerance
            and other.y0 >= self.y0 - tolerance
            and other.x1 <= self.x1 + tolerance
            and other.y1 <= self.y1 + tolerance
        )


@dataclass(frozen=True)
class ReflowStyle:
    font_size: float
    line_height: float
    paragraph_spacing: float
    heading: bool = False

    def __post_init__(self) -> None:
        if self.font_size <= 0 or self.line_height <= 0 or self.paragraph_spacing < 0:
            raise ValueError("reflow style measurements must be positive")


@dataclass(frozen=True)
class FlowRegion:
    target_page_number: int
    rect: Rect
    column_index: int
    order: int
    source_page_number: int
    created_page: bool = False

    def __post_init__(self) -> None:
        if self.target_page_number < 1 or self.source_page_number < 1:
            raise ValueError("page numbers must be one-based")
        if self.column_index < 0 or self.order < 0:
            raise ValueError("column index and order cannot be negative")


@dataclass(frozen=True)
class FlowParagraph:
    occurrence_index: int
    paragraph_id: str
    source_page_number: int
    kind: str
    disposition: ContentDisposition
    text: str
    source_rect: Rect
    source_fragment_rects: tuple[Rect, ...]
    style: ReflowStyle
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        if self.occurrence_index < 0 or self.source_page_number < 1:
            raise ValueError("flow paragraph occurrence and page must be valid")
        if not self.paragraph_id or not self.text or not self.source_fragment_rects:
            raise ValueError("flow paragraph identity, text, and fragments are required")


@dataclass(frozen=True)
class PlacementSegment:
    occurrence_index: int
    paragraph_id: str
    source_page_number: int
    target_page_number: int
    target_rect: Rect
    continuation_index: int
    text_start: int
    text_end: int
    text: str
    font_size: float
    line_height: float
    measured_height: float
    line_count: int
    color: tuple[float, float, float]
    state: PlacementState


@dataclass(frozen=True)
class LayoutPlan:
    regions: tuple[FlowRegion, ...]
    paragraphs: tuple[FlowParagraph, ...]
    segments: tuple[PlacementSegment, ...]
    inserted_pages: int
    unplaced_text_count: int = 0

    @property
    def continuation_count(self) -> int:
        return len(self.segments) - len(self.paragraphs)

    @property
    def continued_occurrences(self) -> int:
        return len({item.occurrence_index for item in self.segments if item.continuation_index > 0})
