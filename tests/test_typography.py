"""Deterministic source-backed typography evidence tests."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pdftranslate.domain.document import DocumentMetadata, ExtractedDocument, SourceDocument
from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox, TextBlock, TextLine, TextSpan
from pdftranslate.reconstruction import (
    LogicalParagraph,
    ParagraphFragment,
    ParagraphKind,
    ParagraphReconstruction,
    ParagraphReconstructionOptions,
    ReconstructionMetrics,
    SourceBlockMapping,
)
from pdftranslate.typography import (
    TextAlignment,
    TypographyBaseline,
    TypographyConfidence,
    TypographyProvenance,
    TypographyRole,
    extract_typography_evidence,
    normalize_source_font_name,
)

Box = tuple[float, float, float, float]


def _span(
    text: str,
    box: Box,
    *,
    font: str | None = "Source-Regular",
    size: float | None = 10,
    bold: bool | None = False,
    italic: bool | None = False,
    color: int | None = 0,
    baseline: float | None = None,
) -> TextSpan:
    return TextSpan(
        text=text,
        bbox=BoundingBox(x0=box[0], y0=box[1], x1=box[2], y1=box[3]),
        font_name=font,
        font_size=size,
        text_color=color,
        font_flags=0,
        origin=(box[0], baseline) if baseline is not None else None,
        bold=bold,
        italic=italic,
    )


def _paragraph(
    identifier: str,
    kind: ParagraphKind,
    lines: Sequence[tuple[Box, Sequence[TextSpan]]],
    *,
    page: int = 1,
) -> LogicalParagraph:
    fragments: list[ParagraphFragment] = []
    for index, (raw_box, spans) in enumerate(lines):
        box = BoundingBox(x0=raw_box[0], y0=raw_box[1], x1=raw_box[2], y1=raw_box[3])
        text = "".join(span.text for span in spans)
        fragments.append(
            ParagraphFragment(
                id=f"{identifier}-l{index + 1}",
                text=text,
                bbox=box,
                mapping=SourceBlockMapping(
                    source_block_id=identifier,
                    page_number=page,
                    bbox=box,
                    original_order=index,
                    normalized_order=index,
                    line_ids=(f"{identifier}-l{index + 1}",),
                ),
                spans=tuple(spans),
                column=0,
            )
        )
    boxes = [fragment.bbox for fragment in fragments]
    return LogicalParagraph(
        id=identifier,
        text=" ".join(fragment.text for fragment in fragments),
        kind=kind,
        anchor_page_number=page,
        bbox=BoundingBox(
            x0=min(box.x0 for box in boxes),
            y0=min(box.y0 for box in boxes),
            x1=max(box.x1 for box in boxes),
            y1=max(box.y1 for box in boxes),
        ),
        fragments=tuple(fragments),
        spans=tuple(span for fragment in fragments for span in fragment.spans),
    )


def _simple_paragraph(
    identifier: str,
    boxes: Sequence[Box],
    *,
    kind: ParagraphKind = ParagraphKind.BODY,
    font: str = "Source-Regular",
    size: float = 10,
    bold: bool = False,
    italic: bool = False,
    color: int = 0,
) -> LogicalParagraph:
    return _paragraph(
        identifier,
        kind,
        tuple(
            (
                box,
                (
                    _span(
                        f"line {index} has meaningful source text",
                        box,
                        font=font,
                        size=size,
                        bold=bold,
                        italic=italic,
                        color=color,
                        baseline=box[1] + 9,
                    ),
                ),
            )
            for index, box in enumerate(boxes)
        ),
    )


def _document(*paragraphs: LogicalParagraph, width: float = 600) -> ExtractedDocument:
    blocks: dict[str, TextBlock] = {}
    for paragraph in paragraphs:
        if paragraph.id in blocks:
            continue
        lines = tuple(
            TextLine(
                id=fragment.id,
                text=fragment.text,
                bbox=fragment.bbox,
                original_order=index,
                spans=fragment.spans,
            )
            for index, fragment in enumerate(paragraph.fragments)
        )
        blocks[paragraph.id] = TextBlock(
            id=paragraph.id,
            text=paragraph.text,
            bbox=paragraph.bbox,
            original_order=len(blocks),
            normalized_order=len(blocks),
            spans=paragraph.spans,
            lines=lines,
        )
    page = ExtractedPage(
        page_number=1,
        source_index=0,
        width=width,
        height=800,
        rotation=0,
        classification=PageClassification.TEXT,
        text_blocks=tuple(blocks.values()),
    )
    return ExtractedDocument(
        schema_version="1.2",
        source=SourceDocument(path="fixture.pdf", file_size=1, sha256="0" * 64),
        page_count=1,
        selected_pages=(1,),
        metadata=DocumentMetadata(),
        encrypted=False,
        password_required=False,
        pages=(page,),
        paragraphs=paragraphs,
        reconstruction=ParagraphReconstruction(
            mode="conservative",
            options=ParagraphReconstructionOptions(),
            metrics=ReconstructionMetrics(
                raw_blocks=len(blocks),
                raw_lines=sum(len(item.lines) for item in blocks.values()),
                logical_paragraphs=len(paragraphs),
                merged_fragments=0,
                ambiguous_decisions=0,
                cross_page_merges=0,
                soft_hyphens_removed=0,
            ),
        ),
    )


def _evidence(*paragraphs: LogicalParagraph, index: int = 0):
    return extract_typography_evidence(_document(*paragraphs)).paragraphs[index]


def test_dominant_font_size_ignores_small_superscript_noise() -> None:
    box = (50.0, 100.0, 500.0, 112.0)
    paragraph = _paragraph(
        "p1",
        ParagraphKind.BODY,
        ((box, (_span("Meaningful main text", box, size=11), _span("1", box, size=6))),),
    )

    result = _evidence(paragraph)

    assert result.font_size_points.value == 11
    assert result.mixed_styles.mixed_font_size is True


def test_font_name_normalization_removes_only_standard_subset_prefix() -> None:
    assert normalize_source_font_name("ABCDEE+MinionPro-Regular") == "MinionPro-Regular"
    assert normalize_source_font_name("AGaramondPro-Regular+f6") == "AGaramondPro-Regular+f6"


def test_explicit_bold_evidence_is_high_confidence() -> None:
    result = _evidence(_simple_paragraph("p1", ((50, 100, 500, 112),), bold=True))

    assert result.bold.value is True
    assert result.bold.confidence is TypographyConfidence.HIGH
    assert result.bold.provenance == (TypographyProvenance.SPAN_FLAGS,)


def test_explicit_italic_evidence_is_high_confidence() -> None:
    result = _evidence(_simple_paragraph("p1", ((50, 100, 500, 112),), italic=True))

    assert result.italic.value is True
    assert result.italic.confidence is TypographyConfidence.HIGH


def test_conflicting_weight_remains_visible() -> None:
    box = (50.0, 100.0, 500.0, 112.0)
    paragraph = _paragraph(
        "p1",
        ParagraphKind.BODY,
        ((box, (_span("regular text", box), _span("bold", box, bold=True))),),
    )

    result = _evidence(paragraph)

    assert result.bold.value is False
    assert result.bold.confidence is TypographyConfidence.MEDIUM
    assert result.mixed_styles.mixed_weight is True


def test_packed_color_becomes_normalized_rgb() -> None:
    result = _evidence(_simple_paragraph("p1", ((50, 100, 500, 112),), color=0x12A0FF))

    assert result.color_rgb.value is not None
    assert result.color_rgb.value.model_dump() == {"red": 0x12, "green": 0xA0, "blue": 0xFF}


def test_left_alignment_uses_stable_left_edges() -> None:
    result = _evidence(
        _simple_paragraph("p1", ((50, 100, 500, 112), (50, 112, 460, 124), (50, 124, 320, 136)))
    )

    assert result.alignment.value is TextAlignment.LEFT


def test_center_alignment_uses_stable_line_centers() -> None:
    result = _evidence(
        _simple_paragraph("p1", ((200, 100, 400, 112), (220, 112, 380, 124), (240, 124, 360, 136)))
    )

    assert result.alignment.value is TextAlignment.CENTER


def test_justified_alignment_uses_full_nonfinal_lines_and_short_final_line() -> None:
    result = _evidence(
        _simple_paragraph("p1", ((50, 100, 500, 112), (50, 112, 501, 124), (50, 124, 300, 136)))
    )

    assert result.alignment.value is TextAlignment.JUSTIFIED


def test_ambiguous_alignment_remains_unknown() -> None:
    result = _evidence(_simple_paragraph("p1", ((120, 100, 400, 112), (160, 112, 450, 124))))

    assert result.alignment.value is TextAlignment.UNKNOWN
    assert result.alignment.confidence is TypographyConfidence.UNKNOWN


def test_line_height_uses_source_baseline_distance() -> None:
    result = _evidence(
        _simple_paragraph("p1", ((50, 91, 500, 103), (50, 103, 500, 115), (50, 115, 300, 127)))
    )

    assert result.line_height_points.value == 12
    assert result.line_height_ratio.value == 1.2
    assert result.line_height_points.confidence is TypographyConfidence.MEDIUM


def test_single_line_has_unknown_line_height() -> None:
    result = _evidence(_simple_paragraph("p1", ((50, 100, 500, 112),)))

    assert result.line_height_points.value is None
    assert result.line_height_points.confidence is TypographyConfidence.UNKNOWN


def test_first_line_indent_is_distinct_from_following_lines() -> None:
    result = _evidence(
        _simple_paragraph("p1", ((70, 100, 500, 112), (50, 112, 500, 124), (50, 124, 300, 136)))
    )

    assert result.first_line_indent_points.value == 20


def test_whole_paragraph_indents_are_relative_to_role_region() -> None:
    reference = _simple_paragraph("reference", ((50, 50, 500, 62), (50, 62, 300, 74)))
    indented = _simple_paragraph("indented", ((80, 100, 470, 112), (80, 112, 300, 124)))

    result = _evidence(reference, indented, index=1)

    assert result.left_indent_points.value == 30
    assert result.right_indent_points.value == 30


def test_footnote_role_and_smaller_source_size_are_retained() -> None:
    result = _evidence(
        _simple_paragraph(
            "footnote",
            ((50, 500, 500, 510), (50, 510, 300, 520)),
            kind=ParagraphKind.FOOTNOTE,
            size=8,
        )
    )

    assert result.role.value is TypographyRole.FOOTNOTE
    assert result.font_size_points.value == 8


def test_heading_role_and_style_remain_distinct() -> None:
    body = _simple_paragraph("body", ((50, 100, 500, 112),), size=10)
    heading = _simple_paragraph(
        "heading", ((180, 50, 420, 66),), kind=ParagraphKind.HEADING, size=15, bold=True
    )

    result = _evidence(body, heading, index=1)

    assert result.role.value is TypographyRole.HEADING
    assert result.font_size_points.value == 15
    assert result.bold.value is True


def test_mixed_inline_style_flags_cover_all_supported_properties() -> None:
    box = (50.0, 100.0, 500.0, 112.0)
    paragraph = _paragraph(
        "mixed",
        ParagraphKind.BODY,
        (
            (
                box,
                (
                    _span("plain source text", box),
                    _span(
                        "variant",
                        box,
                        font="Other-Italic",
                        size=12,
                        bold=True,
                        italic=True,
                        color=0xFF0000,
                    ),
                ),
            ),
        ),
    )

    mixed = _evidence(paragraph).mixed_styles

    assert all(mixed.model_dump().values())


def test_duplicate_paragraph_ids_keep_authoritative_occurrence_indexes() -> None:
    first = _simple_paragraph("duplicate", ((50, 100, 500, 112),))
    second = _simple_paragraph("duplicate", ((50, 150, 500, 162),))

    baseline = extract_typography_evidence(_document(first, second))

    assert [item.paragraph_id for item in baseline.paragraphs] == ["duplicate", "duplicate"]
    assert [item.occurrence_index for item in baseline.paragraphs] == [0, 1]


def test_baseline_serialization_is_typed_and_round_trips() -> None:
    baseline = extract_typography_evidence(
        _document(_simple_paragraph("p1", ((50, 100, 500, 112),)))
    )

    restored = TypographyBaseline.model_validate_json(baseline.model_dump_json())

    assert restored == baseline
    assert restored.paragraphs[0].font_size_points.confidence is TypographyConfidence.HIGH


def test_typography_extraction_does_not_mutate_rendering_input() -> None:
    document = _document(_simple_paragraph("p1", ((50, 100, 500, 112), (50, 112, 300, 124))))
    before = document.model_dump_json()

    extract_typography_evidence(document)

    assert document.model_dump_json() == before


def test_spacing_uses_only_canonical_observed_gap_before() -> None:
    previous = _simple_paragraph("previous", ((50, 100, 500, 112),))
    current = _simple_paragraph("current", ((50, 124, 500, 136),))

    result = _evidence(previous, current, index=1)

    assert result.space_before_points.value == pytest.approx(12)
    assert result.space_before_points.confidence is TypographyConfidence.LOW
    assert result.space_after_points.value is None
