"""Focused generated-fixture tests for logical paragraph reconstruction."""

from __future__ import annotations

from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox, TextBlock, TextLine, TextSpan
from pdftranslate.reconstruction import (
    DecisionAction,
    ParagraphKind,
    ParagraphReconstructionOptions,
    reconstruct_paragraphs,
)


def _block(
    identifier: str,
    text: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    order: int,
    *,
    font_size: float = 10,
) -> TextBlock:
    box = BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)
    span = TextSpan(text=text, bbox=box, font_size=font_size)
    line = TextLine(
        id=f"{identifier}-l1",
        text=text,
        bbox=box,
        original_order=0,
        spans=(span,),
    )
    return TextBlock(
        id=identifier,
        text=text,
        bbox=box,
        original_order=order,
        normalized_order=order,
        spans=(span,),
        lines=(line,),
    )


def _page(number: int, *blocks: TextBlock) -> ExtractedPage:
    return ExtractedPage(
        page_number=number,
        source_index=number - 1,
        width=600,
        height=800,
        rotation=0,
        classification=PageClassification.TEXT,
        text_blocks=blocks,
    )


def test_reconstructs_wrapped_text_and_soft_hyphen_with_mapping() -> None:
    page = _page(
        1,
        _block("p1-b1", "A deterministic para-", 50, 100, 500, 112, 0),
        _block("p1-b2", "graph continues on the next line", 50, 114, 500, 126, 1),
    )

    result = reconstruct_paragraphs((page,))

    assert tuple(item.text for item in result.paragraphs) == (
        "A deterministic paragraph continues on the next line",
    )
    assert tuple(
        fragment.mapping.source_block_id for fragment in result.paragraphs[0].fragments
    ) == ("p1-b1", "p1-b2")
    assert result.evidence.metrics.soft_hyphens_removed == 1


def test_preserves_legitimate_hyphens_and_list_item_boundaries() -> None:
    page = _page(
        1,
        _block("p1-b1", "A well-", 50, 100, 500, 112, 0),
        _block("p1-b2", "known term remains protected.", 50, 114, 500, 126, 1),
        _block("p1-b3", "1. First item", 50, 150, 500, 162, 2),
        _block("p1-b4", "2. Second item", 50, 164, 500, 176, 3),
    )

    result = reconstruct_paragraphs((page,))

    assert result.paragraphs[0].text.startswith("A well- known")
    assert [item.kind for item in result.paragraphs[-2:]] == [
        ParagraphKind.LIST_ITEM,
        ParagraphKind.LIST_ITEM,
    ]


def test_orders_columns_without_merging_across_the_gutter() -> None:
    page = _page(
        1,
        _block("left-1", "Left column starts", 40, 100, 260, 112, 0),
        _block("right-1", "Right column starts", 340, 100, 560, 112, 1),
        _block("left-2", "and continues here.", 40, 114, 260, 126, 2),
        _block("right-2", "and continues there.", 340, 114, 560, 126, 3),
    )

    result = reconstruct_paragraphs((page,))

    assert [item.text for item in result.paragraphs] == [
        "Left column starts and continues here.",
        "Right column starts and continues there.",
    ]
    assert all(
        decision.action is not DecisionAction.MERGE
        for decision in result.evidence.decisions
        if "left" in decision.previous_fragment_id and "right" in decision.current_fragment_id
    )


def test_cross_page_merge_requires_strong_edge_evidence() -> None:
    first = _page(1, _block("p1-tail", "Sentence continues", 50, 760, 500, 774, 0))
    second = _page(2, _block("p2-head", "on the next page.", 50, 20, 500, 34, 0))

    result = reconstruct_paragraphs((first, second))

    assert len(result.paragraphs) == 1
    assert result.paragraphs[0].text == "Sentence continues on the next page."
    assert result.evidence.metrics.cross_page_merges == 1
    assert {fragment.mapping.page_number for fragment in result.paragraphs[0].fragments} == {
        1,
        2,
    }


def test_off_mode_keeps_one_logical_unit_per_physical_block() -> None:
    page = _page(
        1,
        _block("p1-b1", "First unfinished", 50, 100, 500, 112, 0),
        _block("p1-b2", "continuation", 50, 114, 500, 126, 1),
    )

    result = reconstruct_paragraphs((page,), ParagraphReconstructionOptions(mode="off"))

    assert [item.id for item in result.paragraphs] == ["p1-b1", "p1-b2"]
    assert result.evidence.decisions == ()
