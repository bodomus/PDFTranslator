"""Source-backed typography evidence independent of rendering and Typer."""

from pdftranslate.typography.extractor import (
    extract_typography_evidence,
    normalize_source_font_name,
)
from pdftranslate.typography.models import (
    MixedStyleEvidence,
    ParagraphTypographyEvidence,
    RgbColor,
    TextAlignment,
    TypographyBaseline,
    TypographyConfidence,
    TypographyFallback,
    TypographyProperty,
    TypographyProvenance,
    TypographyRole,
)

__all__ = [
    "MixedStyleEvidence",
    "ParagraphTypographyEvidence",
    "RgbColor",
    "TextAlignment",
    "TypographyBaseline",
    "TypographyConfidence",
    "TypographyFallback",
    "TypographyProperty",
    "TypographyProvenance",
    "TypographyRole",
    "extract_typography_evidence",
    "normalize_source_font_name",
]
