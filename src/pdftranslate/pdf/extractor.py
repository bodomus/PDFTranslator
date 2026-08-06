"""Application service for structured PDF extraction."""

from __future__ import annotations

from pathlib import Path

from pdftranslate.config import Settings
from pdftranslate.domain.document import ExtractedDocument
from pdftranslate.pdf.pymupdf_backend import PyMuPdfBackend
from pdftranslate.reconstruction import ParagraphReconstructionOptions
from pdftranslate.repeated import RepeatedElementOptions


class PdfExtractor:
    """Extract the stable intermediate document representation."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._backend = PyMuPdfBackend(settings)

    def extract(
        self,
        input_path: Path,
        page_range: str | None = None,
        reconstruction_options: ParagraphReconstructionOptions | None = None,
        repeated_element_options: RepeatedElementOptions | None = None,
    ) -> ExtractedDocument:
        return self._backend.extract(
            input_path, page_range, reconstruction_options, repeated_element_options
        )
