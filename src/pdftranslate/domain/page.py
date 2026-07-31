"""Extracted page model and classifications."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from pdftranslate.domain.text_block import DomainModel, TextBlock


class PageClassification(StrEnum):
    TEXT = "text"
    SCANNED = "scanned"
    MIXED = "mixed"
    EMPTY = "empty"


class ExtractedPage(DomainModel):
    """Structured content for one source PDF page."""

    page_number: int = Field(ge=1)
    source_index: int = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    rotation: Literal[0, 90, 180, 270]
    classification: PageClassification
    text_blocks: tuple[TextBlock, ...] = ()
    image_count: int = Field(default=0, ge=0)
    image_area_ratio: float = Field(default=0, ge=0, le=1)
    warnings: tuple[str, ...] = ()
