from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf
import pytest

from pdftranslate.domain.text_block import BoundingBox, TextSpan
from pdftranslate.reconstruction import (
    LogicalParagraph,
    ParagraphFragment,
    ParagraphKind,
    SourceBlockMapping,
)
from pdftranslate.rendering.inline_styles import (
    InlineStyleDeferReason,
    InlineStyleMapping,
    InlineStyleRun,
    clip_inline_style_runs,
    map_inline_styles,
    validate_inline_style_runs,
)
from pdftranslate.rendering.reflow import (
    ContentDisposition,
    FlowParagraph,
    FlowRegion,
    Measurement,
    Rect,
    ReflowContentKind,
    ReflowStyle,
    plan_flow,
)
from pdftranslate.rendering.reflow.models import LayoutPlan, PlacementSegment, PlacementState
from pdftranslate.rendering.reflow.pymupdf_layout import (
    PyMuPdfMeasurer,
    build_rich_text,
    insert_reflow_segments,
    validate_saved_segments,
)
from pdftranslate.rendering.renderer import _inline_style_render_decisions

BLACK = (0.0, 0.0, 0.0)
RED = (1.0, 0.0, 0.0)
BOX = BoundingBox(x0=40, y0=50, x1=260, y1=80)


def _paragraph(
    spans: tuple[TextSpan, ...], translated_text: str, *, kind: ParagraphKind = ParagraphKind.BODY
) -> LogicalParagraph:
    text = "".join(span.text for span in spans).strip()
    fragment = ParagraphFragment(
        id="fragment-1",
        text=text,
        bbox=BOX,
        mapping=SourceBlockMapping(
            source_block_id="block-1",
            page_number=1,
            bbox=BOX,
            original_order=0,
            normalized_order=0,
        ),
        spans=spans,
        column=0,
    )
    return LogicalParagraph(
        id="paragraph-1",
        text=text,
        kind=kind,
        anchor_page_number=1,
        bbox=BOX,
        fragments=(fragment,),
        spans=spans,
        translated_text=translated_text,
    )


def _mapping(paragraph: LogicalParagraph) -> InlineStyleMapping:
    return map_inline_styles(
        paragraph,
        translated_text=paragraph.translated_text or "",
        base_font_size=10.0,
        base_color=BLACK,
        base_bold=False,
        base_italic=False,
        base_font_family_group="LiberationSans",
    )


def _run(start: int, end: int, text: str, *, size: float = 14.0) -> InlineStyleRun:
    return InlineStyleRun(
        text_start=start,
        text_end=end,
        text=text,
        font_size_points=size,
        color_rgb=RED,
        bold_requested=True,
        bold_applied=False,
        italic_requested=True,
        italic_applied=False,
        source_font_name="SourceFont-BoldItalic",
        source_font_family_group="SourceFont",
        source_start=start,
        source_end=end,
    )


def test_exact_preserved_run_maps_to_translated_offset_not_source_offset() -> None:
    paragraph = _paragraph(
        (
            TextSpan(text="Before ", bbox=BOX, font_size=10, text_color=0),
            TextSpan(
                text="Latin terminus",
                bbox=BOX,
                font_name="SourceFont-BoldItalic",
                font_size=14,
                text_color=0xFF0000,
                bold=True,
                italic=True,
            ),
            TextSpan(text=" after.", bbox=BOX, font_size=10, text_color=0),
        ),
        "До длинного русского текста Latin terminus после.",
    )

    mapping = _mapping(paragraph)

    assert mapping.candidate_count == 1
    assert not mapping.deferred
    run = mapping.applied[0]
    assert run.text_start == paragraph.translated_text.index("Latin terminus")
    assert run.text_start != paragraph.text.index("Latin terminus")
    assert run.font_size_points == 14
    assert run.color_rgb == RED
    assert run.bold_requested is True and run.bold_applied is False
    assert run.italic_requested is True and run.italic_applied is False


def test_repeated_token_is_deferred_when_source_and_target_counts_do_not_prove_mapping() -> None:
    paragraph = _paragraph(
        (
            TextSpan(text="API", bbox=BOX, font_size=14, text_color=0xFF0000),
            TextSpan(text=" and ", bbox=BOX, font_size=10, text_color=0),
            TextSpan(text="API", bbox=BOX, font_size=14, text_color=0x0000FF),
        ),
        "Русский API текст.",
    )

    mapping = _mapping(paragraph)

    assert not mapping.applied
    assert {item.reason for item in mapping.deferred} == {
        InlineStyleDeferReason.AMBIGUOUS_TARGET_OCCURRENCE
    }


def test_partial_preservation_applies_only_proven_run() -> None:
    paragraph = _paragraph(
        (
            TextSpan(text="Latin terminus", bbox=BOX, font_size=14, text_color=0xFF0000),
            TextSpan(text=" and ", bbox=BOX, font_size=10, text_color=0),
            TextSpan(text="CUDA", bbox=BOX, font_size=16, text_color=0x0000FF),
        ),
        "Русский Latin terminus текст.",
    )

    mapping = _mapping(paragraph)

    assert [item.text for item in mapping.applied] == ["Latin terminus"]
    assert [item.reason for item in mapping.deferred] == [
        InlineStyleDeferReason.NOT_PRESERVED_IN_TRANSLATION
    ]


def test_render_decisions_report_applied_and_deferred_runs_without_plaintext() -> None:
    paragraph = _paragraph(
        (
            TextSpan(text="Latin terminus", bbox=BOX, font_size=14, text_color=0xFF0000),
            TextSpan(text=" and ", bbox=BOX, font_size=10, text_color=0),
            TextSpan(text="CUDA", bbox=BOX, font_size=16, text_color=0x0000FF),
        ),
        "Русский Latin terminus текст.",
    )
    mapping = _mapping(paragraph)
    flow = FlowParagraph(
        occurrence_index=0,
        paragraph_id=paragraph.id,
        source_page_number=1,
        kind="body",
        disposition=ContentDisposition.FLOWABLE_BODY,
        text=paragraph.translated_text or "",
        source_rect=Rect(40, 50, 260, 80),
        source_fragment_rects=(Rect(40, 50, 260, 80),),
        style=ReflowStyle(font_size=10, line_height=1.2, space_before=0, space_after=0),
        inline_styles=mapping,
    )

    decisions = _inline_style_render_decisions(flow)

    assert [item.status for item in decisions] == ["applied", "deferred"]
    assert decisions[0].text_sha256 == hashlib.sha256(b"Latin terminus").hexdigest()
    assert decisions[0].text_start == flow.text.index("Latin terminus")
    assert decisions[1].defer_reason == "not_preserved_in_translation"
    assert all(item.text_sha256 not in {"Latin terminus", "CUDA"} for item in decisions)


def test_unsupported_face_only_candidate_is_retained_but_not_applied() -> None:
    paragraph = _paragraph(
        (
            TextSpan(
                text="Latin",
                bbox=BOX,
                font_name="LiberationSans-BoldItalic",
                font_size=10,
                text_color=0,
                bold=True,
                italic=True,
            ),
        ),
        "Latin",
    )

    mapping = _mapping(paragraph)

    assert not mapping.applied
    assert mapping.deferred[0].reason is InlineStyleDeferReason.UNSUPPORTED_PROPERTY
    assert mapping.deferred[0].candidate.bold_requested is True
    assert mapping.deferred[0].candidate.italic_requested is True


def test_unprovable_fragment_span_order_is_deferred() -> None:
    paragraph = _paragraph(
        (TextSpan(text="different", bbox=BOX, font_size=14, text_color=0xFF0000),),
        "translated",
    )
    fragment = paragraph.fragments[0].model_copy(update={"text": "source"})
    paragraph = paragraph.model_copy(
        update={"text": "source", "fragments": (fragment,), "translated_text": "different"}
    )

    mapping = _mapping(paragraph)

    assert not mapping.applied
    assert mapping.deferred[0].reason is InlineStyleDeferReason.UNSAFE_OR_INVALID_SOURCE_RUN


def test_clipping_rebases_run_crossing_a_continuation_boundary() -> None:
    text = "aaaaa bbbbb"
    run = _run(2, 9, text[2:9])

    first = clip_inline_style_runs((run,), text=text, text_start=0, text_end=6)
    second = clip_inline_style_runs((run,), text=text, text_start=6, text_end=len(text))

    assert (first[0].text_start, first[0].text_end, first[0].text) == (2, 6, "aaa ")
    assert (second[0].text_start, second[0].text_end, second[0].text) == (0, 3, "bbb")


class _RunAwareMeasurer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[InlineStyleRun, ...]]] = []

    def measure(
        self,
        text: str,
        *,
        width: float,
        height: float,
        style: ReflowStyle,
        first_segment: bool,
        inline_runs: tuple[InlineStyleRun, ...] = (),
    ) -> Measurement:
        del width, style, first_segment
        self.calls.append((text, inline_runs))
        used = float(len(text))
        return Measurement(used <= height, used, 1 if text else 0)


def test_planner_measures_prefixes_and_segments_with_the_same_clipped_runs() -> None:
    text = "aaaaa bbbbb"
    mapping = InlineStyleMapping(applied=(_run(2, 9, text[2:9]),))
    paragraph = FlowParagraph(
        occurrence_index=0,
        paragraph_id="paragraph-1",
        source_page_number=1,
        kind="footnote",
        disposition=ContentDisposition.FLOWABLE_FOOTNOTE,
        text=text,
        source_rect=Rect(40, 50, 260, 70),
        source_fragment_rects=(Rect(40, 50, 260, 70),),
        style=ReflowStyle(font_size=8, line_height=1, space_before=0, space_after=0),
        inline_styles=mapping,
    )
    measurer = _RunAwareMeasurer()

    plan = plan_flow(
        (paragraph,),
        (
            FlowRegion(1, Rect(40, 50, 260, 56), 0, 0, 1),
            FlowRegion(2, Rect(40, 50, 260, 80), 0, 1, 1, True),
        ),
        measurer,
        content_kind=ReflowContentKind.FOOTNOTE,
    )

    assert len(plan.segments) == 2
    assert plan.segments[0].inline_runs[0].text == "aaa "
    assert plan.segments[1].inline_runs[0].text == "bbb"
    assert any(runs and runs[0].text_end <= len(candidate) for candidate, runs in measurer.calls)
    assert "".join(item.text for item in plan.segments) == text


class _InlineSizeMeasurer:
    def measure(
        self,
        text: str,
        *,
        width: float,
        height: float,
        style: ReflowStyle,
        first_segment: bool,
        inline_runs: tuple[InlineStyleRun, ...] = (),
    ) -> Measurement:
        del width, first_segment
        used = max(
            (run.font_size_points or style.font_size for run in inline_runs),
            default=style.font_size,
        )
        return Measurement(not text or used <= height, used if text else 0, 1 if text else 0)


def test_heading_orphan_decision_uses_following_body_inline_size() -> None:
    rect = Rect(40, 0, 260, 20)
    base = ReflowStyle(font_size=10, line_height=1, space_before=0, space_after=0)
    preface = FlowParagraph(
        0,
        "preface",
        1,
        "body",
        ContentDisposition.FLOWABLE_BODY,
        "preface",
        rect,
        (rect,),
        base,
    )
    heading = FlowParagraph(
        1,
        "heading",
        1,
        "heading",
        ContentDisposition.FLOWABLE_HEADING,
        "Heading",
        rect,
        (rect,),
        ReflowStyle(
            font_size=10,
            line_height=1,
            space_before=0,
            space_after=0,
            heading=True,
        ),
    )
    body_text = "body"
    body = FlowParagraph(
        2,
        "body",
        1,
        "body",
        ContentDisposition.FLOWABLE_BODY,
        body_text,
        rect,
        (rect,),
        base,
        inline_styles=InlineStyleMapping(applied=(_run(0, len(body_text), body_text, size=20),)),
    )

    plan = plan_flow(
        (preface, heading, body),
        (
            FlowRegion(1, Rect(40, 0, 260, 31), 0, 0, 1),
            FlowRegion(2, Rect(40, 0, 260, 100), 0, 1, 1, True),
        ),
        _InlineSizeMeasurer(),
    )

    heading_segment = next(item for item in plan.segments if item.occurrence_index == 1)
    body_segment = next(item for item in plan.segments if item.occurrence_index == 2)
    assert heading_segment.target_page_number == 2
    assert body_segment.target_page_number == 2


def test_pymupdf_measurement_accounts_for_inline_font_size(cyrillic_font_path: Path) -> None:
    text = "Русский Latin terminus текст " * 3
    start = text.index("Latin terminus")
    run = _run(start, start + len("Latin terminus"), "Latin terminus", size=28)
    style = ReflowStyle(font_size=10, line_height=1.2, space_before=0, space_after=0)

    with PyMuPdfMeasurer(300, 200, cyrillic_font_path) as measurer:
        plain = measurer.measure(text, width=150, height=150, style=style, first_segment=True)
        rich = measurer.measure(
            text,
            width=150,
            height=150,
            style=style,
            first_segment=True,
            inline_runs=(run,),
        )

    assert rich.used_height > plain.used_height


def test_invalid_or_overlapping_target_runs_are_rejected() -> None:
    with pytest.raises(ValueError, match="must match"):
        _run(0, 3, "toolong")

    text = "abcdef"
    first = _run(0, 3, "abc")
    second = _run(2, 5, "cde")
    with pytest.raises(ValueError, match="ordered"):
        validate_inline_style_runs(text, (first, second))


def test_rich_text_escapes_content_and_never_synthesizes_faces(
    cyrillic_font_path: Path,
) -> None:
    text = "Русский <Latin & terminus> текст"
    start = text.index("<Latin")
    run = _run(start, start + len("<Latin & terminus>"), "<Latin & terminus>")

    rich = build_rich_text(
        text,
        cyrillic_font_path,
        ReflowStyle(font_size=10, line_height=1.2, space_before=0, space_after=0),
        BLACK,
        first_line_indent=0,
        inline_runs=(run,),
    )

    assert "&lt;Latin &amp; terminus&gt;" in rich.html
    assert ".r0 { font-size: 14.000000pt; color: rgb(255, 0, 0); }" in rich.css
    assert "font-weight" not in rich.css
    assert "font-style" not in rich.css


def test_saved_pdf_preserves_selectable_inline_size_and_color(
    tmp_path: Path, cyrillic_font_path: Path
) -> None:
    text = "Русский Latin terminus текст"
    start = text.index("Latin terminus")
    run = _run(start, start + len("Latin terminus"), "Latin terminus")
    paragraph = FlowParagraph(
        occurrence_index=0,
        paragraph_id="paragraph-1",
        source_page_number=1,
        kind="body",
        disposition=ContentDisposition.FLOWABLE_BODY,
        text=text,
        source_rect=Rect(40, 40, 260, 80),
        source_fragment_rects=(Rect(40, 40, 260, 80),),
        style=ReflowStyle(font_size=10, line_height=1.2, space_before=0, space_after=0),
        inline_styles=InlineStyleMapping(applied=(run,)),
    )
    segment = PlacementSegment(
        occurrence_index=0,
        paragraph_id="paragraph-1",
        source_page_number=1,
        target_page_number=1,
        target_rect=Rect(40, 40, 260, 90),
        continuation_index=0,
        text_start=0,
        text_end=len(text),
        text=text,
        font_size=10,
        line_height=1.2,
        measured_height=30,
        line_count=2,
        color=BLACK,
        state=PlacementState.COMPLETE,
        inline_runs=(run,),
    )
    plan = LayoutPlan(
        regions=(FlowRegion(1, Rect(40, 40, 260, 100), 0, 0, 1),),
        paragraphs=(paragraph,),
        segments=(segment,),
        inserted_pages=0,
    )
    output = tmp_path / "inline-style.pdf"
    document = pymupdf.open()
    document.new_page(width=300, height=160)
    insert_reflow_segments(document, (plan,), cyrillic_font_path)
    document.save(output)
    document.close()

    validate_saved_segments(output, (plan,))
    saved = pymupdf.open(output)
    try:
        spans = [
            span
            for block in saved[0].get_text("dict")["blocks"]
            for line in block.get("lines", ())
            for span in line.get("spans", ())
        ]
        styled = [span for span in spans if "Latin terminus" in span["text"]]
        assert styled
        assert styled[0]["size"] == pytest.approx(14, abs=0.35)
        assert styled[0]["color"] == 0xFF0000
        assert "Русский" in saved[0].get_text("text")
    finally:
        saved.close()
