"""Typed rendering options and results independent of Typer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pdftranslate.domain.text_block import BoundingBox


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
    """Final layout decision for one translated block."""

    page_number: int
    block_id: str
    source_bbox: BoundingBox
    final_bbox: BoundingBox
    initial_font_size: float
    font_size: float | None
    expanded: bool
    overflow: bool


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
