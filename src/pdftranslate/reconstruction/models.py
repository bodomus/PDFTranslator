"""Typed paragraph-reconstruction contracts independent of PDF adapters and Typer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import Field

from pdftranslate.domain.text_block import BoundingBox, DomainModel, TextSpan

ReconstructionMode = Literal["conservative", "off"]


@dataclass(frozen=True)
class ParagraphReconstructionOptions:
    """Validated deterministic tolerances for conservative reconstruction."""

    mode: ReconstructionMode = "conservative"
    left_alignment_tolerance: float = 8.0
    indentation_tolerance: float = 14.0
    max_vertical_gap_ratio: float = 0.75
    min_width_ratio: float = 0.72
    column_gutter_ratio: float = 0.08
    heading_font_ratio: float = 1.18
    footnote_font_ratio: float = 0.82
    margin_region_ratio: float = 0.12
    cross_page_edge_ratio: float = 0.18
    repeated_margin_min_pages: int = 2

    def __post_init__(self) -> None:
        if self.mode not in {"conservative", "off"}:
            raise ValueError("paragraph reconstruction mode must be conservative or off")
        positive = (
            self.left_alignment_tolerance,
            self.indentation_tolerance,
            self.max_vertical_gap_ratio,
            self.min_width_ratio,
            self.column_gutter_ratio,
            self.heading_font_ratio,
            self.footnote_font_ratio,
            self.margin_region_ratio,
            self.cross_page_edge_ratio,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("paragraph reconstruction tolerances must be greater than zero")
        if self.min_width_ratio > 1:
            raise ValueError("minimum width ratio cannot exceed one")
        if any(
            value > 1
            for value in (
                self.column_gutter_ratio,
                self.footnote_font_ratio,
                self.margin_region_ratio,
                self.cross_page_edge_ratio,
            )
        ):
            raise ValueError("paragraph reconstruction ratios cannot exceed one")
        if self.repeated_margin_min_pages < 2:
            raise ValueError("repeated margin classification requires at least two pages")


class ParagraphKind(StrEnum):
    BODY = "body"
    HEADING = "heading"
    LIST_ITEM = "list_item"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    HEADER = "header"
    FOOTER = "footer"


class DecisionAction(StrEnum):
    MERGE = "merge"
    KEEP = "keep"
    AMBIGUOUS = "ambiguous"


class DecisionReason(StrEnum):
    SAME_SOURCE_BLOCK = "same_source_block"
    SAME_COLUMN = "same_column"
    COLUMN_BOUNDARY = "column_boundary"
    ALIGNED = "aligned"
    INDENTATION_CHANGE = "indentation_change"
    CLOSE_VERTICAL_GAP = "close_vertical_gap"
    GAP_TOO_LARGE = "gap_too_large"
    SIMILAR_WIDTH = "similar_width"
    COMPATIBLE_STYLE = "compatible_style"
    STYLE_CHANGE = "style_change"
    LOWERCASE_CONTINUATION = "lowercase_continuation"
    UNFINISHED_SENTENCE = "unfinished_sentence"
    TERMINAL_PUNCTUATION = "terminal_punctuation"
    SOFT_HYPHEN = "soft_hyphen"
    PROTECTED_HYPHEN = "protected_hyphen"
    HEADING_BOUNDARY = "heading_boundary"
    LIST_BOUNDARY = "list_boundary"
    CAPTION_BOUNDARY = "caption_boundary"
    FOOTNOTE_BOUNDARY = "footnote_boundary"
    REPEATED_MARGIN_TEXT = "repeated_margin_text"
    CROSS_PAGE_CONTINUATION = "cross_page_continuation"
    PAGE_BOUNDARY_WEAK = "page_boundary_weak"
    AMBIGUOUS_GEOMETRY = "ambiguous_geometry"
    MODE_OFF = "mode_off"


class SourceBlockMapping(DomainModel):
    """Reversible reference to one immutable source text block."""

    source_block_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    bbox: BoundingBox
    original_order: int = Field(ge=0)
    normalized_order: int = Field(ge=0)
    line_ids: tuple[str, ...] = ()


class ParagraphFragment(DomainModel):
    """One raw line or block participating in a logical paragraph."""

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    bbox: BoundingBox
    mapping: SourceBlockMapping
    spans: tuple[TextSpan, ...] = ()
    column: int = Field(ge=0)


class LogicalParagraph(DomainModel):
    """Coherent translation unit with reversible source geometry."""

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    kind: ParagraphKind
    anchor_page_number: int = Field(ge=1)
    bbox: BoundingBox
    fragments: tuple[ParagraphFragment, ...] = Field(min_length=1)
    spans: tuple[TextSpan, ...] = ()
    ambiguous: bool = False
    translated_text: str | None = Field(default=None, exclude_if=lambda value: value is None)


class ReconstructionDecision(DomainModel):
    """Auditable deterministic decision between adjacent fragments."""

    previous_fragment_id: str = Field(min_length=1)
    current_fragment_id: str = Field(min_length=1)
    action: DecisionAction
    reasons: tuple[DecisionReason, ...] = Field(min_length=1)
    page_number: int = Field(ge=1)
    cross_page: bool = False


class ReconstructionMetrics(DomainModel):
    raw_blocks: int = Field(ge=0)
    raw_lines: int = Field(ge=0)
    logical_paragraphs: int = Field(ge=0)
    merged_fragments: int = Field(ge=0)
    ambiguous_decisions: int = Field(ge=0)
    cross_page_merges: int = Field(ge=0)
    soft_hyphens_removed: int = Field(ge=0)


class ParagraphReconstruction(DomainModel):
    """Document-level reconstruction evidence persisted in JSON."""

    mode: ReconstructionMode
    options: ParagraphReconstructionOptions
    decisions: tuple[ReconstructionDecision, ...] = ()
    metrics: ReconstructionMetrics


class ReconstructionResult(DomainModel):
    """Pure reconstructor output before it is attached to a document."""

    paragraphs: tuple[LogicalParagraph, ...]
    evidence: ParagraphReconstruction
