"""Book-level models for scanned documents rebuilt from fresh OCR."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import Field

from pdftranslate.domain.document import SourceDocument
from pdftranslate.domain.text_block import DomainModel

BOOK_SCHEMA_VERSION: Literal["book-1.0"] = "book-1.0"
ParagraphKind = Literal["heading", "body"]


@dataclass(frozen=True)
class OcrWord:
    """One recognized word in image pixel coordinates."""

    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass(frozen=True)
class OcrLine:
    words: tuple[OcrWord, ...]

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)

    @property
    def left(self) -> int:
        return min(word.left for word in self.words)

    @property
    def right(self) -> int:
        return max(word.right for word in self.words)

    @property
    def top(self) -> int:
        return min(word.top for word in self.words)

    @property
    def bottom(self) -> int:
        return max(word.bottom for word in self.words)

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass(frozen=True)
class OcrParagraph:
    """A paragraph as segmented by the OCR engine on one page."""

    lines: tuple[OcrLine, ...]

    @property
    def text(self) -> str:
        return " ".join(line.text for line in self.lines)

    @property
    def top(self) -> int:
        return min(line.top for line in self.lines)

    @property
    def bottom(self) -> int:
        return max(line.bottom for line in self.lines)


@dataclass(frozen=True)
class PageOcr:
    """Fresh OCR result for one source page."""

    page_number: int
    width: int
    height: int
    paragraphs: tuple[OcrParagraph, ...] = field(default_factory=tuple)


class RunningHeader(DomainModel):
    """Header or footer text removed from the reading flow, kept for structure hints."""

    page_number: int = Field(ge=1)
    text: str


class BookParagraph(DomainModel):
    """One logical paragraph of the book in reading order."""

    id: str = Field(pattern=r"^b\d{5,}$")
    kind: ParagraphKind
    text: str = Field(min_length=1)
    pages: tuple[int, ...] = Field(min_length=1)
    note_markers: tuple[int, ...] = ()
    low_confidence: tuple[str, ...] = ()


class BookOcrInfo(DomainModel):
    engine: Literal["tesseract"] = "tesseract"
    version: str | None = None
    language: str = "eng"
    page_segmentation_mode: int = 3


class BookStatistics(DomainModel):
    pages: int = Field(ge=0)
    paragraphs: int = Field(ge=0)
    headings: int = Field(ge=0)
    removed_headers: int = Field(ge=0)
    cross_page_merges: int = Field(ge=0)
    dehyphenated_words: int = Field(ge=0)
    note_markers: int = Field(ge=0)
    low_confidence_words: int = Field(ge=0)


class BookDocument(DomainModel):
    """Structured text of a scanned book, independent of its original page layout."""

    schema_version: Literal["book-1.0"] = BOOK_SCHEMA_VERSION
    source: SourceDocument
    page_count: int = Field(ge=1)
    selected_pages: tuple[int, ...]
    ocr: BookOcrInfo
    statistics: BookStatistics
    running_headers: tuple[RunningHeader, ...] = ()
    paragraphs: tuple[BookParagraph, ...] = ()
