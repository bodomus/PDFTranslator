"""Safe translated-PDF rendering services."""

from pdftranslate.rendering.errors import (
    FontValidationError,
    OutputPdfError,
    RenderCompletenessError,
    RenderingError,
    RenderingInputError,
    SourceMismatchError,
)
from pdftranslate.rendering.fonts import discover_font, validate_font
from pdftranslate.rendering.models import (
    BlockRenderResult,
    RenderOptions,
    RenderResult,
    RenderState,
    RenderStrategy,
)
from pdftranslate.rendering.renderer import PdfRenderer
from pdftranslate.rendering.validation import validate_output_pdf

__all__ = [
    "BlockRenderResult",
    "FontValidationError",
    "OutputPdfError",
    "PdfRenderer",
    "RenderCompletenessError",
    "RenderOptions",
    "RenderResult",
    "RenderState",
    "RenderStrategy",
    "RenderingError",
    "RenderingInputError",
    "SourceMismatchError",
    "discover_font",
    "validate_font",
    "validate_output_pdf",
]
