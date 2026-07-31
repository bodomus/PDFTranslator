"""User-facing PDF processing errors."""


class PdfInputError(ValueError):
    """Base error for input PDF validation and processing."""


class PdfNotFoundError(PdfInputError):
    """The requested source is missing or is not a file."""


class PdfCorruptError(PdfInputError):
    """The source is not a readable PDF."""


class PdfEncryptedError(PdfInputError):
    """The source requires a password not accepted by this ticket."""


class PdfEmptyError(PdfInputError):
    """The PDF contains no pages."""


class InvalidPageRangeError(PdfInputError):
    """The one-based CLI page range is malformed or out of bounds."""
