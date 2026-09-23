"""Deterministic role-aware style reconstruction tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.typography_inspect import validate_output_destination

from pdftranslate.typography import (
    FontRole,
    MixedStyleEvidence,
    ParagraphTypographyEvidence,
    ResolvedStyleDocument,
    RgbColor,
    StyleDecisionSource,
    TextAlignment,
    TypographyBaseline,
    TypographyConfidence,
    TypographyFallback,
    TypographyProperty,
    TypographyProvenance,
    TypographyRole,
    build_document_style_baseline,
    infer_font_role,
    normalize_font_family_group,
    reconstruct_styles,
    resolve_paragraph_style,
)


def _property[T](
    value: T | None,
    confidence: TypographyConfidence = TypographyConfidence.HIGH,
    fallback: TypographyFallback = TypographyFallback.PRESERVE_UNKNOWN,
) -> TypographyProperty[T]:
    return TypographyProperty(
        value=value,
        confidence=confidence,
        provenance=(TypographyProvenance.SOURCE_SPAN,),
        fallback=fallback,
    )


def _unknown[T](fallback: TypographyFallback) -> TypographyProperty[T]:
    return _property(None, TypographyConfidence.UNKNOWN, fallback)


def _evidence(
    index: int,
    *,
    identifier: str | None = None,
    role: TypographyRole = TypographyRole.BODY,
    font_name: str | None = "AGaramondPro-Regular",
    font_size: float | None = 10.0,
    confidence: TypographyConfidence = TypographyConfidence.HIGH,
    **updates: object,
) -> ParagraphTypographyEvidence:
    item = ParagraphTypographyEvidence(
        occurrence_index=index,
        paragraph_id=identifier or f"p{index}",
        source_page_number=1,
        text_preview=f"paragraph {index}",
        role=_property(role),
        source_font_name=_property(font_name, confidence, TypographyFallback.RENDERER_DEFAULT_FONT),
        font_size_points=_property(
            font_size, confidence, TypographyFallback.RENDERER_DEFAULT_FONT_SIZE
        ),
        bold=_property(False, confidence, TypographyFallback.REGULAR),
        italic=_property(False, confidence, TypographyFallback.NON_ITALIC),
        color_rgb=_property(RgbColor(red=0, green=0, blue=0), confidence, TypographyFallback.BLACK),
        alignment=_property(
            TextAlignment.LEFT, TypographyConfidence.MEDIUM, TypographyFallback.LEFT
        ),
        line_height_points=_property(
            12.0, TypographyConfidence.MEDIUM, TypographyFallback.DEFAULT_LINE_HEIGHT
        ),
        line_height_ratio=_property(
            1.2, TypographyConfidence.MEDIUM, TypographyFallback.DEFAULT_LINE_HEIGHT
        ),
        first_line_indent_points=_property(
            0.0, TypographyConfidence.MEDIUM, TypographyFallback.ZERO_INDENT
        ),
        left_indent_points=_property(
            0.0, TypographyConfidence.MEDIUM, TypographyFallback.ZERO_INDENT
        ),
        right_indent_points=_property(
            0.0, TypographyConfidence.MEDIUM, TypographyFallback.ZERO_INDENT
        ),
        space_before_points=_unknown(TypographyFallback.ZERO_SPACING),
        space_after_points=_unknown(TypographyFallback.ZERO_SPACING),
        mixed_styles=MixedStyleEvidence(
            mixed_font_family=False,
            mixed_font_size=False,
            mixed_weight=False,
            mixed_italic=False,
            mixed_color=False,
        ),
    )
    return item.model_copy(update=updates)


def _typography(*items: ParagraphTypographyEvidence) -> TypographyBaseline:
    return TypographyBaseline(source_sha256="0" * 64, paragraphs=items)


def test_direct_high_confidence_evidence_wins() -> None:
    evidence = _evidence(0, font_size=13.0)
    baseline = build_document_style_baseline(_typography(evidence, _evidence(1)))

    resolved = resolve_paragraph_style(evidence, baseline)

    assert resolved.font_size_points == 13.0
    assert resolved.decisions.font_size_points.source is StyleDecisionSource.TYPOGRAPHY_EVIDENCE
    assert resolved.decisions.font_size_points.used_fallback is False


def test_medium_confidence_evidence_is_accepted() -> None:
    evidence = _evidence(
        0,
        font_size_points=_property(
            12.5,
            TypographyConfidence.MEDIUM,
            TypographyFallback.RENDERER_DEFAULT_FONT_SIZE,
        ),
    )
    baseline = build_document_style_baseline(_typography(evidence))

    resolved = resolve_paragraph_style(evidence, baseline)

    assert resolved.font_size_points == 12.5
    assert resolved.decisions.font_size_points.confidence is TypographyConfidence.MEDIUM


def test_low_confidence_evidence_uses_stable_role_baseline() -> None:
    stable = (_evidence(0, font_size=10.0), _evidence(1, font_size=10.2))
    low = _evidence(
        2,
        font_size_points=_property(
            40.0,
            TypographyConfidence.LOW,
            TypographyFallback.RENDERER_DEFAULT_FONT_SIZE,
        ),
    )
    baseline = build_document_style_baseline(_typography(*stable, low))

    resolved = resolve_paragraph_style(low, baseline)

    assert resolved.font_size_points == pytest.approx(10.1)
    assert resolved.decisions.font_size_points.source is StyleDecisionSource.ROLE_BASELINE
    assert resolved.decisions.font_size_points.evidence_value == 40.0


def test_unknown_body_font_size_uses_body_baseline() -> None:
    unknown = _evidence(
        2,
        font_size=None,
        confidence=TypographyConfidence.UNKNOWN,
    )
    typography = _typography(_evidence(0, font_size=10.0), _evidence(1, font_size=10.0), unknown)
    baseline = build_document_style_baseline(typography)

    resolved = resolve_paragraph_style(unknown, baseline)

    assert resolved.font_size_points == 10.0
    assert resolved.decisions.font_size_points.source is StyleDecisionSource.ROLE_BASELINE


def test_footnote_fallback_is_isolated_from_body() -> None:
    unknown_note = _evidence(
        4,
        role=TypographyRole.FOOTNOTE,
        font_size=None,
        confidence=TypographyConfidence.UNKNOWN,
    )
    typography = _typography(
        _evidence(0, font_size=11.0),
        _evidence(1, font_size=11.0),
        _evidence(2, role=TypographyRole.FOOTNOTE, font_size=8.0),
        _evidence(3, role=TypographyRole.FOOTNOTE, font_size=8.0),
        unknown_note,
    )
    baseline = build_document_style_baseline(typography)

    resolved = resolve_paragraph_style(unknown_note, baseline)

    assert resolved.font_size_points == 8.0
    assert resolved.font_size_points != baseline.body.font_size_points.value  # type: ignore[union-attr]


def test_heading_baseline_is_absent_without_heading_occurrences() -> None:
    baseline = build_document_style_baseline(_typography(_evidence(0), _evidence(1)))

    assert baseline.heading is None


def test_stable_role_baseline_requires_two_supported_samples() -> None:
    one = build_document_style_baseline(_typography(_evidence(0, font_size=10.0)))
    two = build_document_style_baseline(
        _typography(_evidence(0, font_size=10.0), _evidence(1, font_size=10.2))
    )

    assert one.body is not None and one.body.font_size_points.stable is False
    assert two.body is not None and two.body.font_size_points.stable is True


def test_numeric_outlier_does_not_redefine_role_baseline() -> None:
    baseline = build_document_style_baseline(
        _typography(
            _evidence(0, font_size=10.0),
            _evidence(1, font_size=10.2),
            _evidence(2, font_size=40.0),
        )
    )

    assert baseline.body is not None
    assert baseline.body.font_size_points.stable is True
    assert baseline.body.font_size_points.value == pytest.approx(10.1)
    assert baseline.body.font_size_points.support_count == 2


def test_source_font_identity_and_family_group_remain_distinct() -> None:
    evidence = _evidence(0, font_name="AGaramondPro-BoldItalic")
    resolved = reconstruct_styles(_typography(evidence)).paragraphs[0]

    assert resolved.source_font_name == "AGaramondPro-BoldItalic"
    assert resolved.source_font_family_group == "AGaramondPro"
    assert normalize_font_family_group("ArbitraryDisplay") == "ArbitraryDisplay"
    assert (
        resolved.decisions.source_font_family_group.source
        is StyleDecisionSource.NORMALIZED_SOURCE_VALUE
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("AGaramondPro-Regular", FontRole.SERIF),
        ("HelveticaNeue", FontRole.SANS_SERIF),
        ("CourierNew", FontRole.MONOSPACE),
        ("UnclassifiedDisplay", FontRole.UNKNOWN),
    ],
)
def test_font_role_inference(name: str, expected: FontRole) -> None:
    assert infer_font_role(name) is expected


def test_bold_and_italic_reconstruction_is_explicit() -> None:
    evidence = _evidence(
        0,
        bold=_property(True, TypographyConfidence.HIGH, TypographyFallback.REGULAR),
        italic=_property(True, TypographyConfidence.MEDIUM, TypographyFallback.NON_ITALIC),
    )
    resolved = reconstruct_styles(_typography(evidence)).paragraphs[0]

    assert resolved.bold is True
    assert resolved.italic is True
    assert resolved.decisions.bold.source is StyleDecisionSource.TYPOGRAPHY_EVIDENCE
    assert resolved.decisions.italic.source is StyleDecisionSource.TYPOGRAPHY_EVIDENCE


def test_mixed_style_flags_survive_reconstruction() -> None:
    mixed = MixedStyleEvidence(
        mixed_font_family=True,
        mixed_font_size=True,
        mixed_weight=True,
        mixed_italic=True,
        mixed_color=True,
    )
    resolved = reconstruct_styles(_typography(_evidence(0, mixed_styles=mixed))).paragraphs[0]

    assert resolved.mixed_styles == mixed


def test_document_color_is_the_only_cross_role_fallback() -> None:
    unknown_color = _evidence(
        2,
        role=TypographyRole.FOOTNOTE,
        color_rgb=_unknown(TypographyFallback.BLACK),
    )
    typography = _typography(_evidence(0), _evidence(1), unknown_color)
    baseline = build_document_style_baseline(typography)

    resolved = resolve_paragraph_style(unknown_color, baseline)

    assert resolved.color_rgb == RgbColor(red=0, green=0, blue=0)
    assert resolved.decisions.color_rgb.source is StyleDecisionSource.DOCUMENT_BASELINE


@pytest.mark.parametrize("alignment", [TextAlignment.JUSTIFIED, TextAlignment.CENTER])
def test_supported_alignment_is_retained(alignment: TextAlignment) -> None:
    evidence = _evidence(
        0,
        alignment=_property(alignment, TypographyConfidence.MEDIUM, TypographyFallback.LEFT),
    )
    resolved = reconstruct_styles(_typography(evidence)).paragraphs[0]

    assert resolved.alignment is alignment
    assert resolved.decisions.alignment.used_fallback is False


def test_unknown_alignment_uses_traceable_safe_fallback() -> None:
    evidence = _evidence(
        0,
        alignment=_property(
            TextAlignment.UNKNOWN, TypographyConfidence.UNKNOWN, TypographyFallback.LEFT
        ),
    )
    resolved = reconstruct_styles(_typography(evidence)).paragraphs[0]

    assert resolved.alignment is TextAlignment.LEFT
    assert resolved.decisions.alignment.source is StyleDecisionSource.SAFE_RENDER_DEFAULT
    assert resolved.decisions.alignment.used_fallback is True
    assert resolved.decisions.alignment.fallback_reason


def test_line_height_and_indentation_reconstruction() -> None:
    evidence = _evidence(
        0,
        line_height_ratio=_property(
            1.138, TypographyConfidence.MEDIUM, TypographyFallback.DEFAULT_LINE_HEIGHT
        ),
        first_line_indent_points=_property(
            11.0, TypographyConfidence.MEDIUM, TypographyFallback.ZERO_INDENT
        ),
        left_indent_points=_property(
            2.0, TypographyConfidence.MEDIUM, TypographyFallback.ZERO_INDENT
        ),
        right_indent_points=_property(
            3.0, TypographyConfidence.MEDIUM, TypographyFallback.ZERO_INDENT
        ),
    )
    resolved = reconstruct_styles(_typography(evidence)).paragraphs[0]

    assert resolved.line_height_ratio == 1.138
    assert resolved.first_line_indent_points == 11.0
    assert (resolved.left_indent_points, resolved.right_indent_points) == (2.0, 3.0)


def test_spacing_represents_one_physical_gap_only_once() -> None:
    evidence = _evidence(
        0,
        space_before_points=_property(
            6.0, TypographyConfidence.MEDIUM, TypographyFallback.ZERO_SPACING
        ),
        space_after_points=_property(
            9.0, TypographyConfidence.HIGH, TypographyFallback.ZERO_SPACING
        ),
    )
    resolved = reconstruct_styles(_typography(evidence)).paragraphs[0]

    assert resolved.space_before_points == 6.0
    assert resolved.space_after_points == 0.0
    assert resolved.decisions.space_after_points.used_fallback is True


def test_duplicate_paragraph_ids_preserve_occurrence_identity() -> None:
    reconstructed = reconstruct_styles(
        _typography(_evidence(0, identifier="duplicate"), _evidence(1, identifier="duplicate"))
    )

    assert [item.paragraph_id for item in reconstructed.paragraphs] == ["duplicate", "duplicate"]
    assert [item.occurrence_index for item in reconstructed.paragraphs] == [0, 1]


def test_resolved_document_serialization_round_trips() -> None:
    reconstructed = reconstruct_styles(_typography(_evidence(0), _evidence(1)))

    restored = ResolvedStyleDocument.model_validate_json(reconstructed.model_dump_json())

    assert restored == reconstructed
    assert restored.schema_version == "1.0"


def test_reconstruction_does_not_mutate_typography_input() -> None:
    typography = _typography(_evidence(0), _evidence(1))
    before = typography.model_dump_json()

    reconstruct_styles(typography)

    assert typography.model_dump_json() == before


def test_inspection_output_cannot_alias_source_pdf(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"

    with pytest.raises(ValueError, match="must not resolve to the source PDF"):
        validate_output_destination(source, source)


def test_inspection_output_accepts_distinct_destination(tmp_path: Path) -> None:
    validate_output_destination(tmp_path / "source.pdf", tmp_path / "style.json")
