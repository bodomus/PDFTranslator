"""Glossary integration across logical paragraphs, repetition, cache, and diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

from pdftranslate.glossary import LoadedGlossary, load_glossary
from pdftranslate.reconstruction import ParagraphKind
from pdftranslate.translation import TranslationCache, TranslationOptions, translate_document
from tests.test_repeated_elements import _block, _document, _page, _Translator


def _glossary(path: Path, target: str, version: str) -> LoadedGlossary:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "glossary_version": version,
                "source_language": "en",
                "target_language": "ru",
                "entries": [
                    {
                        "id": "header",
                        "source": "Glossary",
                        "target": target,
                        "mode": "translate",
                        "case_sensitive": True,
                        "match": "whole_word",
                        "inflection": "fixed",
                        "priority": 100,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return load_glossary(path)


def test_repeated_header_glossary_is_deduplicated_and_cache_is_fingerprint_scoped(
    tmp_path: Path,
) -> None:
    pages = tuple(
        _page(
            number,
            _block(number, 0, "Glossary header", 20),
            _block(number, 1, f"Body sentence {number}.", 150),
            _block(number, 2, str(number), 770, x0=290, x1=310),
        )
        for number in range(1, 4)
    )
    source = _document(pages)
    cache_path = tmp_path / "glossary-cache.sqlite3"

    first_translator = _Translator()
    with TranslationCache(cache_path) as cache:
        first = translate_document(
            source,
            translator=first_translator,
            cache=cache,
            options=TranslationOptions(
                glossary=_glossary(tmp_path / "first.json", "Глоссарий", "1.0.0")
            ),
        )
    second_translator = _Translator()
    with TranslationCache(cache_path) as cache:
        second = translate_document(
            source,
            translator=second_translator,
            cache=cache,
            options=TranslationOptions(
                glossary=_glossary(tmp_path / "second.json", "Терминология", "1.0.1")
            ),
        )

    first_headers = [item for item in first.paragraphs if item.kind is ParagraphKind.HEADER]
    second_headers = [item for item in second.paragraphs if item.kind is ParagraphKind.HEADER]
    assert {item.translated_text for item in first_headers} == {"RU Глоссарий header"}
    assert {item.translated_text for item in second_headers} == {"RU Терминология header"}
    assert sum("__PDFTR_" in text for batch in first_translator.batches for text in batch) == 1
    assert second_translator.batches
    assert first.translation is not None and first.translation.glossary is not None
    assert first.translation.glossary.statistics.applied_occurrences == 3
    assert all(
        item.translated_text == item.text
        for item in first.paragraphs
        if item.kind is ParagraphKind.PAGE_NUMBER
    )
