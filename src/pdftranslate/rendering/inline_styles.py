"""Conservative source-backed inline-style mapping for translated reflow text."""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from pdftranslate.domain.text_block import TextSpan
from pdftranslate.reconstruction import LogicalParagraph, ParagraphFragment
from pdftranslate.typography import normalize_font_family_group


class InlineMappingKind(StrEnum):
    EXACT_PRESERVED_TEXT = "exact_preserved_text"


class InlineMappingConfidence(StrEnum):
    HIGH = "high"


class InlineStyleDeferReason(StrEnum):
    NOT_PRESERVED_IN_TRANSLATION = "not_preserved_in_translation"
    AMBIGUOUS_TARGET_OCCURRENCE = "ambiguous_target_occurrence"
    OVERLAPPING_MAPPING = "overlapping_mapping"
    UNSUPPORTED_PROPERTY = "unsupported_property"
    UNSAFE_OR_INVALID_SOURCE_RUN = "unsafe_or_invalid_source_run"


@dataclass(frozen=True)
class SourceInlineStyleRun:
    """One auditable source span whose style differs from the paragraph base."""

    source_order: int
    text: str
    source_start: int | None
    source_end: int | None
    font_size_points: float | None
    color_rgb: tuple[float, float, float] | None
    bold_requested: bool | None
    italic_requested: bool | None
    source_font_name: str | None
    source_font_family_group: str | None
    fragment_id: str
    source_page_number: int

    def __post_init__(self) -> None:
        if self.source_order < 0 or not self.text or self.source_page_number < 1:
            raise ValueError("inline source run identity and text are required")
        if (self.source_start is None) != (self.source_end is None):
            raise ValueError("inline source range must be complete or unavailable")
        if self.source_start is not None and (
            self.source_start < 0 or self.source_end is None or self.source_end <= self.source_start
        ):
            raise ValueError("inline source range must be positive")
        if self.font_size_points is not None and self.font_size_points <= 0:
            raise ValueError("inline font size must be positive")

    @property
    def text_sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    @property
    def has_supported_override(self) -> bool:
        return self.font_size_points is not None or self.color_rgb is not None


@dataclass(frozen=True)
class InlineStyleRun:
    """A proven local override expressed only in translated-text offsets."""

    text_start: int
    text_end: int
    text: str
    font_size_points: float | None
    color_rgb: tuple[float, float, float] | None
    bold_requested: bool | None
    bold_applied: bool
    italic_requested: bool | None
    italic_applied: bool
    source_font_name: str | None
    source_font_family_group: str | None
    source_start: int
    source_end: int
    mapping_kind: InlineMappingKind = InlineMappingKind.EXACT_PRESERVED_TEXT
    confidence: InlineMappingConfidence = InlineMappingConfidence.HIGH

    def __post_init__(self) -> None:
        if self.text_start < 0 or self.text_end <= self.text_start:
            raise ValueError("inline translated range must be positive")
        if self.text_end - self.text_start != len(self.text) or not self.text:
            raise ValueError("inline translated range must match its auditable text")
        if self.source_start < 0 or self.source_end <= self.source_start:
            raise ValueError("inline source range must be positive")
        if self.font_size_points is None and self.color_rgb is None:
            raise ValueError("applied inline run requires a supported override")
        if self.font_size_points is not None and self.font_size_points <= 0:
            raise ValueError("inline font size must be positive")
        if self.bold_applied or self.italic_applied:
            raise ValueError("PDFTR-32 does not apply synthetic bold or italic faces")

    @property
    def applied_character_count(self) -> int:
        return self.text_end - self.text_start

    @property
    def text_sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DeferredInlineStyleRun:
    candidate: SourceInlineStyleRun
    reason: InlineStyleDeferReason


@dataclass(frozen=True)
class InlineStyleMapping:
    applied: tuple[InlineStyleRun, ...] = ()
    deferred: tuple[DeferredInlineStyleRun, ...] = ()

    @property
    def candidate_count(self) -> int:
        return len(self.applied) + len(self.deferred)

    @property
    def applied_character_count(self) -> int:
        return sum(item.applied_character_count for item in self.applied)


def map_inline_styles(
    paragraph: LogicalParagraph,
    *,
    translated_text: str,
    base_font_size: float,
    base_color: tuple[float, float, float],
    base_bold: bool,
    base_italic: bool,
    base_font_family_group: str | None,
) -> InlineStyleMapping:
    """Map only exact, uniquely occurring preserved source runs into translated text."""
    candidates = _source_candidates(
        paragraph,
        base_font_size=base_font_size,
        base_color=base_color,
        base_bold=base_bold,
        base_italic=base_italic,
        base_font_family_group=base_font_family_group,
    )
    deferred: list[DeferredInlineStyleRun] = []
    tentative: list[tuple[SourceInlineStyleRun, InlineStyleRun]] = []
    for candidate in candidates:
        if candidate.source_start is None or candidate.source_end is None:
            deferred.append(
                DeferredInlineStyleRun(
                    candidate, InlineStyleDeferReason.UNSAFE_OR_INVALID_SOURCE_RUN
                )
            )
            continue
        if paragraph.text[candidate.source_start : candidate.source_end] != candidate.text:
            deferred.append(
                DeferredInlineStyleRun(
                    candidate, InlineStyleDeferReason.UNSAFE_OR_INVALID_SOURCE_RUN
                )
            )
            continue
        if not candidate.has_supported_override:
            deferred.append(
                DeferredInlineStyleRun(candidate, InlineStyleDeferReason.UNSUPPORTED_PROPERTY)
            )
            continue
        source_occurrences = _occurrences(paragraph.text, candidate.text)
        target_occurrences = _occurrences(translated_text, candidate.text)
        if not target_occurrences:
            deferred.append(
                DeferredInlineStyleRun(
                    candidate, InlineStyleDeferReason.NOT_PRESERVED_IN_TRANSLATION
                )
            )
            continue
        if (
            len(source_occurrences) != 1
            or len(target_occurrences) != 1
            or candidate.source_start not in source_occurrences
        ):
            deferred.append(
                DeferredInlineStyleRun(
                    candidate, InlineStyleDeferReason.AMBIGUOUS_TARGET_OCCURRENCE
                )
            )
            continue
        target_start = target_occurrences[0]
        target_end = target_start + len(candidate.text)
        if translated_text[target_start:target_end] != candidate.text:
            deferred.append(
                DeferredInlineStyleRun(
                    candidate, InlineStyleDeferReason.UNSAFE_OR_INVALID_SOURCE_RUN
                )
            )
            continue
        tentative.append(
            (
                candidate,
                InlineStyleRun(
                    text_start=target_start,
                    text_end=target_end,
                    text=candidate.text,
                    font_size_points=candidate.font_size_points,
                    color_rgb=candidate.color_rgb,
                    bold_requested=candidate.bold_requested,
                    bold_applied=False,
                    italic_requested=candidate.italic_requested,
                    italic_applied=False,
                    source_font_name=candidate.source_font_name,
                    source_font_family_group=candidate.source_font_family_group,
                    source_start=candidate.source_start,
                    source_end=candidate.source_end,
                ),
            )
        )

    ordered = sorted(tentative, key=lambda item: item[0].source_order)
    if any(
        current[1].text_start < previous[1].text_end
        for previous, current in zip(ordered, ordered[1:], strict=False)
    ):
        deferred.extend(
            DeferredInlineStyleRun(candidate, InlineStyleDeferReason.OVERLAPPING_MAPPING)
            for candidate, _ in ordered
        )
        ordered = []
    applied = tuple(run for _, run in ordered)
    validate_inline_style_runs(translated_text, applied)
    return InlineStyleMapping(
        applied=applied,
        deferred=tuple(sorted(deferred, key=lambda item: item.candidate.source_order)),
    )


def clip_inline_style_runs(
    runs: tuple[InlineStyleRun, ...],
    *,
    text: str,
    text_start: int,
    text_end: int,
) -> tuple[InlineStyleRun, ...]:
    """Intersect full-text runs with a slice and rebase them to slice-local offsets."""
    if text_start < 0 or text_end < text_start or text_end > len(text):
        raise ValueError("inline run clip range is outside its text")
    validate_inline_style_runs(text, runs)
    clipped: list[InlineStyleRun] = []
    local_text = text[text_start:text_end]
    for run in runs:
        overlap_start = max(text_start, run.text_start)
        overlap_end = min(text_end, run.text_end)
        if overlap_start >= overlap_end:
            continue
        left_delta = overlap_start - run.text_start
        right_delta = run.text_end - overlap_end
        local_start = overlap_start - text_start
        local_end = overlap_end - text_start
        clipped.append(
            InlineStyleRun(
                text_start=local_start,
                text_end=local_end,
                text=local_text[local_start:local_end],
                font_size_points=run.font_size_points,
                color_rgb=run.color_rgb,
                bold_requested=run.bold_requested,
                bold_applied=run.bold_applied,
                italic_requested=run.italic_requested,
                italic_applied=run.italic_applied,
                source_font_name=run.source_font_name,
                source_font_family_group=run.source_font_family_group,
                source_start=run.source_start + left_delta,
                source_end=run.source_end - right_delta,
                mapping_kind=run.mapping_kind,
                confidence=run.confidence,
            )
        )
    result = tuple(clipped)
    validate_inline_style_runs(local_text, result)
    return result


def validate_inline_style_runs(text: str, runs: tuple[InlineStyleRun, ...]) -> None:
    previous_end = 0
    for run in runs:
        if run.text_end > len(text) or run.text_start < previous_end:
            raise ValueError(
                "inline translated runs must be ordered, in bounds, and non-overlapping"
            )
        if text[run.text_start : run.text_end] != run.text:
            raise ValueError("inline translated range does not match its auditable text")
        previous_end = run.text_end


def _source_candidates(
    paragraph: LogicalParagraph,
    *,
    base_font_size: float,
    base_color: tuple[float, float, float],
    base_bold: bool,
    base_italic: bool,
    base_font_family_group: str | None,
) -> tuple[SourceInlineStyleRun, ...]:
    locations = _span_locations(paragraph)
    candidates: list[SourceInlineStyleRun] = []
    source_order = 0
    for fragment, span, source_start, source_end, exact_text in locations:
        if not normalized_nonempty(exact_text):
            continue
        font_size = (
            float(span.font_size)
            if span.font_size is not None
            and span.font_size > 0
            and abs(float(span.font_size) - base_font_size) > 1e-3
            else None
        )
        color = _span_color(span)
        color_override = color if color is not None and not _same_color(color, base_color) else None
        family = normalize_font_family_group(span.font_name) if span.font_name else None
        family_changed = family is not None and family != base_font_family_group
        bold_requested = span.bold if span.bold is not None and span.bold != base_bold else None
        italic_requested = (
            span.italic if span.italic is not None and span.italic != base_italic else None
        )
        if not any(
            (
                font_size is not None,
                color_override is not None,
                family_changed,
                bold_requested is not None,
                italic_requested is not None,
            )
        ):
            continue
        candidate = SourceInlineStyleRun(
            source_order=source_order,
            text=exact_text,
            source_start=source_start,
            source_end=source_end,
            font_size_points=font_size,
            color_rgb=color_override,
            bold_requested=bold_requested,
            italic_requested=italic_requested,
            source_font_name=span.font_name,
            source_font_family_group=family,
            fragment_id=fragment.id,
            source_page_number=fragment.mapping.page_number,
        )
        if candidates and _mergeable(candidates[-1], candidate):
            previous = candidates.pop()
            candidate = SourceInlineStyleRun(
                source_order=previous.source_order,
                text=previous.text + candidate.text,
                source_start=previous.source_start,
                source_end=candidate.source_end,
                font_size_points=candidate.font_size_points,
                color_rgb=candidate.color_rgb,
                bold_requested=candidate.bold_requested,
                italic_requested=candidate.italic_requested,
                source_font_name=candidate.source_font_name,
                source_font_family_group=candidate.source_font_family_group,
                fragment_id=candidate.fragment_id,
                source_page_number=candidate.source_page_number,
            )
        candidates.append(candidate)
        source_order += 1
    return tuple(candidates)


def _span_locations(
    paragraph: LogicalParagraph,
) -> tuple[tuple[ParagraphFragment, TextSpan, int | None, int | None, str], ...]:
    locations: list[tuple[ParagraphFragment, TextSpan, int | None, int | None, str]] = []
    rebuilt = ""
    for fragment in paragraph.fragments:
        right = fragment.text.lstrip()
        if not rebuilt:
            fragment_start = 0
            rebuilt = fragment.text.strip()
        else:
            left = rebuilt.rstrip()
            if _is_soft_hyphen(left, right):
                fragment_start = len(left) - 1
                rebuilt = left[:-1] + right
            else:
                fragment_start = len(left) + 1
                rebuilt = f"{left} {right}"
        concatenated = "".join(span.text for span in fragment.spans)
        stripped = concatenated.strip()
        exact = stripped == fragment.text.strip()
        left_trim = len(concatenated) - len(concatenated.lstrip())
        cursor = 0
        for span in fragment.spans:
            raw_start = cursor
            raw_end = cursor + len(span.text)
            cursor = raw_end
            local_start = max(0, raw_start - left_trim)
            local_end = min(len(stripped), raw_end - left_trim)
            text = stripped[local_start:local_end]
            if not text or not exact:
                text = span.text.strip()
                locations.append((fragment, span, None, None, text))
                continue
            source_start = fragment_start + local_start
            source_end = fragment_start + local_end
            if source_end > len(paragraph.text) or paragraph.text[source_start:source_end] != text:
                locations.append((fragment, span, None, None, text))
            else:
                locations.append((fragment, span, source_start, source_end, text))
    if rebuilt != paragraph.text:
        return tuple((fragment, span, None, None, text) for fragment, span, _, _, text in locations)
    return tuple(locations)


def _mergeable(previous: SourceInlineStyleRun, current: SourceInlineStyleRun) -> bool:
    return (
        previous.source_end is not None
        and current.source_start is not None
        and previous.source_end == current.source_start
        and previous.fragment_id == current.fragment_id
        and previous.source_page_number == current.source_page_number
        and previous.font_size_points == current.font_size_points
        and previous.color_rgb == current.color_rgb
        and previous.bold_requested == current.bold_requested
        and previous.italic_requested == current.italic_requested
        and previous.source_font_name == current.source_font_name
        and previous.source_font_family_group == current.source_font_family_group
    )


def _occurrences(text: str, needle: str) -> list[int]:
    starts: list[int] = []
    cursor = 0
    while cursor <= len(text) - len(needle):
        found = text.find(needle, cursor)
        if found < 0:
            break
        starts.append(found)
        cursor = found + 1
    return starts


def _span_color(span: TextSpan) -> tuple[float, float, float] | None:
    if span.text_color is None:
        return None
    return (
        float((span.text_color >> 16) & 0xFF) / 255.0,
        float((span.text_color >> 8) & 0xFF) / 255.0,
        float(span.text_color & 0xFF) / 255.0,
    )


def _same_color(first: tuple[float, float, float], second: tuple[float, float, float]) -> bool:
    return all(
        round(left * 255) == round(right * 255) for left, right in zip(first, second, strict=True)
    )


def _is_soft_hyphen(left: str, right: str) -> bool:
    if not left.endswith("-") or not right or not right[0].islower():
        return False
    token = left.split()[-1]
    stem = token[:-1]
    right_token = right.split()[0]
    legitimate_prefixes = {
        "well",
        "ill",
        "self",
        "non",
        "pre",
        "post",
        "high",
        "low",
        "long",
        "short",
    }
    return not (
        token.startswith("--")
        or "-" in stem
        or "-" in right_token
        or not stem.isalpha()
        or len(stem) < 3
        or stem.casefold() in legitimate_prefixes
    )


def normalized_nonempty(value: str) -> bool:
    """Expose the normalization gate used by the conservative mapper."""
    return bool(unicodedata.normalize("NFC", value).strip())
