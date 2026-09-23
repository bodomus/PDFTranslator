"""Typed renderer-facing paragraph style reconstruction contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from pdftranslate.domain.text_block import DomainModel
from pdftranslate.typography.models import (
    MixedStyleEvidence,
    RgbColor,
    TextAlignment,
    TypographyConfidence,
    TypographyRole,
)


class StyleDecisionSource(StrEnum):
    TYPOGRAPHY_EVIDENCE = "typography_evidence"
    ROLE_BASELINE = "role_baseline"
    DOCUMENT_BASELINE = "document_baseline"
    SAFE_RENDER_DEFAULT = "safe_render_default"
    NORMALIZED_SOURCE_VALUE = "normalized_source_value"
    UNRESOLVED = "unresolved"


class FontRole(StrEnum):
    SERIF = "serif"
    SANS_SERIF = "sans_serif"
    MONOSPACE = "monospace"
    UNKNOWN = "unknown"


class StyleDecision[T](DomainModel):
    """A resolved value plus the evidence and fallback path that selected it."""

    value: T
    evidence_value: T | None = None
    evidence_confidence: TypographyConfidence
    source: StyleDecisionSource
    confidence: TypographyConfidence
    used_fallback: bool
    fallback_reason: str | None = None


class StyleBaselineValue[T](DomainModel):
    """A robust aggregate and the support that makes it usable or unstable."""

    value: T | None
    stable: bool
    sample_count: int = Field(ge=0)
    support_count: int = Field(ge=0)
    dominant_share: float = Field(ge=0, le=1)
    spread: float | None = Field(default=None, ge=0)
    confidence: TypographyConfidence

    @model_validator(mode="after")
    def validate_support(self) -> StyleBaselineValue[T]:
        if self.support_count > self.sample_count:
            raise ValueError("baseline support cannot exceed its sample count")
        if self.stable and (self.value is None or self.support_count == 0):
            raise ValueError("a stable baseline requires a supported value")
        return self


class StyleStabilityPolicy(DomainModel):
    """Versioned deterministic thresholds for role baseline aggregation."""

    minimum_sample_count: int = Field(default=2, ge=2)
    dominant_share: float = Field(default=2 / 3, gt=0.5, le=1)
    confidence_floor: Literal[TypographyConfidence.MEDIUM] = TypographyConfidence.MEDIUM
    font_size_tolerance_points: float = Field(default=0.75, gt=0)
    line_height_ratio_tolerance: float = Field(default=0.08, gt=0)
    indent_tolerance_points: float = Field(default=2.0, gt=0)
    spacing_tolerance_points: float = Field(default=2.0, gt=0)


class RoleStyleBaseline(DomainModel):
    """Stable aggregate candidates for one semantic paragraph role."""

    role: TypographyRole
    paragraph_count: int = Field(ge=1)
    source_font_name: StyleBaselineValue[str]
    source_font_family_group: StyleBaselineValue[str]
    font_role: StyleBaselineValue[FontRole]
    font_size_points: StyleBaselineValue[float]
    bold: StyleBaselineValue[bool]
    italic: StyleBaselineValue[bool]
    color_rgb: StyleBaselineValue[RgbColor]
    alignment: StyleBaselineValue[TextAlignment]
    line_height_ratio: StyleBaselineValue[float]
    first_line_indent_points: StyleBaselineValue[float]
    left_indent_points: StyleBaselineValue[float]
    right_indent_points: StyleBaselineValue[float]
    space_before_points: StyleBaselineValue[float]
    space_after_points: StyleBaselineValue[float]


class DocumentStyleBaseline(DomainModel):
    """Role-isolated style aggregates plus the one safe document-wide fallback."""

    schema_version: Literal["1.0"] = "1.0"
    source_sha256: str = Field(min_length=64, max_length=64)
    policy: StyleStabilityPolicy
    body: RoleStyleBaseline | None = None
    heading: RoleStyleBaseline | None = None
    footnote: RoleStyleBaseline | None = None
    other: RoleStyleBaseline | None = None
    global_color_rgb: StyleBaselineValue[RgbColor]

    def for_role(self, role: TypographyRole) -> RoleStyleBaseline | None:
        if role is TypographyRole.BODY:
            return self.body
        if role is TypographyRole.HEADING:
            return self.heading
        if role is TypographyRole.FOOTNOTE:
            return self.footnote
        return self.other


class ParagraphStyleDecisions(DomainModel):
    role: StyleDecision[TypographyRole]
    source_font_name: StyleDecision[str | None]
    source_font_family_group: StyleDecision[str | None]
    font_role: StyleDecision[FontRole]
    font_size_points: StyleDecision[float]
    bold: StyleDecision[bool]
    italic: StyleDecision[bool]
    color_rgb: StyleDecision[RgbColor]
    alignment: StyleDecision[TextAlignment]
    line_height_ratio: StyleDecision[float]
    first_line_indent_points: StyleDecision[float]
    left_indent_points: StyleDecision[float]
    right_indent_points: StyleDecision[float]
    space_before_points: StyleDecision[float]
    space_after_points: StyleDecision[float]


class ResolvedParagraphStyle(DomainModel):
    """Stable renderer-facing style for one authoritative paragraph occurrence."""

    occurrence_index: int = Field(ge=0)
    paragraph_id: str = Field(min_length=1)
    role: TypographyRole
    source_font_name: str | None
    source_font_family_group: str | None
    font_role: FontRole
    font_size_points: float = Field(gt=0)
    bold: bool
    italic: bool
    color_rgb: RgbColor
    alignment: TextAlignment
    line_height_ratio: float = Field(gt=0)
    first_line_indent_points: float
    left_indent_points: float = Field(ge=0)
    right_indent_points: float = Field(ge=0)
    space_before_points: float = Field(ge=0)
    space_after_points: float = Field(ge=0)
    mixed_styles: MixedStyleEvidence
    decisions: ParagraphStyleDecisions
    fallback_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_resolved_alignment(self) -> ResolvedParagraphStyle:
        if self.alignment is TextAlignment.UNKNOWN:
            raise ValueError("resolved paragraph alignment cannot remain unknown")
        return self


class ResolvedStyleDocument(DomainModel):
    """Versioned derived style output; not part of ExtractedDocument or resume state."""

    schema_version: Literal["1.0"] = "1.0"
    source_sha256: str = Field(min_length=64, max_length=64)
    baseline: DocumentStyleBaseline
    paragraphs: tuple[ResolvedParagraphStyle, ...]
