"""Typed contracts for production single-column reflow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ContentDisposition(StrEnum):
    FLOWABLE_BODY = "flowable_body"
    FLOWABLE_HEADING = "flowable_heading"
    FLOWABLE_FOOTNOTE = "flowable_footnote"
    ANCHORED_PRESERVE = "anchored_preserve"
    FIXED_LAYOUT = "fixed_layout"
    DEFERRED_UNSUPPORTED = "deferred_unsupported"


class PlacementState(StrEnum):
    CONTINUED = "continued"
    COMPLETE = "complete"


class ReflowContentKind(StrEnum):
    BODY = "body"
    FOOTNOTE = "footnote"


class ReflowAlignment(StrEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFIED = "justified"


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
    space_before: float
    space_after: float
    first_line_indent: float = 0.0
    left_indent: float = 0.0
    right_indent: float = 0.0
    alignment: ReflowAlignment = ReflowAlignment.LEFT
    heading: bool = False
    bold_requested: bool = False
    bold_applied: bool = False
    italic_requested: bool = False
    italic_applied: bool = False
    mixed_style: bool = False
    fallback_count: int = 0

    def __post_init__(self) -> None:
        if (
            self.font_size <= 0
            or self.line_height <= 0
            or self.space_before < 0
            or self.space_after < 0
            or self.left_indent < 0
            or self.right_indent < 0
            or self.fallback_count < 0
        ):
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
    alignment: ReflowAlignment = ReflowAlignment.LEFT
    first_line_indent: float = 0.0
    left_indent: float = 0.0
    right_indent: float = 0.0
    space_before: float = 0.0
    space_after: float = 0.0
    bold_requested: bool = False
    bold_applied: bool = False
    italic_requested: bool = False
    italic_applied: bool = False
    mixed_style: bool = False
    fallback_count: int = 0


@dataclass(frozen=True)
class LayoutPlan:
    regions: tuple[FlowRegion, ...]
    paragraphs: tuple[FlowParagraph, ...]
    segments: tuple[PlacementSegment, ...]
    inserted_pages: int
    unplaced_text_count: int = 0
    content_kind: ReflowContentKind = ReflowContentKind.BODY

    @property
    def continuation_count(self) -> int:
        return len(self.segments) - len(self.paragraphs)

    @property
    def continued_occurrences(self) -> int:
        return len({item.occurrence_index for item in self.segments if item.continuation_index > 0})


@dataclass(frozen=True)
class DocumentLayoutPlan:
    """Authoritative pre-mutation layout and source-to-output page mapping."""

    plans: tuple[LayoutPlan, ...]
    final_page_by_source: tuple[tuple[int, int], ...]
    unsupported_body_pages: int = 0
    unsupported_footnote_pages: int = 0

    @property
    def body_plans(self) -> tuple[LayoutPlan, ...]:
        return tuple(item for item in self.plans if item.content_kind is ReflowContentKind.BODY)

    @property
    def footnote_plans(self) -> tuple[LayoutPlan, ...]:
        return tuple(item for item in self.plans if item.content_kind is ReflowContentKind.FOOTNOTE)

    @property
    def selected_occurrences(self) -> frozenset[int]:
        return frozenset(
            paragraph.occurrence_index for plan in self.plans for paragraph in plan.paragraphs
        )

    @property
    def page_map(self) -> dict[int, int]:
        return dict(self.final_page_by_source)

    @property
    def inserted_pages(self) -> int:
        return sum(item.inserted_pages for item in self.plans)
