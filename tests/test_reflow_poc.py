from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

import pymupdf
import pytest
from scripts.reflow_poc.models import ContentDisposition, FlowParagraph, FlowRegion, Rect
from scripts.reflow_poc.planner import (
    CapacityError,
    Measurement,
    PlannerOptions,
    UnsupportedLayoutError,
    plan_flow,
)
from scripts.reflow_poc.pymupdf_adapter import run_poc

from pdftranslate.domain.document import TranslationMetadata, TranslationStatistics
from pdftranslate.pdf import PdfExtractor
from pdftranslate.serialization import write_document_json


class CapacityMeasurer:
    """Deterministic monospace stand-in for pure planner tests."""

    def measure(
        self,
        text: str,
        *,
        width: float,
        height: float,
        font_size: float,
        line_height: float,
    ) -> Measurement:
        characters_per_line = max(1, int(width))
        lines = math.ceil(len(text) / characters_per_line) if text else 0
        used_height = lines * font_size * line_height
        return Measurement(
            fits=used_height <= height,
            used_height=used_height,
            line_count=lines,
        )


def _paragraph(
    index: int, text: str, *, disposition: ContentDisposition | None = None
) -> FlowParagraph:
    rect = Rect(0, 0, 10, 2)
    return FlowParagraph(
        occurrence_index=index,
        paragraph_id=f"p{index}",
        source_page_number=3,
        kind="body",
        disposition=disposition or ContentDisposition.FLOWABLE_NOW,
        text=text,
        source_rect=rect,
        source_fragment_rects=(rect,),
    )


def _region(page: int, order: int, *, height: float = 60) -> FlowRegion:
    return FlowRegion(
        target_page_number=page,
        rect=Rect(0, 0, 20, height),
        column_index=0,
        order=order,
        created_page=page > 1,
    )


def _plan(paragraphs: tuple[FlowParagraph, ...], regions: tuple[FlowRegion, ...]):
    return plan_flow(
        paragraphs,
        regions,
        CapacityMeasurer(),
        source_page_number=3,
        font_path="fake.ttf",
        options=PlannerOptions(font_size=10, line_height=1, paragraph_spacing=0),
    )


def test_sequential_paragraphs_share_one_region_without_overlap_or_loss() -> None:
    paragraphs = (_paragraph(1, "alpha"), _paragraph(2, "bravo"), _paragraph(3, "charlie"))

    plan = _plan(paragraphs, (_region(1, 0),))

    assert [segment.occurrence_index for segment in plan.segments] == [1, 2, 3]
    assert {segment.target_page_number for segment in plan.segments} == {1}
    assert all(
        left.target_rect.y1 <= right.target_rect.y0
        for left, right in zip(plan.segments, plan.segments[1:], strict=False)
    )
    assert "".join(segment.text for segment in plan.segments) == "alphabravocharlie"
    assert plan.metrics.unplaced_text_count == 0


def test_region_overflow_moves_the_third_paragraph_forward() -> None:
    paragraphs = tuple(_paragraph(index, text) for index, text in enumerate(("a" * 18,) * 3))
    regions = (_region(1, 0, height=40), _region(2, 1, height=20))

    plan = _plan(paragraphs, regions)

    assert [segment.target_page_number for segment in plan.segments] == [1, 1, 2]
    assert plan.metrics.planned_paragraph_count == 3
    assert plan.metrics.new_pages_created == 1


def test_long_paragraph_spans_continuations_and_accounts_for_text_exactly_once() -> None:
    paragraph = _paragraph(4, "x" * 55)

    plan = _plan((paragraph,), (_region(1, 0, height=20), _region(2, 1, height=20)))

    assert len(plan.segments) == 2
    assert plan.metrics.planned_continuation_count == 1
    assert "".join(segment.text for segment in plan.segments) == paragraph.text
    assert [(segment.text_start, segment.text_end) for segment in plan.segments] == [
        (0, 40),
        (40, 55),
    ]


def test_non_flow_content_is_rejected() -> None:
    anchored = _paragraph(1, "header", disposition=ContentDisposition.ANCHORED_NOW)

    with pytest.raises(UnsupportedLayoutError, match="not explicitly flowable"):
        _plan((anchored,), (_region(1, 0),))


def test_exhausted_regions_fail_instead_of_returning_partial_plan() -> None:
    paragraph = _paragraph(1, "x" * 100)

    with pytest.raises(CapacityError, match="unplaced translated characters"):
        _plan((paragraph,), (_region(1, 0, height=10),))


def test_poc_pdf_is_selectable_and_continues_to_a_new_page(
    tmp_path: Path, cyrillic_font_path: Path
) -> None:
    source = _source_pdf(tmp_path / "source.pdf")
    source_before = source.read_bytes()
    extracted = PdfExtractor().extract(source)
    occurrence_index = next(
        index
        for index, paragraph in enumerate(extracted.paragraphs)
        if "Controlled body paragraph" in paragraph.text
    )
    source_paragraph = extracted.paragraphs[occurrence_index]
    translated_text = (
        "Это проверяемый перевод основного текста для переноса вперед. " * 10
    ).strip()
    translated_paragraphs = tuple(
        paragraph.model_copy(
            update={
                "translated_text": translated_text if index == occurrence_index else paragraph.text
            }
        )
        for index, paragraph in enumerate(extracted.paragraphs)
    )
    translated = extracted.model_copy(
        update={
            "schema_version": "1.3",
            "paragraphs": translated_paragraphs,
            "translation": _translation_metadata(len(translated_paragraphs)),
        }
    )
    artifact = tmp_path / "translated.json"
    write_document_json(translated, artifact)
    output = tmp_path / "poc.pdf"
    plan_path = tmp_path / "plan.json"
    source_rect = source_paragraph.bbox
    region = Rect(40, float(source_rect.y0), 260, 230)

    plan = run_poc(
        source,
        artifact,
        source_page_number=1,
        occurrence_indexes=(occurrence_index,),
        region_rect=region,
        output_path=output,
        plan_path=plan_path,
        allow_ambiguous_occurrences=(occurrence_index,) if source_paragraph.ambiguous else (),
        font_path=cyrillic_font_path,
        planner_options=PlannerOptions(font_size=14, line_height=1.2, paragraph_spacing=6),
        max_new_pages=3,
    )

    assert source.read_bytes() == source_before
    assert plan.metrics.unplaced_text_count == 0
    assert plan.metrics.new_pages_created >= 1
    assert plan.metrics.planned_continuation_count >= 1
    assert plan.metrics.output_paragraph_count == 1
    assert plan.metrics.output_extracted_character_count > 0
    assert json.loads(plan_path.read_text(encoding="utf-8"))["metrics"]["unplaced_text_count"] == 0
    rendered = pymupdf.open(output)
    try:
        output_text = " ".join(str(page.get_text("text")) for page in rendered)
        assert "проверяемый перевод" in output_text
        assert rendered.page_count == 1 + plan.metrics.new_pages_created
    finally:
        rendered.close()


def _source_pdf(path: Path) -> Path:
    document = pymupdf.open()
    page = document.new_page(width=300, height=300)
    page.insert_text((40, 25), "Running title", fontsize=8)
    page.insert_textbox(
        pymupdf.Rect(40, 50, 260, 120),
        "Controlled body paragraph with enough source words for deterministic extraction.",
        fontsize=11,
    )
    page.insert_text((40, 270), "1 Footnote remains anchored.", fontsize=7)
    document.save(path)
    document.close()
    return path


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
