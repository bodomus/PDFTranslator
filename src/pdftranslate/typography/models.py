"""Typed source-backed typography evidence contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from pdftranslate.domain.text_block import DomainModel


class TypographyConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class TypographyProvenance(StrEnum):
    SOURCE_SPAN = "source_span"
    SOURCE_FONT = "source_font"
    SPAN_FLAGS = "span_flags"
    LINE_GEOMETRY = "line_geometry"
    PARAGRAPH_GEOMETRY = "paragraph_geometry"
    NEIGHBOR_GEOMETRY = "neighbor_geometry"
    PARAGRAPH_KIND = "paragraph_kind"
    FALLBACK = "fallback"


class TypographyFallback(StrEnum):
    PRESERVE_UNKNOWN = "preserve_unknown"
    RENDERER_DEFAULT_FONT = "renderer_default_font"
    RENDERER_DEFAULT_FONT_SIZE = "renderer_default_font_size"
    REGULAR = "regular"
    NON_ITALIC = "non_italic"
    BLACK = "black"
    LEFT = "left"
    DEFAULT_LINE_HEIGHT = "default_line_height"
    ZERO_INDENT = "zero_indent"
    ZERO_SPACING = "zero_spacing"
    OTHER_ROLE = "other_role"


class TypographyRole(StrEnum):
    BODY = "body"
    HEADING = "heading"
    FOOTNOTE = "footnote"
    OTHER = "other"


class TextAlignment(StrEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFIED = "justified"
    UNKNOWN = "unknown"


class TypographyProperty[T](DomainModel):
    """One typography value plus categorical certainty and fallback behavior."""

    value: T | None
    confidence: TypographyConfidence
    provenance: tuple[TypographyProvenance, ...] = Field(min_length=1)
    fallback: TypographyFallback


class RgbColor(DomainModel):
    """Source text color normalized from packed PDF color to 8-bit RGB."""

    red: int = Field(ge=0, le=255)
    green: int = Field(ge=0, le=255)
    blue: int = Field(ge=0, le=255)


class MixedStyleEvidence(DomainModel):
    mixed_font_family: bool
    mixed_font_size: bool
    mixed_weight: bool
    mixed_italic: bool
    mixed_color: bool


class ParagraphTypographyEvidence(DomainModel):
    """Compact typography baseline for one logical paragraph occurrence."""

    occurrence_index: int = Field(ge=0)
    paragraph_id: str = Field(min_length=1)
    source_page_number: int = Field(ge=1)
    text_preview: str
    role: TypographyProperty[TypographyRole]
    source_font_name: TypographyProperty[str]
    font_size_points: TypographyProperty[float]
    bold: TypographyProperty[bool]
    italic: TypographyProperty[bool]
    color_rgb: TypographyProperty[RgbColor]
    alignment: TypographyProperty[TextAlignment]
    line_height_points: TypographyProperty[float]
    line_height_ratio: TypographyProperty[float]
    first_line_indent_points: TypographyProperty[float]
    left_indent_points: TypographyProperty[float]
    right_indent_points: TypographyProperty[float]
    space_before_points: TypographyProperty[float]
    space_after_points: TypographyProperty[float]
    mixed_styles: MixedStyleEvidence


class TypographyBaseline(DomainModel):
    """Versioned diagnostic typography output; occurrence index is authoritative."""

    schema_version: Literal["1.0"] = "1.0"
    source_sha256: str = Field(min_length=64, max_length=64)
    paragraphs: tuple[ParagraphTypographyEvidence, ...]
