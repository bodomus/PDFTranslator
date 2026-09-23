"""Pure role-aware style reconstruction from source typography evidence."""

from __future__ import annotations

import re
import statistics
from collections import Counter
from collections.abc import Callable, Hashable, Iterable, Sequence

from pdftranslate.typography.models import (
    ParagraphTypographyEvidence,
    RgbColor,
    TextAlignment,
    TypographyBaseline,
    TypographyConfidence,
    TypographyProperty,
    TypographyRole,
)
from pdftranslate.typography.style_models import (
    DocumentStyleBaseline,
    FontRole,
    ParagraphStyleDecisions,
    ResolvedParagraphStyle,
    ResolvedStyleDocument,
    RoleStyleBaseline,
    StyleBaselineValue,
    StyleDecision,
    StyleDecisionSource,
    StyleStabilityPolicy,
)

_ACCEPTED_CONFIDENCE = {TypographyConfidence.HIGH, TypographyConfidence.MEDIUM}
_STYLE_SUFFIX = re.compile(
    r"(?i)(?:[-_, ](?:bolditalic|boldoblique|semibolditalic|semibold|demibold|"
    r"regular|roman|book|medium|bold|italic|oblique))+$"
)
_BLACK = RgbColor(red=0, green=0, blue=0)


def normalize_font_family_group(source_name: str) -> str:
    """Remove only recognized terminal face-style tokens from a source font name."""
    normalized = source_name.strip()
    grouped = _STYLE_SUFFIX.sub("", normalized).rstrip("-_, ")
    return grouped or normalized


def infer_font_role(source_name: str | None) -> FontRole:
    """Infer only a conservative generic role; never resolve a local font file."""
    if not source_name:
        return FontRole.UNKNOWN
    lowered = source_name.casefold().replace(" ", "")
    if any(token in lowered for token in ("mono", "courier", "consolas", "typewriter")):
        return FontRole.MONOSPACE
    if any(
        token in lowered
        for token in ("sans", "arial", "helvetica", "calibri", "segoe", "verdana", "tahoma")
    ):
        return FontRole.SANS_SERIF
    if any(
        token in lowered
        for token in (
            "serif",
            "garamond",
            "times",
            "georgia",
            "minion",
            "baskerville",
            "palatino",
            "cambria",
        )
    ):
        return FontRole.SERIF
    return FontRole.UNKNOWN


def build_document_style_baseline(
    typography: TypographyBaseline,
    *,
    policy: StyleStabilityPolicy | None = None,
) -> DocumentStyleBaseline:
    """Build robust role-isolated aggregates from an immutable typography baseline."""
    settings = policy or StyleStabilityPolicy()
    grouped = {
        role: tuple(item for item in typography.paragraphs if _evidence_role(item) is role)
        for role in TypographyRole
    }
    return DocumentStyleBaseline(
        source_sha256=typography.source_sha256,
        policy=settings,
        body=_role_baseline(TypographyRole.BODY, grouped[TypographyRole.BODY], settings),
        heading=_role_baseline(TypographyRole.HEADING, grouped[TypographyRole.HEADING], settings),
        footnote=_role_baseline(
            TypographyRole.FOOTNOTE, grouped[TypographyRole.FOOTNOTE], settings
        ),
        other=_role_baseline(TypographyRole.OTHER, grouped[TypographyRole.OTHER], settings),
        global_color_rgb=_categorical_baseline(
            _accepted(item.color_rgb for item in typography.paragraphs), settings
        ),
    )


def resolve_paragraph_style(
    evidence: ParagraphTypographyEvidence,
    baseline: DocumentStyleBaseline,
) -> ResolvedParagraphStyle:
    """Resolve one paragraph without mutating evidence or consulting rendering/PDF state."""
    role_decision = _role_decision(evidence.role)
    role = role_decision.value
    role_baseline = baseline.for_role(role)

    source_name_decision = _source_identity_decision(evidence.source_font_name)
    family_decision = _family_decision(evidence.source_font_name, role_baseline)
    font_role_decision = _font_role_decision(evidence.source_font_name, role_baseline)
    font_size_decision = _resolve(
        evidence.font_size_points,
        role_baseline.font_size_points if role_baseline else None,
        11.0,
        "no reliable font-size evidence or stable same-role baseline",
    )
    bold_decision = _resolve(
        evidence.bold,
        role_baseline.bold if role_baseline else None,
        False,
        "no reliable weight evidence or stable same-role baseline",
    )
    italic_decision = _resolve(
        evidence.italic,
        role_baseline.italic if role_baseline else None,
        False,
        "no reliable italic evidence or stable same-role baseline",
    )
    color_decision = _resolve(
        evidence.color_rgb,
        role_baseline.color_rgb if role_baseline else None,
        _BLACK,
        "no reliable color evidence or stable baseline",
        document_baseline=baseline.global_color_rgb,
    )
    alignment_decision = _resolve(
        evidence.alignment,
        role_baseline.alignment if role_baseline else None,
        TextAlignment.LEFT,
        "no reliable alignment evidence or stable same-role baseline",
        invalid=lambda value: value is TextAlignment.UNKNOWN,
    )
    line_height_decision = _resolve(
        evidence.line_height_ratio,
        role_baseline.line_height_ratio if role_baseline else None,
        1.2,
        "no reliable line-height evidence or stable same-role baseline",
    )
    first_indent_decision = _resolve(
        evidence.first_line_indent_points,
        role_baseline.first_line_indent_points if role_baseline else None,
        0.0,
        "no reliable first-line indent evidence or stable same-role baseline",
    )
    left_indent_decision = _resolve(
        evidence.left_indent_points,
        role_baseline.left_indent_points if role_baseline else None,
        0.0,
        "no reliable left-indent evidence or stable same-role baseline",
    )
    right_indent_decision = _resolve(
        evidence.right_indent_points,
        role_baseline.right_indent_points if role_baseline else None,
        0.0,
        "no reliable right-indent evidence or stable same-role baseline",
    )
    space_before_decision = _resolve(
        evidence.space_before_points,
        role_baseline.space_before_points if role_baseline else None,
        0.0,
        "no reliable gap-before evidence or stable same-role baseline",
    )
    space_after_decision = StyleDecision(
        value=0.0,
        evidence_value=evidence.space_after_points.value,
        evidence_confidence=evidence.space_after_points.confidence,
        source=StyleDecisionSource.SAFE_RENDER_DEFAULT,
        confidence=TypographyConfidence.HIGH,
        used_fallback=True,
        fallback_reason="one physical paragraph gap is represented only as space_before",
    )

    decisions = ParagraphStyleDecisions(
        role=role_decision,
        source_font_name=source_name_decision,
        source_font_family_group=family_decision,
        font_role=font_role_decision,
        font_size_points=font_size_decision,
        bold=bold_decision,
        italic=italic_decision,
        color_rgb=color_decision,
        alignment=alignment_decision,
        line_height_ratio=line_height_decision,
        first_line_indent_points=first_indent_decision,
        left_indent_points=left_indent_decision,
        right_indent_points=right_indent_decision,
        space_before_points=space_before_decision,
        space_after_points=space_after_decision,
    )
    fallback_count = sum(
        decision.used_fallback
        for decision in (
            role_decision,
            source_name_decision,
            family_decision,
            font_role_decision,
            font_size_decision,
            bold_decision,
            italic_decision,
            color_decision,
            alignment_decision,
            line_height_decision,
            first_indent_decision,
            left_indent_decision,
            right_indent_decision,
            space_before_decision,
            space_after_decision,
        )
    )
    return ResolvedParagraphStyle(
        occurrence_index=evidence.occurrence_index,
        paragraph_id=evidence.paragraph_id,
        role=role,
        source_font_name=source_name_decision.value,
        source_font_family_group=family_decision.value,
        font_role=font_role_decision.value,
        font_size_points=font_size_decision.value,
        bold=bold_decision.value,
        italic=italic_decision.value,
        color_rgb=color_decision.value,
        alignment=alignment_decision.value,
        line_height_ratio=line_height_decision.value,
        first_line_indent_points=first_indent_decision.value,
        left_indent_points=left_indent_decision.value,
        right_indent_points=right_indent_decision.value,
        space_before_points=space_before_decision.value,
        space_after_points=space_after_decision.value,
        mixed_styles=evidence.mixed_styles,
        decisions=decisions,
        fallback_count=fallback_count,
    )


def reconstruct_styles(typography: TypographyBaseline) -> ResolvedStyleDocument:
    """Build the document baseline and resolve every occurrence in deterministic order."""
    baseline = build_document_style_baseline(typography)
    return ResolvedStyleDocument(
        source_sha256=typography.source_sha256,
        baseline=baseline,
        paragraphs=tuple(
            resolve_paragraph_style(paragraph, baseline) for paragraph in typography.paragraphs
        ),
    )


def _role_baseline(
    role: TypographyRole,
    paragraphs: Sequence[ParagraphTypographyEvidence],
    policy: StyleStabilityPolicy,
) -> RoleStyleBaseline | None:
    if not paragraphs:
        return None
    source_names = _accepted(item.source_font_name for item in paragraphs)
    family_groups = tuple(
        (normalize_font_family_group(value), confidence) for value, confidence in source_names
    )
    font_roles = tuple(
        (font_role, confidence)
        for value, confidence in source_names
        if (font_role := infer_font_role(value)) is not FontRole.UNKNOWN
    )
    return RoleStyleBaseline(
        role=role,
        paragraph_count=len(paragraphs),
        source_font_name=_categorical_baseline(source_names, policy),
        source_font_family_group=_categorical_baseline(family_groups, policy),
        font_role=_categorical_baseline(font_roles, policy),
        font_size_points=_numeric_baseline(
            _accepted(item.font_size_points for item in paragraphs),
            policy.font_size_tolerance_points,
            policy,
        ),
        bold=_categorical_baseline(_accepted(item.bold for item in paragraphs), policy),
        italic=_categorical_baseline(_accepted(item.italic for item in paragraphs), policy),
        color_rgb=_categorical_baseline(_accepted(item.color_rgb for item in paragraphs), policy),
        alignment=_categorical_baseline(
            _accepted(
                item.alignment
                for item in paragraphs
                if item.alignment.value is not TextAlignment.UNKNOWN
            ),
            policy,
        ),
        line_height_ratio=_numeric_baseline(
            _accepted(item.line_height_ratio for item in paragraphs),
            policy.line_height_ratio_tolerance,
            policy,
        ),
        first_line_indent_points=_numeric_baseline(
            _accepted(item.first_line_indent_points for item in paragraphs),
            policy.indent_tolerance_points,
            policy,
        ),
        left_indent_points=_numeric_baseline(
            _accepted(item.left_indent_points for item in paragraphs),
            policy.indent_tolerance_points,
            policy,
        ),
        right_indent_points=_numeric_baseline(
            _accepted(item.right_indent_points for item in paragraphs),
            policy.indent_tolerance_points,
            policy,
        ),
        space_before_points=_numeric_baseline(
            _accepted(item.space_before_points for item in paragraphs),
            policy.spacing_tolerance_points,
            policy,
        ),
        space_after_points=_numeric_baseline(
            _accepted(item.space_after_points for item in paragraphs),
            policy.spacing_tolerance_points,
            policy,
        ),
    )


def _evidence_role(item: ParagraphTypographyEvidence) -> TypographyRole:
    if _is_reliable(item.role) and item.role.value is not None:
        return item.role.value
    return TypographyRole.OTHER


def _accepted[T](
    properties: Iterable[TypographyProperty[T]],
) -> tuple[tuple[T, TypographyConfidence], ...]:
    return tuple(
        (item.value, item.confidence)
        for item in properties
        if _is_reliable(item) and item.value is not None
    )


def _categorical_baseline[T: Hashable](
    samples: Sequence[tuple[T, TypographyConfidence]],
    policy: StyleStabilityPolicy,
) -> StyleBaselineValue[T]:
    if not samples:
        return _empty_baseline()
    counts = Counter(value for value, _ in samples)
    value, support = sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))[0]
    share = support / len(samples)
    stable = support >= policy.minimum_sample_count and share >= policy.dominant_share
    supporting_confidence = tuple(confidence for item, confidence in samples if item == value)
    return StyleBaselineValue(
        value=value,
        stable=stable,
        sample_count=len(samples),
        support_count=support,
        dominant_share=round(share, 3),
        spread=None,
        confidence=_aggregate_confidence(supporting_confidence, share)
        if stable
        else TypographyConfidence.LOW,
    )


def _numeric_baseline(
    samples: Sequence[tuple[float, TypographyConfidence]],
    tolerance: float,
    policy: StyleStabilityPolicy,
) -> StyleBaselineValue[float]:
    if not samples:
        return _empty_baseline()
    values = tuple(value for value, _ in samples)
    center = float(statistics.median(values))
    inliers = tuple(
        (value, confidence) for value, confidence in samples if abs(value - center) <= tolerance
    )
    share = len(inliers) / len(samples)
    stable = len(inliers) >= policy.minimum_sample_count and share >= policy.dominant_share
    resolved = (
        round(float(statistics.median(value for value, _ in inliers)), 3)
        if inliers
        else round(center, 3)
    )
    spread = max((abs(value - resolved) for value, _ in inliers), default=0.0)
    return StyleBaselineValue(
        value=resolved,
        stable=stable,
        sample_count=len(samples),
        support_count=len(inliers),
        dominant_share=round(share, 3),
        spread=round(spread, 3),
        confidence=(
            _aggregate_confidence(tuple(confidence for _, confidence in inliers), share)
            if stable
            else TypographyConfidence.LOW
        ),
    )


def _empty_baseline[T]() -> StyleBaselineValue[T]:
    return StyleBaselineValue(
        value=None,
        stable=False,
        sample_count=0,
        support_count=0,
        dominant_share=0.0,
        confidence=TypographyConfidence.UNKNOWN,
    )


def _aggregate_confidence(
    supporting: Sequence[TypographyConfidence], share: float
) -> TypographyConfidence:
    if (
        supporting
        and all(item is TypographyConfidence.HIGH for item in supporting)
        and share >= 0.8
    ):
        return TypographyConfidence.HIGH
    return TypographyConfidence.MEDIUM


def _is_reliable[T](item: TypographyProperty[T]) -> bool:
    return item.confidence in _ACCEPTED_CONFIDENCE


def _role_decision(evidence: TypographyProperty[TypographyRole]) -> StyleDecision[TypographyRole]:
    if _is_reliable(evidence) and evidence.value is not None:
        return StyleDecision(
            value=evidence.value,
            evidence_value=evidence.value,
            evidence_confidence=evidence.confidence,
            source=StyleDecisionSource.TYPOGRAPHY_EVIDENCE,
            confidence=evidence.confidence,
            used_fallback=False,
        )
    return StyleDecision(
        value=TypographyRole.OTHER,
        evidence_value=evidence.value,
        evidence_confidence=evidence.confidence,
        source=StyleDecisionSource.SAFE_RENDER_DEFAULT,
        confidence=TypographyConfidence.UNKNOWN,
        used_fallback=True,
        fallback_reason="paragraph role evidence is missing or unreliable",
    )


def _source_identity_decision(
    evidence: TypographyProperty[str],
) -> StyleDecision[str | None]:
    if evidence.value:
        return StyleDecision(
            value=evidence.value,
            evidence_value=evidence.value,
            evidence_confidence=evidence.confidence,
            source=StyleDecisionSource.TYPOGRAPHY_EVIDENCE,
            confidence=evidence.confidence,
            used_fallback=False,
        )
    return StyleDecision(
        value=None,
        evidence_value=None,
        evidence_confidence=evidence.confidence,
        source=StyleDecisionSource.UNRESOLVED,
        confidence=TypographyConfidence.UNKNOWN,
        used_fallback=False,
        fallback_reason="source font identity is unavailable and is never fabricated",
    )


def _family_decision(
    evidence: TypographyProperty[str],
    baseline: RoleStyleBaseline | None,
) -> StyleDecision[str | None]:
    if evidence.value and _is_reliable(evidence):
        return StyleDecision(
            value=normalize_font_family_group(evidence.value),
            evidence_value=evidence.value,
            evidence_confidence=evidence.confidence,
            source=StyleDecisionSource.NORMALIZED_SOURCE_VALUE,
            confidence=evidence.confidence,
            used_fallback=False,
        )
    role_value = baseline.source_font_family_group if baseline else None
    if role_value and role_value.stable and role_value.value is not None:
        return StyleDecision(
            value=role_value.value,
            evidence_value=evidence.value,
            evidence_confidence=evidence.confidence,
            source=StyleDecisionSource.ROLE_BASELINE,
            confidence=role_value.confidence,
            used_fallback=True,
            fallback_reason=(
                "source font family is unavailable or unreliable; used stable same-role family"
            ),
        )
    return StyleDecision(
        value=None,
        evidence_value=evidence.value,
        evidence_confidence=evidence.confidence,
        source=StyleDecisionSource.UNRESOLVED,
        confidence=TypographyConfidence.UNKNOWN,
        used_fallback=False,
        fallback_reason=("source font family is unavailable or unreliable and is never fabricated"),
    )


def _font_role_decision(
    evidence: TypographyProperty[str],
    baseline: RoleStyleBaseline | None,
) -> StyleDecision[FontRole]:
    inferred = infer_font_role(evidence.value)
    if evidence.value and _is_reliable(evidence) and inferred is not FontRole.UNKNOWN:
        return StyleDecision(
            value=inferred,
            evidence_value=inferred,
            evidence_confidence=evidence.confidence,
            source=StyleDecisionSource.NORMALIZED_SOURCE_VALUE,
            confidence=evidence.confidence,
            used_fallback=False,
        )
    role_value = baseline.font_role if baseline else None
    if role_value and role_value.stable and role_value.value is not None:
        return StyleDecision(
            value=role_value.value,
            evidence_value=inferred,
            evidence_confidence=evidence.confidence,
            source=StyleDecisionSource.ROLE_BASELINE,
            confidence=role_value.confidence,
            used_fallback=True,
            fallback_reason="generic font role is unavailable; used stable same-role role",
        )
    return StyleDecision(
        value=FontRole.UNKNOWN,
        evidence_value=inferred,
        evidence_confidence=evidence.confidence,
        source=StyleDecisionSource.SAFE_RENDER_DEFAULT,
        confidence=TypographyConfidence.UNKNOWN,
        used_fallback=True,
        fallback_reason="generic font role cannot be inferred safely",
    )


def _resolve[T](
    evidence: TypographyProperty[T],
    role_baseline: StyleBaselineValue[T] | None,
    default: T,
    default_reason: str,
    *,
    document_baseline: StyleBaselineValue[T] | None = None,
    invalid: Callable[[T], bool] | None = None,
) -> StyleDecision[T]:
    evidence_value = evidence.value
    if (
        _is_reliable(evidence)
        and evidence_value is not None
        and not (invalid and invalid(evidence_value))
    ):
        return StyleDecision(
            value=evidence_value,
            evidence_value=evidence_value,
            evidence_confidence=evidence.confidence,
            source=StyleDecisionSource.TYPOGRAPHY_EVIDENCE,
            confidence=evidence.confidence,
            used_fallback=False,
        )
    if role_baseline and role_baseline.stable and role_baseline.value is not None:
        return StyleDecision(
            value=role_baseline.value,
            evidence_value=evidence.value,
            evidence_confidence=evidence.confidence,
            source=StyleDecisionSource.ROLE_BASELINE,
            confidence=role_baseline.confidence,
            used_fallback=True,
            fallback_reason="paragraph evidence is unreliable; used stable same-role baseline",
        )
    if document_baseline and document_baseline.stable and document_baseline.value is not None:
        return StyleDecision(
            value=document_baseline.value,
            evidence_value=evidence.value,
            evidence_confidence=evidence.confidence,
            source=StyleDecisionSource.DOCUMENT_BASELINE,
            confidence=document_baseline.confidence,
            used_fallback=True,
            fallback_reason=(
                "paragraph and same-role evidence are unreliable; used safe document baseline"
            ),
        )
    return StyleDecision(
        value=default,
        evidence_value=evidence.value,
        evidence_confidence=evidence.confidence,
        source=StyleDecisionSource.SAFE_RENDER_DEFAULT,
        confidence=TypographyConfidence.UNKNOWN,
        used_fallback=True,
        fallback_reason=default_reason,
    )
