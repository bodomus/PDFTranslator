"""Safe translated-PDF rendering services."""

from pdftranslate.rendering.errors import (
    FontValidationError,
    OutputPdfError,
    RenderingError,
    RenderingInputError,
    SourceMismatchError,
)
from pdftranslate.rendering.fonts import discover_font, validate_font
from pdftranslate.rendering.models import BlockRenderResult, RenderOptions, RenderResult
from pdftranslate.rendering.renderer import PdfRenderer

__all__ = [
    "BlockRenderResult",
    "FontValidationError",
    "OutputPdfError",
    "PdfRenderer",
    "RenderOptions",
    "RenderResult",
    "RenderingError",
    "RenderingInputError",
    "SourceMismatchError",
    "discover_font",
    "validate_font",
]
