"""External OCRmyPDF integration with no dependency on its Python internals."""

from pdftranslate.ocr.diagnostics import OcrDependencies, inspect_ocr_dependencies
from pdftranslate.ocr.errors import (
    OcrDependencyError,
    OcrError,
    OcrOutputError,
    OcrProcessError,
    OcrTimeoutError,
)
from pdftranslate.ocr.models import OcrExecution, OcrMode, OcrOptions
from pdftranslate.ocr.processor import OcrProcessor
from pdftranslate.ocr.validation import validate_ocr_output

__all__ = [
    "OcrDependencies",
    "OcrDependencyError",
    "OcrError",
    "OcrExecution",
    "OcrMode",
    "OcrOptions",
    "OcrOutputError",
    "OcrProcessError",
    "OcrProcessor",
    "OcrTimeoutError",
    "inspect_ocr_dependencies",
    "validate_ocr_output",
]
