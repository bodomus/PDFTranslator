"""PyMuPDF measurement, mutation, and saved-segment validation."""
# mypy: disable-error-code="no-untyped-call"

from __future__ import annotations

import html
import math
import unicodedata
from pathlib import Path

import pymupdf

from pdftranslate.rendering.errors import OutputPdfError
from pdftranslate.rendering.reflow.models import (
    LayoutPlan,
    PlacementSegment,
    Rect,
    ReflowStyle,
)
from pdftranslate.rendering.reflow.planner import Measurement

_FONT_NAME = "PDFTranslateReflowFont"
_PDF_VALIDATION_TEXT = str.maketrans(
    {**{character: "-" for character in "‐‑‒–—−"}, "\ufd3e": "(", "\ufd3f": ")"}
)


class PyMuPdfMeasurer:
    def __init__(self, page_width: float, page_height: float, font_path: Path) -> None:
        self._document = pymupdf.open()
        self._page_width = page_width
        self._page_height = page_height
        self._font_path = font_path
        self._archive = pymupdf.Archive(str(font_path.parent))

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
        style: ReflowStyle,
        first_segment: bool,
    ) -> Measurement:
        if not text:
            return Measurement(True, 0.0, 0)
        page = self._document.new_page(width=self._page_width, height=self._page_height)
        try:
            remaining, scale = page.insert_htmlbox(
                pymupdf.Rect(0, 0, width, height),
                _segment_html(text),
                css=_segment_css(
                    self._font_path,
                    style,
                    (0.0, 0.0, 0.0),
                    first_line_indent=style.first_line_indent if first_segment else 0.0,
                ),
                archive=self._archive,
                scale_low=1,
                overlay=False,
            )
        finally:
            self._document.delete_page(page.number)
        if remaining < -1e-6 or abs(scale - 1.0) > 1e-6:
            return Measurement(False, height, 0)
        used = max(style.font_size * style.line_height, height - float(remaining))
        return Measurement(
            True,
            used,
            max(1, math.ceil(used / (style.font_size * style.line_height))),
        )


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
    archive = pymupdf.Archive(str(font_path.parent))
    for plan in plans:
        for segment in plan.segments:
            page = document[segment.target_page_number - 1]
            style = ReflowStyle(
                font_size=segment.font_size,
                line_height=segment.line_height,
                space_before=segment.space_before,
                space_after=segment.space_after,
                first_line_indent=segment.first_line_indent,
                left_indent=segment.left_indent,
                right_indent=segment.right_indent,
                alignment=segment.alignment,
                bold_requested=segment.bold_requested,
                bold_applied=segment.bold_applied,
                italic_requested=segment.italic_requested,
                italic_applied=segment.italic_applied,
                mixed_style=segment.mixed_style,
                fallback_count=segment.fallback_count,
            )
            remaining, scale = page.insert_htmlbox(
                _pymupdf_rect(segment.target_rect),
                _segment_html(segment.text),
                css=_segment_css(
                    font_path,
                    style,
                    segment.color,
                    first_line_indent=segment.first_line_indent,
                ),
                archive=archive,
                scale_low=1,
            )
            if remaining < -0.1 or abs(scale - 1.0) > 1e-6:
                raise OutputPdfError(
                    "reflow layout changed during insertion for occurrence "
                    f"{segment.occurrence_index}, continuation {segment.continuation_index}"
                )


def _segment_html(text: str) -> str:
    escaped = html.escape(text).replace("\n", "<br>")
    return f"<p>{escaped.encode('ascii', 'xmlcharrefreplace').decode('ascii')}</p>"


def _segment_css(
    font_path: Path,
    style: ReflowStyle,
    color: tuple[float, float, float],
    *,
    first_line_indent: float,
) -> str:
    red, green, blue = (round(component * 255) for component in color)
    return (
        f'@font-face {{ font-family: "{_FONT_NAME}"; src: url("{font_path.name}"); }} '
        "* { margin: 0; padding: 0; } "
        f'p {{ font-family: "{_FONT_NAME}"; font-size: {style.font_size:.6f}pt; '
        f"line-height: {style.line_height:.6f}; text-align: {style.alignment.value}; "
        f"text-indent: {first_line_indent:.6f}pt; color: rgb({red}, {green}, {blue}); }}"
    )


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
