"""User-facing translated-PDF rendering errors."""


class RenderingError(ValueError):
    """Base error for safe translated-PDF rendering."""


class RenderingInputError(RenderingError):
    """The source PDF or translated document is incompatible."""


class SourceMismatchError(RenderingInputError):
    """The translated JSON does not safely describe the supplied PDF."""


class FontValidationError(RenderingError):
    """No usable font can represent the required Cyrillic text."""


class OutputPdfError(RenderingError):
    """The requested output is unsafe or failed post-save validation."""
