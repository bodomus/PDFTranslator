"""Conservative document-level repeated-element classification."""

from __future__ import annotations

import hashlib
import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from pdftranslate.domain.page import ExtractedPage
from pdftranslate.domain.text_block import TextBlock
from pdftranslate.repeated.models import (
    RepeatedBlockClassification,
    RepeatedElementAnalysis,
    RepeatedElementGroup,
    RepeatedElementKind,
    RepeatedElementMetrics,
    RepeatedElementOptions,
    RepeatedElementPolicy,
)

_PAGE_NUMBER = re.compile(r"^\s*(?:page\s+)?(?P<current>\d+)(?:\s*(?:of|/)\s*\d+)?\s*$", re.I)
_LEGAL_CUES = (
    "all rights reserved",
    "copyright",
    "©",
    "confidential",
    "proprietary",
    "unauthorized",
    "terms and conditions",
)
_WATERMARK_CUES = {"draft", "confidential", "sample", "copy", "do not distribute"}


@dataclass(frozen=True)
class _Candidate:
    page: ExtractedPage
    block: TextBlock
    normalized: str
    region: str
    font_size: float


@dataclass(frozen=True)
class _Decision:
    kind: RepeatedElementKind
    policy: RepeatedElementPolicy
    confidence: float
    ambiguous: bool
    reasons: tuple[str, ...]
    group_id: str | None = None


def classify_repeated_elements(
    pages: Sequence[ExtractedPage],
    options: RepeatedElementOptions | None = None,
) -> RepeatedElementAnalysis:
    """Classify every source block without deleting or rewriting source content."""
    selected = options or RepeatedElementOptions()
    candidates = tuple(_candidates(pages, selected))
    if selected.mode == "off":
        off_decisions = {
            item.block.id: _Decision(
                RepeatedElementKind.BODY,
                RepeatedElementPolicy.TRANSLATE,
                1.0,
                False,
                ("mode_off",),
            )
            for item in candidates
        }
        return _analysis(selected, candidates, off_decisions, ())

    decisions: dict[str, _Decision] = {}
    groups: list[RepeatedElementGroup] = []
    _classify_page_numbers(candidates, decisions, groups)
    document_font = _document_font(candidates)
    by_text: defaultdict[str, list[_Candidate]] = defaultdict(list)
    for item in candidates:
        if item.block.id not in decisions:
            by_text[item.normalized].append(item)

    total_pages = len({item.page.page_number for item in candidates})
    for normalized, occurrences in sorted(by_text.items()):
        page_numbers = tuple(sorted({item.page.page_number for item in occurrences}))
        if not normalized or len(page_numbers) < 2:
            continue
        stable_geometry = _geometry_similar(occurrences, selected)
        stable_font = _font_similar(occurrences, selected)
        ratio, parity = _recurrence(page_numbers, pages)
        recurring = ratio >= selected.min_recurrence_ratio or (
            parity != "all"
            and _parity_ratio(page_numbers, pages, parity) >= selected.parity_recurrence_ratio
        )
        short_document = total_pages < selected.min_confirmed_pages
        region = (
            occurrences[0].region if len({item.region for item in occurrences}) == 1 else "mixed"
        )
        legal = any(cue in normalized for cue in _LEGAL_CUES)
        conspicuous = _watermark_like(occurrences, document_font, selected)

        if stable_geometry and recurring and not short_document and legal:
            decision = _group_decision(
                normalized,
                occurrences,
                RepeatedElementKind.REPEATED_BOILERPLATE,
                RepeatedElementPolicy.TRANSLATE,
                ratio,
                parity,
                0.94,
                False,
                ("legal_cue", "repeated_text", "stable_geometry"),
            )
        elif stable_geometry and recurring and not short_document and conspicuous:
            decision = _group_decision(
                normalized,
                occurrences,
                RepeatedElementKind.WATERMARK_CANDIDATE,
                RepeatedElementPolicy.SKIP,
                ratio,
                parity,
                0.82,
                True,
                ("central_repetition", "conspicuous_font", "preserve_source"),
            )
        elif (
            stable_geometry
            and stable_font
            and recurring
            and not short_document
            and region in {"top", "bottom"}
        ):
            kind = (
                RepeatedElementKind.RUNNING_HEADER
                if region == "top"
                else RepeatedElementKind.RUNNING_FOOTER
            )
            decision = _group_decision(
                normalized,
                occurrences,
                kind,
                RepeatedElementPolicy.TRANSLATE,
                ratio,
                parity,
                min(0.98, 0.76 + ratio * 0.22),
                False,
                ("margin_position", "repeated_text", f"parity_{parity}"),
            )
        elif stable_geometry and stable_font:
            decision = _group_decision(
                normalized,
                occurrences,
                RepeatedElementKind.UNKNOWN_REPEATED,
                RepeatedElementPolicy.PRESERVE,
                ratio,
                parity,
                0.55,
                True,
                ("repeated_text", "insufficient_non_body_evidence", "preserve_on_uncertainty"),
            )
        else:
            continue
        group, group_decision = decision
        groups.append(group)
        for item in occurrences:
            decisions[item.block.id] = group_decision

    for item in candidates:
        decisions.setdefault(
            item.block.id,
            _Decision(
                RepeatedElementKind.BODY,
                RepeatedElementPolicy.TRANSLATE,
                1.0,
                False,
                ("no_repeated_non_body_evidence",),
            ),
        )
    return _analysis(selected, candidates, decisions, tuple(groups))


def _classify_page_numbers(
    candidates: Sequence[_Candidate],
    decisions: dict[str, _Decision],
    groups: list[RepeatedElementGroup],
) -> None:
    matches: list[tuple[_Candidate, int]] = []
    for item in candidates:
        match = _PAGE_NUMBER.fullmatch(item.block.text)
        if match is not None and item.region in {"top", "bottom"}:
            matches.append((item, int(match.group("current"))))
    sequential = [(item, value) for item, value in matches if value == item.page.page_number]
    if len({item.page.page_number for item, _ in sequential}) < 2:
        return
    normalized = "page-sequence"
    group_id = _group_id(RepeatedElementKind.PAGE_NUMBER, normalized, "sequence")
    page_numbers = tuple(sorted({item.page.page_number for item, _ in sequential}))
    ratio = len(page_numbers) / max(len({item.page.page_number for item in candidates}), 1)
    groups.append(
        RepeatedElementGroup(
            id=group_id,
            kind=RepeatedElementKind.PAGE_NUMBER,
            normalized_text=normalized,
            page_numbers=page_numbers,
            recurrence_ratio=ratio,
            parity="sequence",
            confidence=0.99,
            policy=RepeatedElementPolicy.PRESERVE,
        )
    )
    for item, _ in sequential:
        decisions[item.block.id] = _Decision(
            RepeatedElementKind.PAGE_NUMBER,
            RepeatedElementPolicy.PRESERVE,
            0.99,
            False,
            ("numeric_sequence", "margin_position"),
            group_id,
        )


def _group_decision(
    normalized: str,
    occurrences: Sequence[_Candidate],
    kind: RepeatedElementKind,
    policy: RepeatedElementPolicy,
    ratio: float,
    parity: str,
    confidence: float,
    ambiguous: bool,
    reasons: tuple[str, ...],
) -> tuple[RepeatedElementGroup, _Decision]:
    group_id = _group_id(kind, normalized, parity)
    page_numbers = tuple(sorted({item.page.page_number for item in occurrences}))
    selected_parity: Literal["all", "odd", "even"] = "all"
    if parity == "odd":
        selected_parity = "odd"
    elif parity == "even":
        selected_parity = "even"
    group = RepeatedElementGroup(
        id=group_id,
        kind=kind,
        normalized_text=normalized,
        page_numbers=page_numbers,
        recurrence_ratio=ratio,
        parity=selected_parity,
        confidence=confidence,
        policy=policy,
        ambiguous=ambiguous,
    )
    return group, _Decision(kind, policy, confidence, ambiguous, reasons, group_id)


def _analysis(
    options: RepeatedElementOptions,
    candidates: Sequence[_Candidate],
    decisions: dict[str, _Decision],
    groups: Sequence[RepeatedElementGroup],
) -> RepeatedElementAnalysis:
    blocks = tuple(
        RepeatedBlockClassification(
            block_id=item.block.id,
            page_number=item.page.page_number,
            bbox=item.block.bbox,
            kind=decisions[item.block.id].kind,
            confidence=decisions[item.block.id].confidence,
            group_id=decisions[item.block.id].group_id,
            policy=decisions[item.block.id].policy,
            ambiguous=decisions[item.block.id].ambiguous,
            reasons=decisions[item.block.id].reasons,
        )
        for item in candidates
    )
    counts = Counter(item.kind.value for item in blocks)
    classified = sum(item.kind is not RepeatedElementKind.BODY for item in blocks)
    return RepeatedElementAnalysis(
        mode=options.mode,
        options=options,
        blocks=blocks,
        groups=tuple(groups),
        metrics=RepeatedElementMetrics(
            total_blocks=len(blocks),
            classified_blocks=classified,
            ambiguous_blocks=sum(item.ambiguous for item in blocks),
            groups=len(groups),
            counts=dict(sorted(counts.items())),
        ),
    )


def _candidates(
    pages: Sequence[ExtractedPage], options: RepeatedElementOptions
) -> Iterable[_Candidate]:
    for page in pages:
        for block in page.text_blocks:
            yield _Candidate(
                page=page,
                block=block,
                normalized=_normalize(block.text),
                region=_region(block, page, options),
                font_size=_font_size(block),
            )


def _region(block: TextBlock, page: ExtractedPage, options: RepeatedElementOptions) -> str:
    if block.bbox.y1 <= page.height * options.margin_region_ratio:
        return "top"
    if block.bbox.y0 >= page.height * (1 - options.margin_region_ratio):
        return "bottom"
    return "middle"


def _geometry_similar(items: Sequence[_Candidate], options: RepeatedElementOptions) -> bool:
    if len({item.region for item in items}) != 1:
        return False
    values = (
        [item.block.bbox.x0 / item.page.width for item in items],
        [item.block.bbox.y0 / item.page.height for item in items],
        [item.block.bbox.x1 / item.page.width for item in items],
        [item.block.bbox.y1 / item.page.height for item in items],
    )
    return all(max(group) - min(group) <= options.bbox_tolerance_ratio for group in values)


def _font_similar(items: Sequence[_Candidate], options: RepeatedElementOptions) -> bool:
    values = [item.font_size for item in items if item.font_size > 0]
    if not values:
        return True
    median = statistics.median(values)
    return max(values) - min(values) <= max(0.5, median * options.font_size_tolerance_ratio)


def _watermark_like(
    items: Sequence[_Candidate], document_font: float, options: RepeatedElementOptions
) -> bool:
    normalized = items[0].normalized
    cue = normalized in _WATERMARK_CUES
    central = all(
        item.page.height * 0.25 <= item.block.bbox.y0 <= item.page.height * 0.75 for item in items
    )
    large = document_font > 0 and all(
        item.font_size >= document_font * options.watermark_font_ratio for item in items
    )
    return central and (large or cue)


def _recurrence(page_numbers: Sequence[int], pages: Sequence[ExtractedPage]) -> tuple[float, str]:
    available = tuple(page.page_number for page in pages)
    observed = set(page_numbers)
    eligible = list(available)
    if eligible and eligible[0] not in observed:
        eligible.pop(0)
    if eligible and eligible[-1] not in observed:
        eligible.pop()
    ratio = len(observed) / max(len(eligible), 1)
    odd = _parity_ratio(page_numbers, pages, "odd")
    even = _parity_ratio(page_numbers, pages, "even")
    if odd > ratio and odd >= even:
        return min(ratio, 1.0), "odd"
    if even > ratio:
        return min(ratio, 1.0), "even"
    return min(ratio, 1.0), "all"


def _parity_ratio(
    page_numbers: Sequence[int], pages: Sequence[ExtractedPage], parity: str
) -> float:
    expected = [
        page.page_number for page in pages if (page.page_number % 2 == 1) == (parity == "odd")
    ]
    observed = set(page_numbers)
    return sum(number in observed for number in expected) / max(len(expected), 1)


def _document_font(items: Sequence[_Candidate]) -> float:
    values = [item.font_size for item in items if item.font_size > 0]
    return statistics.median(values) if values else 0.0


def _font_size(block: TextBlock) -> float:
    values = [
        span.font_size for span in block.spans if span.font_size is not None and span.font_size > 0
    ]
    return statistics.median(values) if values else 0.0


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _group_id(kind: RepeatedElementKind, normalized: str, parity: str) -> str:
    digest = hashlib.sha256(f"{kind.value}\0{normalized}\0{parity}".encode()).hexdigest()[:12]
    return f"repeat-{digest}"
