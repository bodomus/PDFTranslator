"""Typed, serializable contracts for the isolated reflow proof of concept."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class ContentDisposition(StrEnum):
    """Explicit content decision; unknown content never enters body flow implicitly."""

    FLOWABLE_NOW = "flowable_now"
    ANCHORED_NOW = "anchored_now"
    DEFERRED = "deferred"
    UNSUPPORTED = "unsupported_fail_closed"


class PlacementState(StrEnum):
    """Whether a segment completes its paragraph or continues forward."""

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
class FlowRegion:
    target_page_number: int
    rect: Rect
    column_index: int
    order: int
    created_page: bool = False

    def __post_init__(self) -> None:
        if self.target_page_number < 1:
            raise ValueError("target page number must be one-based")
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

    def __post_init__(self) -> None:
        if self.occurrence_index < 0:
            raise ValueError("paragraph occurrence index cannot be negative")
        if not self.paragraph_id or not self.text:
            raise ValueError("flow paragraph identity and text are required")
        if self.source_page_number < 1:
            raise ValueError("source page number must be one-based")
        if not self.source_fragment_rects:
            raise ValueError("flow paragraph must retain its source fragments")


@dataclass(frozen=True)
class PlacementSegment:
    occurrence_index: int
    paragraph_id: str
    source_page_number: int
    target_page_number: int
    target_rect: Rect
    continuation_index: int
    font_size: float
    measured_height: float
    line_count: int
    text_start: int
    text_end: int
    text: str
    state: PlacementState


@dataclass(frozen=True)
class LayoutMetrics:
    input_logical_paragraph_count: int
    input_translated_character_count: int
    planned_paragraph_count: int
    planned_continuation_count: int
    output_paragraph_count: int
    output_extracted_character_count: int
    unplaced_text_count: int
    new_pages_created: int


@dataclass(frozen=True)
class LayoutPlan:
    schema_version: str
    source_page_number: int
    font_path: str
    font_size: float
    line_height: float
    paragraph_spacing: float
    regions: tuple[FlowRegion, ...]
    paragraphs: tuple[FlowParagraph, ...]
    segments: tuple[PlacementSegment, ...]
    metrics: LayoutMetrics

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation with stable enum values."""
        return asdict(self)
