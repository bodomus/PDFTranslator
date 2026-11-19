"""Rebuild book reading flow from per-page OCR paragraphs.

The rules target typeset books: running headers and page numbers sit in narrow top and bottom
bands, paragraphs start with a first-line indent, and a paragraph continues on the next page
when that page's first paragraph is not indented.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from pdftranslate.book.models import (
    BookParagraph,
    BookStatistics,
    OcrLine,
    OcrParagraph,
    PageOcr,
    RunningHeader,
)

BlockKind = Literal["heading", "body"]

_TERMINAL = re.compile(r"[.!?…:][”\"’')\]]*$")
_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
_LEADING_JUNK = re.compile(r"^[«»~_|\-]+(?=[A-Z])")
_HYPHENS = ("-", "‐", "­")
_DASHES = ("—", "–")
_SINGLE_QUOTES = "’'"
_DOUBLE_QUOTES = '”"'
_MARKER_GLYPHS = "*®©°¢™¹²³⁴⁵⁶⁷⁸⁹⁰"
_MARKER = re.compile(
    r"(?<=[A-Za-z)\]”\"’'])(?P<punct>[.,;:?!])(?P<run>[”\"’'!" + _MARKER_GLYPHS + r"\d]+)(?=\s|$)"
)


@dataclass(frozen=True)
class AssemblyOptions:
    header_band: float = 0.07
    footer_band: float = 0.07
    indent_ratio: float = 0.5
    heading_height_ratio: float = 1.2
    low_confidence: float = 50.0


@dataclass(frozen=True)
class PageBlock:
    kind: BlockKind
    lines: tuple[OcrLine, ...]
    indented: bool
    last_line_full: bool


@dataclass(frozen=True)
class PageLayout:
    page_number: int
    blocks: tuple[PageBlock, ...]
    headers: tuple[str, ...]


@dataclass
class _Draft:
    kind: BlockKind
    lines: list[OcrLine]
    pages: list[int]
    last_line_full: bool
    from_page: int


@dataclass
class _Counters:
    removed_headers: int = 0
    cross_page_merges: int = 0
    dehyphenated: int = 0
    note_markers: int = 0
    low_confidence: int = 0


@dataclass(frozen=True)
class AssembledBook:
    paragraphs: tuple[BookParagraph, ...]
    running_headers: tuple[RunningHeader, ...]
    statistics: BookStatistics


@dataclass(frozen=True)
class CleanedText:
    text: str
    note_markers: tuple[int, ...] = field(default_factory=tuple)


def analyze_page(page: PageOcr, options: AssemblyOptions | None = None) -> PageLayout:
    """Classify one page's OCR paragraphs as running headers, headings or body text."""
    settings = options or AssemblyOptions()
    paragraphs = tuple(item for item in page.paragraphs if _has_content(item))
    lines = [line for paragraph in paragraphs for line in paragraph.lines]
    if not lines:
        return PageLayout(page.page_number, (), ())
    prose = [line for line in lines if len(line.words) >= 4] or lines
    line_height = statistics.median(line.height for line in prose)
    body_left = statistics.median(line.left for line in prose)
    body_right = max(line.right for line in prose)
    text_width = max(1.0, body_right - body_left)

    blocks: list[PageBlock] = []
    headers: list[str] = []
    segments: list[OcrParagraph] = []
    for paragraph in paragraphs:
        if _is_running_header(paragraph, page.height, settings):
            headers.append(paragraph.text)
            continue
        segments.extend(_split_at_short_lines(paragraph, body_right, line_height))
    for paragraph in segments:
        first, last = paragraph.lines[0], paragraph.lines[-1]
        height = statistics.median(line.height for line in paragraph.lines)
        text = paragraph.text
        centered = first.left - body_left > 0.1 * text_width and (
            body_right - last.right > 0.1 * text_width
        )
        heading = (
            len(paragraph.lines) <= 3
            and not _TERMINAL.search(text)
            and (
                height >= settings.heading_height_ratio * line_height or _is_upper(text) or centered
            )
        )
        blocks.append(
            PageBlock(
                kind="heading" if heading else "body",
                lines=paragraph.lines,
                indented=first.left - body_left > settings.indent_ratio * line_height,
                last_line_full=last.right >= body_right - 1.5 * line_height,
            )
        )
    return PageLayout(page.page_number, tuple(blocks), tuple(headers))


def assemble_book(
    pages: Sequence[PageOcr], options: AssemblyOptions | None = None
) -> AssembledBook:
    """Join page blocks into logical paragraphs across page breaks and line hyphenation."""
    settings = options or AssemblyOptions()
    layouts = [analyze_page(page, settings) for page in pages]
    vocabulary = build_vocabulary(
        line.text for layout in layouts for block in layout.blocks for line in block.lines
    )
    counters = _Counters()
    headers: list[RunningHeader] = []
    drafts: list[_Draft] = []
    for layout in layouts:
        counters.removed_headers += len(layout.headers)
        headers.extend(
            RunningHeader(page_number=layout.page_number, text=text) for text in layout.headers
        )
        first_body_on_page = True
        for block in layout.blocks:
            previous = drafts[-1] if drafts else None
            if (
                block.kind == "body"
                and first_body_on_page
                and previous is not None
                and _continues(previous, block, layout.page_number)
            ):
                previous.lines.extend(block.lines)
                previous.pages.append(layout.page_number)
                previous.last_line_full = block.last_line_full
                previous.from_page = layout.page_number
                counters.cross_page_merges += 1
            else:
                drafts.append(
                    _Draft(
                        kind=block.kind,
                        lines=list(block.lines),
                        pages=[layout.page_number],
                        last_line_full=block.last_line_full,
                        from_page=layout.page_number,
                    )
                )
            if block.kind == "body":
                first_body_on_page = False

    paragraphs: list[BookParagraph] = []
    for draft in drafts:
        joined, dehyphenated = join_lines([line.text for line in draft.lines], vocabulary)
        counters.dehyphenated += dehyphenated
        joined = _LEADING_JUNK.sub("", joined)
        cleaned = clean_note_markers(joined) if draft.kind == "body" else CleanedText(joined)
        counters.note_markers += len(cleaned.note_markers)
        if not cleaned.text.strip():
            continue
        suspicious = tuple(
            word.text
            for line in draft.lines
            for word in line.words
            if word.confidence < settings.low_confidence and any(c.isalpha() for c in word.text)
        )
        counters.low_confidence += len(suspicious)
        paragraphs.append(
            BookParagraph(
                id=f"b{len(paragraphs) + 1:05d}",
                kind=draft.kind,
                text=cleaned.text,
                pages=tuple(dict.fromkeys(draft.pages)),
                note_markers=cleaned.note_markers,
                low_confidence=suspicious,
            )
        )
    return AssembledBook(
        paragraphs=tuple(paragraphs),
        running_headers=tuple(headers),
        statistics=BookStatistics(
            pages=len(pages),
            paragraphs=len(paragraphs),
            headings=sum(item.kind == "heading" for item in paragraphs),
            removed_headers=counters.removed_headers,
            cross_page_merges=counters.cross_page_merges,
            dehyphenated_words=counters.dehyphenated,
            note_markers=counters.note_markers,
            low_confidence_words=counters.low_confidence,
        ),
    )


def build_vocabulary(lines: Iterable[str]) -> Counter[str]:
    """Count unbroken word forms; line-final hyphenated fragments are excluded."""
    counts: Counter[str] = Counter()
    for line in lines:
        tokens = line.split()
        for index, token in enumerate(tokens):
            if index == len(tokens) - 1 and token.endswith(_HYPHENS):
                continue
            for match in re.finditer(r"[A-Za-z]+(?:-[A-Za-z]+)*", token):
                counts[match.group(0).casefold()] += 1
    return counts


def join_lines(lines: Sequence[str], vocabulary: Counter[str]) -> tuple[str, int]:
    """Join OCR lines, resolving line-end hyphenation with book-wide evidence."""
    text = ""
    dehyphenated = 0
    for line in (item.strip() for item in lines):
        if not line:
            continue
        if not text:
            text = line
            continue
        if text.endswith(_DASHES):
            text += line
            continue
        if text.endswith(_HYPHENS) and line[0].isalpha():
            left = _trailing_word(text[:-1])
            right = _leading_word(line)
            if left and right and _drop_hyphen(left, right, vocabulary):
                text = text[:-1] + line
                dehyphenated += 1
            else:
                text = text[:-1] + "-" + line
            continue
        text = f"{text} {line}"
    return text, dehyphenated


def clean_note_markers(text: str) -> CleanedText:
    """Remove OCR renderings of superscript note numbers and record their positions."""
    pieces: list[str] = []
    markers: list[int] = []
    cursor = 0
    length = 0
    for match in _MARKER.finditer(text):
        run = match.group("run")
        if len(run) == 1 and run in _SINGLE_QUOTES + _DOUBLE_QUOTES:
            continue
        keep = run[0] if run[0] in _DOUBLE_QUOTES else ""
        prefix = text[cursor : match.start("run")]
        pieces.append(prefix)
        pieces.append(keep)
        length += len(prefix) + len(keep)
        markers.append(length)
        cursor = match.end("run")
    pieces.append(text[cursor:])
    return CleanedText("".join(pieces), tuple(markers))


def _split_at_short_lines(
    paragraph: OcrParagraph, body_right: float, line_height: float
) -> list[OcrParagraph]:
    """Split where a sentence ends on a short line; OCR engines sometimes miss that break."""
    pieces: list[OcrParagraph] = []
    current: list[OcrLine] = []
    for index, line in enumerate(paragraph.lines):
        current.append(line)
        is_last = index == len(paragraph.lines) - 1
        short = line.right < body_right - 3 * line_height
        if not is_last and short and _TERMINAL.search(clean_note_markers(line.text).text):
            pieces.append(OcrParagraph(tuple(current)))
            current = []
    if current:
        pieces.append(OcrParagraph(tuple(current)))
    return pieces


def _continues(previous: _Draft, block: PageBlock, page_number: int) -> bool:
    if previous.kind != "body" or page_number != previous.from_page + 1:
        return False
    if block.lines[0].text[:1].islower():
        return True
    if block.indented:
        return False
    tail = previous.lines[-1].text.rstrip()
    return previous.last_line_full or not _TERMINAL.search(tail)


def _drop_hyphen(left: str, right: str, vocabulary: Counter[str]) -> bool:
    if not right[0].islower():
        return False
    joined = vocabulary[(left + right).casefold()]
    compound = vocabulary[f"{left}-{right}".casefold()]
    if joined or compound:
        return joined >= compound
    return True


def _trailing_word(text: str) -> str:
    match = re.search(r"[A-Za-z]+$", text)
    return match.group(0) if match else ""


def _leading_word(text: str) -> str:
    match = _WORD.match(text)
    return match.group(0) if match else ""


def _has_content(paragraph: OcrParagraph) -> bool:
    return any(character.isalnum() for character in paragraph.text)


def _is_running_header(paragraph: OcrParagraph, page_height: int, options: AssemblyOptions) -> bool:
    if len(paragraph.lines) != 1 or page_height <= 0:
        return False
    in_top = paragraph.bottom <= options.header_band * page_height
    in_bottom = paragraph.top >= (1 - options.footer_band) * page_height
    return in_top or in_bottom


def _is_upper(text: str) -> bool:
    letters = [character for character in text if character.isalpha()]
    return len(letters) >= 2 and all(character.isupper() for character in letters)
