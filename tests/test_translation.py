from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from pdftranslate.domain.document import (
    DocumentMetadata,
    ExtractedDocument,
    SourceDocument,
)
from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox, TextBlock
from pdftranslate.translation import (
    ProtectedTokenError,
    TranslationCache,
    TranslationCacheError,
    TranslationInterruptedError,
    TranslationOptions,
    TranslationOutOfMemoryError,
    translate_document,
)
from pdftranslate.translation.text import protect_text, segment_text


class FakeTranslator:
    backend_name = "fake"
    model_name = "fake-model"
    device = "cpu"

    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def count_tokens(self, text: str) -> int:
        return len(text.split()) + 2

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        self.batches.append(list(texts))
        return [f"RU {text}" for text in texts]


class InterruptingTranslator(FakeTranslator):
    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        raise KeyboardInterrupt


class OomTranslator(FakeTranslator):
    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        self.batches.append(list(texts))
        if len(texts) > 1:
            raise TranslationOutOfMemoryError("test OOM")
        return [f"RU {texts[0]}"]


def _document(*texts: str) -> ExtractedDocument:
    blocks = tuple(
        TextBlock(
            id=f"p1-b{index}",
            text=text,
            bbox=BoundingBox(x0=0, y0=index * 10, x1=100, y1=index * 10 + 8),
            original_order=index,
            normalized_order=index,
        )
        for index, text in enumerate(texts)
    )
    return ExtractedDocument(
        source=SourceDocument(path="C:/input/source.pdf", file_size=100, sha256="0" * 64),
        page_count=1,
        selected_pages=(1,),
        metadata=DocumentMetadata(),
        encrypted=False,
        password_required=False,
        pages=(
            ExtractedPage(
                page_number=1,
                source_index=0,
                width=100,
                height=100,
                rotation=0,
                classification=PageClassification.TEXT,
                text_blocks=blocks,
            ),
        ),
    )


def test_pipeline_preserves_originals_protected_tokens_and_duplicates(tmp_path: Path) -> None:
    protected = (
        "Visit https://example.com, email a@example.com, use C:\\docs\\a.txt, "
        "then set 25 mm for item ID-12345."
    )
    source = _document(protected, protected, "42", "A normal sentence.")
    translator = FakeTranslator()

    with TranslationCache(tmp_path / "cache.sqlite3") as cache:
        result = translate_document(
            source,
            translator=translator,
            cache=cache,
            options=TranslationOptions(batch_size=2, max_input_tokens=30),
        )

    blocks = result.pages[0].text_blocks
    assert result.schema_version == "1.1"
    assert [block.text for block in blocks] == [protected, protected, "42", "A normal sentence."]
    assert blocks[0].translated_text == blocks[1].translated_text
    assert "https://example.com" in (blocks[0].translated_text or "")
    assert "a@example.com" in (blocks[0].translated_text or "")
    assert "C:\\docs\\a.txt" in (blocks[0].translated_text or "")
    assert "25 mm" in (blocks[0].translated_text or "")
    assert "ID-12345" in (blocks[0].translated_text or "")
    assert blocks[2].translated_text == "42"
    assert sum(len(batch) for batch in translator.batches) == 2
    assert result.translation is not None
    assert result.translation.status == "completed"
    assert result.translation.statistics.cache_hits == 1
    assert result.translation.statistics.skipped_blocks == 1


def test_cache_prevents_work_across_runs(tmp_path: Path) -> None:
    source = _document("Repeated source sentence.")
    cache_path = tmp_path / "cache.sqlite3"
    first = FakeTranslator()
    with TranslationCache(cache_path) as cache:
        translate_document(
            source,
            translator=first,
            cache=cache,
            options=TranslationOptions(),
        )
    second = FakeTranslator()
    with TranslationCache(cache_path) as cache:
        result = translate_document(
            source,
            translator=second,
            cache=cache,
            options=TranslationOptions(),
        )

    assert first.batches
    assert second.batches == []
    assert result.translation is not None
    assert result.translation.statistics.cache_hits == 1
    assert result.translation.statistics.cache_misses == 0


def test_long_text_is_segmented_without_truncation(tmp_path: Path) -> None:
    source = _document(" ".join(f"word{number}" for number in range(30)))
    translator = FakeTranslator()
    with TranslationCache(tmp_path / "cache.sqlite3") as cache:
        result = translate_document(
            source,
            translator=translator,
            cache=cache,
            options=TranslationOptions(batch_size=3, max_input_tokens=8),
        )

    assert len(translator.batches) > 1
    assert all(translator.count_tokens(text) <= 8 for batch in translator.batches for text in batch)
    assert result.translation is not None
    assert result.translation.warnings
    translated = result.pages[0].text_blocks[0].translated_text or ""
    assert all(f"word{number}" in translated for number in range(30))


def test_oom_batches_are_split_with_a_finite_fallback(tmp_path: Path) -> None:
    translator = OomTranslator()
    source = _document("First sentence.", "Second sentence.")
    with TranslationCache(tmp_path / "cache.sqlite3") as cache:
        result = translate_document(
            source,
            translator=translator,
            cache=cache,
            options=TranslationOptions(batch_size=2),
        )

    assert [len(batch) for batch in translator.batches] == [2, 1, 1]
    assert result.translation is not None
    assert result.translation.status == "completed"


def test_interruption_checkpoint_can_resume(tmp_path: Path) -> None:
    source = _document("Translate this sentence.")
    checkpoints: list[ExtractedDocument] = []
    cache_path = tmp_path / "cache.sqlite3"

    with (
        TranslationCache(cache_path) as cache,
        pytest.raises(TranslationInterruptedError) as caught,
    ):
        translate_document(
            source,
            translator=InterruptingTranslator(),
            cache=cache,
            options=TranslationOptions(),
            checkpoint=checkpoints.append,
        )

    partial = caught.value.partial_document
    assert isinstance(partial, ExtractedDocument)
    assert partial.translation is not None
    assert partial.translation.status == "interrupted"
    assert checkpoints[-1] == partial

    with TranslationCache(cache_path) as cache:
        resumed = translate_document(
            source,
            translator=FakeTranslator(),
            cache=cache,
            options=TranslationOptions(),
            resume_document=partial,
        )
    assert resumed.translation is not None
    assert resumed.translation.status == "completed"
    assert resumed.translation.started_at == partial.translation.started_at


def test_cache_corruption_is_recoverable_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.sqlite3"
    path.write_bytes(b"not a sqlite database")

    with (
        pytest.raises(TranslationCacheError, match="cannot open translation cache"),
        TranslationCache(path),
    ):
        pass


def test_protected_token_loss_is_not_silent() -> None:
    protected = protect_text("Read https://example.com")

    with pytest.raises(ProtectedTokenError, match="example.com"):
        protected.restore("translated without the sentinel")


def test_segmentation_retains_paragraph_breaks() -> None:
    result = segment_text(
        "First very short sentence.\n\nSecond very short sentence.",
        count_tokens=lambda value: len(value.split()) + 2,
        max_tokens=8,
    )

    assert "\n\n" in "".join(segment.text + segment.separator_after for segment in result.segments)
