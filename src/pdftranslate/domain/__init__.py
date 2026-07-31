"""Validated domain models for extracted PDF documents."""

from pdftranslate.domain.document import (
    DOCUMENT_SCHEMA_VERSION,
    DocumentMetadata,
    ExtractedDocument,
    InspectionReport,
    SourceDocument,
)
from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox, TextBlock, TextSpan

__all__ = [
    "DOCUMENT_SCHEMA_VERSION",
    "BoundingBox",
    "DocumentMetadata",
    "ExtractedDocument",
    "ExtractedPage",
    "InspectionReport",
    "PageClassification",
    "SourceDocument",
    "TextBlock",
    "TextSpan",
]
