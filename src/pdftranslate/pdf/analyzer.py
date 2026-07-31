"""Application service for PDF inspection."""

from __future__ import annotations

from pathlib import Path

from pdftranslate.config import Settings
from pdftranslate.domain.document import InspectionReport
from pdftranslate.pdf.pymupdf_backend import PyMuPdfBackend


class PdfAnalyzer:
    """Produce aggregate document diagnostics without CLI coupling."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._backend = PyMuPdfBackend(settings)

    def inspect(self, input_path: Path) -> InspectionReport:
        return self._backend.inspect(input_path)
