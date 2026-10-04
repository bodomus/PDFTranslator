"""Source evidence, provider boundaries and real shared-path saved-PDF probes."""
# mypy: disable-error-code="no-untyped-call"

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pymupdf
import pytest

from pdftranslate.domain.document import DocumentMetadata, ExtractedDocument, SourceDocument
from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox, TextBlock, TextSpan
from pdftranslate.pdf import PdfExtractor
from pdftranslate.reconstruction import (
    LogicalParagraph,
    ParagraphFragment,
    ParagraphKind,
    ParagraphReconstruction,
    ParagraphReconstructionOptions,
    ReconstructionMetrics,
    SourceBlockMapping,
)
from pdftranslate.reconstruction.list_items import is_list_marker, source_list_item
from pdftranslate.rendering import PdfRenderer, RenderOptions
from pdftranslate.rendering.errors import OutputPdfError
from pdftranslate.rendering.reflow import FlowRegion, Rect, ReflowAlignment, discover_reflow_page
from pdftranslate.rendering.reflow.planner import plan_flow
from pdftranslate.rendering.reflow.pymupdf_layout import (
    PyMuPdfMeasurer,
    insert_continuation_pages,
    insert_reflow_segments,
    validate_saved_segments,
)
from pdftranslate.serialization import document_from_json, document_to_json
from pdftranslate.translation import TranslationCache, TranslationOptions, translate_document
from pdftranslate.typography import TypographyRole, extract_typography_evidence, reconstruct_styles


def _box(x0: float = 40, y0: float = 50, x1: float = 260, y1: float = 65) -> BoundingBox:
    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)


def _paragraph(
    marker: str = "1.",
    content: str = "Configure project",
    *,
    index: int = 0,
    content_x: float = 70,
    kind: ParagraphKind = ParagraphKind.LIST_ITEM,
) -> LogicalParagraph:
    y = 50 + index * 35
    box = _box(y0=y, y1=y + 15)
    spans = (
        TextSpan(text=f"{marker} ", bbox=_box(40, y, 49, y + 15), font_size=10),
        TextSpan(text=content, bbox=_box(content_x, y, 260, y + 15), font_size=10),
    )
    fragment = ParagraphFragment(
        id=f"line-{index}",
        text=f"{marker} {content}",
        bbox=box,
        mapping=SourceBlockMapping(
            source_block_id=f"block-{index}",
            page_number=1,
            bbox=box,
            original_order=index,
            normalized_order=index,
        ),
        spans=spans,
        column=0,
    )
    return LogicalParagraph(
        id=f"block-{index}",
        text=fragment.text,
        kind=kind,
        anchor_page_number=1,
        bbox=box,
        fragments=(fragment,),
        spans=spans,
    )


def _document(*paragraphs: LogicalParagraph) -> ExtractedDocument:
    return ExtractedDocument(
        schema_version="1.2",
        source=SourceDocument(path="source.pdf", file_size=0, sha256="0" * 64),
        page_count=1,
        selected_pages=(1,),
        metadata=DocumentMetadata(),
        encrypted=False,
        password_required=False,
        pages=(
            ExtractedPage(
                page_number=1,
                source_index=0,
                width=300,
                height=400,
                rotation=0,
                classification=PageClassification.TEXT,
                text_blocks=tuple(
                    TextBlock(
                        id=item.id,
                        text=item.text,
                        bbox=item.bbox,
                        original_order=index,
                        normalized_order=index,
                        spans=item.spans,
                    )
                    for index, item in enumerate(paragraphs)
                ),
            ),
        ),
        paragraphs=paragraphs,
        reconstruction=ParagraphReconstruction(
            mode="conservative",
            options=ParagraphReconstructionOptions(),
            metrics=ReconstructionMetrics(
                raw_blocks=len(paragraphs),
                raw_lines=len(paragraphs),
                logical_paragraphs=len(paragraphs),
                merged_fragments=0,
                ambiguous_decisions=0,
                cross_page_merges=0,
                soft_hyphens_removed=0,
            ),
        ),
    )


class Provider:
    backend_name = "fake-list"
    model_name = "no-model"
    device = "cpu"

    def __init__(self, output: str = "2. Настройте проект") -> None:
        self.output = output
        self.inputs: list[str] = []

    def count_tokens(self, text: str) -> int:
        return len(text.split()) + 2

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        self.inputs.extend(texts)
        return [
            self.output.replace("1.5 mm", "__PDFTR_0000__")
            if "__PDFTR_0000__" in text
            else self.output
            for text in texts
        ]


def _translate(document: ExtractedDocument, provider: Provider, path: Path) -> ExtractedDocument:
    with TranslationCache(path) as cache:
        return translate_document(
            document, translator=provider, cache=cache, options=TranslationOptions()
        )


@pytest.mark.parametrize("marker", ["•", "-", "–", "*", "1.", "2)", "a)", "A."])
def test_source_marker_forms_need_real_independent_rectangles(marker: str) -> None:
    paragraph = _paragraph(marker)
    context = (paragraph, _paragraph("B.", index=1)) if marker == "A." else (paragraph,)
    item = source_list_item(paragraph, context)
    assert item is not None
    assert item.marker_text == marker
    assert item.marker_source_rect == paragraph.spans[0].bbox
    assert item.content_source_rect == paragraph.spans[1].bbox
    assert item.semantic.text == "Configure project"
    assert item.semantic.spans == paragraph.spans[1:]
    assert paragraph.text == f"{marker} Configure project"
    assert is_list_marker(marker)


@pytest.mark.parametrize("text", ["A. Smith", "1.5 mm", "3.14"])
def test_semantic_lookalikes_and_provider_prefixes_survive(tmp_path: Path, text: str) -> None:
    ordinary = _paragraph("1.").model_copy(update={"text": text, "kind": ParagraphKind.BODY})
    assert source_list_item(ordinary) is None
    provider = Provider(text)
    result = _translate(_document(ordinary), provider, tmp_path / "cache.db")
    assert provider.inputs == ([text] if text == "A. Smith" else [])
    assert result.paragraphs[0].translated_text == text


@pytest.mark.parametrize("text", ["A. Smith", "1.5 mm", "3.14", "2. Настройте проект"])
def test_ordinary_provider_output_is_not_stripped(tmp_path: Path, text: str) -> None:
    ordinary = _paragraph().model_copy(
        update={"text": "Configure project", "kind": ParagraphKind.BODY}
    )
    provider = Provider(text)
    result = _translate(_document(ordinary), provider, tmp_path / "cache.db")
    assert provider.inputs == ["Configure project"]
    assert result.paragraphs[0].translated_text == text


@pytest.mark.parametrize("text", ["A. Smith", "1.5 mm", "3.14"])
def test_semantic_prefix_inside_confirmed_list_survives(tmp_path: Path, text: str) -> None:
    source = _paragraph(content=f"{text} is the reference")
    provider = Provider(f"2. {text} — значение")
    result = _translate(_document(source), provider, tmp_path / "cache.db")
    assert result.paragraphs[0].translated_text == f"1. {text} — значение"
    assert provider.inputs and not provider.inputs[0].startswith("1. ")


def test_separate_initial_and_surname_remain_ambiguous() -> None:
    paragraph = _paragraph("A.", "Smith")
    assert source_list_item(paragraph, (paragraph,)) is None
    assert (
        extract_typography_evidence(_document(paragraph)).paragraphs[0].role.value
        is TypographyRole.OTHER
    )


@pytest.mark.parametrize(
    "output", ["2. Настройте проект", "• Настройте проект", "Настройте проект"]
)
def test_provider_receives_semantic_only_and_source_marker_is_restored(
    tmp_path: Path, output: str
) -> None:
    source = _document(_paragraph())
    provider = Provider(output)
    result = _translate(source, provider, tmp_path / "cache.db")
    assert provider.inputs == ["Configure project"]
    assert result.paragraphs[0].translated_text == "1. Настройте проект"
    assert result.pages == source.pages
    assert result.paragraphs[0].text == source.paragraphs[0].text
    assert document_from_json(document_to_json(result)) == result


def test_cache_and_duplicate_semantics_restore_each_source_marker_without_affecting_ordinary(
    tmp_path: Path,
) -> None:
    first, second = _paragraph("1."), _paragraph("2)", index=1)
    ordinary = _paragraph(index=2).model_copy(
        update={"text": "Configure project", "kind": ParagraphKind.BODY}
    )
    source = _document(first, second, ordinary)
    provider = Provider()
    result = _translate(source, provider, tmp_path / "cache.db")
    assert provider.inputs == ["Configure project"]
    assert [item.translated_text for item in result.paragraphs] == [
        "1. Настройте проект",
        "2) Настройте проект",
        "2. Настройте проект",
    ]
    cached_provider = Provider("must not run")
    cached = _translate(source, cached_provider, tmp_path / "cache.db")
    assert cached_provider.inputs == []
    assert cached.paragraphs == result.paragraphs


@pytest.mark.parametrize(
    "defect",
    [
        "combined",
        "overlap",
        "nan",
        "infinite",
        "empty",
        "different_line",
        "outside",
        "ambiguous",
        "contradictory",
    ],
)
def test_weak_source_evidence_falls_back(defect: str) -> None:
    paragraph = _paragraph()
    marker, content = paragraph.spans
    if defect == "combined":
        spans = (marker.model_copy(update={"text": paragraph.text, "bbox": paragraph.bbox}),)
    elif defect == "overlap":
        spans = (marker.model_copy(update={"bbox": _box(40, 50, 75, 65)}), content)
    elif defect == "nan":
        spans = (marker.model_copy(update={"bbox": _box(float("nan"), 50, 49, 65)}), content)
    elif defect == "infinite":
        spans = (marker, content.model_copy(update={"bbox": _box(70, 50, float("inf"), 65)}))
    elif defect == "empty":
        spans = (marker.model_copy(update={"bbox": _box(40, 50, 40, 65)}), content)
    elif defect == "different_line":
        spans = (marker, content.model_copy(update={"bbox": _box(70, 80, 260, 95)}))
    elif defect == "outside":
        spans = (marker, content.model_copy(update={"bbox": _box(70, 50, 300, 65)}))
    elif defect == "contradictory":
        spans = (marker.model_copy(update={"text": "2. "}), content)
    else:
        spans = paragraph.spans
        paragraph = paragraph.model_copy(update={"ambiguous": True})
    fragment = paragraph.fragments[0].model_copy(update={"spans": spans})
    paragraph = paragraph.model_copy(update={"spans": spans, "fragments": (fragment,)})
    assert source_list_item(paragraph) is None


def _discover(document: ExtractedDocument, page: pymupdf.Page):
    styles = reconstruct_styles(extract_typography_evidence(document))
    return discover_reflow_page(
        document,
        document.pages[0],
        page,
        default_font_size=10,
        min_font_size=6,
        line_height=1.2,
        style_by_occurrence={item.occurrence_index: item for item in styles.paragraphs},
    )


def test_styled_semantic_prefix_has_offsets_without_marker(tmp_path: Path) -> None:
    paragraph = _paragraph(content="A. Smith configures the project")
    marker, content = paragraph.spans
    styled = content.model_copy(
        update={"text": "A. Smith", "text_color": 0xFF0000, "bbox": _box(70, 50, 115, 65)}
    )
    rest = content.model_copy(
        update={"text": " configures the project", "text_color": 0, "bbox": _box(115, 50, 260, 65)}
    )
    spans = (marker, styled, rest)
    paragraph = paragraph.model_copy(
        update={
            "spans": spans,
            "fragments": (paragraph.fragments[0].model_copy(update={"spans": spans}),),
        }
    )
    translated = _translate(
        _document(paragraph, _paragraph(index=1)),
        Provider("2. A. Smith настраивает проект"),
        tmp_path / "cache.db",
    )
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=300, height=400)
        discovered = _discover(translated, page)
    assert discovered is not None
    flow = discovered.paragraphs[0]
    assert flow.text == "A. Smith настраивает проект"
    run = next(item for item in flow.inline_styles.applied if item.text == "A. Smith")
    assert run.text_start == run.source_start == 0
    assert run.text_end == run.source_end == len("A. Smith")
    assert flow.list_layout is not None


@pytest.mark.parametrize(
    "alignment", [ReflowAlignment.LEFT, ReflowAlignment.CENTER, ReflowAlignment.RIGHT]
)
@pytest.mark.parametrize("content_x", [49.5, 100])
def test_source_geometry_pagination_and_saved_validation(
    tmp_path: Path, cyrillic_font_path: Path, alignment: ReflowAlignment, content_x: float
) -> None:
    source = _document(_paragraph(content_x=content_x), _paragraph(index=1, content_x=content_x))
    translated = _translate(
        source,
        Provider("2. Independent semantic words wrap across multiple pages. " * 15),
        tmp_path / "cache.db",
    )
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=300, height=400)
        discovered = _discover(translated, page)
    assert discovered is not None
    paragraph = discovered.paragraphs[0]
    paragraph = replace(
        paragraph,
        style=replace(paragraph.style, alignment=alignment, font_size=10, line_height=1.2),
    )
    regions = tuple(
        FlowRegion(number, Rect(40, 40, 260, 140), 0, number - 1, 1, number > 1)
        for number in range(1, 30)
    )
    with PyMuPdfMeasurer(300, 200, cyrillic_font_path) as measurer:
        plan = plan_flow((paragraph,), regions, measurer)
    assert len(plan.segments) > 1
    assert all(
        item.target_rect.x0 == content_x and item.first_line_indent == 0 for item in plan.segments
    )
    output = tmp_path / "list.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page(width=300, height=200)
        insert_continuation_pages(pdf, (plan,))
        insert_reflow_segments(pdf, (plan,), cyrillic_font_path)
        pdf.save(output)
    validate_saved_segments(output, (plan,))
    with pymupdf.open(output) as pdf:
        marker_words = [word for page in pdf for word in page.get_text("words") if word[4] == "1."]
        assert len(marker_words) == 1
        assert marker_words[0][0] == pytest.approx(40, abs=0.1)
        if alignment is ReflowAlignment.LEFT:
            lines = [
                line
                for page in pdf
                for block in page.get_text("dict")["blocks"]
                for line in block.get("lines", ())
                if not any(span["text"] == "1." for span in line["spans"])
            ]
            assert len(lines) > 2
            assert all(line["bbox"][0] == pytest.approx(content_x, abs=0.1) for line in lines)

    for defect in (
        "duplicate",
        "continuation",
        "missing_marker",
        "marker_elsewhere",
        "missing_semantic",
    ):
        broken = tmp_path / f"{defect}.pdf"
        with pymupdf.open(output) as pdf:
            if defect in {"duplicate", "continuation"}:
                index = 0 if defect == "duplicate" else 1
                segment = plan.segments[index]
                pdf[segment.target_page_number - 1].insert_text(
                    (40, segment.target_rect.y0 + 25), "1.", fontsize=10
                )
            else:
                segment = plan.segments[0]
                rect = (
                    segment.structural_fragment.target_rect
                    if defect in {"missing_marker", "marker_elsewhere"}
                    else segment.target_rect
                )
                pdf[0].add_redact_annot(pymupdf.Rect(rect.x0, rect.y0 - 3, rect.x1, rect.y1 + 3))
                pdf[0].apply_redactions()
                if defect == "marker_elsewhere":
                    pdf[0].insert_text((10, 20), "1.", fontsize=10)
            pdf.save(broken)
        with pytest.raises(OutputPdfError):
            validate_saved_segments(broken, (plan,))


@pytest.mark.parametrize(
    "marker_pair", [("1.", "2)"), ("•", "-"), ("–", "*"), ("a)", "b)"), ("A.", "B.")]
)
def test_real_source_pdf_translation_to_production_renderer(
    tmp_path: Path, cyrillic_font_path: Path, marker_pair: tuple[str, str]
) -> None:
    source_path = tmp_path / "source.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=300, height=400)
        page.insert_font(fontname="sourcefont", fontfile=str(cyrillic_font_path))
        for marker, y in zip(marker_pair, (80, 120), strict=True):
            page.insert_text(
                (40, y), marker + " ", fontname="sourcefont", fontsize=10, color=(0.2, 0.2, 0.2)
            )
            page.insert_text(
                (70, y),
                "Configure project and install the package",
                fontname="sourcefont",
                fontsize=10,
            )
        pdf.save(source_path)
    source_bytes = source_path.read_bytes()
    source = PdfExtractor().extract(source_path)
    assert len(source.paragraphs) == 2
    assert all(source_list_item(item, source.paragraphs) is not None for item in source.paragraphs)
    provider = Provider("2. Настройте проект и установите пакет")
    translated = _translate(source, provider, tmp_path / "cache.db")
    assert provider.inputs == ["Configure project and install the package"]
    output = tmp_path / "translated.pdf"
    result = PdfRenderer().render(
        source_path, translated, output, font_path=cyrillic_font_path, options=RenderOptions()
    )
    assert result.reflowed_paragraphs == 2
    assert source_path.read_bytes() == source_bytes
    with pymupdf.open(output) as pdf:
        words = pdf[0].get_text("words")
        markers = [word for word in words if word[4] in marker_pair]
        assert [word[4] for word in markers] == list(marker_pair)
        assert all(word[0] == pytest.approx(40, abs=0.1) for word in markers)


def test_adjacent_source_initials_preserve_semantics_without_list_contract(
    tmp_path: Path, cyrillic_font_path: Path
) -> None:
    path = tmp_path / "names.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=300, height=400)
        page.insert_font(fontname="sourcefont", fontfile=str(cyrillic_font_path))
        for initial, surname, y in (("A.", "Smith", 80), ("B.", "Jones", 120)):
            page.insert_text(
                (40, y), initial + " ", fontname="sourcefont", fontsize=10, color=(0.2, 0.2, 0.2)
            )
            page.insert_text((70, y), surname, fontname="sourcefont", fontsize=10)
        pdf.save(path)
    source = PdfExtractor().extract(path)
    assert [item.text for item in source.paragraphs] == ["A. Smith", "B. Jones"]
    assert all(source_list_item(item, source.paragraphs) is None for item in source.paragraphs)
    provider = Provider("Имя сохранено")
    translated = _translate(source, provider, tmp_path / "cache.db")
    assert provider.inputs == ["A. Smith", "B. Jones"]
    with pymupdf.open(path) as pdf:
        assert _discover(translated, pdf[0]) is None


@pytest.mark.parametrize("continuation_x", [70, 82])
def test_real_source_wrapped_items_are_owned_or_fall_back(
    tmp_path: Path, cyrillic_font_path: Path, continuation_x: float
) -> None:
    path = tmp_path / "wrapped.pdf"
    first_lines = (
        "Configure project and install package",
        "Run tests and verify the results",
    )
    continuation = "and keep the settings for later use."
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=300, height=400)
        page.insert_font(fontname="sourcefont", fontfile=str(cyrillic_font_path))
        for marker, text, y in zip(("1.", "2."), first_lines, (80, 140), strict=True):
            page.insert_text(
                (40, y), marker + " ", fontname="sourcefont", fontsize=10, color=(0.2, 0.2, 0.2)
            )
            page.insert_text((70, y), text, fontname="sourcefont", fontsize=10)
            page.insert_text(
                (continuation_x, y + 12), continuation, fontname="sourcefont", fontsize=10
            )
        pdf.save(path)
    source = PdfExtractor().extract(path)
    provider = Provider("2. " + "Сохраните параметры проекта и проверьте результаты работы. " * 3)
    translated = _translate(source, provider, tmp_path / "cache.db")
    with pymupdf.open(path) as pdf:
        discovered = _discover(translated, pdf[0])
    if continuation_x != 70:
        assert len(source.paragraphs) == 4
        assert discovered is None
        return
    assert len(source.paragraphs) == 2
    assert provider.inputs == [f"{text} {continuation}" for text in first_lines]
    assert discovered is not None
    assert all(item.list_layout is not None for item in discovered.paragraphs)
    output = tmp_path / "wrapped-translated.pdf"
    result = PdfRenderer().render(
        path, translated, output, font_path=cyrillic_font_path, options=RenderOptions()
    )
    assert result.reflowed_paragraphs == 2
    with pymupdf.open(output) as pdf:
        words = [word for page in pdf for word in page.get_text("words")]
        assert sum(word[4] == "1." for word in words) == 1
        assert sum(word[4] == "2." for word in words) == 1
        lines = [
            line
            for page in pdf
            for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", ())
            if not any(span["text"] in {"1.", "2."} for span in line["spans"])
        ]
        assert len(lines) > 2
        assert all(line["bbox"][0] == pytest.approx(70, abs=0.1) for line in lines)
