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
