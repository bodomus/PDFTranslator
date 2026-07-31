"""Actionable OCR integration failures."""


class OcrError(RuntimeError):
    """Base class for OCR preprocessing failures."""


class OcrDependencyError(OcrError):
    """A required external OCR component or language is unavailable."""


class OcrProcessError(OcrError):
    """OCRmyPDF exited unsuccessfully or could not be launched."""


class OcrTimeoutError(OcrProcessError):
    """OCRmyPDF exceeded the controlled execution timeout."""


class OcrOutputError(OcrError):
    """OCRmyPDF produced a missing, corrupt, or incompatible PDF."""
