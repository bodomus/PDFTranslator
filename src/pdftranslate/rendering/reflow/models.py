"""Typed contracts for production single-column reflow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from pdftranslate.rendering.inline_styles import (
    InlineStyleMapping,
    InlineStyleRun,
    validate_inline_style_runs,
)


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


class ReflowBoxOrigin(StrEnum):
    LEGACY = "legacy"
    SOURCE_OWNED = "source_owned"


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
    box_origin: ReflowBoxOrigin = ReflowBoxOrigin.LEGACY

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
class ListLayoutContract:
    """Explicit source evidence, never inferred from semantic text or font advances.

    Origins are source coordinates, not offsets relative to a flow region. Callers
    without independently identified marker/content evidence must leave this absent.
    """

    marker_text: str
    marker_source_rect: Rect
    content_source_rect: Rect

    def __post_init__(self) -> None:
        if not self.marker_text.strip() or any(char.isspace() for char in self.marker_text):
            raise ValueError("structural marker must be a non-empty single token")
        for rect in (self.marker_source_rect, self.content_source_rect):
            if not isinstance(rect, Rect) or not all(
                isfinite(value) for value in (rect.x0, rect.y0, rect.x1, rect.y1)
            ):
                raise ValueError("list layout requires finite source rectangles")
        if self.marker_x > self.content_x or self.marker_source_rect.x1 > self.content_x:
            raise ValueError("source marker must precede semantic content")
        if not (
            self.marker_source_rect.y0 < self.content_source_rect.y1
            and self.content_source_rect.y0 < self.marker_source_rect.y1
        ):
            raise ValueError("marker and content must share a source line")

    @property
    def marker_x(self) -> float:
        return self.marker_source_rect.x0

    @property
    def content_x(self) -> float:
        return self.content_source_rect.x0


class OutputOccurrenceKind(StrEnum):
    SEMANTIC = "semantic"
    STRUCTURAL_MARKER = "structural_marker"


@dataclass(frozen=True)
class StructuralFragment:
    text: str
    target_rect: Rect


@dataclass(frozen=True)
class OutputOccurrence:
    """Deterministic saved-validation identity derived from the authoritative plan."""

    occurrence_index: int
    paragraph_id: str
    continuation_index: int
    target_page_number: int
    kind: OutputOccurrenceKind
    text: str
    target_rect: Rect

    @property
    def identity(self) -> tuple[int, OutputOccurrenceKind, int]:
        return self.occurrence_index, self.kind, self.continuation_index


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
    inline_styles: InlineStyleMapping = InlineStyleMapping()
    list_layout: ListLayoutContract | None = None

    def __post_init__(self) -> None:
        if self.occurrence_index < 0 or self.source_page_number < 1:
            raise ValueError("flow paragraph occurrence and page must be valid")
        if not self.paragraph_id or not self.text or not self.source_fragment_rects:
            raise ValueError("flow paragraph identity, text, and fragments are required")
        validate_inline_style_runs(self.text, self.inline_styles.applied)


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
    inline_runs: tuple[InlineStyleRun, ...] = ()
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
    structural_fragment: StructuralFragment | None = None
    box_origin: ReflowBoxOrigin = ReflowBoxOrigin.LEGACY

    @property
    def output_occurrences(self) -> tuple[OutputOccurrence, ...]:
        semantic = OutputOccurrence(
            self.occurrence_index,
            self.paragraph_id,
            self.continuation_index,
            self.target_page_number,
            OutputOccurrenceKind.SEMANTIC,
            self.text,
            self.target_rect,
        )
        if self.structural_fragment is None:
            return (semantic,)
        structural = OutputOccurrence(
            self.occurrence_index,
            self.paragraph_id,
            self.continuation_index,
            self.target_page_number,
            OutputOccurrenceKind.STRUCTURAL_MARKER,
            self.structural_fragment.text,
            self.structural_fragment.target_rect,
        )
        return (semantic, structural)

    def __post_init__(self) -> None:
        if self.structural_fragment is not None and (
            self.continuation_index != 0 or self.text_start != 0
        ):
            raise ValueError("structural fragment belongs only to the first logical occurrence")
        if self.text_end - self.text_start != len(self.text):
            raise ValueError("placement segment offsets must match its text")
        validate_inline_style_runs(self.text, self.inline_runs)


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
