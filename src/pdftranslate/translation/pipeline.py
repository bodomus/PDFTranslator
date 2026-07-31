"""Document-level translation orchestration independent of Typer."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from pdftranslate.domain.document import (
    ExtractedDocument,
    TranslationMetadata,
    TranslationStatistics,
)
from pdftranslate.translation.cache import TranslationCache
from pdftranslate.translation.errors import (
    ResumeMismatchError,
    TranslationBackendError,
    TranslationInterruptedError,
    TranslationOutOfMemoryError,
)
from pdftranslate.translation.protocol import Translator
from pdftranslate.translation.text import (
    ProtectedText,
    Segment,
    normalize_source_text,
    protect_text,
    recombine_segments,
    segment_text,
    should_skip_translation,
)

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

    def __post_init__(self) -> None:
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if self.max_input_tokens < 8:
            raise ValueError("max_input_tokens must be at least 8")
        if (self.source_language, self.target_language) != ("en", "ru"):
            raise ValueError("only English to Russian translation is currently supported")


@dataclass(frozen=True)
class TranslationProgress:
    """Stable progress event suitable for terminals and plain logs."""

    completed_blocks: int
    total_blocks: int
    cache_hits: int
    cache_misses: int
    page_number: int
    block_id: str


@dataclass
class _Counters:
    total_blocks: int
    completed_blocks: int = 0
    skipped_blocks: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    translated_segments: int = 0

    def snapshot(self) -> TranslationStatistics:
        return TranslationStatistics(
            total_blocks=self.total_blocks,
            completed_blocks=self.completed_blocks,
            skipped_blocks=self.skipped_blocks,
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            translated_segments=self.translated_segments,
        )


@dataclass
class _Work:
    source_text: str
    protected: ProtectedText
    segments: tuple[Segment, ...]
    targets: list[tuple[int, int]] = field(default_factory=list)
    translated: list[str] = field(default_factory=list)


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
    """Translate all eligible blocks and checkpoint resumable schema 1.1 output."""
    if document.translation is not None:
        raise ResumeMismatchError("input document must be the original extracted JSON")
    total_blocks = sum(len(page.text_blocks) for page in document.pages)
    pages = [list(page.text_blocks) for page in document.pages]
    started_at = clock()
    warnings: list[str] = []
    counters = _Counters(total_blocks=total_blocks)

    if resume_document is not None:
        _validate_resume(document, resume_document, translator, options)
        pages = [list(page.text_blocks) for page in resume_document.pages]
        metadata = resume_document.translation
        assert metadata is not None
        started_at = metadata.started_at
        warnings.extend(metadata.warnings)
        counters = _Counters(
            total_blocks=total_blocks,
            completed_blocks=sum(
                block.translated_text is not None for page in pages for block in page
            ),
            skipped_blocks=sum(
                block.translated_text is not None and should_skip_translation(block.text)
                for page in pages
                for block in page
            ),
            cache_hits=metadata.statistics.cache_hits,
            cache_misses=metadata.statistics.cache_misses,
            translated_segments=metadata.statistics.translated_segments,
        )

    def build(status: TranslationStatus) -> ExtractedDocument:
        now = clock()
        translated_pages = tuple(
            page.model_copy(update={"text_blocks": tuple(page_blocks)})
            for page, page_blocks in zip(document.pages, pages, strict=True)
        )
        metadata = TranslationMetadata(
            status=status,
            backend=translator.backend_name,
            model=translator.model_name,
            source_language=options.source_language,
            target_language=options.target_language,
            effective_device=translator.device,
            batch_size=options.batch_size,
            max_input_tokens=options.max_input_tokens,
            started_at=started_at,
            updated_at=now,
            completed_at=now if status == "completed" else None,
            statistics=counters.snapshot(),
            warnings=tuple(dict.fromkeys(warnings)),
        )
        return document.model_copy(
            update={"schema_version": "1.1", "pages": translated_pages, "translation": metadata}
        )

    def save_checkpoint() -> None:
        if checkpoint is not None:
            checkpoint(build("in_progress"))

    work_by_text: dict[str, _Work] = {}
    try:
        for page_index, page in enumerate(document.pages):
            for block_index, block in enumerate(page.text_blocks):
                if pages[page_index][block_index].translated_text is not None:
                    continue
                if should_skip_translation(block.text):
                    pages[page_index][block_index] = block.model_copy(
                        update={"translated_text": block.text}
                    )
                    counters.completed_blocks += 1
                    counters.skipped_blocks += 1
                    _notify(progress, counters, page.page_number, block.id)
                    save_checkpoint()
                    continue

                normalized = normalize_source_text(block.text)
                cached = cache.get(
                    backend=translator.backend_name,
                    model=translator.model_name,
                    source_language=options.source_language,
                    target_language=options.target_language,
                    source_text=normalized,
                )
                if cached is not None:
                    pages[page_index][block_index] = block.model_copy(
                        update={"translated_text": cached}
                    )
                    counters.completed_blocks += 1
                    counters.cache_hits += 1
                    _notify(progress, counters, page.page_number, block.id)
                    save_checkpoint()
                    continue

                existing = work_by_text.get(normalized)
                if existing is not None:
                    existing.targets.append((page_index, block_index))
                    counters.cache_hits += 1
                    continue

                protected = protect_text(block.text)
                segmentation = segment_text(
                    protected.value,
                    count_tokens=translator.count_tokens,
                    max_tokens=options.max_input_tokens,
                )
                if segmentation.quality_warning:
                    warnings.append(
                        f"block {block.id}: forced splitting may reduce translation quality"
                    )
                work_by_text[normalized] = _Work(
                    source_text=normalized,
                    protected=protected,
                    segments=segmentation.segments,
                    targets=[(page_index, block_index)],
                )
                counters.cache_misses += 1

        entries = [(work, segment) for work in work_by_text.values() for segment in work.segments]
        for offset in range(0, len(entries), options.batch_size):
            batch = entries[offset : offset + options.batch_size]
            results = _translate_with_bounded_oom(
                translator, [segment.text for _, segment in batch]
            )
            counters.translated_segments += len(results)
            completed_work: list[_Work] = []
            for (work, _segment), translated in zip(batch, results, strict=True):
                work.translated.append(translated)
                if len(work.translated) == len(work.segments):
                    completed_work.append(work)
            for work in completed_work:
                translated_text = work.protected.restore(
                    recombine_segments(work.segments, work.translated)
                )
                cache.put(
                    backend=translator.backend_name,
                    model=translator.model_name,
                    source_language=options.source_language,
                    target_language=options.target_language,
                    source_text=work.source_text,
                    translated_text=translated_text,
                )
                for page_index, block_index in work.targets:
                    source_block = document.pages[page_index].text_blocks[block_index]
                    pages[page_index][block_index] = source_block.model_copy(
                        update={"translated_text": translated_text}
                    )
                    counters.completed_blocks += 1
                    _notify(
                        progress,
                        counters,
                        document.pages[page_index].page_number,
                        source_block.id,
                    )
                save_checkpoint()
    except KeyboardInterrupt as error:
        partial = build("interrupted")
        if checkpoint is not None:
            checkpoint(partial)
        raise TranslationInterruptedError(partial) from error

    if counters.completed_blocks != total_blocks:
        raise TranslationBackendError("translation finished with incomplete blocks")
    result = build("completed")
    if checkpoint is not None:
        checkpoint(result)
    return result


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


def _validate_resume(
    source: ExtractedDocument,
    resumed: ExtractedDocument,
    translator: Translator,
    options: TranslationOptions,
) -> None:
    metadata = resumed.translation
    if resumed.schema_version != "1.1" or metadata is None:
        raise ResumeMismatchError("resume output is not translated schema 1.1")
    if metadata.status == "completed":
        raise ResumeMismatchError("translation output is already complete")
    expected = (
        translator.backend_name,
        translator.model_name,
        options.source_language,
        options.target_language,
        options.batch_size,
        options.max_input_tokens,
    )
    actual = (
        metadata.backend,
        metadata.model,
        metadata.source_language,
        metadata.target_language,
        metadata.batch_size,
        metadata.max_input_tokens,
    )
    if expected != actual:
        raise ResumeMismatchError("resume settings do not match the partial output")
    if source.source != resumed.source or source.selected_pages != resumed.selected_pages:
        raise ResumeMismatchError("resume output belongs to a different source document")
    source_blocks = tuple(
        (block.id, block.text) for page in source.pages for block in page.text_blocks
    )
    resumed_blocks = tuple(
        (block.id, block.text) for page in resumed.pages for block in page.text_blocks
    )
    if source_blocks != resumed_blocks:
        raise ResumeMismatchError("resume output block structure does not match the source")


def _notify(
    callback: ProgressCallback | None,
    counters: _Counters,
    page_number: int,
    block_id: str,
) -> None:
    if callback is not None:
        callback(
            TranslationProgress(
                completed_blocks=counters.completed_blocks,
                total_blocks=counters.total_blocks,
                cache_hits=counters.cache_hits,
                cache_misses=counters.cache_misses,
                page_number=page_number,
                block_id=block_id,
            )
        )
