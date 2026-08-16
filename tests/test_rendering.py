from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pymupdf
import pytest
from pytest import MonkeyPatch
from typer.testing import CliRunner

from pdftranslate.cli import app
from pdftranslate.domain.document import TranslationMetadata, TranslationStatistics
from pdftranslate.pdf import PdfExtractor
from pdftranslate.rendering import (
    FontValidationError,
    OutputPdfError,
    PdfRenderer,
    RenderingInputError,
    RenderOptions,
    SourceMismatchError,
    validate_font,
)
from pdftranslate.rendering.renderer import (
    _ExpectedText,
    _normalize_validation_text,
    _validate_saved_pdf,
)
from pdftranslate.serialization import write_document_json

runner = CliRunner()


def test_saved_pdf_text_validation_normalizes_embedded_font_hyphens() -> None:
    assert _normalize_validation_text("каким‐либо\n10022‑5299") == ("каким-либо 10022-5299")


def test_saved_pdf_text_validation_normalizes_pdf_parenthesis_forms() -> None:
    assert _normalize_validation_text("текст \ufd3eсм. пример\ufd3f") == "текст (см. пример)"


def _expected_text(
    *,
    block_id: str,
    text: str,
    rect: pymupdf.Rect,
    font_path: Path,
) -> _ExpectedText:
    return _ExpectedText(
        page_number=1,
        block_id=block_id,
        source_text="source",
        translated_text=text,
        source_rect=rect,
        final_rect=rect,
        font_path=font_path,
        font_size=12,
        overflow=False,
        expanded=False,
    )


def test_saved_pdf_validation_uses_render_unit_clip_when_page_order_differs(
    tmp_path: Path,
    cyrillic_font_path: Path,
) -> None:
    path = tmp_path / "order.pdf"
    document = pymupdf.open()
    page = document.new_page(width=420, height=160)
    shape = page.new_shape()
    shape.insert_textbox(
        pymupdf.Rect(40, 40, 220, 70),
        "Первая строка",
        fontname="PDFTranslateFont",
        fontfile=str(cyrillic_font_path),
        fontsize=12,
    )
    shape.insert_textbox(
        pymupdf.Rect(260, 52, 380, 82),
        "Помеха",
        fontname="PDFTranslateFont",
        fontfile=str(cyrillic_font_path),
        fontsize=12,
    )
    shape.insert_textbox(
        pymupdf.Rect(40, 76, 220, 106),
        "Вторая строка",
        fontname="PDFTranslateFont",
        fontfile=str(cyrillic_font_path),
        fontsize=12,
    )
    shape.commit()
    document.save(path)
    document.close()

    _validate_saved_pdf(
        path,
        1,
        [
            _expected_text(
                block_id="p1",
                text="Первая строка Вторая строка",
                rect=pymupdf.Rect(35, 40, 230, 110),
                font_path=cyrillic_font_path,
            )
        ],
    )


def test_saved_pdf_validation_rejects_partial_render_unit(
    tmp_path: Path,
    cyrillic_font_path: Path,
) -> None:
    path = tmp_path / "partial.pdf"
    document = pymupdf.open()
    page = document.new_page(width=300, height=120)
    shape = page.new_shape()
    shape.insert_textbox(
        pymupdf.Rect(40, 40, 240, 70),
        "Первая строка",
        fontname="PDFTranslateFont",
        fontfile=str(cyrillic_font_path),
        fontsize=12,
    )
    shape.commit()
    document.save(path)
    document.close()

    with pytest.raises(OutputPdfError, match="block p1"):
        _validate_saved_pdf(
            path,
            1,
            [
                _expected_text(
                    block_id="p1",
                    text="Первая строка Вторая строка",
                    rect=pymupdf.Rect(35, 40, 220, 80),
                    font_path=cyrillic_font_path,
                )
            ],
        )


def _source_pdf(path: Path, *, image: bool = False, background: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    page = document.new_page(width=400, height=400)
    if background:
        page.draw_rect(page.rect, fill=(0.86, 0.9, 0.72), color=None)
    page.draw_line((25, 130), (375, 130), color=(0.2, 0.3, 0.4), width=2)
    page.insert_textbox(
        pymupdf.Rect(40, 40, 270, 95),
        "English source paragraph with two lines\nfor rendering tests.",
        fontsize=14,
        lineheight=1.2,
    )
    if image:
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
        pixmap.clear_with(0x336699)
        page.insert_image(pymupdf.Rect(280, 220, 370, 310), pixmap=pixmap)
    document.save(path)
    document.close()
    return path


def _split_block_pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    page = document.new_page(width=400, height=180)
    page.insert_textbox(
        pymupdf.Rect(40, 40, 270, 95),
        "68.\nThe Origin of Justice",
        fontsize=14,
        lineheight=1.2,
    )
    document.save(path)
    document.close()
    return path


def _translated(source: Path, text: str):
    extracted = PdfExtractor().extract(source)
    pages = tuple(
        page.model_copy(
            update={
                "text_blocks": tuple(
                    block.model_copy(update={"translated_text": text}) for block in page.text_blocks
                )
            }
        )
        for page in extracted.pages
    )
    total = sum(len(page.text_blocks) for page in pages)
    now = datetime.now(UTC)
    metadata = TranslationMetadata(
        status="completed",
        backend="nllb",
        model="fake",
        source_language="en",
        target_language="ru",
        effective_device="cpu",
        batch_size=1,
        max_input_tokens=64,
        started_at=now,
        updated_at=now,
        completed_at=now,
        statistics=TranslationStatistics(
            total_blocks=total,
            completed_blocks=total,
            skipped_blocks=0,
            cache_hits=0,
            cache_misses=total,
            translated_segments=total,
        ),
    )
    return extracted.model_copy(
        update={"schema_version": "1.1", "pages": pages, "translation": metadata}
    )


def _translation_metadata(total: int) -> TranslationMetadata:
    now = datetime.now(UTC)
    return TranslationMetadata(
        status="completed",
        backend="nllb",
        model="fake",
        source_language="en",
        target_language="ru",
        effective_device="cpu",
        batch_size=1,
        max_input_tokens=64,
        started_at=now,
        updated_at=now,
        completed_at=now,
        statistics=TranslationStatistics(
            total_blocks=total,
            completed_blocks=total,
            skipped_blocks=0,
            cache_hits=0,
            cache_misses=total,
            translated_segments=total,
        ),
    )


def _schema_1_3_with_split_paragraphs(
    source: Path,
    *,
    marker_translation: str,
    heading_translation: str,
):
    extracted = PdfExtractor().extract(source)
    marker, heading = extracted.paragraphs[:2]
    paragraphs = (
        marker.model_copy(update={"translated_text": marker_translation}),
        heading.model_copy(update={"translated_text": heading_translation}),
    )
    return extracted.model_copy(
        update={
            "schema_version": "1.3",
            "paragraphs": paragraphs,
            "translation": _translation_metadata(len(paragraphs)),
        }
    )


def test_render_replaces_text_and_preserves_source_geometry_images_and_vectors(
    tmp_path: Path,
    cyrillic_font_path: Path,
) -> None:
    source = _source_pdf(tmp_path / "source.pdf", image=True, background=True)
    before = source.read_bytes()
    translated = _translated(source, "Русский перевод абзаца для проверки.")
    output = tmp_path / "translated.pdf"

    result = PdfRenderer().render(
        source,
        translated,
        output,
        font_path=cyrillic_font_path,
        options=RenderOptions(allow_expand=True),
    )

    assert source.read_bytes() == before
    assert result.blocks_rendered == len(translated.pages[0].text_blocks)
    assert result.overflow_blocks == 0
    assert result.file_size == output.stat().st_size
    source_document = pymupdf.open(source)
    rendered_document = pymupdf.open(output)
    try:
        assert rendered_document.page_count == source_document.page_count == 1
        assert rendered_document[0].rect == source_document[0].rect
        assert len(rendered_document[0].get_images(full=True)) == 1
        assert len(rendered_document[0].get_drawings()) >= len(source_document[0].get_drawings())
        rendered_text = rendered_document[0].get_text("text")
        assert "Русский перевод" in rendered_text
        assert "English source paragraph" not in rendered_text
    finally:
        rendered_document.close()
        source_document.close()


def test_schema_1_3_render_accepts_split_block_when_marker_translation_is_present(
    tmp_path: Path,
    cyrillic_font_path: Path,
) -> None:
    source = _split_block_pdf(tmp_path / "split-block.pdf")
    translated = _schema_1_3_with_split_paragraphs(
        source,
        marker_translation="68.",
        heading_translation="Русское происхождение справедливости.",
    )

    result = PdfRenderer().render(
        source,
        translated,
        tmp_path / "split-block.ru.pdf",
        font_path=cyrillic_font_path,
        options=RenderOptions(allow_expand=True),
    )

    assert result.blocks_rendered == 2
    assert [item.block_id for item in result.blocks] == [
        translated.paragraphs[0].id,
        translated.paragraphs[1].id,
    ]


def test_schema_1_3_render_still_rejects_empty_translate_policy_paragraph(
    tmp_path: Path,
    cyrillic_font_path: Path,
) -> None:
    source = _split_block_pdf(tmp_path / "missing-split-block.pdf")
    translated = _schema_1_3_with_split_paragraphs(
        source,
        marker_translation="",
        heading_translation="Русское происхождение справедливости.",
    )

    with pytest.raises(RenderingInputError, match="translated text is missing"):
        PdfRenderer().render(
            source,
            translated,
            tmp_path / "missing-split-block.ru.pdf",
            font_path=cyrillic_font_path,
        )


def test_font_size_is_reduced_for_longer_translation(
    tmp_path: Path,
    cyrillic_font_path: Path,
) -> None:
    source = _source_pdf(tmp_path / "font-reduction.pdf")
    translated = _translated(
        source,
        "Это заметно более длинный русский перевод текста для проверки размера. " * 2,
    )

    result = PdfRenderer().render(
        source,
        translated,
        tmp_path / "font-reduction.ru.pdf",
        font_path=cyrillic_font_path,
        options=RenderOptions(min_font_size=5, font_size_step=0.5),
    )

    assert result.font_reductions >= 1
    assert result.overflow_blocks == 0
    assert all(block.font_size is not None for block in result.blocks)


def test_overflow_is_reported_without_silent_clipping(
    tmp_path: Path,
    cyrillic_font_path: Path,
) -> None:
    source = _source_pdf(tmp_path / "overflow.pdf")
    translated = _translated(source, "Очень длинный русский текст " * 100)

    result = PdfRenderer().render(
        source,
        translated,
        tmp_path / "overflow.ru.pdf",
        font_path=cyrillic_font_path,
        options=RenderOptions(min_font_size=10, font_size_step=1),
    )

    assert result.overflow_blocks >= 1
    assert any("overflows" in warning for warning in result.warnings)
    assert any(block.font_size is None for block in result.blocks)


def test_allow_expand_uses_safe_downward_space(
    tmp_path: Path,
    cyrillic_font_path: Path,
) -> None:
    source = _source_pdf(tmp_path / "expand.pdf")
    translated = _translated(source, "Расширенный перевод " * 18)

    result = PdfRenderer().render(
        source,
        translated,
        tmp_path / "expand.ru.pdf",
        font_path=cyrillic_font_path,
        options=RenderOptions(min_font_size=8, allow_expand=True),
    )

    assert result.expanded_blocks >= 1
    assert result.overflow_blocks == 0
    assert any(block.final_bbox.y1 > block.source_bbox.y1 for block in result.blocks)


def test_source_fingerprint_mismatch_is_rejected(
    tmp_path: Path,
    cyrillic_font_path: Path,
) -> None:
    source = _source_pdf(tmp_path / "mismatch.pdf")
    translated = _translated(source, "Русский перевод.")
    document = pymupdf.open(source)
    metadata = document.metadata
    metadata["title"] = "Changed after extraction"
    document.set_metadata(metadata)
    changed = tmp_path / "changed.pdf"
    document.save(changed)
    document.close()
    changed.replace(source)

    with pytest.raises(SourceMismatchError, match="SHA-256"):
        PdfRenderer().render(
            source,
            translated,
            tmp_path / "rejected.pdf",
            font_path=cyrillic_font_path,
        )

    result = PdfRenderer().render(
        source,
        translated,
        tmp_path / "forced.pdf",
        font_path=cyrillic_font_path,
        options=RenderOptions(force_source_mismatch=True),
    )
    assert result.output_path.exists()


def test_font_validation_reports_missing_cyrillic_glyphs(
    cyrillic_font_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    class MissingGlyphFont:
        def has_glyph(self, _codepoint: int) -> int:
            return 0

    monkeypatch.setattr(pymupdf, "Font", lambda **_kwargs: MissingGlyphFont())

    with pytest.raises(FontValidationError, match="lacks required Cyrillic glyphs"):
        validate_font(cyrillic_font_path, ("Русский",))


def test_cli_render_supports_unicode_paths_and_separate_debug_output(
    tmp_path: Path,
    cyrillic_font_path: Path,
) -> None:
    directory = tmp_path / "папка с пробелами"
    source = _source_pdf(directory / "источник.pdf")
    translated = _translated(source, "Русский текст в PDF.")
    document_json = directory / "перевод.json"
    output = directory / "результат.pdf"
    write_document_json(translated, document_json)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

    result = runner.invoke(
        app,
        [
            "render",
            str(source),
            str(document_json),
            "--output",
            str(output),
            "--font",
            str(cyrillic_font_path),
            "--allow-expand",
            "--debug-layout",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Rendered" in result.stdout
    assert output.exists()
    assert output.with_name("результат.debug.pdf").exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash


def test_renderer_protects_source_and_existing_output(
    tmp_path: Path,
    cyrillic_font_path: Path,
) -> None:
    source = _source_pdf(tmp_path / "protected.pdf")
    translated = _translated(source, "Защищённый результат.")

    with pytest.raises(OutputPdfError, match="must not be the source"):
        PdfRenderer().render(source, translated, source, font_path=cyrillic_font_path)

    output = tmp_path / "existing.pdf"
    output.write_bytes(b"existing")
    with pytest.raises(OutputPdfError, match="already exists"):
        PdfRenderer().render(source, translated, output, font_path=cyrillic_font_path)
    assert output.read_bytes() == b"existing"


def test_debug_layout_preserves_failed_temporary_pdf_without_publishing_output(
    tmp_path: Path,
    cyrillic_font_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source = _source_pdf(tmp_path / "failed-debug.pdf")
    translated = _translated(source, "Русский текст должен быть вставлен.")
    output = tmp_path / "failed-debug.ru.pdf"

    monkeypatch.setattr("pdftranslate.rendering.renderer._insert_page", lambda *_args: None)

    with pytest.raises(OutputPdfError, match="block"):
        PdfRenderer().render(
            source,
            translated,
            output,
            font_path=cyrillic_font_path,
            options=RenderOptions(debug_layout=True),
        )

    assert not output.exists()
    assert output.with_name("failed-debug.ru.failed-render.pdf").exists()
    assert not output.with_name("failed-debug.ru.debug.pdf").exists()
