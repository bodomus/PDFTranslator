"""Opt-in real-PDF validation harness."""

from pdftranslate.validation.models import (
    CorpusDocument,
    CorpusManifest,
    DocumentValidationResult,
    ManualReview,
    ManualReviewManifest,
    ValidationOptions,
    ValidationSummary,
)
from pdftranslate.validation.runner import run_validation

__all__ = [
    "CorpusDocument",
    "CorpusManifest",
    "DocumentValidationResult",
    "ManualReview",
    "ManualReviewManifest",
    "ValidationOptions",
    "ValidationSummary",
    "run_validation",
]
