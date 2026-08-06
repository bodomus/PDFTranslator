"""Focused generated-fixture coverage for repeated non-body elements."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pymupdf

from pdftranslate.diagnostics.builder import build_success_report
from pdftranslate.domain.document import DocumentMetadata, ExtractedDocument, SourceDocument
from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox, TextBlock, TextLine, TextSpan
from pdftranslate.pdf import PdfExtractor
from pdftranslate.reconstruction import ParagraphKind, reconstruct_paragraphs
from pdftranslate.rendering import PdfRenderer
from pdftranslate.repeated import (
    RepeatedElementKind,
    RepeatedElementOptions,
    RepeatedElementPolicy,
    classify_repeated_elements,
)
from pdftranslate.translation import TranslationCache, TranslationOptions, translate_document


class _Translator:
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


def _block(
    page: int,
    order: int,
    text: str,
    y0: float,
    *,
    x0: float = 50,
    x1: float = 550,
    height: float = 14,
    font_size: float = 10,
) -> TextBlock:
    identifier = f"p{page:04d}-b{order:04d}"
    box = BoundingBox(x0=x0, y0=y0, x1=x1, y1=y0 + height)
    span = TextSpan(text=text, bbox=box, font_size=font_size)
    line = TextLine(
        id=f"{identifier}-l0001",
        text=text,
        bbox=box,
        original_order=0,
        spans=(span,),
    )
    return TextBlock(
        id=identifier,
        text=text,
        bbox=box,
        original_order=order,
        normalized_order=order,
        spans=(span,),
        lines=(line,),
    )


def _page(number: int, *blocks: TextBlock) -> ExtractedPage:
    return ExtractedPage(
        page_number=number,
        source_index=number - 1,
        width=600,
        height=800,
        rotation=0,
        classification=PageClassification.TEXT,
        text_blocks=blocks,
    )


def _by_text(pages: Sequence[ExtractedPage], analysis: object) -> dict[str, object]:
    evidence = analysis.by_block_id()  # type: ignore[attr-defined]
    return {block.text: evidence[block.id] for page in pages for block in page.text_blocks}


def test_detects_sequential_page_numbers_and_preserves_policy() -> None:
    pages = tuple(
        _page(
            number,
            _block(number, 0, f"Body text {number}.", 120),
            _block(number, 1, str(number), 770, x0=290, x1=310),
        )
        for number in range(1, 5)
    )

    result = classify_repeated_elements(pages)
    numbers = [item for item in result.blocks if item.kind is RepeatedElementKind.PAGE_NUMBER]

    assert [item.page_number for item in numbers] == [1, 2, 3, 4]
    assert {item.policy for item in numbers} == {RepeatedElementPolicy.PRESERVE}
    assert len({item.group_id for item in numbers}) == 1


def test_detects_uniform_and_alternating_headers_with_first_page_exception() -> None:
    pages: list[ExtractedPage] = []
    for number in range(1, 7):
        blocks = [
            _block(number, 0, "Left running header" if number % 2 else "Right running header", 20),
            _block(number, 1, f"Body {number}.", 150),
        ]
        if number > 1:
            blocks.append(_block(number, 2, "Manual title", 45))
        pages.append(_page(number, *blocks))

    result = classify_repeated_elements(tuple(pages))
    kinds = _by_text(pages, result)

    assert kinds["Left running header"].kind is RepeatedElementKind.RUNNING_HEADER  # type: ignore[attr-defined]
    assert kinds["Right running header"].kind is RepeatedElementKind.RUNNING_HEADER  # type: ignore[attr-defined]
    manual = [item for item in result.blocks if item.block_id.endswith("0002")]
    assert len(manual) == 5
    assert {item.kind for item in manual} == {RepeatedElementKind.RUNNING_HEADER}


def test_chapter_headers_and_short_documents_remain_uncertain() -> None:
    pages = tuple(
        _page(
            number,
            _block(number, 0, "Chapter A" if number in {2, 3} else f"Unique {number}", 20),
            _block(number, 1, f"Body {number}.", 150),
        )
        for number in range(1, 7)
    )
    result = classify_repeated_elements(pages)
    chapter = [item for item in result.blocks if item.block_id in {"p0002-b0000", "p0003-b0000"}]
    assert {item.kind for item in chapter} == {RepeatedElementKind.UNKNOWN_REPEATED}
    assert all(item.ambiguous and item.policy is RepeatedElementPolicy.PRESERVE for item in chapter)

    short = tuple(
        _page(number, _block(number, 0, "Short header", 20), _block(number, 1, "Body", 150))
        for number in (1, 2)
    )
    short_result = classify_repeated_elements(short)
    headers = [item for item in short_result.blocks if item.block_id.endswith("0000")]
    assert {item.kind for item in headers} == {RepeatedElementKind.UNKNOWN_REPEATED}
    assert all(item.ambiguous for item in headers)


def test_classifies_legal_footer_watermark_and_legitimate_repeated_body() -> None:
    pages = tuple(
        _page(
            number,
            _block(number, 0, "DRAFT", 330, x0=220, x1=380, font_size=28),
            _block(number, 1, "A legitimately repeated body sentence.", 120 + number * 30),
            _block(number, 2, "Copyright 2026. All rights reserved.", 750, font_size=8),
        )
        for number in range(1, 5)
    )
    result = classify_repeated_elements(pages)
    evidence = result.by_block_id()

    assert {evidence[f"p{number:04d}-b0000"].kind for number in range(1, 5)} == {
        RepeatedElementKind.WATERMARK_CANDIDATE
    }
    assert {evidence[f"p{number:04d}-b0000"].policy for number in range(1, 5)} == {
        RepeatedElementPolicy.SKIP
    }
    assert {evidence[f"p{number:04d}-b0002"].kind for number in range(1, 5)} == {
        RepeatedElementKind.REPEATED_BOILERPLATE
    }
    assert {evidence[f"p{number:04d}-b0001"].kind for number in range(1, 5)} == {
        RepeatedElementKind.BODY
    }


def test_reconstruction_excludes_confirmed_elements_from_body_merging() -> None:
    pages = tuple(
        _page(
            number,
            _block(number, 0, "Running header", 20),
            _block(number, 1, f"Body paragraph {number} continues", 100),
            _block(number, 2, str(number), 770, x0=290, x1=310),
        )
        for number in range(1, 4)
    )
    repeated = classify_repeated_elements(pages)
    result = reconstruct_paragraphs(pages, repeated_elements=repeated)

    assert sum(item.kind is ParagraphKind.HEADER for item in result.paragraphs) == 3
    assert sum(item.kind is ParagraphKind.PAGE_NUMBER for item in result.paragraphs) == 3
    assert result.evidence.metrics.cross_page_merges == 0
    assert all(
        len(paragraph.fragments) == 1
        for paragraph in result.paragraphs
        if paragraph.kind in {ParagraphKind.HEADER, ParagraphKind.PAGE_NUMBER}
    )


def test_off_mode_classifies_everything_as_body() -> None:
    pages = tuple(_page(number, _block(number, 0, "Repeated header", 20)) for number in range(1, 4))
    result = classify_repeated_elements(pages, RepeatedElementOptions(mode="off"))
    assert {item.kind for item in result.blocks} == {RepeatedElementKind.BODY}
    assert result.groups == ()


def _document(pages: tuple[ExtractedPage, ...]) -> ExtractedDocument:
    repeated = classify_repeated_elements(pages)
    reconstructed = reconstruct_paragraphs(pages, repeated_elements=repeated)
    return ExtractedDocument(
        schema_version="1.2",
        source=SourceDocument(path="source.pdf", file_size=0, sha256="0" * 64),
        page_count=len(pages),
        selected_pages=tuple(page.page_number for page in pages),
        metadata=DocumentMetadata(),
        encrypted=False,
        password_required=False,
        pages=pages,
        paragraphs=reconstructed.paragraphs,
        reconstruction=reconstructed.evidence,
        repeated_elements=repeated,
    )


def test_repeated_translation_is_reused_and_preserve_skip_avoid_model(tmp_path: Path) -> None:
    pages = tuple(
        _page(
            number,
            _block(number, 0, "Reusable header", 20),
            _block(number, 1, "DRAFT", 330, x0=220, x1=380, font_size=28),
            _block(number, 2, f"Body sentence {number}.", 150),
            _block(number, 3, str(number), 770, x0=290, x1=310),
        )
        for number in range(1, 5)
    )
    source = _document(pages)
    translator = _Translator()
    with TranslationCache(tmp_path / "repeated-cache.sqlite3") as cache:
        result = translate_document(
            source,
            translator=translator,
            cache=cache,
            options=TranslationOptions(batch_size=8),
        )

    model_inputs = [text for batch in translator.batches for text in batch]
    assert model_inputs.count("Reusable header") == 1
    assert "DRAFT" not in model_inputs
    assert not any(text in {"1", "2", "3", "4"} for text in model_inputs)
    assert result.translation is not None
    assert result.translation.statistics.skipped_blocks == 8
    headers = [item for item in result.paragraphs if item.kind is ParagraphKind.HEADER]
    assert len({item.translated_text for item in headers}) == 1
    assert {item.anchor_page_number for item in headers} == {1, 2, 3, 4}

    diagnostic_output = tmp_path / "diagnostic-output.pdf"
    diagnostic_output.write_bytes(b"pdf")
    now = datetime.now(UTC)
    report = build_success_report(
        run_id="pdftr12-test",
        started_at=now,
        finished_at=now,
        input_path=tmp_path / "source.pdf",
        output_path=diagnostic_output,
        translated=result,
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
    assert report.summary.repeated_elements["running_header"] == 4
    assert report.summary.repeated_elements["page_number"] == 4
    header_diagnostic = report.pages[0].blocks[0]
    assert header_diagnostic.repeated_classification is RepeatedElementKind.RUNNING_HEADER
    assert header_diagnostic.repeated_policy is RepeatedElementPolicy.TRANSLATE
    assert header_diagnostic.repeated_group_id is not None
    assert header_diagnostic.source_text is None
    assert header_diagnostic.translated_text is None


def test_rendering_keeps_repeated_units_on_their_source_pages(tmp_path: Path) -> None:
    source = tmp_path / "repeated-source.pdf"
    document = pymupdf.open()
    for number in range(1, 4):
        page = document.new_page(width=600, height=800)
        page.insert_text((50, 30), "Reusable header", fontsize=10)
        page.insert_text((50, 160), f"Body sentence {number}.", fontsize=10)
        page.insert_text((295, 780), str(number), fontsize=10)
    document.save(source)
    document.close()

    extracted = PdfExtractor().extract(source)
    translator = _Translator()
    with TranslationCache(tmp_path / "render-cache.sqlite3") as cache:
        translated = translate_document(
            extracted,
            translator=translator,
            cache=cache,
            options=TranslationOptions(batch_size=8),
        )
    output = tmp_path / "repeated-output.pdf"
    render_result = PdfRenderer().render(source, translated, output)
    rendered_ids = {item.block_id for item in render_result.blocks}
    preserved_ids = {
        paragraph.id
        for paragraph in translated.paragraphs
        if paragraph.kind is ParagraphKind.PAGE_NUMBER
    }
    assert rendered_ids.isdisjoint(preserved_ids)

    rendered = pymupdf.open(output)
    try:
        for number, page in enumerate(rendered, start=1):
            text = page.get_text("text")
            assert "RU Reusable header" in text
            assert f"RU Body sentence {number}." in text
            assert str(number) in text
    finally:
        rendered.close()
