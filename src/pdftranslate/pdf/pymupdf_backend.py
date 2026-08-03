"""PyMuPDF adapter for safe, deterministic structured extraction."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal, cast

import pymupdf

from pdftranslate.config import Settings
from pdftranslate.domain.document import (
    DocumentMetadata,
    ExtractedDocument,
    InspectionReport,
    SourceDocument,
)
from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox, TextBlock, TextLine, TextSpan
from pdftranslate.pdf.errors import (
    PdfCorruptError,
    PdfEmptyError,
    PdfEncryptedError,
    PdfNotFoundError,
)
from pdftranslate.pdf.page_ranges import parse_page_range
from pdftranslate.reconstruction import (
    ParagraphReconstructionOptions,
    ReconstructionResult,
    reconstruct_paragraphs,
)


def _bbox(value: object) -> BoundingBox:
    coordinates = tuple(cast(Iterable[float], value))
    if len(coordinates) != 4:
        raise PdfCorruptError("PDF content contains an invalid bounding box")
    return BoundingBox(
        x0=float(coordinates[0]),
        y0=float(coordinates[1]),
        x1=float(coordinates[2]),
        y1=float(coordinates[3]),
    )


def _clean_metadata_value(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _metadata(document: pymupdf.Document) -> DocumentMetadata:
    values = cast(Mapping[str, object], document.metadata or {})
    return DocumentMetadata(
        format=_clean_metadata_value(values.get("format")),
        title=_clean_metadata_value(values.get("title")),
        author=_clean_metadata_value(values.get("author")),
        subject=_clean_metadata_value(values.get("subject")),
        keywords=_clean_metadata_value(values.get("keywords")),
        creator=_clean_metadata_value(values.get("creator")),
        producer=_clean_metadata_value(values.get("producer")),
        creation_date=_clean_metadata_value(values.get("creationDate")),
        modification_date=_clean_metadata_value(values.get("modDate")),
        trapped=_clean_metadata_value(values.get("trapped")),
        encryption=_clean_metadata_value(values.get("encryption")),
    )


def source_identity(path: Path) -> SourceDocument:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return SourceDocument(
        path=str(path.resolve()),
        file_size=path.stat().st_size,
        sha256=digest.hexdigest(),
    )


def _normalize_text(lines: Iterable[str]) -> str:
    return "\n".join(line.strip() for line in lines if line.strip()).strip()


def _span_from_dict(span: Mapping[str, Any]) -> TextSpan | None:
    text = str(span.get("text", ""))
    if not text:
        return None
    flags = int(span.get("flags", 0))
    return TextSpan(
        text=text,
        bbox=_bbox(span["bbox"]),
        font_name=_clean_metadata_value(span.get("font")),
        font_size=float(span["size"]) if span.get("size") is not None else None,
        text_color=int(span["color"]) if span.get("color") is not None else None,
        bold=bool(flags & pymupdf.TEXT_FONT_BOLD),
        italic=bool(flags & pymupdf.TEXT_FONT_ITALIC),
    )


def _text_block_from_dict(
    block: Mapping[str, Any],
    page_number: int,
    original_order: int,
    normalized_order: int,
) -> TextBlock | None:
    block_id = f"p{page_number:04d}-b{normalized_order + 1:04d}"
    spans: list[TextSpan] = []
    lines: list[TextLine] = []
    for line_order, line in enumerate(cast(Iterable[Mapping[str, Any]], block.get("lines", ()))):
        line_spans = [
            span
            for raw_span in cast(Iterable[Mapping[str, Any]], line.get("spans", ()))
            if (span := _span_from_dict(raw_span)) is not None
        ]
        spans.extend(line_spans)
        line_text = "".join(span.text for span in line_spans).strip()
        if not line_text:
            continue
        line_bbox = (
            _bbox(line["bbox"])
            if line.get("bbox") is not None
            else BoundingBox(
                x0=min(span.bbox.x0 for span in line_spans),
                y0=min(span.bbox.y0 for span in line_spans),
                x1=max(span.bbox.x1 for span in line_spans),
                y1=max(span.bbox.y1 for span in line_spans),
            )
        )
        lines.append(
            TextLine(
                id=f"{block_id}-l{len(lines) + 1:04d}",
                text=line_text,
                bbox=line_bbox,
                original_order=line_order,
                spans=tuple(line_spans),
            )
        )

    text = _normalize_text(line.text for line in lines)
    if not text:
        return None
    return TextBlock(
        id=block_id,
        text=text,
        bbox=_bbox(block["bbox"]),
        original_order=original_order,
        normalized_order=normalized_order,
        spans=tuple(spans),
        lines=tuple(lines),
    )


def _merge_adjacent_text_blocks(blocks: list[TextBlock], page_number: int) -> list[TextBlock]:
    """Coalesce line fragments that are clearly one paragraph."""
    merged: list[TextBlock] = []
    for block in blocks:
        if merged and _is_paragraph_continuation(merged[-1], block):
            previous = merged[-1]
            merged[-1] = previous.model_copy(
                update={
                    "text": _join_paragraph_text(previous.text, block.text),
                    "bbox": BoundingBox(
                        x0=min(previous.bbox.x0, block.bbox.x0),
                        y0=min(previous.bbox.y0, block.bbox.y0),
                        x1=max(previous.bbox.x1, block.bbox.x1),
                        y1=max(previous.bbox.y1, block.bbox.y1),
                    ),
                    "spans": previous.spans + block.spans,
                }
            )
        else:
            merged.append(block)
    return [
        block.model_copy(
            update={
                "id": f"p{page_number:04d}-b{index + 1:04d}",
                "normalized_order": index,
            }
        )
        for index, block in enumerate(merged)
    ]


def _is_paragraph_continuation(previous: TextBlock, current: TextBlock) -> bool:
    previous_text = previous.text.rstrip()
    current_text = current.text.lstrip()
    if not previous_text or not current_text or not current_text[0].islower():
        return False
    previous_width = max(previous.bbox.x1 - previous.bbox.x0, 1.0)
    current_width = max(current.bbox.x1 - current.bbox.x0, 1.0)
    width_ratio = min(previous_width, current_width) / max(previous_width, current_width)
    left_aligned = abs(previous.bbox.x0 - current.bbox.x0) <= 8.0
    vertical_gap = current.bbox.y0 - previous.bbox.y1
    line_height = min(
        max(previous.bbox.y1 - previous.bbox.y0, 1.0),
        max(current.bbox.y1 - current.bbox.y0, 1.0),
    )
    close_vertically = -line_height * 0.25 <= vertical_gap <= line_height * 0.5
    source_continues = previous_text.endswith("-") or previous_text[-1] not in ".?!:;"
    return left_aligned and width_ratio >= 0.8 and close_vertically and source_continues


def _join_paragraph_text(previous: str, current: str) -> str:
    left = previous.rstrip()
    right = current.lstrip()
    if left.endswith("-") and right and right[0].islower():
        return left[:-1] + right
    return f"{left} {right}"


def _probable_language(texts: Iterable[str]) -> str | None:
    latin = 0
    cyrillic = 0
    for character in "".join(texts):
        lowered = character.lower()
        if "a" <= lowered <= "z":
            latin += 1
        elif "\u0430" <= lowered <= "\u044f" or lowered == "\u0451":
            cyrillic += 1

    total = latin + cyrillic
    if total < 20:
        return None
    if latin / total >= 0.7:
        return "en"
    if cyrillic / total >= 0.7:
        return "ru"
    return "mixed"


class PyMuPdfBackend:
    """Own PyMuPDF lifecycle, validation, and adapter-specific extraction."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._reconstruction_options = ParagraphReconstructionOptions(
            mode=self._settings.paragraph_reconstruction_mode,
            left_alignment_tolerance=self._settings.paragraph_left_alignment_tolerance,
            indentation_tolerance=self._settings.paragraph_indentation_tolerance,
            max_vertical_gap_ratio=self._settings.paragraph_max_vertical_gap_ratio,
            min_width_ratio=self._settings.paragraph_min_width_ratio,
            column_gutter_ratio=self._settings.paragraph_column_gutter_ratio,
            heading_font_ratio=self._settings.paragraph_heading_font_ratio,
            footnote_font_ratio=self._settings.paragraph_footnote_font_ratio,
            margin_region_ratio=self._settings.paragraph_margin_region_ratio,
            cross_page_edge_ratio=self._settings.paragraph_cross_page_edge_ratio,
            repeated_margin_min_pages=self._settings.paragraph_repeated_margin_min_pages,
        )

    @contextmanager
    def open_pdf(self, input_path: Path) -> Iterator[pymupdf.Document]:
        path = input_path.expanduser()
        if not path.exists() or not path.is_file():
            raise PdfNotFoundError(f"PDF input file does not exist: {path}")
        if path.suffix.lower() != ".pdf":
            raise PdfCorruptError(f"input must have a .pdf extension: {path}")
        try:
            document = pymupdf.open(path)  # type: ignore[no-untyped-call]
        except (pymupdf.EmptyFileError, pymupdf.FileDataError, RuntimeError) as error:
            raise PdfCorruptError(f"cannot open PDF file {path}: {error}") from error

        try:
            if not document.is_pdf:
                raise PdfCorruptError(f"input is not a PDF document: {path}")
            yield document
        finally:
            document.close()  # type: ignore[no-untyped-call]

    def inspect(self, input_path: Path) -> InspectionReport:
        path = input_path.expanduser()
        with self.open_pdf(path) as document:
            source = source_identity(path)
            encrypted = bool(document.is_encrypted or document.needs_pass)
            password_required = bool(document.needs_pass)
            if password_required:
                return InspectionReport(
                    source=source,
                    page_count=document.page_count,
                    encrypted=encrypted,
                    password_required=True,
                    warnings=("PDF requires a password; page content was not inspected.",),
                )
            if document.page_count == 0:
                raise PdfEmptyError(f"PDF contains no pages: {path}")
            extracted = self._extract_validated(
                document, source, None, self._reconstruction_options
            )
        return _inspection_from_document(extracted)

    def extract(
        self,
        input_path: Path,
        page_range: str | None = None,
        reconstruction_options: ParagraphReconstructionOptions | None = None,
    ) -> ExtractedDocument:
        path = input_path.expanduser()
        with self.open_pdf(path) as document:
            source = source_identity(path)
            if document.needs_pass:
                raise PdfEncryptedError(f"PDF requires a password and cannot be extracted: {path}")
            if document.page_count == 0:
                raise PdfEmptyError(f"PDF contains no pages: {path}")
            return self._extract_validated(
                document,
                source,
                page_range,
                reconstruction_options or self._reconstruction_options,
            )

    def _extract_validated(
        self,
        document: pymupdf.Document,
        source: SourceDocument,
        page_range: str | None,
        reconstruction_options: ParagraphReconstructionOptions,
    ) -> ExtractedDocument:
        try:
            return self._extract_open_document(document, source, page_range, reconstruction_options)
        except (PdfCorruptError, PdfEmptyError, PdfEncryptedError):
            raise
        except (KeyError, IndexError, TypeError, ValueError, RuntimeError) as error:
            raise PdfCorruptError(
                f"cannot extract structured content from PDF {source.path}: {error}"
            ) from error

    def _extract_open_document(
        self,
        document: pymupdf.Document,
        source: SourceDocument,
        page_range: str | None,
        reconstruction_options: ParagraphReconstructionOptions,
    ) -> ExtractedDocument:
        selected_pages = parse_page_range(page_range, document.page_count)
        pages = tuple(self._extract_page(document[number - 1], number) for number in selected_pages)
        reconstructed: ReconstructionResult = reconstruct_paragraphs(pages, reconstruction_options)
        language = _probable_language(paragraph.text for paragraph in reconstructed.paragraphs)
        warnings = tuple(dict.fromkeys(warning for page in pages for warning in page.warnings))
        return ExtractedDocument(
            schema_version="1.2",
            source=source,
            page_count=document.page_count,
            selected_pages=selected_pages,
            metadata=_metadata(document),
            encrypted=bool(document.is_encrypted),
            password_required=False,
            probable_source_language=language,
            pages=pages,
            paragraphs=reconstructed.paragraphs,
            reconstruction=reconstructed.evidence,
            warnings=warnings,
        )

    def _extract_page(self, page: pymupdf.Page, page_number: int) -> ExtractedPage:
        page_dict = cast(
            Mapping[str, Any],
            page.get_text("dict", sort=False),  # type: ignore[no-untyped-call]
        )
        raw_blocks = cast(Iterable[Mapping[str, Any]], page_dict.get("blocks", ()))
        text_blocks: list[TextBlock] = []
        image_boxes: list[BoundingBox] = []
        for original_order, block in enumerate(raw_blocks):
            block_type = int(block.get("type", -1))
            if block_type == 0:
                text_block = _text_block_from_dict(
                    block,
                    page_number,
                    original_order,
                    len(text_blocks),
                )
                if text_block is not None:
                    text_blocks.append(text_block)
            elif block_type == 1:
                image_boxes.append(_bbox(block["bbox"]))

        page_area = max(float(page.rect.width * page.rect.height), 1.0)
        image_area_ratio = min(sum(box.area for box in image_boxes) / page_area, 1.0)
        classification, warnings = self._classify_page(
            text_blocks,
            len(image_boxes),
            image_area_ratio,
        )
        return ExtractedPage(
            page_number=page_number,
            source_index=page.number,
            width=float(page.rect.width),
            height=float(page.rect.height),
            rotation=cast(Literal[0, 90, 180, 270], int(page.rotation)),
            classification=classification,
            text_blocks=tuple(text_blocks),
            image_count=len(image_boxes),
            image_area_ratio=image_area_ratio,
            warnings=warnings,
        )

    def _classify_page(
        self,
        blocks: list[TextBlock],
        image_count: int,
        image_area_ratio: float,
    ) -> tuple[PageClassification, tuple[str, ...]]:
        text_characters = sum(len(block.text.strip()) for block in blocks)
        meaningful_text = (
            text_characters >= self._settings.classification_min_text_characters
            or len(blocks) > self._settings.classification_max_incidental_text_blocks
        )
        if not blocks and image_count == 0:
            return PageClassification.EMPTY, ()
        if image_count > 0 and not meaningful_text:
            warnings: tuple[str, ...] = ()
            if image_area_ratio < self._settings.classification_scanned_image_area_ratio:
                warnings = (
                    "Image-only or incidental-text page classified as scanned "
                    "despite low image coverage.",
                )
            return PageClassification.SCANNED, warnings
        if (
            meaningful_text
            and image_count > 0
            and image_area_ratio >= self._settings.classification_mixed_image_area_ratio
        ):
            return PageClassification.MIXED, ()
        return PageClassification.TEXT, ()


def _inspection_from_document(document: ExtractedDocument) -> InspectionReport:
    counts = {classification.value: 0 for classification in PageClassification}
    for page in document.pages:
        counts[page.classification.value] += 1
    return InspectionReport(
        source=document.source,
        page_count=document.page_count,
        text_pages=counts[PageClassification.TEXT.value],
        scanned_pages=counts[PageClassification.SCANNED.value],
        mixed_pages=counts[PageClassification.MIXED.value],
        empty_pages=counts[PageClassification.EMPTY.value],
        text_block_count=sum(len(page.text_blocks) for page in document.pages),
        image_count=sum(page.image_count for page in document.pages),
        encrypted=document.encrypted,
        password_required=document.password_required,
        probable_source_language=document.probable_source_language,
        warnings=document.warnings,
    )
