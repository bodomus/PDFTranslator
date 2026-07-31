"""Extracted document and inspection report models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from pdftranslate.domain.page import ExtractedPage
from pdftranslate.domain.text_block import DomainModel

DOCUMENT_SCHEMA_VERSION = "1.0"


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


class ExtractedDocument(DomainModel):
    """Versioned intermediate representation for later pipeline stages."""

    schema_version: Literal["1.0"] = "1.0"
    source: SourceDocument
    page_count: int = Field(ge=1)
    selected_pages: tuple[int, ...]
    metadata: DocumentMetadata
    encrypted: bool
    password_required: bool
    probable_source_language: str | None = None
    pages: tuple[ExtractedPage, ...]
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_page_selection(self) -> ExtractedDocument:
        page_numbers = tuple(page.page_number for page in self.pages)
        if self.selected_pages != page_numbers:
            raise ValueError("selected_pages must match the extracted page numbers")
        if any(number > self.page_count for number in self.selected_pages):
            raise ValueError("selected page number exceeds page_count")
        if tuple(sorted(set(self.selected_pages))) != self.selected_pages:
            raise ValueError("selected_pages must be unique and strictly increasing")
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
