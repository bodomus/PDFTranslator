"""PDFTR-38 blocker evidence, NOT tests asserting production list support.

Exercise the installed HTML engine and current paragraph representation with saved,
selectable PDFs. Native CSS positive controls distinguish unsupported custom marker
features from a font/archive or insertion failure.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from pdftranslate.pdf import PdfExtractor
from pdftranslate.reconstruction import ParagraphKind, ParagraphReconstructionOptions
from pdftranslate.rendering.reflow.models import ReflowStyle
from pdftranslate.rendering.reflow.pymupdf_layout import build_rich_text

_CONTENT = "Semantic content here that wraps on a second line in a narrow box."


def _saved_words(
    path: Path, html: str, css: str, font: Path
) -> list[tuple[float, float, float, float, str, int, int, int]]:
    with pymupdf.open() as document:
        page = document.new_page(width=400, height=400)
        remaining, scale = page.insert_htmlbox(
            pymupdf.Rect(50, 50, 250, 250),
            html,
            css=css,
            archive=pymupdf.Archive(str(font.parent)),
            scale_low=1,
        )
        assert remaining >= 0
        assert scale == 1
        document.save(path)
    with pymupdf.open(path) as saved:
        return saved[0].get_text("words")


def _native_css(font: Path) -> str:
    return (
        f'@font-face {{font-family: Probe; src: url("{font.name}");}} '
        "* {margin:0; padding:0;} body {font-family:Probe; font-size:12pt;} "
    )


@pytest.mark.parametrize(
    ("markup", "extra_css", "marker"),
    [
        ("<ul><li>{}</li></ul>", "li {list-style-type:disc;}", "•"),
        ('<ol start="2"><li>{}</li></ol>', "li {list-style-type:decimal;}", "2."),
        ('<ol start="3"><li>{}</li></ol>', "li {list-style-type:lower-alpha;}", "c."),
    ],
)
def test_native_marker_positive_controls_have_hanging_geometry(
    tmp_path: Path, cyrillic_font_path: Path, markup: str, extra_css: str, marker: str
) -> None:
    words = _saved_words(
        tmp_path / "native.pdf",
        markup.format(_CONTENT),
        _native_css(cyrillic_font_path) + extra_css,
        cyrillic_font_path,
    )
    texts = [word[4] for word in words]
    assert texts.count(marker) == 1
    assert texts[1:] == _CONTENT.split()
    content = next(word for word in words if word[4] == "Semantic")
    continuation = next(word for word in words if word[4] == "wraps")
    assert words[0][0] < content[0]
    assert continuation[1] > content[1]
    assert continuation[0] == pytest.approx(content[0], abs=0.1)


@pytest.mark.parametrize(
    "extra_css",
    ['li {list-style-type: "2) ";}', 'li::marker {content:"2)";}'],
)
def test_native_custom_marker_features_do_not_emit_source_identity(
    tmp_path: Path, cyrillic_font_path: Path, extra_css: str
) -> None:
    words = _saved_words(
        tmp_path / "custom.pdf",
        f"<ul><li>{_CONTENT}</li></ul>",
        _native_css(cyrillic_font_path) + extra_css,
        cyrillic_font_path,
    )
    texts = [word[4] for word in words]
    assert "2)" not in texts
    assert texts[1:] == _CONTENT.split()


def test_inline_padding_does_not_supply_independent_content_edge(
    tmp_path: Path, cyrillic_font_path: Path
) -> None:
    html = f"<p><span>2)</span>{_CONTENT}</p>"
    plain = _saved_words(
        tmp_path / "plain.pdf", html, _native_css(cyrillic_font_path), cyrillic_font_path
    )
    padded = _saved_words(
        tmp_path / "padded.pdf",
        html,
        _native_css(cyrillic_font_path) + "span {padding-right:40pt;}",
        cyrillic_font_path,
    )
    assert padded == plain
    assert padded[0][4] == "2)Semantic"


@pytest.mark.parametrize("requested_gap", [20.0, 60.0])
def test_shared_paragraph_cannot_encode_marker_and_content_edges_independently(
    tmp_path: Path, cyrillic_font_path: Path, requested_gap: float
) -> None:
    # This is the unchanged production representation, not a proposed list renderer.
    rich = build_rich_text(
        "2) " + _CONTENT,
        cyrillic_font_path,
        ReflowStyle(font_size=12, line_height=1.2, space_before=0, space_after=0),
        (0, 0, 0),
        first_line_indent=0,
    )
    words = _saved_words(tmp_path / "paragraph.pdf", rich.html, rich.css, cyrillic_font_path)
    marker = next(word for word in words if word[4] == "2)")
    content = next(word for word in words if word[4] == "Semantic")
    continuation = next(word for word in words if word[1] > marker[1] + 1)
    assert content[0] - marker[0] != pytest.approx(requested_gap, abs=0.5)
    assert continuation[1] > marker[1]
    assert continuation[0] == pytest.approx(marker[0], abs=0.1)
    assert continuation[0] != pytest.approx(content[0], abs=0.5)


@pytest.mark.parametrize("indent", [4.0, 40.0])
def test_native_list_padding_moves_marker_and_content_together(
    tmp_path: Path, cyrillic_font_path: Path, indent: float
) -> None:
    html = f'<ol start="2"><li>{_CONTENT}</li></ol>'
    base = _saved_words(
        tmp_path / "base.pdf", html, _native_css(cyrillic_font_path), cyrillic_font_path
    )
    shifted = _saved_words(
        tmp_path / "shifted.pdf",
        html,
        _native_css(cyrillic_font_path) + f"li {{padding-left:{indent}pt;}}",
        cyrillic_font_path,
    )
    for token in ("2.", "Semantic"):
        original = next(word for word in base if word[4] == token)
        moved = next(word for word in shifted if word[4] == token)
        assert moved[0] - original[0] == pytest.approx(indent, abs=0.1)
    # Padding changes overall indentation, not marker/content separation.
    assert shifted[1][0] - shifted[0][0] == pytest.approx(base[1][0] - base[0][0], abs=0.1)


@pytest.mark.parametrize("text", ["A. Smith", "1.5 mm", "3.14"])
def test_semantic_lookalikes_remain_whole_in_current_reconstruction(
    tmp_path: Path, text: str
) -> None:
    path = tmp_path / "semantic.pdf"
    with pymupdf.open() as document:
        page = document.new_page(width=400, height=400)
        page.insert_text((50, 100), text)
        document.save(path)
    extracted = PdfExtractor().extract(
        path, reconstruction_options=ParagraphReconstructionOptions(mode="conservative")
    )
    assert len(extracted.paragraphs) == 1
    paragraph = extracted.paragraphs[0]
    assert paragraph.text == text
    # A regex candidate label is deliberately not claimed as structural evidence.
    if text == "A. Smith":
        assert paragraph.kind is ParagraphKind.LIST_ITEM
    else:
        assert paragraph.kind is not ParagraphKind.LIST_ITEM
