from __future__ import annotations

import hashlib
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
    ReflowAlignment,
    ReflowContentKind,
    ReflowStyle,
    UnsupportedLayoutError,
    discover_footnote_page,
    discover_reflow_page,
    plan_flow,
)
from pdftranslate.rendering.reflow.models import LayoutPlan, PlacementSegment, PlacementState
from pdftranslate.rendering.reflow.pymupdf_layout import validate_saved_segments
from pdftranslate.rendering.reflow.typography import body_reflow_style, heading_reflow_style
from pdftranslate.typography import (
    MixedStyleEvidence,
    RgbColor,
    TextAlignment,
    extract_typography_evidence,
    reconstruct_styles,
)


def test_cyrillic_font_fixture_uses_pinned_bundled_bytes(cyrillic_font_path: Path) -> None:
    expected_path = (
        Path(__file__).parent / "resources" / "fonts" / "LiberationSans-Regular.ttf"
    ).resolve()

    assert cyrillic_font_path == expected_path
    assert hashlib.sha256(cyrillic_font_path.read_bytes()).hexdigest() == (
        "76d04c18ea243f426b7de1f3ad208e927008f961dc5945e5aad352d0dfde8ee8"
    )


class CapacityMeasurer:
    def measure(
        self,
        text: str,
        *,
        width: float,
        height: float,
        style: ReflowStyle,
        first_segment: bool,
    ) -> Measurement:
        del first_segment
        lines = math.ceil(len(text) / max(1, int(width))) if text else 0
        used = lines * style.font_size * style.line_height
        return Measurement(used <= height, used, lines)


class FirstLineAwareMeasurer:
    def measure(
        self,
        text: str,
        *,
        width: float,
        height: float,
        style: ReflowStyle,
        first_segment: bool,
    ) -> Measurement:
        effective_width = width - (style.first_line_indent if first_segment else 0.0)
        if text and effective_width < style.font_size:
            return Measurement(False, height, 0)
        lines = math.ceil(len(text) / max(1, int(effective_width))) if text else 0
        used = lines * style.font_size * style.line_height
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
            space_before=0,
            space_after=4,
            heading=heading,
        ),
    )


def _region(page: int, order: int, height: float = 40) -> FlowRegion:
    return FlowRegion(page, Rect(40, 60, 260, 60 + height), 0, order, 1, page > 1)


def _footnote(index: int, text: str, *, paragraph_id: str | None = None) -> FlowParagraph:
    rect = Rect(40, 220 + index * 12, 260, 230 + index * 12)
    return FlowParagraph(
        occurrence_index=index,
        paragraph_id=paragraph_id or f"fn{index}",
        source_page_number=1,
        kind="footnote",
        disposition=ContentDisposition.FLOWABLE_FOOTNOTE,
        text=text,
        source_rect=rect,
        source_fragment_rects=(rect,),
        style=ReflowStyle(font_size=8, line_height=1, space_before=0, space_after=2),
    )


def test_planner_keeps_multiple_paragraphs_ordered_after_continuation() -> None:
    paragraphs = (_flow(0, "a" * 1000), _flow(1, "beta"), _flow(2, "gamma"))

    plan = plan_flow(paragraphs, (_region(1, 0), _region(2, 1, height=80)), CapacityMeasurer())

    assert tuple(item.occurrence_index for item in plan.segments)[-2:] == (1, 2)
    assert "".join(item.text for item in plan.segments if item.occurrence_index == 0) == "a" * 1000
    assert plan.continuation_count >= 1
    assert plan.unplaced_text_count == 0


def test_footnote_planner_preserves_duplicate_ids_order_and_exact_text() -> None:
    paragraphs = (
        _footnote(0, "first note", paragraph_id="shared"),
        _footnote(1, "second note", paragraph_id="shared"),
    )

    plan = plan_flow(
        paragraphs,
        (_region(1, 0, height=100),),
        CapacityMeasurer(),
        content_kind=ReflowContentKind.FOOTNOTE,
    )

    assert plan.content_kind is ReflowContentKind.FOOTNOTE
    assert tuple(item.occurrence_index for item in plan.segments) == (0, 1)
    assert plan.segments[0].target_rect.y1 <= plan.segments[1].target_rect.y0
    for paragraph in paragraphs:
        assert (
            "".join(
                item.text
                for item in plan.segments
                if item.occurrence_index == paragraph.occurrence_index
            )
            == paragraph.text
        )


def test_footnote_planner_continues_then_places_following_note() -> None:
    paragraphs = (_footnote(0, "alpha " * 180), _footnote(1, "beta follows"))

    plan = plan_flow(
        paragraphs,
        (_region(1, 0, height=32), _region(2, 1, height=120)),
        CapacityMeasurer(),
        content_kind=ReflowContentKind.FOOTNOTE,
    )

    first = tuple(item for item in plan.segments if item.occurrence_index == 0)
    second = tuple(item for item in plan.segments if item.occurrence_index == 1)
    assert len(first) > 1
    assert first[-1].target_page_number == 2
    assert second[0].target_page_number == 2
    assert first[-1].target_rect.y1 <= second[0].target_rect.y0
    assert "".join(item.text for item in first) == paragraphs[0].text


def test_heading_moves_forward_when_it_would_be_orphaned() -> None:
    paragraphs = (_flow(0, "preface"), _flow(1, "Heading", heading=True), _flow(2, "body"))
    regions = (_region(1, 0, height=39), _region(2, 1, height=80))

    plan = plan_flow(paragraphs, regions, CapacityMeasurer())

    heading = next(item for item in plan.segments if item.occurrence_index == 1)
    body = next(item for item in plan.segments if item.occurrence_index == 2)
    assert heading.target_page_number == 2
    assert body.target_page_number == 2
    assert heading.font_size > body.font_size


def test_heading_moves_with_body_when_first_line_geometry_cannot_fit() -> None:
    preface = _flow(0, "preface")
    heading = _flow(1, "Heading", heading=True)
    body = _flow(2, "body")
    body = FlowParagraph(
        **{
            **body.__dict__,
            "style": ReflowStyle(
                font_size=10,
                line_height=1,
                space_before=0,
                space_after=4,
                first_line_indent=215,
            ),
        }
    )
    regions = (
        FlowRegion(1, Rect(40, 60, 260, 110), 0, 0, 1),
        FlowRegion(2, Rect(40, 60, 400, 140), 0, 1, 1, True),
    )

    plan = plan_flow((preface, heading, body), regions, FirstLineAwareMeasurer())

    heading_segment = next(item for item in plan.segments if item.occurrence_index == 1)
    body_segment = next(item for item in plan.segments if item.occurrence_index == 2)
    assert heading_segment.target_page_number == 2
    assert body_segment.target_page_number == 2


def test_body_typography_controls_indents_spacing_and_continuation_once() -> None:
    paragraph = _flow(0, "word " * 250)
    paragraph = FlowParagraph(
        **{
            **paragraph.__dict__,
            "style": ReflowStyle(
                font_size=10,
                line_height=1.1,
                space_before=3,
                space_after=4,
                first_line_indent=12,
                left_indent=5,
                right_indent=7,
                alignment=ReflowAlignment.RIGHT,
            ),
        }
    )

    plan = plan_flow(
        (paragraph,),
        (_region(1, 0, height=25), _region(2, 1, height=100)),
        CapacityMeasurer(),
    )

    assert len(plan.segments) > 1
    first, continuation = plan.segments[:2]
    assert first.target_rect.x0 == 45
    assert first.target_rect.x1 == 253
    assert first.target_rect.y0 == 63
    assert first.first_line_indent == 12
    assert first.space_before == 3
    assert continuation.first_line_indent == 0
    assert continuation.space_before == 0
    assert plan.segments[-1].space_after == 4
    assert all(item.alignment is ReflowAlignment.RIGHT for item in plan.segments)


def test_heading_typography_controls_orphan_measurement_and_spacing() -> None:
    document, _ = _classified_document(ambiguous=False)
    resolved = (
        reconstruct_styles(extract_typography_evidence(document))
        .paragraphs[0]
        .model_copy(
            update={
                "font_size_points": 18.0,
                "line_height_ratio": 1.4,
                "space_before_points": 3.0,
                "space_after_points": 10.0,
            }
        )
    )
    heading_style, heading_color = heading_reflow_style(resolved)
    heading = _flow(1, "Heading", heading=True)
    heading = FlowParagraph(**{**heading.__dict__, "style": heading_style, "color": heading_color})
    paragraphs = (_flow(0, "preface"), heading, _flow(2, "body"))

    plan = plan_flow(
        paragraphs,
        (_region(1, 0, height=60), _region(2, 1, height=100)),
        CapacityMeasurer(),
    )

    heading_segment = next(item for item in plan.segments if item.occurrence_index == 1)
    body_segment = next(item for item in plan.segments if item.occurrence_index == 2)
    assert heading_segment.target_page_number == 2
    assert body_segment.target_page_number == 2
    assert heading_segment.space_before == 3.0
    assert heading_segment.space_after == 10.0


def test_heading_typography_applies_first_segment_and_completion_spacing_once() -> None:
    paragraph = _flow(0, "word " * 250, heading=True)
    paragraph = FlowParagraph(
        **{
            **paragraph.__dict__,
            "style": ReflowStyle(
                font_size=10,
                line_height=1.1,
                space_before=3,
                space_after=4,
                first_line_indent=12,
                left_indent=5,
                right_indent=7,
                alignment=ReflowAlignment.CENTER,
                heading=True,
            ),
        }
    )

    plan = plan_flow(
        (paragraph,),
        (_region(1, 0, height=25), _region(2, 1, height=100)),
        CapacityMeasurer(),
    )

    assert len(plan.segments) > 1
    first, continuation = plan.segments[:2]
    assert first.first_line_indent == 12
    assert first.space_before == 3
    assert continuation.first_line_indent == 0
    assert continuation.space_before == 0
    assert plan.segments[-1].space_after == 4
    assert all(item.alignment is ReflowAlignment.CENTER for item in plan.segments)


def test_heading_typography_rejects_indents_that_remove_usable_width() -> None:
    paragraph = _flow(0, "unsafe heading", heading=True)
    paragraph = FlowParagraph(
        **{
            **paragraph.__dict__,
            "style": ReflowStyle(
                font_size=12,
                line_height=1.2,
                space_before=0,
                space_after=0,
                left_indent=120,
                right_indent=101,
                heading=True,
            ),
        }
    )

    with pytest.raises(UnsupportedLayoutError, match="indents"):
        plan_flow((paragraph,), (_region(1, 0),), CapacityMeasurer())


def test_body_typography_rejects_indents_that_remove_usable_width() -> None:
    paragraph = _flow(0, "unsafe")
    paragraph = FlowParagraph(
        **{
            **paragraph.__dict__,
            "style": ReflowStyle(
                font_size=10,
                line_height=1.2,
                space_before=0,
                space_after=0,
                left_indent=120,
                right_indent=101,
            ),
        }
    )

    with pytest.raises(UnsupportedLayoutError, match="indents"):
        plan_flow((paragraph,), (_region(1, 0),), CapacityMeasurer())


def test_body_typography_allows_safe_hanging_indent() -> None:
    paragraph = _flow(0, "safe hanging indent")
    paragraph = FlowParagraph(
        **{
            **paragraph.__dict__,
            "style": ReflowStyle(
                font_size=10,
                line_height=1.2,
                space_before=0,
                space_after=0,
                first_line_indent=-8,
                left_indent=12,
            ),
        }
    )

    plan = plan_flow((paragraph,), (_region(1, 0),), CapacityMeasurer())

    assert plan.segments[0].target_rect.x0 == 52
    assert plan.segments[0].first_line_indent == -8


def test_body_typography_rejects_hanging_indent_outside_flow_region() -> None:
    paragraph = _flow(0, "unsafe hanging indent")
    paragraph = FlowParagraph(
        **{
            **paragraph.__dict__,
            "style": ReflowStyle(
                font_size=10,
                line_height=1.2,
                space_before=0,
                space_after=0,
                first_line_indent=-12,
                left_indent=4,
            ),
        }
    )

    with pytest.raises(UnsupportedLayoutError, match="first-line/hanging indent"):
        plan_flow((paragraph,), (_region(1, 0),), CapacityMeasurer())


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


def test_body_discovery_maps_resolved_styles_by_occurrence_not_paragraph_id() -> None:
    document, page_model = _classified_document(ambiguous=False)
    paragraphs = list(document.paragraphs)
    paragraphs[1] = paragraphs[1].model_copy(update={"id": "duplicate"})
    paragraphs[2] = paragraphs[2].model_copy(update={"id": "duplicate"})
    document = document.model_copy(update={"paragraphs": tuple(paragraphs)})
    resolved = reconstruct_styles(extract_typography_evidence(document))
    style_by_occurrence = {item.occurrence_index: item for item in resolved.paragraphs}
    style_by_occurrence[1] = style_by_occurrence[1].model_copy(
        update={
            "font_size_points": 9.0,
            "line_height_ratio": 1.3,
            "first_line_indent_points": 8.0,
            "left_indent_points": 4.0,
            "right_indent_points": 6.0,
            "space_before_points": 2.0,
            "space_after_points": 5.0,
            "alignment": TextAlignment.RIGHT,
            "color_rgb": RgbColor(red=32, green=64, blue=96),
        }
    )
    style_by_occurrence[2] = style_by_occurrence[2].model_copy(
        update={"font_size_points": 13.0, "alignment": TextAlignment.CENTER}
    )
    pdf = pymupdf.open()
    page = pdf.new_page(width=300, height=400)
    try:
        discovered = discover_reflow_page(
            document,
            page_model,
            page,
            default_font_size=11,
            min_font_size=6,
            line_height=1.2,
            style_by_occurrence=style_by_occurrence,
        )
    finally:
        pdf.close()

    assert discovered is not None
    first_body, second_body = discovered.paragraphs[1:]
    assert first_body.paragraph_id == second_body.paragraph_id == "duplicate"
    assert first_body.style.font_size == 9.0
    assert second_body.style.font_size == 13.0
    assert first_body.style.alignment is ReflowAlignment.RIGHT
    assert second_body.style.alignment is ReflowAlignment.CENTER
    assert first_body.color == pytest.approx((32 / 255, 64 / 255, 96 / 255))
    assert discovered.paragraphs[0].style.heading is True


def test_heading_discovery_maps_heterogeneous_resolved_styles_by_occurrence() -> None:
    document, page_model = _document_with_two_headings()
    paragraphs = list(document.paragraphs)
    paragraphs[0] = paragraphs[0].model_copy(update={"id": "duplicate-heading"})
    paragraphs[3] = paragraphs[3].model_copy(update={"id": "duplicate-heading"})
    document = document.model_copy(update={"paragraphs": tuple(paragraphs)})
    resolved = reconstruct_styles(extract_typography_evidence(document))
    style_by_occurrence = {item.occurrence_index: item for item in resolved.paragraphs}
    style_by_occurrence[0] = style_by_occurrence[0].model_copy(
        update={
            "font_size_points": 14.0,
            "line_height_ratio": 1.25,
            "first_line_indent_points": 3.0,
            "left_indent_points": 4.0,
            "right_indent_points": 5.0,
            "space_before_points": 6.0,
            "space_after_points": 7.0,
            "alignment": TextAlignment.RIGHT,
            "color_rgb": RgbColor(red=24, green=48, blue=72),
        }
    )
    style_by_occurrence[3] = style_by_occurrence[3].model_copy(
        update={"font_size_points": 20.0, "alignment": TextAlignment.CENTER}
    )
    pdf = pymupdf.open()
    page = pdf.new_page(width=300, height=400)
    try:
        discovered = discover_reflow_page(
            document,
            page_model,
            page,
            default_font_size=11,
            min_font_size=6,
            line_height=1.2,
            style_by_occurrence=style_by_occurrence,
        )
    finally:
        pdf.close()

    assert discovered is not None
    headings = tuple(
        item
        for item in discovered.paragraphs
        if item.disposition is ContentDisposition.FLOWABLE_HEADING
    )
    assert len(headings) == 2
    assert headings[0].paragraph_id == headings[1].paragraph_id == "duplicate-heading"
    assert headings[0].style.font_size == 14.0
    assert headings[1].style.font_size == 20.0
    assert headings[0].style.alignment is ReflowAlignment.RIGHT
    assert headings[1].style.alignment is ReflowAlignment.CENTER
    assert headings[0].style.first_line_indent == 3.0
    assert headings[0].style.left_indent == 4.0
    assert headings[0].style.right_indent == 5.0
    assert headings[0].style.space_before == 6.0
    assert headings[0].style.space_after == 7.0
    assert headings[0].color == pytest.approx((24 / 255, 48 / 255, 72 / 255))
    assert all(item.style.heading for item in headings)


def test_heading_discovery_fails_closed_for_invalid_resolved_identity_or_role() -> None:
    document, page_model = _classified_document(ambiguous=False)
    resolved = reconstruct_styles(extract_typography_evidence(document))
    original = {item.occurrence_index: item for item in resolved.paragraphs}
    variants = []

    missing = dict(original)
    missing.pop(0)
    variants.append(missing)

    wrong_occurrence = dict(original)
    wrong_occurrence[0] = wrong_occurrence[0].model_copy(update={"occurrence_index": 99})
    variants.append(wrong_occurrence)

    wrong_id = dict(original)
    wrong_id[0] = wrong_id[0].model_copy(update={"paragraph_id": "wrong-heading"})
    variants.append(wrong_id)

    wrong_role = dict(original)
    wrong_role[0] = wrong_role[1].model_copy(
        update={"occurrence_index": 0, "paragraph_id": document.paragraphs[0].id}
    )
    variants.append(wrong_role)

    pdf = pymupdf.open()
    page = pdf.new_page(width=300, height=400)
    try:
        for style_by_occurrence in variants:
            assert (
                discover_reflow_page(
                    document,
                    page_model,
                    page,
                    default_font_size=11,
                    min_font_size=6,
                    line_height=1.2,
                    style_by_occurrence=style_by_occurrence,
                )
                is None
            )
    finally:
        pdf.close()


def test_body_style_reports_requested_bold_italic_and_mixed_without_faking_faces() -> None:
    document, _ = _classified_document(ambiguous=False)
    resolved = reconstruct_styles(extract_typography_evidence(document)).paragraphs[1]
    resolved = resolved.model_copy(
        update={
            "bold": True,
            "italic": True,
            "mixed_styles": MixedStyleEvidence(
                mixed_font_family=False,
                mixed_font_size=False,
                mixed_weight=True,
                mixed_italic=True,
                mixed_color=False,
            ),
        }
    )

    style, _ = body_reflow_style(resolved)

    assert style.bold_requested is True
    assert style.bold_applied is False
    assert style.italic_requested is True
    assert style.italic_applied is False
    assert style.mixed_style is True


def test_heading_style_reports_resolved_typography_without_faking_faces() -> None:
    document, _ = _classified_document(ambiguous=False)
    resolved = reconstruct_styles(extract_typography_evidence(document)).paragraphs[0]
    resolved = resolved.model_copy(
        update={
            "font_size_points": 17.0,
            "line_height_ratio": 1.35,
            "first_line_indent_points": 2.0,
            "left_indent_points": 3.0,
            "right_indent_points": 4.0,
            "space_before_points": 5.0,
            "space_after_points": 6.0,
            "alignment": TextAlignment.CENTER,
            "color_rgb": RgbColor(red=10, green=20, blue=30),
            "bold": True,
            "italic": True,
            "mixed_styles": MixedStyleEvidence(
                mixed_font_family=True,
                mixed_font_size=False,
                mixed_weight=True,
                mixed_italic=True,
                mixed_color=False,
            ),
        }
    )

    style, color = heading_reflow_style(resolved)

    assert style.heading is True
    assert style.font_size == 17.0
    assert style.line_height == 1.35
    assert style.alignment is ReflowAlignment.CENTER
    assert style.first_line_indent == 2.0
    assert style.left_indent == 3.0
    assert style.right_indent == 4.0
    assert style.space_before == 5.0
    assert style.space_after == 6.0
    assert style.bold_requested is True
    assert style.bold_applied is False
    assert style.italic_requested is True
    assert style.italic_applied is False
    assert style.mixed_style is True
    assert style.fallback_count == resolved.fallback_count
    assert color == pytest.approx((10 / 255, 20 / 255, 30 / 255))

    with pytest.raises(ValueError, match="BODY"):
        body_reflow_style(resolved)


def test_footnote_region_discovery_rejects_unsafe_objects() -> None:
    document, page_model = _classified_document(ambiguous=False)
    pdf = pymupdf.open()
    page = pdf.new_page(width=300, height=400)

    discovered = discover_footnote_page(
        document,
        page_model,
        page,
        body_region=None,
        default_font_size=11,
        min_font_size=6,
        line_height=1.2,
    )
    assert discovered is not None
    assert discovered.occurrence_indexes == (3,)
    assert discovered.source_region_rect.y0 >= 340

    page.draw_rect(pymupdf.Rect(50, 345, 250, 370))
    assert (
        discover_footnote_page(
            document,
            page_model,
            page,
            body_region=None,
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
    image_page.insert_image(pymupdf.Rect(50, 345, 250, 370), stream=pixmap.tobytes("png"))
    assert (
        discover_footnote_page(
            document,
            page_model,
            image_page,
            body_region=None,
            default_font_size=11,
            min_font_size=6,
            line_height=1.2,
        )
        is None
    )
    image_pdf.close()


def test_footnote_page_budget_must_not_be_negative() -> None:
    with pytest.raises(ValueError, match="max_footnote_pages"):
        RenderOptions(max_footnote_pages=-1)


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
    body_indexes = {
        index
        for index, paragraph in enumerate(translated.paragraphs)
        if paragraph.kind is ParagraphKind.BODY
    }
    heading_index = next(
        index
        for index, paragraph in enumerate(translated.paragraphs)
        if paragraph.kind is ParagraphKind.HEADING
    )
    body_results = tuple(
        item
        for item in result.blocks
        if item.strategy is RenderStrategy.REFLOW_LAYOUT and item.unit_index in body_indexes
    )
    assert len(body_results) == 2
    assert all(item.applied_alignment is not None for item in body_results)
    assert all(item.bold_applied is False for item in body_results)
    assert all(item.italic_applied is False for item in body_results)
    heading_result = next(
        item
        for item in result.blocks
        if item.strategy is RenderStrategy.REFLOW_LAYOUT and item.unit_index == heading_index
    )
    expected_heading = reconstruct_styles(extract_typography_evidence(translated)).paragraphs[
        heading_index
    ]
    assert heading_result.font_size == expected_heading.font_size_points
    assert heading_result.applied_line_height == expected_heading.line_height_ratio
    assert heading_result.applied_alignment == expected_heading.alignment.value
    assert heading_result.applied_first_line_indent == expected_heading.first_line_indent_points
    assert heading_result.applied_left_indent == expected_heading.left_indent_points
    assert heading_result.applied_right_indent == expected_heading.right_indent_points
    assert heading_result.applied_space_before == expected_heading.space_before_points
    assert heading_result.applied_space_after == expected_heading.space_after_points
    assert heading_result.bold_requested is expected_heading.bold
    assert heading_result.bold_applied is False
    assert heading_result.italic_requested is expected_heading.italic
    assert heading_result.italic_applied is False
    assert heading_result.mixed_style is not None
    assert heading_result.style_fallback_count == expected_heading.fallback_count
    rendered = pymupdf.open(output)
    try:
        text = " ".join(str(page.get_text("text")) for page in rendered)
        normalized_text = " ".join(text.split())
        assert "Latin terminus" in normalized_text
        assert "Ελληνικά" in normalized_text
        assert "Глава Chapter Α" in normalized_text
        assert "Running title" in normalized_text
        assert "Footnote remains anchored" in normalized_text
    finally:
        rendered.close()


def test_renderer_paginates_footnotes_after_body_pages_and_preserves_separator(
    tmp_path: Path, cyrillic_font_path: Path
) -> None:
    source = _source_pdf(tmp_path / "source.pdf", separator=True)
    translated = _translated_source(
        source,
        footnote_repetitions=20,
        footnote_text="Сноска Latin terminus Ελληνικά. ",
    )
    output = tmp_path / "translated.pdf"

    result = PdfRenderer().render(
        source,
        translated,
        output,
        font_path=cyrillic_font_path,
        options=RenderOptions(max_reflow_pages=4),
    )

    footnote = next(
        item for item in result.blocks if item.strategy is RenderStrategy.REFLOW_FOOTNOTE
    )
    body = tuple(item for item in result.blocks if item.strategy is RenderStrategy.REFLOW_LAYOUT)
    assert result.footnotes_reflowed == 1
    assert result.footnote_segments == footnote.segment_count
    assert result.continued_footnotes == 1
    assert footnote.applied_line_height is None
    assert footnote.applied_alignment is None
    assert result.footnote_continuation_pages >= 1
    assert result.footnote_unplaced_text_count == 0
    assert footnote.page_number == 1
    assert footnote.unit_index >= 0
    assert footnote.target_pages[0] == 1
    assert max(page for item in body for page in item.target_pages) < footnote.target_pages[-1]

    rendered = pymupdf.open(output)
    try:
        assert rendered.page_count == 1 + result.inserted_pages
        assert rendered[0].get_drawings()
        text = " ".join(str(page.get_text("text")) for page in rendered)
        assert "Latin terminus" in text
        assert "Ελληνικά" in text
        assert "Running title" in text
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

    with pytest.raises(RenderCompletenessError, match="reflow capacity exhausted"):
        PdfRenderer().render(
            source,
            translated,
            output,
            font_path=cyrillic_font_path,
            options=RenderOptions(
                max_reflow_pages=4,
                max_footnote_pages=1,
                overwrite=True,
            ),
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


def _document_with_two_headings() -> tuple[ExtractedDocument, ExtractedPage]:
    document, page = _classified_document(ambiguous=False)
    paragraphs = list(document.paragraphs)
    original = paragraphs[3]
    bbox = BoundingBox(x0=40, y0=250, x1=260, y1=278)
    span = TextSpan(text="subheading", bbox=bbox, font_size=19)
    fragment = original.fragments[0].model_copy(
        update={
            "text": "subheading",
            "bbox": bbox,
            "mapping": original.fragments[0].mapping.model_copy(update={"bbox": bbox}),
            "spans": (span,),
        }
    )
    paragraphs[3] = original.model_copy(
        update={
            "text": "subheading",
            "kind": ParagraphKind.HEADING,
            "bbox": bbox,
            "fragments": (fragment,),
            "spans": (span,),
            "translated_text": "translated subheading",
        }
    )
    return document.model_copy(update={"paragraphs": tuple(paragraphs)}), page


def _source_pdf(path: Path, *, separator: bool = False) -> Path:
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
    if separator:
        page.draw_line((40, 450), (260, 450), color=(0, 0, 0), width=0.8)
    document.save(path)
    document.close()
    return path


def _translated_source(
    source: Path,
    *,
    overflowing_footnote: bool = False,
    footnote_repetitions: int | None = None,
    footnote_text: str = "переполнение ",
) -> ExtractedDocument:
    extracted = PdfExtractor().extract(source)
    translated_paragraphs = []
    for paragraph in extracted.paragraphs:
        if "Chapter" in paragraph.text:
            kind = ParagraphKind.HEADING
            translated = "Глава Chapter Α"
        elif "Body paragraph" in paragraph.text:
            kind = ParagraphKind.BODY
            translated = (
                "Точный русский текст с Latin terminus и Ελληνικά без изменения. " * 25
            ).strip()
        elif "Footnote" in paragraph.text:
            kind = ParagraphKind.FOOTNOTE
            if footnote_repetitions is not None:
                translated = (footnote_text * footnote_repetitions).strip()
            else:
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
