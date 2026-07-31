"""Extracted document, translation metadata, and inspection report models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from pdftranslate.domain.page import ExtractedPage
from pdftranslate.domain.text_block import DomainModel

DOCUMENT_SCHEMA_VERSION = "1.0"
TRANSLATED_DOCUMENT_SCHEMA_VERSION = "1.1"


class SourceDocument(DomainModel):
    """Identity of the immutable source PDF."""

    path: str = Field(min_length=1)
    file_size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class DocumentMetadata(DomainModel):
    """Normalized PDF metadata fields."""

    format: str | None = None
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    keywords: str | None = None
    creator: str | None = None
    producer: str | None = None
    creation_date: str | None = None
    modification_date: str | None = None
    trapped: str | None = None
    encryption: str | None = None


class TranslationStatistics(DomainModel):
    """Counters persisted with checkpoints and final output."""

    total_blocks: int = Field(ge=0)
    completed_blocks: int = Field(ge=0)
    skipped_blocks: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    cache_misses: int = Field(ge=0)
    translated_segments: int = Field(ge=0)


class TranslationMetadata(DomainModel):
    """Identity and lifecycle of a translation run."""

    status: Literal["in_progress", "interrupted", "completed"]
    backend: str = Field(min_length=1)
    model: str = Field(min_length=1)
    source_language: str = Field(min_length=1)
    target_language: str = Field(min_length=1)
    effective_device: Literal["cpu", "cuda"]
    batch_size: int = Field(ge=1)
    max_input_tokens: int = Field(ge=8)
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    statistics: TranslationStatistics
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_lifecycle(self) -> TranslationMetadata:
        if self.statistics.completed_blocks > self.statistics.total_blocks:
            raise ValueError("completed_blocks cannot exceed total_blocks")
        if self.statistics.skipped_blocks > self.statistics.completed_blocks:
            raise ValueError("skipped_blocks cannot exceed completed_blocks")
        if self.updated_at < self.started_at:
            raise ValueError("updated_at cannot precede started_at")
        if self.status == "completed":
            if self.statistics.completed_blocks != self.statistics.total_blocks:
                raise ValueError("completed translation must include every block")
            if self.completed_at is None:
                raise ValueError("completed translation requires completed_at")
        elif self.completed_at is not None:
            raise ValueError("incomplete translation cannot contain completed_at")
        return self


class ExtractedDocument(DomainModel):
    """Versioned intermediate representation shared by pipeline stages."""

    schema_version: Literal["1.0", "1.1"] = "1.0"
    source: SourceDocument
    page_count: int = Field(ge=1)
    selected_pages: tuple[int, ...]
    metadata: DocumentMetadata
    encrypted: bool
    password_required: bool
    probable_source_language: str | None = None
    pages: tuple[ExtractedPage, ...]
    warnings: tuple[str, ...] = ()
    translation: TranslationMetadata | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

    @model_validator(mode="after")
    def validate_page_selection(self) -> ExtractedDocument:
        page_numbers = tuple(page.page_number for page in self.pages)
        if self.selected_pages != page_numbers:
            raise ValueError("selected_pages must match the extracted page numbers")
        if any(number > self.page_count for number in self.selected_pages):
            raise ValueError("selected page number exceeds page_count")
        if tuple(sorted(set(self.selected_pages))) != self.selected_pages:
            raise ValueError("selected_pages must be unique and strictly increasing")
        if self.schema_version == "1.0" and self.translation is not None:
            raise ValueError("schema 1.0 cannot contain translation metadata")
        if self.schema_version == "1.1" and self.translation is None:
            raise ValueError("schema 1.1 requires translation metadata")
        return self


class InspectionReport(DomainModel):
    """Compact aggregate intended for humans or machine-readable CLI output."""

    source: SourceDocument
    page_count: int = Field(ge=0)
    text_pages: int = Field(default=0, ge=0)
    scanned_pages: int = Field(default=0, ge=0)
    mixed_pages: int = Field(default=0, ge=0)
    empty_pages: int = Field(default=0, ge=0)
    text_block_count: int = Field(default=0, ge=0)
    image_count: int = Field(default=0, ge=0)
    encrypted: bool
    password_required: bool
    probable_source_language: str | None = None
    warnings: tuple[str, ...] = ()
