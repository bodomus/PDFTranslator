"""Scanned-book OCR pipeline: page images, cached Tesseract runs and book assembly."""

from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

import pymupdf

from pdftranslate.book.assembly import AssemblyOptions, assemble_book
from pdftranslate.book.models import BookDocument, BookOcrInfo, PageOcr
from pdftranslate.book.tesseract import TesseractRunner, parse_tsv
from pdftranslate.pdf.page_ranges import parse_page_range
from pdftranslate.pdf.pymupdf_backend import source_identity

ProgressCallback = Callable[[int, int], None]

_FULL_PAGE_IMAGE = 0.9
_RENDER_DPI = 400


@dataclass(frozen=True)
class BookOcrOptions:
    pages: str | None = None
    jobs: int = max(1, (os.cpu_count() or 2) - 1)
    work_dir: Path | None = None
    assembly: AssemblyOptions = AssemblyOptions()


def ocr_book(
    source: Path,
    runner: TesseractRunner,
    options: BookOcrOptions | None = None,
    *,
    progress: ProgressCallback | None = None,
) -> BookDocument:
    """OCR selected pages afresh and rebuild the book's paragraph flow.

    Per-page TSV results are cached in ``work_dir`` so an interrupted run resumes.
    """
    settings = options or BookOcrOptions()
    path = source.expanduser().resolve()
    identity = source_identity(path)
    work_dir = (settings.work_dir or path.with_name(f"{path.stem}.ocr")).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    with pymupdf.open(path) as document:  # type: ignore[no-untyped-call]
        page_count = document.page_count
        selected = parse_page_range(settings.pages, page_count)
        pending: list[tuple[int, Path, int]] = []
        for number in selected:
            if _tsv_path(work_dir, number).is_file():
                continue
            image, dpi = _page_image(document, number, work_dir)
            pending.append((number, image, dpi))

    done = len(selected) - len(pending)
    if progress is not None:
        progress(done, len(selected))

    def recognize(item: tuple[int, Path, int]) -> int:
        number, image, dpi = item
        try:
            tsv = runner.recognize(image, dpi)
            _write_atomic(_tsv_path(work_dir, number), tsv)
        finally:
            image.unlink(missing_ok=True)
        return number

    with ThreadPoolExecutor(max_workers=max(1, settings.jobs)) as pool:
        for _ in pool.map(recognize, pending):
            done += 1
            if progress is not None:
                progress(done, len(selected))

    pages: list[PageOcr] = [
        parse_tsv(_tsv_path(work_dir, number).read_text(encoding="utf-8"), number)
        for number in selected
    ]
    assembled = assemble_book(pages, settings.assembly)
    return BookDocument(
        source=identity,
        page_count=page_count,
        selected_pages=selected,
        ocr=BookOcrInfo(
            version=runner.version(),
            language=runner.language,
            page_segmentation_mode=runner.page_segmentation_mode,
        ),
        statistics=assembled.statistics,
        running_headers=assembled.running_headers,
        paragraphs=assembled.paragraphs,
    )


def book_to_text(book: BookDocument) -> str:
    """Plain-text rendering for human review of OCR and paragraph flow."""
    chunks = [
        f"## {item.text}" if item.kind == "heading" else item.text for item in book.paragraphs
    ]
    return "\n\n".join(chunks) + "\n"


def _page_image(document: pymupdf.Document, number: int, work_dir: Path) -> tuple[Path, int]:
    """Use the embedded scan when it fills the page, otherwise render the page."""
    page = document[number - 1]
    target = work_dir / f"page-{number:04d}.png"
    page_area = page.rect.width * page.rect.height
    images = page.get_images(full=True)  # type: ignore[no-untyped-call]
    if len(images) == 1 and page_area > 0:
        xref = images[0][0]
        rects = page.get_image_rects(xref)
        covered = sum(rect.width * rect.height for rect in rects)
        if rects and covered / page_area >= _FULL_PAGE_IMAGE:
            pixmap = pymupdf.Pixmap(document, xref)  # type: ignore[no-untyped-call]
            if pixmap.alpha or pixmap.n > 4:
                pixmap = pymupdf.Pixmap(pymupdf.csRGB, pixmap)  # type: ignore[no-untyped-call]
            dpi = round(pixmap.width / (rects[0].width / 72))
            pixmap.save(target)  # type: ignore[no-untyped-call]
            return target, max(70, dpi)
    pixmap = page.get_pixmap(dpi=_RENDER_DPI)
    pixmap.save(target)  # type: ignore[no-untyped-call]
    return target, _RENDER_DPI


def _tsv_path(work_dir: Path, number: int) -> Path:
    return work_dir / f"page-{number:04d}.tsv"


def _write_atomic(path: Path, text: str) -> None:
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)
