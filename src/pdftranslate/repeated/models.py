"""Typed repeated-element classification contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import Field

from pdftranslate.domain.text_block import BoundingBox, DomainModel

RepeatedElementsMode = Literal["auto", "off"]


class RepeatedElementKind(StrEnum):
    BODY = "body"
    PAGE_NUMBER = "page_number"
    RUNNING_HEADER = "running_header"
    RUNNING_FOOTER = "running_footer"
    REPEATED_BOILERPLATE = "repeated_boilerplate"
    WATERMARK_CANDIDATE = "watermark_candidate"
    UNKNOWN_REPEATED = "unknown_repeated"


class RepeatedElementPolicy(StrEnum):
    TRANSLATE = "translate"
    PRESERVE = "preserve"
    SKIP = "skip"
    REMOVE = "remove"


@dataclass(frozen=True)
class RepeatedElementOptions:
    """Validated conservative document-level heuristic settings."""

    mode: RepeatedElementsMode = "auto"
    margin_region_ratio: float = 0.12
    min_recurrence_ratio: float = 0.60
    parity_recurrence_ratio: float = 0.75
    bbox_tolerance_ratio: float = 0.035
    font_size_tolerance_ratio: float = 0.18
    watermark_font_ratio: float = 1.60
    min_confirmed_pages: int = 3

    def __post_init__(self) -> None:
        if self.mode not in {"auto", "off"}:
            raise ValueError("repeated-elements mode must be auto or off")
        ratios = (
            self.margin_region_ratio,
            self.min_recurrence_ratio,
            self.parity_recurrence_ratio,
            self.bbox_tolerance_ratio,
            self.font_size_tolerance_ratio,
        )
        if any(value <= 0 or value > 1 for value in ratios):
            raise ValueError("repeated-element ratios must be greater than zero and at most one")
        if self.watermark_font_ratio <= 1:
            raise ValueError("watermark font ratio must be greater than one")
        if self.min_confirmed_pages < 3:
            raise ValueError("confirmed repeated elements require at least three pages")


class RepeatedBlockClassification(DomainModel):
    block_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    bbox: BoundingBox
    kind: RepeatedElementKind
    confidence: float = Field(ge=0, le=1)
    group_id: str | None = None
    policy: RepeatedElementPolicy
    ambiguous: bool = False
    reasons: tuple[str, ...] = ()


class RepeatedElementGroup(DomainModel):
    id: str = Field(min_length=1)
    kind: RepeatedElementKind
    normalized_text: str = Field(min_length=1)
    page_numbers: tuple[int, ...] = Field(min_length=1)
    recurrence_ratio: float = Field(ge=0, le=1)
    parity: Literal["all", "odd", "even", "sequence"]
    confidence: float = Field(ge=0, le=1)
    policy: RepeatedElementPolicy
    ambiguous: bool = False


class RepeatedElementMetrics(DomainModel):
    total_blocks: int = Field(ge=0)
    classified_blocks: int = Field(ge=0)
    ambiguous_blocks: int = Field(ge=0)
    groups: int = Field(ge=0)
    counts: dict[str, int]


class RepeatedElementAnalysis(DomainModel):
    """Persisted classification evidence; source blocks remain immutable."""

    mode: RepeatedElementsMode
    options: RepeatedElementOptions
    blocks: tuple[RepeatedBlockClassification, ...]
    groups: tuple[RepeatedElementGroup, ...] = ()
    metrics: RepeatedElementMetrics

    def by_block_id(self) -> dict[str, RepeatedBlockClassification]:
        return {item.block_id: item for item in self.blocks}
