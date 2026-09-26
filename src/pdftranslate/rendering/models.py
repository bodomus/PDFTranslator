"""Typed rendering options and results independent of Typer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pdftranslate.domain.text_block import BoundingBox
from pdftranslate.repeated import RepeatedElementPolicy


class RenderState(StrEnum):
    """Terminal rendering state for one source-backed render unit."""

    RENDERED = "rendered"
    PRESERVED = "preserved"
    EXCLUDED_BY_POLICY = "excluded_by_policy"
    OVERFLOW = "overflow"
    FAILED = "failed"


class RenderStrategy(StrEnum):
    """Physical placement strategy selected for a logical occurrence."""

    FIXED_LAYOUT = "fixed_layout"
    REFLOW_LAYOUT = "reflow_layout"
    REFLOW_FOOTNOTE = "reflow_footnote"
    ANCHORED_PRESERVED = "anchored_preserved"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class RenderOptions:
    """Deterministic layout and publication behavior."""

    min_font_size: float = 6.0
    font_size_step: float = 0.5
    line_height: float = 1.2
    redaction_padding: float = 0.5
    allow_expand: bool = False
    overwrite: bool = False
    force_source_mismatch: bool = False
    debug_layout: bool = False
    default_font_size: float = 11.0
    max_reflow_pages: int = 4
    max_footnote_pages: int = 8

    def __post_init__(self) -> None:
        if self.min_font_size <= 0:
            raise ValueError("min_font_size must be greater than zero")
        if self.font_size_step <= 0:
            raise ValueError("font_size_step must be greater than zero")
        if self.line_height <= 0:
            raise ValueError("line_height must be greater than zero")
        if self.redaction_padding < 0:
            raise ValueError("redaction_padding cannot be negative")
        if self.default_font_size < self.min_font_size:
            raise ValueError("default_font_size cannot be below min_font_size")
        if self.max_reflow_pages < 0:
            raise ValueError("max_reflow_pages cannot be negative")
        if self.max_footnote_pages < 0:
            raise ValueError("max_footnote_pages cannot be negative")


@dataclass(frozen=True)
class InlineStyleRenderDecision:
    """Privacy-safe applied/deferred evidence for one source-backed inline candidate."""

    status: str
    text_sha256: str
    source_start: int | None
    source_end: int | None
    text_start: int | None
    text_end: int | None
    mapping_kind: str | None
    confidence: str | None
    defer_reason: str | None
    font_size_points: float | None
    color_rgb: tuple[float, float, float] | None
    bold_requested: bool | None
    bold_applied: bool
    italic_requested: bool | None
    italic_applied: bool
    source_font_name: str | None
    source_font_family_group: str | None


@dataclass(frozen=True)
class BlockRenderResult:
    """Authoritative terminal decision for one source-backed render unit."""

    unit_index: int
    page_number: int
    block_id: str
    policy: RepeatedElementPolicy
    state: RenderState
    source_bbox: BoundingBox
    final_bbox: BoundingBox
    initial_font_size: float | None
    font_size: float | None
    min_font_size: float
    fitting_attempts: int
    expanded: bool
    overflow: bool
    translated_character_count: int
    strategy: RenderStrategy = RenderStrategy.FIXED_LAYOUT
    target_pages: tuple[int, ...] = ()
    segment_count: int = 0
    continuation_count: int = 0
    target_rects: tuple[BoundingBox, ...] = ()
    text_offsets: tuple[tuple[int, int], ...] = ()
    applied_line_height: float | None = None
    applied_alignment: str | None = None
    applied_first_line_indent: float | None = None
    applied_left_indent: float | None = None
    applied_right_indent: float | None = None
    applied_space_before: float | None = None
    applied_space_after: float | None = None
    applied_color: tuple[float, float, float] | None = None
    bold_requested: bool | None = None
    bold_applied: bool | None = None
    italic_requested: bool | None = None
    italic_applied: bool | None = None
    mixed_style: bool | None = None
    style_fallback_count: int | None = None
    inline_style_candidate_count: int = 0
    inline_style_applied_count: int = 0
    inline_style_deferred_count: int = 0
    inline_style_applied_character_count: int = 0
    inline_style_decisions: tuple[InlineStyleRenderDecision, ...] = ()


@dataclass(frozen=True)
class RenderResult:
    """Validated translated-PDF publication summary."""

    output_path: Path
    debug_output_path: Path | None
    font_path: Path
    blocks_rendered: int
    font_reductions: int
    expanded_blocks: int
    overflow_blocks: int
    file_size: int
    warnings: tuple[str, ...]
    blocks: tuple[BlockRenderResult, ...]
    reflowed_paragraphs: int = 0
    reflow_segments: int = 0
    continued_paragraphs: int = 0
    inserted_pages: int = 0
    fixed_layout_paragraphs: int = 0
    unsupported_pages: int = 0
    unplaced_text_count: int = 0
    footnotes_reflowed: int = 0
    footnote_segments: int = 0
    continued_footnotes: int = 0
    footnote_continuation_pages: int = 0
    footnote_fixed_layout_units: int = 0
    footnote_unsupported_pages: int = 0
    footnote_unplaced_text_count: int = 0
    inline_style_candidate_count: int = 0
    inline_style_applied_count: int = 0
    inline_style_deferred_count: int = 0
    inline_style_applied_character_count: int = 0

    @property
    def expected_units(self) -> int:
        return len(self.blocks)

    @property
    def preserved_units(self) -> int:
        return sum(block.state is RenderState.PRESERVED for block in self.blocks)

    @property
    def excluded_units(self) -> int:
        return sum(block.state is RenderState.EXCLUDED_BY_POLICY for block in self.blocks)

    @property
    def failed_units(self) -> tuple[BlockRenderResult, ...]:
        return tuple(
            block
            for block in self.blocks
            if block.state in {RenderState.OVERFLOW, RenderState.FAILED}
        )
