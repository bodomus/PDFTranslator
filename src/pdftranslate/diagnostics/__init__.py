"""Structured translation-run diagnostics and offline reports."""

from pdftranslate.diagnostics.models import (
    BlockDiagnostic,
    DiagnosticCode,
    DiagnosticFinding,
    InlineStyleDiagnostic,
    PageDiagnostic,
    ReportSummary,
    TranslationReport,
)
from pdftranslate.diagnostics.reporting import write_report

__all__ = [
    "BlockDiagnostic",
    "DiagnosticCode",
    "DiagnosticFinding",
    "InlineStyleDiagnostic",
    "PageDiagnostic",
    "ReportSummary",
    "TranslationReport",
    "write_report",
]
