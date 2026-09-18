from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

import pymupdf
import pytest

from pdftranslate.domain.document import (
    DocumentMetadata,
    ExtractedDocument,
    SourceDocument,
    TranslationMetadata,
    TranslationStatistics,
)
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
from pdftranslate.rendering import PdfRenderer, RenderOptions, RenderStrategy
from pdftranslate.rendering.errors import OutputPdfError, RenderCompletenessError
from pdftranslate.rendering.reflow import (
    ContentDisposition,
    FlowParagraph,
    FlowRegion,
    Measurement,
    Rect,
    ReflowStyle,
    discover_reflow_page,
    plan_flow,
)
from pdftranslate.rendering.reflow.models import LayoutPlan, PlacementSegment, PlacementState
from pdftranslate.rendering.reflow.pymupdf_layout import validate_saved_segments


class CapacityMeasurer:
    def measure(
        self,
        text: str,
        *,
        width: float,
        height: float,
        font_size: float,
        line_height: float,
    ) -> Measurement:
        lines = math.ceil(len(text) / max(1, int(width))) if text else 0
        used = lines * font_size * line_height
        return Measurement(used <= height, used, lines)


def _flow(
    index: int,
    text: str,
    *,
    heading: bool = False,
    source_page: int = 1,
) -> FlowParagraph:
    rect = Rect(40, 70 + index * 20, 260, 85 + index * 20)
    return FlowParagraph(
        occurrence_index=index,
        paragraph_id=f"p{index}",
        source_page_number=source_page,
        kind="heading" if heading else "body",
        disposition=(
            ContentDisposition.FLOWABLE_HEADING if heading else ContentDisposition.FLOWABLE_BODY
        ),
        text=text,
        source_rect=rect,
        source_fragment_rects=(rect,),
        style=ReflowStyle(
            font_size=12 if heading else 10,
            line_height=1,
            paragraph_spacing=4,
            heading=heading,
        ),
    )


def _region(page: int, order: int, height: float = 40) -> FlowRegion:
    return FlowRegion(page, Rect(40, 60, 260, 60 + height), 0, order, 1, page > 1)


def test_planner_keeps_multiple_paragraphs_ordered_after_continuation() -> None:
    paragraphs = (_flow(0, "a" * 1000), _flow(1, "beta"), _flow(2, "gamma"))

    plan = plan_flow(paragraphs, (_region(1, 0), _region(2, 1, height=80)), CapacityMeasurer())

    assert tuple(item.occurrence_index for item in plan.segments)[-2:] == (1, 2)
    assert "".join(item.text for item in plan.segments if item.occurrence_index == 0) == "a" * 1000
    assert plan.continuation_count >= 1
    assert plan.unplaced_text_count == 0


def test_heading_moves_forward_when_it_would_be_orphaned() -> None:
    paragraphs = (_flow(0, "preface"), _flow(1, "Heading", heading=True), _flow(2, "body"))
    regions = (_region(1, 0, height=39), _region(2, 1, height=80))

    plan = plan_flow(paragraphs, regions, CapacityMeasurer())

    heading = next(item for item in plan.segments if item.occurrence_index == 1)
    body = next(item for item in plan.segments if item.occurrence_index == 2)
    assert heading.target_page_number == 2
    assert body.target_page_number == 2
    assert heading.font_size > body.font_size


def test_segment_local_validation_rejects_missing_duplicate(tmp_path: Path) -> None:
    output = tmp_path / "duplicates.pdf"
    document = pymupdf.open()
    page = document.new_page(width=300, height=300)
    page.insert_textbox(pymupdf.Rect(40, 40, 260, 80), "duplicate text", fontsize=12)
    document.save(output)
    document.close()
    segments = tuple(
        PlacementSegment(
            occurrence_index=index,
            paragraph_id=f"p{index}",
            source_page_number=1,
            target_page_number=1,
            target_rect=rect,
            continuation_index=0,
            text_start=0,
            text_end=14,
            text="duplicate text",
            font_size=12,
            line_height=1.2,
            measured_height=14,
            line_count=1,
            color=(0, 0, 0),
            state=PlacementState.COMPLETE,
        )
        for index, rect in enumerate((Rect(40, 40, 260, 80), Rect(40, 140, 260, 180)))
    )
    layout = LayoutPlan((_region(1, 0, 150),), (), segments, 0)

    with pytest.raises(OutputPdfError, match=r"occurrence 1.*local=''.*page_diagnostic"):
        validate_saved_segments(output, (layout,))


def test_region_discovery_rejects_ambiguous_and_drawing_intersections() -> None:
    document, page_model = _classified_document(ambiguous=False)
    pdf = pymupdf.open()
    page = pdf.new_page(width=300, height=400)

    discovered = discover_reflow_page(
        document,
        page_model,
        page,
        default_font_size=11,
        min_font_size=6,
        line_height=1.2,
    )
    assert discovered is not None
    assert [item.disposition for item in discovered.paragraphs] == [
        ContentDisposition.FLOWABLE_HEADING,
        ContentDisposition.FLOWABLE_BODY,
        ContentDisposition.FLOWABLE_BODY,
    ]
    assert all(item.kind != "footnote" for item in discovered.paragraphs)

    ambiguous, ambiguous_page = _classified_document(ambiguous=True)
    assert (
        discover_reflow_page(
            ambiguous,
            ambiguous_page,
            page,
            default_font_size=11,
            min_font_size=6,
            line_height=1.2,
        )
        is None
    )
    page.draw_rect(pymupdf.Rect(50, 100, 250, 180))
    assert (
        discover_reflow_page(
            document,
            page_model,
            page,
            default_font_size=11,
            min_font_size=6,
            line_height=1.2,
        )
        is None
    )
    pdf.close()

    image_pdf = pymupdf.open()
    image_page = image_pdf.new_page(width=300, height=400)
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 4, 4), False)
    pixmap.clear_with(0)
    image_page.insert_image(pymupdf.Rect(50, 100, 250, 180), stream=pixmap.tobytes("png"))
    assert (
        discover_reflow_page(
            document,
            page_model,
            image_page,
            default_font_size=11,
            min_font_size=6,
            line_height=1.2,
        )
        is None
    )
    image_pdf.close()


def test_renderer_reflows_selectable_foreign_text_and_preserves_anchors(
    tmp_path: Path, cyrillic_font_path: Path
) -> None:
    source = _source_pdf(tmp_path / "source.pdf")
    source_before = source.read_bytes()
    translated = _translated_source(source)
    output = tmp_path / "translated.pdf"

    result = PdfRenderer().render(
        source,
        translated,
        output,
        font_path=cyrillic_font_path,
        options=RenderOptions(max_reflow_pages=4),
    )

    assert source.read_bytes() == source_before
    assert result.reflowed_paragraphs == 3
    assert result.inserted_pages >= 1
    assert result.unplaced_text_count == 0
    assert any(item.strategy is RenderStrategy.REFLOW_LAYOUT for item in result.blocks)
    rendered = pymupdf.open(output)
    try:
        text = " ".join(str(page.get_text("text")) for page in rendered)
        assert "Latin terminus" in text
        assert "Ελληνικά" in text
        assert "Running title" in text
        assert "Footnote remains anchored" in text
    finally:
        rendered.close()


def test_footnote_overflow_is_fatal_and_existing_output_is_unchanged(
    tmp_path: Path, cyrillic_font_path: Path
) -> None:
    source = _source_pdf(tmp_path / "source.pdf")
    translated = _translated_source(source, overflowing_footnote=True)
    output = tmp_path / "existing.pdf"
    original = b"existing-output-must-survive"
    output.write_bytes(original)

    with pytest.raises(RenderCompletenessError, match="required paragraph"):
        PdfRenderer().render(
            source,
            translated,
            output,
            font_path=cyrillic_font_path,
            options=RenderOptions(max_reflow_pages=4, overwrite=True),
        )

    assert output.read_bytes() == original


def _classified_document(*, ambiguous: bool) -> tuple[ExtractedDocument, ExtractedPage]:
    specs = (
        ("heading", ParagraphKind.HEADING, BoundingBox(x0=40, y0=50, x1=260, y1=75)),
        ("body-1", ParagraphKind.BODY, BoundingBox(x0=40, y0=90, x1=260, y1=140)),
        ("body-2", ParagraphKind.BODY, BoundingBox(x0=42, y0=150, x1=258, y1=210)),
        ("footnote", ParagraphKind.FOOTNOTE, BoundingBox(x0=40, y0=340, x1=260, y1=360)),
    )
    blocks: list[TextBlock] = []
    paragraphs: list[LogicalParagraph] = []
    for index, (text, kind, bbox) in enumerate(specs):
        block_id = f"b{index}"
        span = TextSpan(text=text, bbox=bbox, font_size=14 if kind is ParagraphKind.HEADING else 11)
        blocks.append(
            TextBlock(
                id=block_id,
                text=text,
                bbox=bbox,
                original_order=index,
                normalized_order=index,
                spans=(span,),
            )
        )
        fragment = ParagraphFragment(
            id=f"f{index}",
            text=text,
            bbox=bbox,
            mapping=SourceBlockMapping(
                source_block_id=block_id,
                page_number=1,
                bbox=bbox,
                original_order=index,
                normalized_order=index,
            ),
            spans=(span,),
            column=0,
        )
        paragraphs.append(
            LogicalParagraph(
                id=f"p{index}",
                text=text,
                kind=kind,
                anchor_page_number=1,
                bbox=bbox,
                fragments=(fragment,),
                spans=(span,),
                ambiguous=ambiguous and kind is ParagraphKind.BODY,
                translated_text=f"translated {text}",
            )
        )
    page = ExtractedPage(
        page_number=1,
        source_index=0,
        width=300,
        height=400,
        rotation=0,
        classification=PageClassification.TEXT,
        text_blocks=tuple(blocks),
    )
    reconstruction = ParagraphReconstruction(
        mode="conservative",
        options=ParagraphReconstructionOptions(),
        metrics=ReconstructionMetrics(
            raw_blocks=4,
            raw_lines=4,
            logical_paragraphs=4,
            merged_fragments=0,
            ambiguous_decisions=int(ambiguous),
            cross_page_merges=0,
            soft_hyphens_removed=0,
        ),
    )
    document = ExtractedDocument(
        schema_version="1.3",
        source=SourceDocument(path="source.pdf", file_size=0, sha256="0" * 64),
        page_count=1,
        selected_pages=(1,),
        metadata=DocumentMetadata(),
        encrypted=False,
        password_required=False,
        pages=(page,),
        paragraphs=tuple(paragraphs),
        reconstruction=reconstruction,
        translation=_translation_metadata(4),
    )
    return document, page


def _source_pdf(path: Path) -> Path:
    document = pymupdf.open()
    page = document.new_page(width=300, height=500)
    page.insert_text((40, 25), "Running title", fontsize=8)
    page.insert_textbox(pymupdf.Rect(40, 55, 260, 80), "Chapter One", fontsize=14)
    page.insert_textbox(
        pymupdf.Rect(40, 100, 260, 150),
        "Body paragraph one contains enough source words for reconstruction.",
        fontsize=11,
    )
    page.insert_textbox(
        pymupdf.Rect(42, 165, 258, 220),
        "Body paragraph two contains enough source words for stable reconstruction width.",
        fontsize=11,
    )
    page.insert_text((40, 470), "1 Footnote remains anchored.", fontsize=7)
    document.save(path)
    document.close()
    return path


def _translated_source(source: Path, *, overflowing_footnote: bool = False) -> ExtractedDocument:
    extracted = PdfExtractor().extract(source)
    translated_paragraphs = []
    for paragraph in extracted.paragraphs:
        if "Chapter" in paragraph.text:
            kind = ParagraphKind.HEADING
            translated = "Глава Α"
        elif "Body paragraph" in paragraph.text:
            kind = ParagraphKind.BODY
            translated = (
                "Точный русский текст с Latin terminus и Ελληνικά без изменения. " * 25
            ).strip()
        elif "Footnote" in paragraph.text:
            kind = ParagraphKind.FOOTNOTE
            translated = "переполнение " * 200 if overflowing_footnote else paragraph.text
        else:
            kind = ParagraphKind.HEADER
            translated = paragraph.text
        translated_paragraphs.append(
            paragraph.model_copy(
                update={"kind": kind, "ambiguous": False, "translated_text": translated}
            )
        )
    return extracted.model_copy(
        update={
            "schema_version": "1.3",
            "paragraphs": tuple(translated_paragraphs),
            "translation": _translation_metadata(len(translated_paragraphs)),
        }
    )


def _translation_metadata(total: int) -> TranslationMetadata:
    now = datetime.now(UTC)
    return TranslationMetadata(
        status="completed",
        backend="fake",
        model="fake",
        source_language="en",
        target_language="ru",
        effective_device="cpu",
        batch_size=1,
        max_input_tokens=64,
        started_at=now,
        updated_at=now,
        completed_at=now,
        statistics=TranslationStatistics(
            total_blocks=total,
            completed_blocks=total,
            skipped_blocks=0,
            cache_hits=0,
            cache_misses=total,
            translated_segments=total,
        ),
    )
