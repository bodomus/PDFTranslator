"""Versioned glossary loading, matching, processing, and evidence."""

from pdftranslate.glossary.errors import GlossaryComplianceError, GlossaryError
from pdftranslate.glossary.loader import glossary_fingerprint, load_glossary
from pdftranslate.glossary.matcher import GlossaryMatch, find_glossary_matches
from pdftranslate.glossary.models import (
    GLOSSARY_BEHAVIOR_REVISION,
    GLOSSARY_PLACEHOLDER_PREFIX,
    GlossaryDocument,
    GlossaryEntry,
    GlossaryEntryMode,
    GlossaryInflection,
    GlossaryMatchType,
    GlossaryOccurrenceEvidence,
    GlossaryStatistics,
    GlossaryTranslationEvidence,
    LoadedGlossary,
    ParagraphGlossaryEvidence,
)
from pdftranslate.glossary.processor import (
    PreparedGlossaryText,
    build_glossary_evidence,
    prepare_glossary_text,
    validate_glossary_output,
)

__all__ = [
    "GLOSSARY_BEHAVIOR_REVISION",
    "GLOSSARY_PLACEHOLDER_PREFIX",
    "GlossaryComplianceError",
    "GlossaryDocument",
    "GlossaryEntry",
    "GlossaryEntryMode",
    "GlossaryError",
    "GlossaryInflection",
    "GlossaryMatch",
    "GlossaryMatchType",
    "GlossaryOccurrenceEvidence",
    "GlossaryStatistics",
    "GlossaryTranslationEvidence",
    "LoadedGlossary",
    "ParagraphGlossaryEvidence",
    "PreparedGlossaryText",
    "build_glossary_evidence",
    "find_glossary_matches",
    "glossary_fingerprint",
    "load_glossary",
    "prepare_glossary_text",
    "validate_glossary_output",
]
