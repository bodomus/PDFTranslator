"""Deterministic paragraph-bounded glossary matching."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pdftranslate.glossary.models import (
    GlossaryDocument,
    GlossaryEntry,
    GlossaryMatchType,
)


@dataclass(frozen=True)
class GlossaryMatch:
    entry: GlossaryEntry
    start: int
    end: int


def find_glossary_matches(text: str, glossary: GlossaryDocument) -> tuple[GlossaryMatch, ...]:
    """Return non-overlapping matches using the documented deterministic precedence."""
    candidates: list[GlossaryMatch] = []
    for entry in glossary.entries:
        pattern = _pattern(entry)
        flags = 0 if entry.case_sensitive else re.IGNORECASE
        candidates.extend(
            GlossaryMatch(entry=entry, start=match.start(), end=match.end())
            for match in re.finditer(pattern, text, flags=flags)
        )
    candidates.sort(key=_precedence)
    selected: list[GlossaryMatch] = []
    for candidate in candidates:
        if any(_overlaps(candidate, existing) for existing in selected):
            continue
        selected.append(candidate)
    return tuple(sorted(selected, key=lambda item: (item.start, item.end, item.entry.id)))


def _pattern(entry: GlossaryEntry) -> str:
    source = entry.source.strip()
    body = r"\s+".join(re.escape(part) for part in source.split())
    if entry.match is GlossaryMatchType.EXACT:
        return rf"(?s)\A\s*{body}\s*\Z"
    return rf"(?<!\w){body}(?!\w)"


def _precedence(item: GlossaryMatch) -> tuple[int, int, int, int, str, int]:
    match_rank = {
        GlossaryMatchType.EXACT: 3,
        GlossaryMatchType.PHRASE: 2,
        GlossaryMatchType.WHOLE_WORD: 1,
    }
    return (
        -item.entry.priority,
        -(item.end - item.start),
        -int(item.entry.case_sensitive),
        -match_rank[item.entry.match],
        item.entry.id,
        item.start,
    )


def _overlaps(left: GlossaryMatch, right: GlossaryMatch) -> bool:
    return left.start < right.end and right.start < left.end
