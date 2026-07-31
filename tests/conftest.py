"""Generated PDF fixtures used by extraction and CLI tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pymupdf
import pytest

PdfFactory = Callable[..., Path]


@pytest.fixture
def pdf_factory() -> PdfFactory:
    def create(
        path: Path,
        *,
        page_specs: tuple[str, ...] = ("text",),
        encrypted: bool = False,
    ) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        document = pymupdf.open()
        for page_number, spec in enumerate(page_specs, start=1):
            page = document.new_page(width=400, height=400)
            if spec in {"text", "mixed", "ordered", "rotated"}:
                if spec == "ordered":
                    page.insert_text((40, 220), "Second inserted block with enough English text.")
                    page.insert_text((40, 80), "First visual block with enough English text.")
                else:
                    page.insert_text(
                        (40, 60),
                        f"English source text on page {page_number} for PDFTranslate testing.",
                    )
            if spec == "rotated":
                page.set_rotation(90)
            if spec in {"image", "mixed"}:
                pixmap = pymupdf.Pixmap(
                    pymupdf.csRGB,
                    pymupdf.IRect(0, 0, 100, 100),
                    False,
                )
                pixmap.clear_with(0x336699)
                image_rect = pymupdf.Rect(20, 90, 380, 380)
                page.insert_image(image_rect, pixmap=pixmap)

        document.set_metadata({"title": "Generated PDF fixture", "author": "PDFTranslate tests"})
        save_options = {}
        if encrypted:
            save_options = {
                "encryption": pymupdf.PDF_ENCRYPT_AES_256,
                "owner_pw": "owner-password",
                "user_pw": "user-password",
            }
        document.save(path, **save_options)
        document.close()
        return path

    return create


@pytest.fixture
def cyrillic_font_path() -> Path:
    """Return a system font without copying proprietary files into the repository."""
    import os

    candidates = (
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    pytest.skip("no system Cyrillic font is available")
