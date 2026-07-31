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
    RenderOptions,
    SourceMismatchError,
    validate_font,
)
from pdftranslate.serialization import write_document_json

runner = CliRunner()


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
