from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path

import pymupdf
import pytest

from pdftranslate.book import (
    BookOcrOptions,
    TesseractError,
    TesseractRunner,
    assemble_book,
    book_to_text,
    ocr_book,
    parse_tsv,
)
from pdftranslate.book.assembly import (
    analyze_page,
    build_vocabulary,
    clean_note_markers,
    join_lines,
)
from pdftranslate.book.models import PageOcr

PAGE_WIDTH = 2000
PAGE_HEIGHT = 3000
LEFT = 200
RIGHT = 1800
LINE_HEIGHT = 40

Line = tuple[int, int, str] | tuple[int, int, str, int]


def _tsv(lines: list[Line]) -> str:
    """Build Tesseract TSV for (paragraph, left, text[, right]) lines placed top to bottom."""
    rows = [
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
        f"1\t1\t0\t0\t0\t0\t0\t0\t{PAGE_WIDTH}\t{PAGE_HEIGHT}\t-1\t",
    ]
    line_numbers: Counter[int] = Counter()
    for spec in lines:
        paragraph, top, text = spec[0], spec[1], spec[2]
        left = spec[3] if len(spec) == 4 else LEFT
        line_numbers[paragraph] += 1
        words = text.split()
        right = RIGHT if len(words) > 6 else left + 60 * len(words)
        step = (right - left) // max(1, len(words))
        for number, word in enumerate(words, start=1):
            x = left + (number - 1) * step
            width = max(10, step - 10)
            rows.append(
                f"5\t1\t1\t{paragraph}\t{line_numbers[paragraph]}\t{number}\t{x}\t{top}\t"
                f"{width}\t{LINE_HEIGHT}\t95.0\t{word}"
            )
    return "\n".join(rows) + "\n"


FULL = "word " * 12


def _page(number: int, lines: list[Line]) -> PageOcr:
    return parse_tsv(_tsv(lines), number)


def test_parse_tsv_groups_words_into_paragraph_lines() -> None:
    page = _page(1, [(1, 300, "First line of text here and more words"), (1, 350, "second line")])

    assert page.width == PAGE_WIDTH
    assert page.height == PAGE_HEIGHT
    assert len(page.paragraphs) == 1
    assert [line.text for line in page.paragraphs[0].lines] == [
        "First line of text here and more words",
        "second line",
    ]


def test_running_headers_and_page_numbers_leave_reading_flow() -> None:
    page = _page(
        7,
        [
            (1, 60, "THE SWORD AND THE SHIELD / 26"),
            (2, 300, f"Body {FULL}"),
            (2, 350, "ends here."),
            (3, 2900, "26"),
        ],
    )

    layout = analyze_page(page)

    assert layout.headers == ("THE SWORD AND THE SHIELD / 26", "26")
    assert [block.kind for block in layout.blocks] == ["body"]


def test_paragraph_continues_on_next_page_without_indent() -> None:
    first = _page(1, [(1, 300, f"Start {FULL}"), (1, 350, f"middle {FULL}")])
    second = _page(2, [(1, 300, f"Continued {FULL}"), (1, 350, "end.")])

    book = assemble_book([first, second])

    assert len(book.paragraphs) == 1
    assert book.paragraphs[0].pages == (1, 2)
    assert book.statistics.cross_page_merges == 1


def test_indented_paragraph_after_finished_one_starts_new_paragraph() -> None:
    first = _page(1, [(1, 300, f"Start {FULL}"), (1, 350, "done.")])
    second = _page(2, [(1, 300, f"New {FULL}", LEFT + 60), (1, 350, f"text {FULL}")])

    book = assemble_book([first, second])

    assert [item.pages for item in book.paragraphs] == [(1,), (2,)]


def test_lowercase_start_continues_even_when_indented() -> None:
    first = _page(1, [(1, 300, f"Quote {FULL}"), (1, 350, "short.")])
    second = _page(2, [(1, 300, f"when you {FULL}", LEFT + 60), (1, 350, "end.")])

    book = assemble_book([first, second])

    assert len(book.paragraphs) == 1


def test_short_line_ending_a_sentence_splits_an_ocr_paragraph() -> None:
    page = _page(
        1,
        [(1, 300, f"One {FULL}"), (1, 350, "short end."), (1, 400, f"Two {FULL}"), (1, 450, "x.")],
    )

    book = assemble_book([page])

    assert [item.text.split()[0] for item in book.paragraphs] == ["One", "Two"]


def test_headings_are_detected_by_case_and_never_merge() -> None:
    page = _page(1, [(1, 300, "CHAPTER TWO", LEFT + 500), (2, 400, f"Body {FULL}"), (2, 450, "x.")])

    book = assemble_book([page])

    assert [item.kind for item in book.paragraphs] == ["heading", "body"]
    assert book.statistics.headings == 1
    assert book.paragraphs[0].text == "CHAPTER TWO"


def test_dehyphenation_uses_book_vocabulary() -> None:
    vocabulary = build_vocabulary(["counter-revolutionary forces", "the information was clear"])

    syllables, joined = join_lines(["useful infor-", "mation here"], vocabulary)
    compound, kept = join_lines(["a counter-", "revolutionary plot"], vocabulary)
    unknown, guessed = join_lines(["fac-", "ing it"], vocabulary)
    dash, _ = join_lines(["secretly—", "and urgently"], vocabulary)

    assert (syllables, joined) == ("useful information here", 1)
    assert (compound, kept) == ("a counter-revolutionary plot", 0)
    assert (unknown, guessed) == ("facing it", 1)
    assert dash == "secretly—and urgently"


def test_vocabulary_ignores_line_final_fragments() -> None:
    vocabulary = build_vocabulary(["the infor-", "mation"])

    assert "infor" not in vocabulary
    assert vocabulary["mation"] == 1


@pytest.mark.parametrize(
    ("source", "expected", "markers"),
    [
        ('interrogators."* In', 'interrogators." In', (15,)),
        ("the terror.”'® On", "the terror.” On", (12,)),
        ("Stalin's Terror.'®", "Stalin's Terror.", (16,)),
        ("a battle.”” That", "a battle.” That", (10,)),
        ("the spot.!’ However", "the spot. However", (9,)),
        ("was 3.14 exactly.", "was 3.14 exactly.", ()),
        ("he said “no.” Then", "he said “no.” Then", ()),
        ("people.’ The", "people.’ The", ()),
        ("Kannegiser.12 In", "Kannegiser. In", (11,)),
    ],
)
def test_note_markers_are_removed_and_located(
    source: str, expected: str, markers: tuple[int, ...]
) -> None:
    cleaned = clean_note_markers(source)

    assert cleaned.text == expected
    assert cleaned.note_markers == markers


def test_leading_ocr_junk_is_removed_from_paragraphs() -> None:
    book = assemble_book([_page(1, [(1, 300, f"«-Berzin {FULL}"), (1, 350, "end.")])])

    assert book.paragraphs[0].text.startswith("Berzin ")


def test_low_confidence_words_are_reported() -> None:
    tsv = _tsv([(1, 300, f"Cheha {FULL}"), (1, 350, "end.")]).replace("95.0\tCheha", "13.1\tCheha")

    book = assemble_book([parse_tsv(tsv, 1)])

    assert book.paragraphs[0].low_confidence == ("Cheha",)
    assert book.statistics.low_confidence_words == 1


class FakeRunner:
    language = "eng"
    page_segmentation_mode = 3

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def version(self) -> str:
        return "5.4.0"

    def recognize(self, image_path: Path, dpi: int) -> str:
        assert image_path.is_file()
        self.calls.append((image_path.name, dpi))
        return _tsv([(1, 300, f"Page text {FULL}"), (1, 350, "ends.")])


def _scanned_pdf(path: Path, pages: int) -> Path:
    document = pymupdf.open()
    for _ in range(pages):
        page = document.new_page(width=360, height=540)
        pixmap = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 500, 750), False)
        pixmap.clear_with(255)
        page.insert_image(page.rect, pixmap=pixmap)
    document.save(path)
    document.close()
    return path


def test_ocr_book_uses_embedded_scans_and_resumes_from_cache(tmp_path: Path) -> None:
    source = _scanned_pdf(tmp_path / "book.pdf", 3)
    runner = FakeRunner()
    options = BookOcrOptions(pages="1-2", jobs=2, work_dir=tmp_path / "work")

    book = ocr_book(source, runner, options)  # type: ignore[arg-type]

    assert book.selected_pages == (1, 2)
    assert book.page_count == 3
    assert book.ocr.version == "5.4.0"
    assert sorted(runner.calls) == [("page-0001.png", 100), ("page-0002.png", 100)]
    assert len(book.paragraphs) == 2
    assert not list((tmp_path / "work").glob("*.png"))

    resumed = FakeRunner()
    again = ocr_book(source, resumed, options)  # type: ignore[arg-type]

    assert resumed.calls == []
    assert again.paragraphs == book.paragraphs
    assert book_to_text(book).startswith("Page text word")


def test_runner_requires_tesseract() -> None:
    with pytest.raises(TesseractError, match="unavailable"):
        TesseractRunner(find_executable=lambda _name: None)


def test_runner_invokes_tsv_with_single_thread_and_reports_failures(tmp_path: Path) -> None:
    seen: list[list[str]] = []
    environments: list[dict[str, str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(command)
        environment = kwargs.get("env")
        if isinstance(environment, dict):
            environments.append(environment)
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, "tesseract v5.4.0.20240606\n", "")
        if "bad.png" in command[1]:
            return subprocess.CompletedProcess(command, 1, "", "Error: cannot read\n")
        return subprocess.CompletedProcess(command, 0, "tsv", "")

    runner = TesseractRunner(run_process=run, find_executable=lambda _name: "tesseract")

    assert runner.version() == "5.4.0.20240606"
    assert runner.recognize(tmp_path / "ok.png", 470) == "tsv"
    assert seen[-1][-1] == "tsv" and "470" in seen[-1]
    assert environments[-1]["OMP_THREAD_LIMIT"] == "1"
    with pytest.raises(TesseractError, match="cannot read"):
        runner.recognize(tmp_path / "bad.png", 300)
