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
from pdftranslate.typography.reconstruction import (
    build_document_style_baseline,
    infer_font_role,
    normalize_font_family_group,
    reconstruct_styles,
    resolve_paragraph_style,
)
from pdftranslate.typography.style_models import (
    DocumentStyleBaseline,
    FontRole,
    ParagraphStyleDecisions,
    ResolvedParagraphStyle,
    ResolvedStyleDocument,
    RoleStyleBaseline,
    StyleBaselineValue,
    StyleDecision,
    StyleDecisionSource,
    StyleStabilityPolicy,
)

__all__ = [
    "MixedStyleEvidence",
    "DocumentStyleBaseline",
    "FontRole",
    "ParagraphTypographyEvidence",
    "ParagraphStyleDecisions",
    "ResolvedParagraphStyle",
    "ResolvedStyleDocument",
    "RgbColor",
    "RoleStyleBaseline",
    "StyleBaselineValue",
    "StyleDecision",
    "StyleDecisionSource",
    "StyleStabilityPolicy",
    "TextAlignment",
    "TypographyBaseline",
    "TypographyConfidence",
    "TypographyFallback",
    "TypographyProperty",
    "TypographyProvenance",
    "TypographyRole",
    "build_document_style_baseline",
    "extract_typography_evidence",
    "infer_font_role",
    "normalize_font_family_group",
    "normalize_source_font_name",
    "reconstruct_styles",
    "resolve_paragraph_style",
]
