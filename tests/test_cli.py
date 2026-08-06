from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from pdftranslate.cli import app
from tests.conftest import PdfFactory

runner = CliRunner()


def test_version_exits_successfully() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "PDFTranslate" in result.stdout
    assert "0.1.0" in result.stdout


def test_doctor_exits_successfully() -> None:
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "PDFTranslate doctor" in result.stdout
    assert "Application" in result.stdout
    assert "OCRmyPDF" in result.stdout
    assert "English OCR" in result.stdout
    assert "Status" in result.stdout


def test_doctor_works_without_cuda_tools() -> None:
    with (
        patch("pdftranslate.cli.importlib.util.find_spec", return_value=None),
        patch("pdftranslate.cli.shutil.which", return_value=None),
    ):
        result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "PyTorch is not installed" in result.stdout
    assert "nvidia-smi is unavailable" in result.stdout


def test_inspect_produces_readable_report(tmp_path: Path, pdf_factory: PdfFactory) -> None:
    source = pdf_factory(tmp_path / "inspect.pdf")

    result = runner.invoke(app, ["inspect", str(source)])

    assert result.exit_code == 0
    assert "PDF inspection" in result.stdout
    assert "Text pages" in result.stdout
    assert "SHA-256" in result.stdout


def test_inspect_json_is_clean_machine_output(tmp_path: Path, pdf_factory: PdfFactory) -> None:
    source = pdf_factory(tmp_path / "inspect-json.pdf")

    result = runner.invoke(app, ["inspect", str(source), "--json"])

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["page_count"] == 1
    assert report["text_pages"] == 1
    assert "\x1b[" not in result.stdout


def test_extract_writes_compact_versioned_json(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "extract.pdf", page_specs=("text", "empty"))
    output = tmp_path / "output document.json"

    result = runner.invoke(
        app,
        [
            "extract",
            str(source),
            "--pages",
            "2",
            "--output",
            str(output),
            "--compact",
            "--repeated-elements",
            "off",
        ],
    )

    assert result.exit_code == 0
    assert "Extracted 1 page(s)" in result.stdout
    payload = output.read_text(encoding="utf-8")
    document = json.loads(payload)
    assert document["schema_version"] == "1.2"
    assert document["selected_pages"] == [2]
    assert document["pages"][0]["classification"] == "empty"
    assert document["repeated_elements"]["mode"] == "off"
    assert document["repeated_elements"]["metrics"]["classified_blocks"] == 0
    assert payload.count("\n") == 1


def test_extract_protects_existing_output(tmp_path: Path, pdf_factory: PdfFactory) -> None:
    source = pdf_factory(tmp_path / "source.pdf")
    output = tmp_path / "exists.json"
    output.write_text("keep", encoding="utf-8")

    result = runner.invoke(app, ["extract", str(source), "--output", str(output)])

    assert result.exit_code == 2
    assert "--overwrite" in result.stderr
    assert output.read_text(encoding="utf-8") == "keep"


def test_missing_pdf_fails_predictably(tmp_path: Path) -> None:
    result = runner.invoke(app, ["inspect", str(tmp_path / "missing.pdf")])

    assert result.exit_code == 2
    assert "does not exist" in result.stderr


def test_unsupported_command_exits_predictably() -> None:
    result = runner.invoke(app, ["does-not-exist"])

    assert result.exit_code == 2
    assert "No such command" in result.output
