"""Independent final-PDF validation used before pipeline publication."""

from pathlib import Path

import pymupdf

from pdftranslate.rendering.errors import OutputPdfError


def validate_output_pdf(path: Path, expected_page_count: int) -> int:
    """Reopen a PDF candidate and return its non-zero file size when valid."""
    candidate = path.expanduser().resolve()
    if not candidate.is_file():
        raise OutputPdfError(f"rendered PDF does not exist: {candidate}")
    try:
        document = pymupdf.open(candidate)  # type: ignore[no-untyped-call]
    except (pymupdf.EmptyFileError, pymupdf.FileDataError, RuntimeError) as error:
        raise OutputPdfError(f"rendered PDF cannot be reopened: {error}") from error
    try:
        if not document.is_pdf:
            raise OutputPdfError("rendered output is not a PDF document")
        if document.page_count != expected_page_count:
            raise OutputPdfError("rendered PDF page count does not match the immutable source")
    finally:
        document.close()  # type: ignore[no-untyped-call]
    size = candidate.stat().st_size
    if size <= 0:
        raise OutputPdfError("rendered PDF is empty")
    return size
