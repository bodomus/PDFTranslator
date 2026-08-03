from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from _pytest.monkeypatch import MonkeyPatch

from pdftranslate.config import Settings
from pdftranslate.domain.page import PageClassification
from pdftranslate.domain.text_block import BoundingBox, TextBlock
from pdftranslate.pdf import (
    InvalidPageRangeError,
    PdfAnalyzer,
    PdfCorruptError,
    PdfEmptyError,
    PdfEncryptedError,
    PdfExtractor,
)
from pdftranslate.pdf.page_ranges import parse_page_range
from pdftranslate.pdf.pymupdf_backend import PyMuPdfBackend, _merge_adjacent_text_blocks
from tests.conftest import PdfFactory


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, (1, 2, 3, 4, 5)),
        ("1", (1,)),
        ("1-3", (1, 2, 3)),
        ("1,3-5", (1, 3, 4, 5)),
    ],
)
def test_parse_page_range(value: str | None, expected: tuple[int, ...]) -> None:
    assert parse_page_range(value, 5) == expected


@pytest.mark.parametrize("value", ["", "0", "2-1", "1,1", "1-3,3", "1,a", "6"])
def test_parse_page_range_rejects_invalid_values(value: str) -> None:
    with pytest.raises(InvalidPageRangeError):
        parse_page_range(value, 5)


def test_extracts_one_page_text_with_layout_metadata(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "one-page.pdf")

    document = PdfExtractor().extract(source)

    assert document.schema_version == "1.2"
    assert document.page_count == 1
    assert document.selected_pages == (1,)
    assert document.source.file_size > 0
    assert len(document.source.sha256) == 64
    assert document.probable_source_language == "en"
    page = document.pages[0]
    assert page.page_number == 1
    assert page.source_index == 0
    assert page.classification is PageClassification.TEXT
    assert page.width == 400
    assert page.height == 400
    assert page.rotation == 0
    assert page.text_blocks
    block = page.text_blocks[0]
    assert block.id == "p0001-b0001"
    assert block.original_order == 0
    assert block.normalized_order == 0
    assert block.bbox.x1 > block.bbox.x0
    assert block.spans[0].font_name
    assert block.spans[0].font_size
    assert isinstance(block.spans[0].text_color, int)
    assert block.spans[0].bold is False
    assert block.spans[0].italic is False
    assert block.lines
    assert document.paragraphs
    assert document.reconstruction is not None
    assert document.reconstruction.metrics.raw_blocks == len(page.text_blocks)
    assert document.paragraphs[0].fragments[0].mapping.source_block_id == block.id


def test_extracts_selected_pages_from_multi_page_pdf(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "multi.pdf", page_specs=("text", "empty", "text"))

    document = PdfExtractor().extract(source, "1,3")

    assert document.page_count == 3
    assert document.selected_pages == (1, 3)
    assert [page.page_number for page in document.pages] == [1, 3]
    assert [page.source_index for page in document.pages] == [0, 2]


@pytest.mark.parametrize(
    ("spec", "classification"),
    [
        ("text", PageClassification.TEXT),
        ("empty", PageClassification.EMPTY),
        ("image", PageClassification.SCANNED),
        ("mixed", PageClassification.MIXED),
    ],
)
def test_classifies_generated_page_types(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    spec: str,
    classification: PageClassification,
) -> None:
    source = pdf_factory(tmp_path / f"{spec}.pdf", page_specs=(spec,))

    page = PdfExtractor().extract(source).pages[0]

    assert page.classification is classification
    if spec in {"image", "mixed"}:
        assert page.image_count == 1
        assert page.image_area_ratio > 0.5


def test_inspection_aggregates_all_page_classes(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(
        tmp_path / "classes.pdf",
        page_specs=("text", "empty", "image", "mixed"),
    )

    report = PdfAnalyzer().inspect(source)

    assert report.page_count == 4
    assert report.text_pages == 1
    assert report.empty_pages == 1
    assert report.scanned_pages == 1
    assert report.mixed_pages == 1
    assert report.image_count == 2
    assert report.text_block_count == 2
    assert report.encrypted is False
    assert report.password_required is False


def test_invalid_pdf_fails_with_domain_error(tmp_path: Path) -> None:
    source = tmp_path / "invalid.pdf"
    source.write_text("not a PDF", encoding="utf-8")

    with pytest.raises(PdfCorruptError, match="cannot open PDF"):
        PdfExtractor().extract(source)


def test_non_pdf_extension_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "document.txt"
    source.write_text("not a PDF", encoding="utf-8")

    with pytest.raises(PdfCorruptError, match=".pdf extension"):
        PdfAnalyzer().inspect(source)


def test_encrypted_pdf_can_be_identified_but_not_extracted(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "encrypted.pdf", encrypted=True)

    report = PdfAnalyzer().inspect(source)

    assert report.encrypted is True
    assert report.password_required is True
    assert report.warnings
    with pytest.raises(PdfEncryptedError, match="requires a password"):
        PdfExtractor().extract(source)


def test_extraction_order_is_stable_and_preserves_backend_order(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "ordered.pdf", page_specs=("ordered",))

    first = PdfExtractor().extract(source)
    second = PdfExtractor().extract(source)
    first_blocks = first.pages[0].text_blocks

    assert first == second
    assert [block.original_order for block in first_blocks] == list(range(len(first_blocks)))
    assert [block.normalized_order for block in first_blocks] == list(range(len(first_blocks)))
    assert [block.id for block in first_blocks] == [
        f"p0001-b{number:04d}" for number in range(1, len(first_blocks) + 1)
    ]


def test_adjacent_paragraph_fragments_are_merged_and_dehyphenated() -> None:
    blocks = [
        TextBlock(
            id="p0007-b0001",
            text="No part of this book",
            bbox=BoundingBox(x0=40, y0=380, x1=346, y1=392),
            original_order=4,
            normalized_order=0,
        ),
        TextBlock(
            id="p0007-b0002",
            text="may be reproduced. For infor-",
            bbox=BoundingBox(x0=41, y0=394, x1=354, y1=414),
            original_order=5,
            normalized_order=1,
        ),
        TextBlock(
            id="p0007-b0003",
            text="mation, address Basic Books.",
            bbox=BoundingBox(x0=47, y0=414, x1=323, y1=427),
            original_order=6,
            normalized_order=2,
        ),
    ]

    merged = _merge_adjacent_text_blocks(blocks, 7)

    assert len(merged) == 1
    assert merged[0].id == "p0007-b0001"
    assert merged[0].text == (
        "No part of this book may be reproduced. For information, address Basic Books."
    )
    assert merged[0].bbox == BoundingBox(x0=40, y0=380, x1=354, y1=427)


def test_adjacent_blocks_with_separate_title_content_are_not_merged() -> None:
    blocks = [
        TextBlock(
            id="p0003-b0001",
            text="THE",
            bbox=BoundingBox(x0=175, y0=65, x1=195, y1=75),
            original_order=0,
            normalized_order=0,
        ),
        TextBlock(
            id="p0003-b0002",
            text="AND THE",
            bbox=BoundingBox(x0=160, y0=145, x1=215, y1=155),
            original_order=1,
            normalized_order=1,
        ),
    ]

    assert _merge_adjacent_text_blocks(blocks, 3) == blocks


def test_paths_with_spaces_and_cyrillic_are_supported(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(
        tmp_path / "РїР°РїРєР° СЃ РїСЂРѕР±РµР»РѕРј" / "РґРѕРєСѓРјРµРЅС‚ СЃ РїСЂРѕР±РµР»РѕРј.pdf"
    )

    document = PdfExtractor().extract(source)

    assert "РїР°РїРєР° СЃ РїСЂРѕР±РµР»РѕРј" in document.source.path
    assert document.pages[0].text_blocks


def test_metadata_and_rotation_are_preserved(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "rotated.pdf", page_specs=("rotated",))

    document = PdfExtractor().extract(source)

    assert document.metadata.title == "Generated PDF fixture"
    assert document.metadata.author == "PDFTranslate tests"
    assert document.pages[0].rotation == 90


def test_classification_thresholds_are_configurable(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "threshold.pdf", page_specs=("mixed",))
    settings = Settings(classification_mixed_image_area_ratio=0.99)

    page = PdfExtractor(settings).extract(source).pages[0]

    assert page.classification is PageClassification.TEXT


def test_zero_page_pdf_is_rejected(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source = tmp_path / "zero-pages.pdf"
    source.write_bytes(b"%PDF-1.7\n")
    backend = PyMuPdfBackend()

    @contextmanager
    def open_empty_document(_: Path) -> Iterator[SimpleNamespace]:
        yield SimpleNamespace(page_count=0, needs_pass=False, is_encrypted=False)

    monkeypatch.setattr(backend, "open_pdf", open_empty_document)

    with pytest.raises(PdfEmptyError, match="no pages"):
        backend.extract(source)
