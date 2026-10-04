"""Explicit structural evidence exercises the ordinary shared reflow path."""
# mypy: disable-error-code="no-untyped-call"

from dataclasses import replace
from pathlib import Path

import pymupdf
import pytest

from pdftranslate.rendering.errors import OutputPdfError
from pdftranslate.rendering.inline_styles import InlineStyleRun
from pdftranslate.rendering.reflow.models import (
    ContentDisposition,
    FlowParagraph,
    FlowRegion,
    ListLayoutContract,
    OutputOccurrenceKind,
    Rect,
    ReflowAlignment,
    ReflowStyle,
)
from pdftranslate.rendering.reflow.planner import (
    Measurement,
    UnsupportedLayoutError,
    plan_flow,
)
from pdftranslate.rendering.reflow.pymupdf_layout import (
    PyMuPdfMeasurer,
    build_rich_text,
    insert_continuation_pages,
    insert_reflow_segments,
    redact_reflow_fragments,
    validate_saved_segments,
)


def _contract() -> ListLayoutContract:
    return ListLayoutContract("1.", Rect(40, 50, 50, 65), Rect(70, 50, 230, 65))


def _paragraph(text: str = "semantic content " * 100) -> FlowParagraph:
    source = Rect(40, 50, 230, 150)
    return FlowParagraph(
        0,
        "item",
        1,
        "body",
        ContentDisposition.FLOWABLE_BODY,
        text,
        source,
        (source,),
        ReflowStyle(10, 1.2, 0, 0, first_line_indent=15),
        list_layout=_contract(),
    )


def _regions() -> tuple[FlowRegion, ...]:
    return tuple(
        FlowRegion(page, Rect(40, 40, 240, 140), 0, page - 1, 1, page > 1) for page in range(1, 20)
    )


class RecordingMeasurer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float, ReflowStyle, bool]] = []

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
        self.calls.append((text, width, style, first_segment))
        # Deterministic capacity test double, not production font geometry.
        lines = 1 if text == "1." else (len(text) + 99) // 100
        used = lines * 12
        return Measurement(used <= height, used, lines)


def test_valid_contract_and_semantic_text_are_independent() -> None:
    paragraph = _paragraph("semantic only")
    assert paragraph.list_layout == _contract()
    assert _contract().marker_x == 40
    assert _contract().content_x == 70
    assert paragraph.text == "semantic only"
    assert "1." not in paragraph.text


@pytest.mark.parametrize(
    ("marker", "content"),
    [
        (Rect(80, 50, 90, 65), Rect(70, 50, 230, 65)),
        (Rect(40, 50, 80, 65), Rect(70, 50, 230, 65)),
        (Rect(float("nan"), 50, 50, 65), Rect(70, 50, 230, 65)),
        (Rect(40, 50, float("inf"), 65), Rect(70, 50, 230, 65)),
        (Rect(40, 50, 50, 65), Rect(70, 50, float("inf"), 65)),
        (Rect(40, 50, 50, 65), Rect(70, 80, 230, 95)),
        (None, Rect(70, 50, 230, 65)),
        (Rect(40, 50, 50, 65), None),
    ],
)
def test_contract_rejects_invalid_or_missing_evidence(
    marker: Rect | None,
    content: Rect | None,
) -> None:
    with pytest.raises(ValueError):
        ListLayoutContract("1.", marker, content)  # type: ignore[arg-type]


@pytest.mark.parametrize("text", ["", " ", "a b", "1.\n", "\t1."])
def test_contract_rejects_unsupported_marker_evidence(text: str) -> None:
    with pytest.raises(ValueError):
        replace(_contract(), marker_text=text)


@pytest.mark.parametrize("alignment", list(ReflowAlignment))
def test_shared_planner_geometry_and_first_occurrence_ownership(
    alignment: ReflowAlignment,
) -> None:
    paragraph = _paragraph()
    paragraph = replace(paragraph, style=replace(paragraph.style, alignment=alignment))
    measurer = RecordingMeasurer()
    plan = plan_flow((paragraph,), _regions(), measurer)
    assert len(plan.segments) > 1
    assert "".join(segment.text for segment in plan.segments) == paragraph.text
    assert all(segment.target_rect.x0 == 70 for segment in plan.segments)
    assert all(segment.first_line_indent == 0 for segment in plan.segments)
    assert all(segment.alignment is alignment for segment in plan.segments)
    marker_calls = [call for call in measurer.calls if call[0] == "1."]
    assert len(marker_calls) == 1
    assert marker_calls[0][1] == 30
    assert marker_calls[0][2].alignment is ReflowAlignment.LEFT
    semantic_calls = [call for call in measurer.calls if call[0] != "1."]
    assert all(call[1] == 170 and call[2].first_line_indent == 0 for call in semantic_calls)
    assert any(call[3] for call in semantic_calls)
    assert any(not call[3] for call in semantic_calls)
    fragment = plan.segments[0].structural_fragment
    assert fragment is not None and fragment.target_rect.x0 == 40
    assert all(segment.structural_fragment is None for segment in plan.segments[1:])
    occurrences = [item for segment in plan.segments for item in segment.output_occurrences]
    assert len({item.identity for item in occurrences}) == len(occurrences)
    marker = [item for item in occurrences if item.kind is OutputOccurrenceKind.STRUCTURAL_MARKER]
    assert len(marker) == 1 and marker[0].identity == (0, OutputOccurrenceKind.STRUCTURAL_MARKER, 0)
    assert marker[0].paragraph_id == paragraph.paragraph_id
    with pytest.raises(ValueError, match="first logical occurrence"):
        replace(plan.segments[1], structural_fragment=fragment)


def test_contract_absent_keeps_ordinary_indent_geometry() -> None:
    paragraph = replace(_paragraph("ordinary"), list_layout=None)
    measurer = RecordingMeasurer()
    plan = plan_flow((paragraph,), _regions(), measurer)
    assert plan.segments[0].target_rect.x0 == 40
    assert plan.segments[0].first_line_indent == 15
    assert measurer.calls[0][1:3] == (200, paragraph.style)
    assert plan.segments[0].structural_fragment is None
    assert len(plan.segments[0].output_occurrences) == 1


def test_ordinary_rich_text_keeps_legacy_box_origin(cyrillic_font_path: Path) -> None:
    paragraph = replace(_paragraph("ordinary"), list_layout=None)
    rich_text = build_rich_text(
        paragraph.text,
        cyrillic_font_path,
        paragraph.style,
        paragraph.color,
        first_line_indent=15,
    )
    assert rich_text.html == "<p>ordinary</p>"
    assert "body {" not in rich_text.css
    assert "text-indent: 15.000000pt" in rich_text.css


def test_marker_moves_with_first_semantic_occurrence_not_first_page() -> None:
    preface = replace(_paragraph("x" * 760), list_layout=None)
    item = replace(_paragraph(), occurrence_index=1, paragraph_id="list-item")
    plan = plan_flow((preface, item), _regions(), RecordingMeasurer())
    segments = [segment for segment in plan.segments if segment.occurrence_index == 1]
    assert segments[0].target_page_number == 2
    assert segments[0].structural_fragment is not None
    assert all(segment.structural_fragment is None for segment in segments[1:])


def test_list_geometry_outside_region_fails_closed() -> None:
    region = replace(_regions()[0], rect=Rect(45, 40, 240, 140))
    with pytest.raises(UnsupportedLayoutError, match="escapes"):
        plan_flow((_paragraph(),), (region,), RecordingMeasurer())


@pytest.mark.parametrize(
    "alignment", [ReflowAlignment.LEFT, ReflowAlignment.CENTER, ReflowAlignment.RIGHT]
)
def test_multi_page_list_saved_pdf_shared_path(
    tmp_path: Path,
    cyrillic_font_path: Path,
    alignment: ReflowAlignment,
) -> None:
    paragraph = _paragraph("Independent semantic words wrap across multiple pages. " * 40)
    paragraph = replace(paragraph, style=replace(paragraph.style, alignment=alignment))
    with PyMuPdfMeasurer(300, 200, cyrillic_font_path) as measurer:
        plan = plan_flow((paragraph,), _regions(), measurer)
    assert len(plan.segments) > 1
    output = tmp_path / "list.pdf"
    with pymupdf.open() as document:
        document.new_page(width=300, height=200)
        insert_continuation_pages(document, (plan,))
        insert_reflow_segments(document, (plan,), cyrillic_font_path)
        document.save(output)
    validate_saved_segments(output, (plan,))
    with pymupdf.open(output) as saved:
        markers = [
            span
            for page in saved
            for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", [])
            for span in line["spans"]
            if span["text"] == "1."
        ]
        assert len(markers) == 1
        assert markers[0]["bbox"][0] == pytest.approx(40, abs=0.1)
        if alignment is ReflowAlignment.LEFT:
            semantic_lines = [
                line
                for block in saved[0].get_text("dict")["blocks"]
                for line in block.get("lines", [])
                if any("Independent" in span["text"] for span in line["spans"])
            ]
            assert len(semantic_lines) > 1
            assert all(line["bbox"][0] == pytest.approx(70, abs=0.1) for line in semantic_lines)
        assert "1." not in "".join(page.get_text() for page in list(saved)[1:])
    # Same validator, not a parallel marker-only validation path.
    missing = tmp_path / "missing-marker.pdf"
    semantic_plan = replace(
        plan,
        segments=tuple(replace(item, structural_fragment=None) for item in plan.segments),
    )
    with pymupdf.open() as document:
        document.new_page(width=300, height=200)
        insert_continuation_pages(document, (semantic_plan,))
        insert_reflow_segments(document, (semantic_plan,), cyrillic_font_path)
        document.save(missing)
    with pytest.raises(OutputPdfError, match="structural_marker"):
        validate_saved_segments(missing, (plan,))


def test_marker_fit_is_measured_independently(cyrillic_font_path: Path) -> None:
    paragraph = _paragraph("fits")
    layout = ListLayoutContract("W" * 100, Rect(40, 50, 50, 65), Rect(70, 50, 230, 65))
    with (
        PyMuPdfMeasurer(300, 200, cyrillic_font_path) as measurer,
        pytest.raises(UnsupportedLayoutError, match="structural marker"),
    ):
        plan_flow((replace(paragraph, list_layout=layout),), _regions(), measurer)


def test_marker_source_evidence_joins_shared_redaction(cyrillic_font_path: Path) -> None:
    paragraph = _paragraph("semantic")
    paragraph = replace(paragraph, source_fragment_rects=(_contract().content_source_rect,))
    with PyMuPdfMeasurer(300, 200, cyrillic_font_path) as measurer:
        plan = plan_flow((paragraph,), (_regions()[0],), measurer)
    with pymupdf.open() as document:
        page = document.new_page(width=300, height=200)
        page.insert_text((40, 60), "1.")
        page.insert_text((70, 60), "semantic")
        redact_reflow_fragments(
            document,
            (plan,),
            {1: 0},
            padding=0,
            sample_background=lambda page, rect: (1.0, 1.0, 1.0),
        )
        assert not page.get_text().strip()
        insert_reflow_segments(document, (plan,), cyrillic_font_path)
        assert page.get_text().count("1.") == 1


@pytest.mark.parametrize("marker", ["+", "§", "1."])
def test_saved_contract_marker_ownership_includes_semantic_rectangle(
    tmp_path: Path, cyrillic_font_path: Path, marker: str
) -> None:
    # Explicit contract tokens are independent of automatic detection. Planned
    # marker-like semantic text, including the contract token itself, is valid.
    text = f"A. Smith compares 1.5 mm and 3.14; {marker} is a literal semantic token. " * 20
    paragraph = replace(_paragraph(text), list_layout=replace(_contract(), marker_text=marker))
    with PyMuPdfMeasurer(300, 200, cyrillic_font_path) as measurer:
        plan = plan_flow((paragraph,), _regions(), measurer)
    assert len(plan.segments) > 1
    output = tmp_path / "valid.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page(width=300, height=200)
        insert_continuation_pages(pdf, (plan,))
        insert_reflow_segments(pdf, (plan,), cyrillic_font_path)
        pdf.save(output)
    validate_saved_segments(output, (plan,))
    for defect in ("missing", "duplicate_lane", "duplicate_semantic", "continuation_semantic"):
        broken = tmp_path / f"{defect}.pdf"
        with pymupdf.open(output) as pdf:
            segment = plan.segments[1 if defect == "continuation_semantic" else 0]
            page = pdf[segment.target_page_number - 1]
            if defect == "missing":
                fragment = segment.structural_fragment
                assert fragment is not None
                rect = fragment.target_rect
                page.add_redact_annot(pymupdf.Rect(rect.x0, rect.y0 - 3, rect.x1, rect.y1 + 3))
                page.apply_redactions()
            else:
                x = 40 if defect == "duplicate_lane" else segment.target_rect.x0 + 30
                page.insert_font(fontname="probe", fontfile=str(cyrillic_font_path))
                page.insert_text(
                    (x, segment.target_rect.y0 + 9), marker, fontsize=10, fontname="probe"
                )
            pdf.save(broken)
        with pytest.raises(OutputPdfError, match="structural_marker"):
            validate_saved_segments(broken, (plan,))
