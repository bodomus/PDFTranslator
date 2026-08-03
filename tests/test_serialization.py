from __future__ import annotations

from pathlib import Path

import pytest

from pdftranslate.pdf import PdfExtractor
from pdftranslate.serialization import (
    OutputExistsError,
    document_from_json,
    document_to_json,
    write_document_json,
)
from tests.conftest import PdfFactory


def test_document_json_round_trip_preserves_domain_model(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "round-trip.pdf", page_specs=("text", "empty"))
    document = PdfExtractor().extract(source)

    payload = document_to_json(document)

    assert '"schema_version":"1.2"'.replace(":", ": ") in payload
    assert '"translated_text"' not in payload
    assert '"translation"' not in payload
    assert document_from_json(payload) == document


def test_compact_json_has_no_formatting_newlines(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    document = PdfExtractor().extract(pdf_factory(tmp_path / "compact.pdf"))

    assert "\n" not in document_to_json(document, pretty=False)


def test_writer_protects_existing_output_and_supports_overwrite(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "source.pdf")
    document = PdfExtractor().extract(source)
    output = tmp_path / "nested" / "document.json"

    write_document_json(document, output)
    original = output.read_text(encoding="utf-8")
    with pytest.raises(OutputExistsError, match="--overwrite"):
        write_document_json(document, output)

    write_document_json(document, output, pretty=False, overwrite=True)

    assert output.read_text(encoding="utf-8") != original
    assert document_from_json(output.read_text(encoding="utf-8")) == document
    assert not list(output.parent.glob("*.tmp"))


def test_writer_never_overwrites_source_pdf(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "immutable.pdf")
    original_bytes = source.read_bytes()
    document = PdfExtractor().extract(source)

    with pytest.raises(OutputExistsError, match="source PDF"):
        write_document_json(document, source, overwrite=True)

    assert source.read_bytes() == original_bytes


def test_json_preserves_unicode_as_utf8_text(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "папка" / "документ.pdf")
    document = PdfExtractor().extract(source)

    payload = document_to_json(document)

    assert "папка" in payload
    assert "\\u043f" not in payload.lower()
