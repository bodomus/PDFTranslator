"""PyMuPDF measurement, mutation, and saved-segment validation."""
# mypy: disable-error-code="no-untyped-call"

from __future__ import annotations

import math
import unicodedata
from pathlib import Path

import pymupdf

from pdftranslate.rendering.errors import OutputPdfError
from pdftranslate.rendering.reflow.models import LayoutPlan, PlacementSegment, Rect
from pdftranslate.rendering.reflow.planner import Measurement

_FONT_NAME = "PDFTranslateReflowFont"
_PDF_VALIDATION_TEXT = str.maketrans(
    {**{character: "-" for character in "‐‑‒–—−"}, "\ufd3e": "(", "\ufd3f": ")"}
)


class PyMuPdfMeasurer:
    def __init__(self, page_width: float, page_height: float, font_path: Path) -> None:
        self._document = pymupdf.open()
        self._page = self._document.new_page(width=page_width, height=page_height)
        self._font_path = font_path

    def __enter__(self) -> PyMuPdfMeasurer:
        return self

    def __exit__(self, *_: object) -> None:
        self._document.close()

    def measure(
        self,
        text: str,
        *,
        width: float,
        height: float,
        font_size: float,
        line_height: float,
    ) -> Measurement:
        if not text:
            return Measurement(True, 0.0, 0)
        shape = self._page.new_shape()
        remaining = shape.insert_textbox(
            pymupdf.Rect(0, 0, width, height),
            text,
            fontname=_FONT_NAME,
            fontfile=str(self._font_path),
            fontsize=font_size,
            lineheight=line_height,
        )
        if remaining < -1e-6:
            return Measurement(False, height, 0)
        used = max(font_size * line_height, height - float(remaining))
        return Measurement(True, used, max(1, math.ceil(used / (font_size * line_height))))


def redact_reflow_fragments(
    document: pymupdf.Document,
    plans: tuple[LayoutPlan, ...],
    page_index_by_number: dict[int, int],
    *,
    padding: float,
    sample_background: object,
) -> None:
    seen: set[tuple[int, float, float, float, float]] = set()
    touched: set[int] = set()
    for plan in plans:
        for paragraph in plan.paragraphs:
            page_index = page_index_by_number[paragraph.source_page_number]
            page = document[page_index]
            for source in paragraph.source_fragment_rects:
                key = (paragraph.source_page_number, source.x0, source.y0, source.x1, source.y1)
                if key in seen:
                    continue
                seen.add(key)
                rect = _pymupdf_rect(source)
                clip = _padded_rect(rect, page.rect, padding)
                background = sample_background(page, rect)  # type: ignore[operator]
                page.add_redact_annot(clip, fill=background, cross_out=False)
                touched.add(page_index)
    for page_index in touched:
        document[page_index].apply_redactions(images=0, graphics=0, text=0)


def insert_continuation_pages(
    document: pymupdf.Document,
    plans: tuple[LayoutPlan, ...],
) -> None:
    for plan in plans:
        for region in plan.regions:
            if not region.created_page:
                continue
            source_page = document[region.target_page_number - 2]
            document.new_page(
                pno=region.target_page_number - 1,
                width=float(source_page.rect.width),
                height=float(source_page.rect.height),
            )


def insert_reflow_segments(
    document: pymupdf.Document, plans: tuple[LayoutPlan, ...], font_path: Path
) -> None:
    for plan in plans:
        for segment in plan.segments:
            page = document[segment.target_page_number - 1]
            shape = page.new_shape()
            remaining = shape.insert_textbox(
                _pymupdf_rect(segment.target_rect),
                segment.text,
                fontname=_FONT_NAME,
                fontfile=str(font_path),
                fontsize=segment.font_size,
                lineheight=segment.line_height,
                color=segment.color,
            )
            if remaining < -0.1:
                raise OutputPdfError(
                    "reflow layout changed during insertion for occurrence "
                    f"{segment.occurrence_index}, continuation {segment.continuation_index}"
                )
            shape.commit(overlay=True)


def validate_saved_segments(path: Path, plans: tuple[LayoutPlan, ...]) -> None:
    document = pymupdf.open(path)
    try:
        page_diagnostics: dict[int, str] = {}
        for segment in (item for plan in plans for item in plan.segments):
            page = document[segment.target_page_number - 1]
            normalized_page = page_diagnostics.setdefault(
                segment.target_page_number, _normalize(str(page.get_text("text")))
            )
            clip = _segment_clip(page, segment)
            local = _normalize(str(page.get_text("text", clip=clip)))
            expected = _normalize(segment.text)
            if expected not in local:
                raise OutputPdfError(
                    "saved PDF is missing a local reflow segment for "
                    f"occurrence {segment.occurrence_index}, "
                    f"continuation {segment.continuation_index}; "
                    f"expected_chars={len(expected)} local_chars={len(local)}; "
                    f"expected={expected[:160]!r}; local={local[:160]!r}; "
                    f"expected_tail={expected[-160:]!r}; local_tail={local[-160:]!r}; "
                    f"page_diagnostic={normalized_page[:160]!r}"
                )
    finally:
        document.close()


def _segment_clip(page: pymupdf.Page, segment: PlacementSegment) -> pymupdf.Rect:
    padding = max(2.0, segment.font_size * 0.8)
    return _padded_rect(_pymupdf_rect(segment.target_rect), page.rect, padding)


def _padded_rect(rect: pymupdf.Rect, page_rect: pymupdf.Rect, padding: float) -> pymupdf.Rect:
    return pymupdf.Rect(
        max(page_rect.x0, rect.x0 - padding),
        max(page_rect.y0, rect.y0 - padding),
        min(page_rect.x1, rect.x1 + padding),
        min(page_rect.y1, rect.y1 + padding),
    )


def _pymupdf_rect(rect: Rect) -> pymupdf.Rect:
    return pymupdf.Rect(rect.x0, rect.y0, rect.x1, rect.y1)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).translate(_PDF_VALIDATION_TEXT)
    return " ".join(normalized.split())
