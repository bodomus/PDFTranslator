"""Stable domain models for PDFTranslate pipeline stages."""

from pdftranslate.domain.document import (
    ExtractedDocument,
    TranslationMetadata,
    TranslationStatistics,
)
from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox, TextBlock, TextSpan

__all__ = [
    "BoundingBox",
    "ExtractedDocument",
    "ExtractedPage",
    "PageClassification",
    "TextBlock",
    "TextSpan",
    "TranslationMetadata",
    "TranslationStatistics",
]
