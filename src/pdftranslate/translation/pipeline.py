"""Document-level translation orchestration independent of Typer."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pdftranslate.domain.document import (
    ExtractedDocument,
)
from pdftranslate.glossary import LoadedGlossary
from pdftranslate.translation.cache import TranslationCache
from pdftranslate.translation.errors import (
    ResumeMismatchError,
    TranslationBackendError,
    TranslationOutOfMemoryError,
)
from pdftranslate.translation.protocol import Translator

Clock = Callable[[], datetime]
Checkpoint = Callable[[ExtractedDocument], None]
ProgressCallback = Callable[["TranslationProgress"], None]
TranslationStatus = Literal["in_progress", "interrupted", "completed"]


@dataclass(frozen=True)
class TranslationOptions:
    """Behavior-defining settings persisted for safe resume."""

    source_language: str = "en"
    target_language: str = "ru"
    batch_size: int = 8
    max_input_tokens: int = 512
    glossary: LoadedGlossary | None = None

    def __post_init__(self) -> None:
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if self.max_input_tokens < 8:
            raise ValueError("max_input_tokens must be at least 8")
        if (self.source_language, self.target_language) != ("en", "ru"):
            raise ValueError("only English to Russian translation is currently supported")
        if self.glossary is not None and (
            self.glossary.document.source_language,
            self.glossary.document.target_language,
        ) != (self.source_language, self.target_language):
            raise ValueError("glossary language pair does not match translation settings")


@dataclass(frozen=True)
class TranslationProgress:
    """Stable progress event suitable for terminals and plain logs."""

    completed_blocks: int
    total_blocks: int
    cache_hits: int
    cache_misses: int
    page_number: int
    block_id: str
    cache_status: Literal["hit", "miss", "skipped", "unknown"] = "unknown"
    segmentation_count: int | None = None


def translate_document(
    document: ExtractedDocument,
    *,
    translator: Translator,
    cache: TranslationCache,
    options: TranslationOptions,
    resume_document: ExtractedDocument | None = None,
    checkpoint: Checkpoint | None = None,
    progress: ProgressCallback | None = None,
    clock: Clock = lambda: datetime.now(UTC),
) -> ExtractedDocument:
    """Translate reconstructed logical paragraphs of an extracted schema 1.2 document."""
    if document.schema_version == "1.2":
        from pdftranslate.translation.paragraphs import translate_paragraphs

        return translate_paragraphs(
            document,
            translator=translator,
            cache=cache,
            options=options,
            resume_document=resume_document,
            checkpoint=checkpoint,
            progress=progress,
            clock=clock,
            progress_factory=TranslationProgress,
        )
    raise ResumeMismatchError(
        f"unsupported document schema {document.schema_version}; "
        "translation requires original extracted schema 1.2"
    )


def _translate_with_bounded_oom(translator: Translator, texts: Sequence[str]) -> list[str]:
    try:
        result = translator.translate_batch(texts)
    except TranslationOutOfMemoryError:
        if len(texts) == 1:
            raise
        middle = len(texts) // 2
        return _translate_with_bounded_oom(
            translator, texts[:middle]
        ) + _translate_with_bounded_oom(translator, texts[middle:])
    if len(result) != len(texts):
        raise TranslationBackendError("backend returned a different number of translations")
    return result
