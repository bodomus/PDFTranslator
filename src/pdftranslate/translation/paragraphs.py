"""Paragraph-aware translation for reconstructed document schema 1.2."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pdftranslate.domain.document import (
    ExtractedDocument,
    ForeignLanguageClassification,
    ForeignLanguageStatistics,
    ForeignLanguageTranslationEvidence,
    ForeignLanguageUnitEvidence,
    TranslationMetadata,
    TranslationStatistics,
)
from pdftranslate.glossary import (
    GlossaryEntryMode,
    ParagraphGlossaryEvidence,
    PreparedGlossaryText,
    build_glossary_evidence,
    prepare_glossary_text,
    validate_glossary_output,
)
from pdftranslate.reconstruction import LogicalParagraph
from pdftranslate.repeated import RepeatedElementPolicy
from pdftranslate.translation.cache import TRANSLATION_BEHAVIOR_REVISION, TranslationCache
from pdftranslate.translation.errors import (
    ResumeMismatchError,
    TranslationBackendError,
    TranslationInterruptedError,
)
from pdftranslate.translation.foreign_language import (
    PreparedForeignLanguageText,
    prepare_foreign_language_text,
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
    protected_parts: tuple[ProtectedText, ...]
    segments: tuple[Segment, ...]
    segment_counts: tuple[int, ...]
    glossary: PreparedGlossaryText | None = None
    foreign_language: PreparedForeignLanguageText | None = None
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
    foreign_language_evidence: dict[int, ForeignLanguageUnitEvidence] = {}

    if resume_document is not None:
        _validate_resume(document, resume_document, translator, options)
        paragraphs = list(resume_document.paragraphs)
        metadata = resume_document.translation
        assert metadata is not None
        if metadata.behavior_revision != TRANSLATION_BEHAVIOR_REVISION:
            raise ResumeMismatchError("resume translation behavior revision does not match")
        started_at = metadata.started_at
        completed = sum(item.translated_text is not None for item in paragraphs)
        if metadata.foreign_language is not None:
            foreign_language_evidence.update(
                (item.unit_index, item) for item in metadata.foreign_language.units
            )
        preserved_indices = {
            item.unit_index
            for item in foreign_language_evidence.values()
            if item.classification is ForeignLanguageClassification.PRESERVE_FOREIGN_UNIT
        }
        skipped = sum(
            item.translated_text is not None
            and (
                index in preserved_indices
                or _paragraph_policy(resume_document, item) is not RepeatedElementPolicy.TRANSLATE
                or should_skip_translation(item.text)
            )
            for index, item in enumerate(paragraphs)
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
        foreign_units = tuple(
            foreign_language_evidence[index] for index in sorted(foreign_language_evidence)
        )
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
            behavior_revision=TRANSLATION_BEHAVIOR_REVISION,
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
            foreign_language=ForeignLanguageTranslationEvidence(
                behavior_revision=TRANSLATION_BEHAVIOR_REVISION,
                units=foreign_units,
                statistics=ForeignLanguageStatistics(
                    preserved_units=sum(
                        item.classification is ForeignLanguageClassification.PRESERVE_FOREIGN_UNIT
                        for item in foreign_units
                    ),
                    translated_with_preserved_spans=sum(
                        item.classification
                        is ForeignLanguageClassification.TRANSLATE_WITH_PRESERVED_SPANS
                        for item in foreign_units
                    ),
                    preserved_spans=sum(item.preserved_span_count for item in foreign_units),
                ),
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
            allow_whole_unit = not (
                prepared is not None
                and any(
                    match.entry.mode is GlossaryEntryMode.TRANSLATE for match in prepared.matches
                )
            )
            foreign_language = prepare_foreign_language_text(
                prepared.value if prepared is not None else paragraph.text,
                allow_whole_unit=allow_whole_unit,
                whole_unit_text=paragraph.text,
            )
            if (
                foreign_language.decision.classification
                is ForeignLanguageClassification.PRESERVE_FOREIGN_UNIT
            ):
                paragraphs[index] = paragraph.model_copy(update={"translated_text": paragraph.text})
                foreign_language_evidence[index] = _foreign_evidence(
                    index,
                    paragraph,
                    foreign_language,
                    translator_called=False,
                )
                completed += 1
                skipped += 1
                notify(index, "skipped", 0)
                save()
                continue
            cached = cache.get(
                backend=translator.backend_name,
                model=translator.model_name,
                source_language=source_language,
                target_language=target_language,
                source_text=normalized,
                glossary_fingerprint=options.glossary.fingerprint if options.glossary else None,
            )
            if cached is not None:
                foreign_language.validate_restored(cached, paragraph.id)
                paragraphs[index] = paragraph.model_copy(update={"translated_text": cached})
                if prepared is not None:
                    glossary_evidence[paragraph.id] = validate_glossary_output(
                        cached,
                        paragraph.id,
                        prepared.matches,
                    )
                foreign_language_evidence[index] = _foreign_evidence(
                    index,
                    paragraph,
                    foreign_language,
                    translator_called=False,
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
            protected_parts: list[ProtectedText] = []
            segments: list[Segment] = []
            segment_counts: list[int] = []
            for part in foreign_language.translatable_parts():
                protected = protect_text(part)
                protected_parts.append(protected)
                if not protected.value:
                    segment_counts.append(0)
                    continue
                segmentation = segment_text(
                    protected.value,
                    count_tokens=translator.count_tokens,
                    max_tokens=max_input_tokens,
                )
                segments.extend(segmentation.segments)
                segment_counts.append(len(segmentation.segments))
                if segmentation.quality_warning:
                    warnings.append(
                        f"paragraph {paragraph.id}: forced splitting may reduce translation quality"
                    )
            if not segments:
                translated_text = foreign_language.restore_parts(
                    tuple("" for _ in protected_parts), paragraph.id
                )
                if prepared is not None:
                    translated_text, glossary_evidence[paragraph.id] = (
                        prepared.restore_and_validate(translated_text, paragraph.id)
                    )
                paragraphs[index] = paragraph.model_copy(
                    update={"translated_text": translated_text}
                )
                foreign_language_evidence[index] = _foreign_evidence(
                    index,
                    paragraph,
                    foreign_language,
                    translator_called=False,
                )
                completed += 1
                skipped += 1
                notify(index, "skipped", 0)
                save()
                continue
            work_by_text[normalized] = _Work(
                source_text=normalized,
                protected_parts=tuple(protected_parts),
                segments=tuple(segments),
                segment_counts=tuple(segment_counts),
                targets=[(index, "miss")],
                glossary=prepared,
                foreign_language=foreign_language,
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
                first_paragraph = document.paragraphs[work.targets[0][0]]
                translated_parts: list[str] = []
                cursor = 0
                for protected, segment_count in zip(
                    work.protected_parts, work.segment_counts, strict=True
                ):
                    part_segments = work.segments[cursor : cursor + segment_count]
                    part_translations = work.translated[cursor : cursor + segment_count]
                    translated_parts.append(
                        protected.restore(recombine_segments(part_segments, part_translations))
                    )
                    cursor += segment_count
                if work.foreign_language is None:
                    raise TranslationBackendError("foreign-language preparation is missing")
                translated_text = work.foreign_language.restore_parts(
                    tuple(translated_parts), first_paragraph.id
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
                    source_paragraph = document.paragraphs[index]
                    paragraphs[index] = source_paragraph.model_copy(
                        update={"translated_text": translated_text}
                    )
                    completed += 1
                    if evidence is not None:
                        glossary_evidence[document.paragraphs[index].id] = evidence.model_copy(
                            update={"paragraph_id": document.paragraphs[index].id}
                        )
                    if work.foreign_language is not None:
                        foreign_language_evidence[index] = _foreign_evidence(
                            index,
                            source_paragraph,
                            work.foreign_language,
                            translator_called=True,
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


def _foreign_evidence(
    unit_index: int,
    paragraph: LogicalParagraph,
    prepared: PreparedForeignLanguageText,
    *,
    translator_called: bool,
) -> ForeignLanguageUnitEvidence:
    return ForeignLanguageUnitEvidence(
        unit_index=unit_index,
        paragraph_id=paragraph.id,
        page_number=paragraph.anchor_page_number,
        classification=prepared.decision.classification,
        reasons=prepared.decision.reasons,
        preserved_span_count=prepared.preserved_span_count,
        translator_called=translator_called,
    )


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
        TRANSLATION_BEHAVIOR_REVISION,
    )
    actual = (
        metadata.backend,
        metadata.model,
        metadata.source_language,
        metadata.target_language,
        metadata.batch_size,
        metadata.max_input_tokens,
        metadata.glossary.fingerprint if metadata.glossary is not None else None,
        metadata.behavior_revision,
    )
    if expected != actual:
        raise ResumeMismatchError("resume settings do not match the partial output")
    if source.source != resumed.source or source.selected_pages != resumed.selected_pages:
        raise ResumeMismatchError("resume output belongs to a different source document")
    source_units = tuple((item.id, item.text) for item in source.paragraphs)
    resumed_units = tuple((item.id, item.text) for item in resumed.paragraphs)
    if source_units != resumed_units:
        raise ResumeMismatchError("resume paragraph structure does not match the source")
