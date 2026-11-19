"""Translate a rebuilt book paragraph by paragraph with any registered engine."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from pdftranslate.book.models import BookDocument, BookParagraph, BookTranslationInfo
from pdftranslate.engines.base import EngineRequest, EngineResult, TranslationEngine
from pdftranslate.translation.cache import TranslationCache

BookProgress = Callable[[int, int, int], None]
"""Called with (paragraphs done, total, failed so far)."""

# Engines without context get this many paragraphs per call; their own batching does the rest.
NO_CONTEXT_BATCH = 16


def translate_book(
    book: BookDocument,
    engine: TranslationEngine,
    *,
    engine_name: str,
    cache: TranslationCache | None = None,
    progress: BookProgress | None = None,
) -> BookDocument:
    """Return the book with a translation, or the failure reason, on every paragraph.

    Engines that use context see the previous paragraph and its translation. To keep that
    while serving several requests at once, the book is cut into contiguous lanes that advance
    in lockstep: step k translates the k-th paragraph of every lane. Finished paragraphs are
    cached, so rerunning after a crash or with failures only spends work on what is missing.
    """
    paragraphs = list(book.paragraphs)
    total = len(paragraphs)
    translations: list[str | None] = [None] * total
    errors: list[str | None] = [None] * total
    done = 0
    failed = 0

    def finish(index: int, result: EngineResult) -> None:
        nonlocal done, failed
        translations[index] = result.text
        errors[index] = None if result.ok else (result.error or "translation failed")
        done += 1
        failed += 0 if result.ok else 1

    capabilities = engine.capabilities
    schedule = _schedule(total, capabilities.uses_context, capabilities.parallel_requests)
    # Lane starts never get context, so a rerun sends the same requests and hits the cache.
    lane_starts = frozenset(schedule[0]) if schedule and capabilities.uses_context else frozenset()
    for step in schedule:
        pending: list[tuple[int, EngineRequest, str]] = []
        for index in step:
            with_context = capabilities.uses_context and index not in lane_starts
            request = _request(paragraphs, translations, index, with_context)
            key = _cache_text(request)
            cached = _cache_get(cache, engine.engine_id, key)
            if cached is not None:
                finish(index, EngineResult(cached))
                continue
            pending.append((index, request, key))
        if pending:
            results = engine.translate([request for _index, request, _key in pending])
            if len(results) != len(pending):
                raise RuntimeError(
                    f"engine {engine.engine_id} returned {len(results)} results "
                    f"for {len(pending)} requests"
                )
            for (index, _request_item, key), result in zip(pending, results, strict=True):
                finish(index, result)
                if result.ok and cache is not None and result.text is not None:
                    cache.put(
                        backend=engine.engine_id,
                        model="book",
                        source_language="en",
                        target_language="ru",
                        source_text=key,
                        translated_text=result.text,
                    )
        if progress is not None:
            progress(done, total, failed)

    updated = tuple(
        paragraph.model_copy(update={"translation": text, "translation_error": error})
        for paragraph, text, error in zip(paragraphs, translations, errors, strict=True)
    )
    missing = sum(text is None for text in translations)
    return book.model_copy(
        update={
            "paragraphs": updated,
            "translation": BookTranslationInfo(
                engine=engine_name,
                engine_id=engine.engine_id,
                translated=total - missing,
                failed=missing,
            ),
        }
    )


def book_translation_text(book: BookDocument) -> str:
    """Plain-text Russian rendering for review; untranslated paragraphs are flagged."""
    chunks: list[str] = []
    for item in book.paragraphs:
        text = item.translation if item.translation is not None else f"[НЕ ПЕРЕВЕДЕНО] {item.text}"
        chunks.append(f"## {text}" if item.kind == "heading" else text)
    return "\n\n".join(chunks) + "\n"


def _schedule(total: int, uses_context: bool, parallel: int) -> list[list[int]]:
    """Group paragraph indexes into engine calls, preserving reading order inside each lane."""
    if total == 0:
        return []
    if not uses_context:
        size = max(NO_CONTEXT_BATCH, parallel)
        return [list(range(start, min(total, start + size))) for start in range(0, total, size)]
    lanes = max(1, min(parallel, total))
    length = math.ceil(total / lanes)
    starts = range(0, total, length)
    return [
        [start + step for start in starts if start + step < min(total, start + length)]
        for step in range(length)
    ]


def _request(
    paragraphs: Sequence[BookParagraph],
    translations: Sequence[str | None],
    index: int,
    with_context: bool,
) -> EngineRequest:
    text = paragraphs[index].text
    if not with_context:
        return EngineRequest(text)
    previous = translations[index - 1]
    if previous is None:
        return EngineRequest(text)
    return EngineRequest(
        text,
        previous_source=paragraphs[index - 1].text,
        previous_translation=previous,
    )


def _cache_text(request: EngineRequest) -> str:
    """Everything the engine sees, so a changed neighbour never reuses a stale translation."""
    parts = [request.text]
    if request.previous_source is not None:
        parts += [request.previous_source, request.previous_translation or ""]
    parts += [f"{source}\t{target}" for source, target in request.glossary]
    return "\n␞\n".join(parts)


def _cache_get(cache: TranslationCache | None, engine_id: str, key: str) -> str | None:
    if cache is None:
        return None
    return cache.get(
        backend=engine_id,
        model="book",
        source_language="en",
        target_language="ru",
        source_text=key,
    )
