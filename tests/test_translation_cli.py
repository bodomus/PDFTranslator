from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from pdftranslate.cli import app
from pdftranslate.pdf import PdfExtractor
from pdftranslate.serialization import read_document_json, write_document_json
from tests.conftest import PdfFactory

runner = CliRunner()


class FakeCliTranslator:
    backend_name = "nllb"
    model_name = "fake-nllb"
    device = "cpu"

    def count_tokens(self, text: str) -> int:
        return len(text.split()) + 2

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        return [f"RU {text}" for text in texts]


def test_translate_command_uses_fake_backend_and_writes_schema_1_3(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source_pdf = pdf_factory(tmp_path / "source.pdf")
    input_json = tmp_path / "document.json"
    output_json = tmp_path / "document.ru.json"
    write_document_json(PdfExtractor().extract(source_pdf), input_json)

    with patch("pdftranslate.cli.NllbTranslator", return_value=FakeCliTranslator()) as loader:
        result = runner.invoke(
            app,
            [
                "translate",
                str(input_json),
                "--output",
                str(output_json),
                "--cache-dir",
                str(tmp_path / "cache"),
                "--offline",
                "--batch-size",
                "2",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "Loading model" in result.stdout
    assert "Blocks 1/1" in result.stdout
    assert "elapsed" in result.stdout
    loader.assert_called_once()
    assert loader.call_args.kwargs["offline"] is True
    translated = read_document_json(output_json)
    assert translated.schema_version == "1.3"
    assert translated.translation is not None
    assert translated.translation.status == "completed"
    paragraph = translated.paragraphs[0]
    assert paragraph.translated_text is not None
    assert paragraph.translated_text.startswith("RU ")
    assert paragraph.text in paragraph.translated_text


def test_translate_rejects_unknown_backend_before_model_loading(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    input_json = tmp_path / "document.json"
    write_document_json(PdfExtractor().extract(pdf_factory(tmp_path / "source.pdf")), input_json)

    with patch("pdftranslate.cli.NllbTranslator") as loader:
        result = runner.invoke(
            app,
            [
                "translate",
                str(input_json),
                "--output",
                str(tmp_path / "output.json"),
                "--backend",
                "cloud",
            ],
        )

    assert result.exit_code == 2
    assert "unsupported translation backend" in result.stderr
    loader.assert_not_called()
