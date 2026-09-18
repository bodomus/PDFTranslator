"""Local translation pipeline and backend boundaries."""

from pdftranslate.translation.cache import TranslationCache
from pdftranslate.translation.errors import (
    ProtectedTokenError,
    ResumeMismatchError,
    TranslationBackendError,
    TranslationCacheError,
    TranslationError,
    TranslationInterruptedError,
    TranslationOutOfMemoryError,
)
from pdftranslate.translation.foreign_language import (
    ForeignLanguageDecision,
    PreparedForeignLanguageText,
    prepare_foreign_language_text,
)
from pdftranslate.translation.nllb import DEFAULT_NLLB_MODEL, NllbTranslator
from pdftranslate.translation.pipeline import (
    TranslationOptions,
    TranslationProgress,
    translate_document,
)
from pdftranslate.translation.protocol import Translator

__all__ = [
    "DEFAULT_NLLB_MODEL",
    "ForeignLanguageDecision",
    "NllbTranslator",
    "ProtectedTokenError",
    "PreparedForeignLanguageText",
    "ResumeMismatchError",
    "TranslationBackendError",
    "TranslationCache",
    "TranslationCacheError",
    "TranslationError",
    "TranslationInterruptedError",
    "TranslationOptions",
    "TranslationOutOfMemoryError",
    "TranslationProgress",
    "Translator",
    "prepare_foreign_language_text",
    "translate_document",
]
