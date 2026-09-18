from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pdftranslate.diagnostics.builder import build_success_report
from pdftranslate.domain.document import (
    DocumentMetadata,
    ExtractedDocument,
    ForeignLanguageClassification,
    SourceDocument,
)
from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox, TextBlock
from pdftranslate.glossary.models import (
    GlossaryDocument,
    GlossaryEntry,
    GlossaryEntryMode,
    GlossaryInflection,
    GlossaryMatchType,
    LoadedGlossary,
)
from pdftranslate.reconstruction import (
    LogicalParagraph,
    ParagraphFragment,
    ParagraphKind,
    ParagraphReconstruction,
    ParagraphReconstructionOptions,
    ReconstructionMetrics,
    SourceBlockMapping,
)
from pdftranslate.serialization import document_from_json, document_to_json
from pdftranslate.translation import (
    ProtectedTokenError,
    ResumeMismatchError,
    TranslationCache,
    TranslationCacheError,
    TranslationInterruptedError,
    TranslationOptions,
    TranslationOutOfMemoryError,
    prepare_foreign_language_text,
    translate_document,
)
from pdftranslate.translation.cache import TRANSLATION_BEHAVIOR_REVISION
from pdftranslate.translation.text import (
    normalize_source_text,
    protect_text,
    segment_text,
    should_skip_translation,
)


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


def _paragraph_document(*paragraph_texts: str, paragraph_id: str = "p1-b1") -> ExtractedDocument:
    box = BoundingBox(x0=0, y0=0, x1=100, y1=40)
    block = TextBlock(
        id=paragraph_id,
        text="\n".join(paragraph_texts),
        bbox=box,
        original_order=0,
        normalized_order=0,
    )
    fragments = tuple(
        ParagraphFragment(
            id=f"{paragraph_id}-l{index:04d}",
            text=text,
            bbox=BoundingBox(x0=0, y0=index * 12, x1=100, y1=index * 12 + 10),
            mapping=SourceBlockMapping(
                source_block_id=paragraph_id,
                page_number=1,
                bbox=box,
                original_order=0,
                normalized_order=0,
                line_ids=(),
            ),
            spans=(),
            column=0,
        )
        for index, text in enumerate(paragraph_texts, start=1)
    )
    paragraphs = tuple(
        LogicalParagraph(
            id=paragraph_id,
            text=fragment.text,
            kind=ParagraphKind.BODY,
            anchor_page_number=1,
            bbox=fragment.bbox,
            fragments=(fragment,),
            spans=(),
        )
        for fragment in fragments
    )
    return ExtractedDocument(
        schema_version="1.2",
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
                text_blocks=(block,),
            ),
        ),
        paragraphs=paragraphs,
        reconstruction=ParagraphReconstruction(
            mode="conservative",
            options=ParagraphReconstructionOptions(),
            metrics=ReconstructionMetrics(
                raw_blocks=1,
                raw_lines=len(paragraphs),
                logical_paragraphs=len(paragraphs),
                merged_fragments=0,
                ambiguous_decisions=0,
                cross_page_merges=0,
                soft_hyphens_removed=0,
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


def test_paragraph_pipeline_preserves_pdf_private_use_markers_without_model(
    tmp_path: Path,
) -> None:
    source = _paragraph_document(
        "\uf646\uf64b", "The Origin of Justice", paragraph_id="p0001-b0008"
    )
    translator = FakeTranslator()

    with TranslationCache(tmp_path / "cache.sqlite3") as cache:
        result = translate_document(
            source,
            translator=translator,
            cache=cache,
            options=TranslationOptions(batch_size=2),
        )

    assert should_skip_translation("\uf646\uf64b")
    assert not should_skip_translation("\uf644.\uf647The Logismos Phase")
    assert [text for batch in translator.batches for text in batch] == ["The Origin of Justice"]
    assert [item.id for item in result.paragraphs] == ["p0001-b0008", "p0001-b0008"]
    assert result.paragraphs[0].translated_text == "\uf646\uf64b"
    assert result.paragraphs[1].translated_text == "RU The Origin of Justice"
    assert result.translation is not None
    assert result.translation.statistics.skipped_blocks == 1

    round_tripped = document_from_json(document_to_json(result))
    assert [item.translated_text for item in round_tripped.paragraphs] == [
        "\uf646\uf64b",
        "RU The Origin of Justice",
    ]


def test_whole_latin_passages_are_explicitly_preserved_without_model(tmp_path: Path) -> None:
    first = (
        "praesidium reges ipsi sibi perfugiumque, et pecudes et agros divisere atque "
        "dedere pro facie cuiusque et viribus ingenioque."
    )
    second = (
        "inde magistratum partim docuere creare iuraque constituere, ut vellent legibus "
        "uti. nam genus humanum, defessum vi colere aevum, ex inimicitiis languebat; "
        "quo magis ipsum sponte sua cecidit sub leges artaque iura."
    )
    ordinary = "The ordinary English paragraph must still be translated by the model."
    source = _paragraph_document(first, second, ordinary)
    translator = FakeTranslator()

    with TranslationCache(tmp_path / "cache.sqlite3") as cache:
        result = translate_document(
            source,
            translator=translator,
            cache=cache,
            options=TranslationOptions(),
        )

    assert [item.translated_text for item in result.paragraphs] == [
        first,
        second,
        f"RU {ordinary}",
    ]
    assert [text for batch in translator.batches for text in batch] == [ordinary]
    assert result.translation is not None
    evidence = result.translation.foreign_language
    assert evidence is not None
    assert evidence.statistics.preserved_units == 2
    assert [item.unit_index for item in evidence.units] == [0, 1, 2]
    assert all(
        item.classification is ForeignLanguageClassification.PRESERVE_FOREIGN_UNIT
        and not item.translator_called
        for item in evidence.units[:2]
    )
    assert evidence.units[2].classification is ForeignLanguageClassification.TRANSLATE
    assert evidence.units[2].translator_called


def test_whole_greek_quotation_is_preserved_without_model(tmp_path: Path) -> None:
    greek = "Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν."
    source = _paragraph_document(greek)
    translator = FakeTranslator()

    with TranslationCache(tmp_path / "cache.sqlite3") as cache:
        result = translate_document(
            source,
            translator=translator,
            cache=cache,
            options=TranslationOptions(),
        )

    assert result.paragraphs[0].translated_text == greek
    assert translator.batches == []
    assert result.translation is not None
    assert result.translation.foreign_language is not None
    assert result.translation.foreign_language.units[0].reasons == ("greek_script_unit",)


def test_mixed_prose_translates_and_restores_latin_and_greek_spans(tmp_path: Path) -> None:
    latin = "The passage distinguishes lex from ius and refers to ipsi and sibi."
    greek = "Epicurus writes ἡ φύσις while the English explanation continues."
    source = _paragraph_document(latin, greek)
    translator = FakeTranslator()

    with TranslationCache(tmp_path / "cache.sqlite3") as cache:
        result = translate_document(
            source,
            translator=translator,
            cache=cache,
            options=TranslationOptions(),
        )

    translated = [item.translated_text or "" for item in result.paragraphs]
    assert all(item.startswith("RU ") for item in translated)
    assert all(term in translated[0] for term in ("lex", "ius", "ipsi", "sibi"))
    assert "ἡ" in translated[1]
    assert "φύσις" in translated[1]
    model_inputs = [text for batch in translator.batches for text in batch]
    assert all(
        term not in model_input
        for model_input in model_inputs
        for term in ("lex", "ius", "ipsi", "sibi")
    )
    assert all("__PDFTR_FOREIGN_" not in item for item in model_inputs)
    assert all("ἡ" not in item and "φύσις" not in item for item in model_inputs)
    assert result.translation is not None
    evidence = result.translation.foreign_language
    assert evidence is not None
    assert evidence.statistics.translated_with_preserved_spans == 2
    assert evidence.statistics.preserved_spans == 6
    assert all(item.translator_called for item in evidence.units)

    round_tripped = document_from_json(document_to_json(result))
    assert round_tripped.translation is not None
    assert round_tripped.translation.foreign_language == evidence


def test_explicit_glossary_translation_overrides_whole_latin_preservation(tmp_path: Path) -> None:
    latin = (
        "inde magistratum partim docuere creare iuraque constituere, ut vellent legibus uti. "
        "nam genus humanum ex inimicitiis languebat quo magis sua sub leges."
    )
    target = "обязательный перевод латинской цитаты"
    glossary = LoadedGlossary(
        document=GlossaryDocument(
            schema_version="1.0",
            glossary_version="1.0.0",
            source_language="en",
            target_language="ru",
            entries=(
                GlossaryEntry(
                    id="translate-latin-quotation",
                    source=latin,
                    target=target,
                    mode=GlossaryEntryMode.TRANSLATE,
                    case_sensitive=True,
                    match=GlossaryMatchType.EXACT,
                    inflection=GlossaryInflection.FIXED,
                    priority=100,
                ),
            ),
        ),
        fingerprint="1" * 64,
    )
    translator = FakeTranslator()

    with TranslationCache(tmp_path / "cache.sqlite3") as cache:
        result = translate_document(
            _paragraph_document(latin),
            translator=translator,
            cache=cache,
            options=TranslationOptions(glossary=glossary),
        )

    assert translator.batches
    assert result.paragraphs[0].translated_text == f"RU {target}"
    assert result.translation is not None
    assert result.translation.foreign_language is not None
    evidence = result.translation.foreign_language.units[0]
    assert evidence.classification is ForeignLanguageClassification.TRANSLATE
    assert evidence.translator_called


def test_missing_foreign_span_placeholder_fails_closed() -> None:
    prepared = prepare_foreign_language_text("The argument uses lex and ἡ φύσις here.")

    with pytest.raises(ProtectedTokenError, match="foreign-language span"):
        prepared.restore("Перевод без плейсхолдеров", "p1-b1")

    repeated = prepare_foreign_language_text("English lex between another lex example.")
    with pytest.raises(ProtectedTokenError, match="cached translation"):
        repeated.validate_restored("Перевод только с одним lex.", "p1-b2")


def test_foreign_language_evidence_is_exposed_in_diagnostics(tmp_path: Path) -> None:
    source = _paragraph_document(
        "The argument contrasts lex with ius.",
        "This ordinary English sentence is translated.",
    )
    with TranslationCache(tmp_path / "cache.sqlite3") as cache:
        translated = translate_document(
            source,
            translator=FakeTranslator(),
            cache=cache,
            options=TranslationOptions(),
        )
    output = tmp_path / "output.pdf"
    output.write_bytes(b"pdf")
    now = datetime.now(UTC)

    report = build_success_report(
        run_id="foreign-language-test",
        started_at=now,
        finished_at=now,
        input_path=tmp_path / "input.pdf",
        output_path=output,
        translated=translated,
        render=None,
        ocr_pages=(),
        ocr_warnings=(),
        elapsed_seconds=0.1,
        stage_durations={},
        peak_ram_bytes=None,
        include_text=False,
        debug_layout_path=None,
        block_evidence={},
    )

    assert report.summary.translated_with_preserved_foreign_spans == 1
    assert report.summary.preserved_foreign_spans == 2
    assert report.pages[0].blocks[0].foreign_language_classification == (
        "translate_with_preserved_spans"
    )
    assert report.pages[0].blocks[0].preserved_foreign_spans == 2
    assert report.pages[0].blocks[1].foreign_language_classification == "translate"


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


def test_resume_rejects_pre_foreign_language_behavior_revision(tmp_path: Path) -> None:
    source = _paragraph_document("Translate this ordinary English sentence.")
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
    assert partial.translation is not None
    stale = partial.model_copy(
        update={
            "translation": partial.translation.model_copy(
                update={"behavior_revision": TRANSLATION_BEHAVIOR_REVISION - 1}
            )
        }
    )
    with (
        TranslationCache(cache_path) as cache,
        pytest.raises(ResumeMismatchError, match="resume settings do not match"),
    ):
        translate_document(
            source,
            translator=FakeTranslator(),
            cache=cache,
            options=TranslationOptions(),
            resume_document=stale,
        )


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


def test_protected_tokens_use_ascii_placeholders_and_avoid_source_collisions() -> None:
    protected = protect_text("Copyright 1999; literal __PDFTR_0000__ remains source text.")

    placeholder, original = protected.replacements[0]
    assert placeholder == "___PDFTR_0000___"
    assert placeholder.isascii()
    assert original == "1999"
    assert protected.restore(protected.value) == (
        "Copyright 1999; literal __PDFTR_0000__ remains source text."
    )


@pytest.mark.parametrize(
    "expression",
    [
        "men/first",
        "men/ﬁrst",
        "he/she",
        "and/or",
        "input/output",
        "true/false",
        "yes/no",
        "long-term/short-term",
        "pro-choice/anti-choice",
        "nature/agreement",
        "virtue/pleasure",
    ],
)
def test_slash_separated_prose_is_not_treated_as_protected_path(expression: str) -> None:
    protected = protect_text(f"Epicurean justice compares {expression} in prose.")

    assert protected.replacements == ()
    assert "__PDFTR_" not in protected.value


@pytest.mark.parametrize(
    "path",
    [
        "./foo/bar",
        "../foo/bar",
        "/foo/bar",
        "src/module/file.py",
        "assets/images/logo.png",
        "docs/reference/index.md",
        "folder/file.json",
        "C:\\Temp\\data.json",
        "J:\\Projects\\PDFTranslator\\README.md",
    ],
)
def test_real_paths_remain_protected_after_slash_prose_fix(path: str) -> None:
    protected = protect_text(f"Read {path} before running.")

    assert protected.replacements == (("__PDFTR_0000__", path),)


def test_men_first_ligature_regression_is_normalized_and_not_protected() -> None:
    assert normalize_source_text("men/ﬁrst") == "men/first"

    protected = protect_text("The men/ﬁrst distinction remains prose.")

    assert protected.value == "The men/first distinction remains prose."
    assert protected.replacements == ()
    assert protected.restore(f"RU {protected.value}") == (
        "RU The men/first distinction remains prose."
    )


def test_pdf_ligatures_are_normalized_inside_protected_paths() -> None:
    protected = protect_text("The ofﬁce/virtue relation cites docs/ﬁle.pdf.")

    assert "office/virtue" in protected.value
    assert protected.replacements == (("__PDFTR_0000__", "docs/file.pdf"),)


def test_pre_pdftr16_translation_cache_revision_is_not_reused(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.sqlite3"
    source = "The men/ﬁrst distinction remains prose."
    stale_key = _translation_cache_key_for_revision(
        TRANSLATION_BEHAVIOR_REVISION - 1,
        source,
    )
    with TranslationCache(cache_path):
        pass
    with sqlite3.connect(cache_path) as connection:
        connection.execute(
            "INSERT INTO translations(cache_key, translated_text) VALUES (?, ?)",
            (stale_key, "STALE"),
        )
        connection.commit()

    with TranslationCache(cache_path) as cache:
        assert (
            cache.get(
                backend="fake",
                model="fake-model",
                source_language="en",
                target_language="ru",
                source_text=source,
            )
            is None
        )


def _translation_cache_key_for_revision(revision: int, source_text: str) -> str:
    parts = (
        str(revision),
        "fake",
        "fake-model",
        "en",
        "ru",
        "no-glossary",
        normalize_source_text(source_text),
    )
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def test_segmentation_retains_paragraph_breaks() -> None:
    result = segment_text(
        "First very short sentence.\n\nSecond very short sentence.",
        count_tokens=lambda value: len(value.split()) + 2,
        max_tokens=8,
    )

    assert "\n\n" in "".join(segment.text + segment.separator_after for segment in result.segments)
