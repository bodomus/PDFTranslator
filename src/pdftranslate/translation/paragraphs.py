"""Paragraph-aware translation for reconstructed document schema 1.2."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pdftranslate.domain.document import (
    ExtractedDocument,
    TranslationMetadata,
    TranslationStatistics,
)
from pdftranslate.glossary import (
    ParagraphGlossaryEvidence,
    PreparedGlossaryText,
    build_glossary_evidence,
    prepare_glossary_text,
    validate_glossary_output,
)
from pdftranslate.reconstruction import LogicalParagraph
from pdftranslate.repeated import RepeatedElementPolicy
from pdftranslate.translation.cache import TranslationCache
from pdftranslate.translation.errors import (
    ResumeMismatchError,
    TranslationBackendError,
    TranslationInterruptedError,
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

if TYPE_CHECKING:
    from pdftranslate.translation.pipeline import (
        TranslationOptions,
        TranslationProgress,
    )


@dataclass
class _Work:
    source_text: str
    protected: ProtectedText
    segments: tuple[Segment, ...]
    glossary: PreparedGlossaryText | None = None
    targets: list[tuple[int, str]] = field(default_factory=list)
    translated: list[str] = field(default_factory=list)


def translate_paragraphs(
    document: ExtractedDocument,
    *,
    translator: Translator,
    cache: TranslationCache,
    options: TranslationOptions,
    resume_document: ExtractedDocument | None,
    checkpoint: Callable[[ExtractedDocument], None] | None,
    progress: Callable[[TranslationProgress], None] | None,
    clock: Callable[[], datetime],
    progress_factory: Callable[..., TranslationProgress],
) -> ExtractedDocument:
    """Translate logical paragraphs while retaining raw source blocks unchanged."""
    if document.schema_version != "1.2" or document.translation is not None:
        raise ResumeMismatchError("paragraph translation requires original schema 1.2")
    source_language = str(options.source_language)
    target_language = str(options.target_language)
    batch_size = int(options.batch_size)
    max_input_tokens = int(options.max_input_tokens)
    paragraphs = list(document.paragraphs)
    total = len(paragraphs)
    started_at = clock()
    completed = skipped = hits = misses = translated_segments = 0
    warnings: list[str] = []
    glossary_evidence: dict[str, ParagraphGlossaryEvidence] = {}

    if resume_document is not None:
        _validate_resume(document, resume_document, translator, options)
        paragraphs = list(resume_document.paragraphs)
        metadata = resume_document.translation
        assert metadata is not None
        started_at = metadata.started_at
        completed = sum(item.translated_text is not None for item in paragraphs)
        skipped = sum(
            item.translated_text is not None
            and (
                _paragraph_policy(resume_document, item) is not RepeatedElementPolicy.TRANSLATE
                or should_skip_translation(item.text)
            )
            for item in paragraphs
        )
        hits = metadata.statistics.cache_hits
        misses = metadata.statistics.cache_misses
        translated_segments = metadata.statistics.translated_segments
        warnings.extend(metadata.warnings)
        if metadata.glossary is not None:
            glossary_evidence.update(
                (item.paragraph_id, item) for item in metadata.glossary.paragraphs
            )

    def build(status: Literal["in_progress", "interrupted", "completed"]) -> ExtractedDocument:
        now = clock()
        statistics = TranslationStatistics(
            total_blocks=total,
            completed_blocks=completed,
            skipped_blocks=skipped,
            cache_hits=hits,
            cache_misses=misses,
            translated_segments=translated_segments,
        )
        metadata = TranslationMetadata(
            status=status,
            backend=translator.backend_name,
            model=translator.model_name,
            source_language=source_language,
            target_language=target_language,
            effective_device=translator.device,
            batch_size=batch_size,
            max_input_tokens=max_input_tokens,
            started_at=started_at,
            updated_at=now,
            completed_at=now if status == "completed" else None,
            statistics=statistics,
            warnings=tuple(dict.fromkeys(warnings)),
            glossary=(
                build_glossary_evidence(options.glossary, tuple(glossary_evidence.values()))
                if options.glossary is not None
                else None
            ),
        )
        return document.model_copy(
            update={
                "schema_version": "1.3",
                "paragraphs": tuple(paragraphs),
                "translation": metadata,
            }
        )

    def save() -> None:
        if checkpoint is not None:
            checkpoint(build("in_progress"))

    def notify(index: int, cache_status: str, segments: int | None = None) -> None:
        if progress is None:
            return
        item = paragraphs[index]
        progress(
            progress_factory(
                completed_blocks=completed,
                total_blocks=total,
                cache_hits=hits,
                cache_misses=misses,
                page_number=item.anchor_page_number,
                block_id=item.id,
                cache_status=cache_status,
                segmentation_count=segments,
            )
        )

    work_by_text: dict[str, _Work] = {}
    try:
        for index, paragraph in enumerate(document.paragraphs):
            if paragraphs[index].translated_text is not None:
                continue
            policy = _paragraph_policy(document, paragraph)
            if policy is not RepeatedElementPolicy.TRANSLATE:
                translated_text = paragraph.text if policy is RepeatedElementPolicy.PRESERVE else ""
                paragraphs[index] = paragraph.model_copy(
                    update={"translated_text": translated_text}
                )
                completed += 1
                skipped += 1
                notify(index, "skipped", 0)
                save()
                continue
            if should_skip_translation(paragraph.text):
                paragraphs[index] = paragraph.model_copy(update={"translated_text": paragraph.text})
                completed += 1
                skipped += 1
                notify(index, "skipped", 0)
                save()
                continue
            normalized = normalize_source_text(paragraph.text)
            prepared = (
                prepare_glossary_text(paragraph.text, options.glossary)
                if options.glossary is not None
                else None
            )
            cached = cache.get(
                backend=translator.backend_name,
                model=translator.model_name,
                source_language=source_language,
                target_language=target_language,
                source_text=normalized,
                glossary_fingerprint=options.glossary.fingerprint if options.glossary else None,
            )
            if cached is not None:
                paragraphs[index] = paragraph.model_copy(update={"translated_text": cached})
                if prepared is not None:
                    glossary_evidence[paragraph.id] = validate_glossary_output(
                        cached,
                        paragraph.id,
                        prepared.matches,
                    )
                completed += 1
                hits += 1
                notify(index, "hit")
                save()
                continue
            if normalized in work_by_text:
                work_by_text[normalized].targets.append((index, "hit"))
                hits += 1
                continue
            protected = protect_text(prepared.value if prepared is not None else paragraph.text)
            segmentation = segment_text(
                protected.value,
                count_tokens=translator.count_tokens,
                max_tokens=max_input_tokens,
            )
            if segmentation.quality_warning:
                warnings.append(
                    f"paragraph {paragraph.id}: forced splitting may reduce translation quality"
                )
            work_by_text[normalized] = _Work(
                source_text=normalized,
                protected=protected,
                segments=segmentation.segments,
                targets=[(index, "miss")],
                glossary=prepared,
            )
            misses += 1

        entries = [(work, segment) for work in work_by_text.values() for segment in work.segments]
        for offset in range(0, len(entries), batch_size):
            batch = entries[offset : offset + batch_size]
            from pdftranslate.translation.pipeline import _translate_with_bounded_oom

            results = _translate_with_bounded_oom(
                translator, [segment.text for _, segment in batch]
            )
            translated_segments += len(results)
            for (work, _), translated in zip(batch, results, strict=True):
                work.translated.append(translated)
                if len(work.translated) != len(work.segments):
                    continue
                translated_text = work.protected.restore(
                    recombine_segments(work.segments, work.translated)
                )
                evidence: ParagraphGlossaryEvidence | None = None
                if work.glossary is not None:
                    translated_text, evidence = work.glossary.restore_and_validate(
                        translated_text,
                        document.paragraphs[work.targets[0][0]].id,
                    )
                cache.put(
                    backend=translator.backend_name,
                    model=translator.model_name,
                    source_language=source_language,
                    target_language=target_language,
                    source_text=work.source_text,
                    translated_text=translated_text,
                    glossary_fingerprint=(
                        options.glossary.fingerprint if options.glossary else None
                    ),
                )
                for index, cache_status in work.targets:
                    paragraphs[index] = document.paragraphs[index].model_copy(
                        update={"translated_text": translated_text}
                    )
                    completed += 1
                    if evidence is not None:
                        glossary_evidence[document.paragraphs[index].id] = evidence.model_copy(
                            update={"paragraph_id": document.paragraphs[index].id}
                        )
                    notify(index, cache_status, len(work.segments))
                save()
    except KeyboardInterrupt as error:
        partial = build("interrupted")
        if checkpoint is not None:
            checkpoint(partial)
        raise TranslationInterruptedError(partial) from error

    if completed != total:
        raise TranslationBackendError("translation finished with incomplete paragraphs")
    result = build("completed")
    if checkpoint is not None:
        checkpoint(result)
    return result


def _paragraph_policy(
    document: ExtractedDocument,
    paragraph: LogicalParagraph,
) -> RepeatedElementPolicy:
    evidence = document.repeated_elements
    if evidence is None:
        return RepeatedElementPolicy.TRANSLATE
    by_id = evidence.by_block_id()
    policies = {
        item.policy
        for fragment in paragraph.fragments
        if (item := by_id.get(fragment.mapping.source_block_id)) is not None
    }
    if not policies:
        return RepeatedElementPolicy.TRANSLATE
    if len(policies) > 1:
        return RepeatedElementPolicy.PRESERVE
    return next(iter(policies))


def _validate_resume(
    source: ExtractedDocument,
    resumed: ExtractedDocument,
    translator: Translator,
    options: TranslationOptions,
) -> None:
    metadata = resumed.translation
    if resumed.schema_version != "1.3" or metadata is None:
        raise ResumeMismatchError("resume output is not translated paragraph schema 1.3")
    if metadata.status == "completed":
        raise ResumeMismatchError("translation output is already complete")
    expected = (
        translator.backend_name,
        translator.model_name,
        options.source_language,
        options.target_language,
        options.batch_size,
        options.max_input_tokens,
        options.glossary.fingerprint if options.glossary is not None else None,
    )
    actual = (
        metadata.backend,
        metadata.model,
        metadata.source_language,
        metadata.target_language,
        metadata.batch_size,
        metadata.max_input_tokens,
        metadata.glossary.fingerprint if metadata.glossary is not None else None,
    )
    if expected != actual:
        raise ResumeMismatchError("resume settings do not match the partial output")
    if source.source != resumed.source or source.selected_pages != resumed.selected_pages:
        raise ResumeMismatchError("resume output belongs to a different source document")
    source_units = tuple((item.id, item.text) for item in source.paragraphs)
    resumed_units = tuple((item.id, item.text) for item in resumed.paragraphs)
    if source_units != resumed_units:
        raise ResumeMismatchError("resume paragraph structure does not match the source")
