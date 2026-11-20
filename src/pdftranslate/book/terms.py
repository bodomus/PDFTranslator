"""Find names, abbreviations and codenames that a book-wide glossary should fix."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from pdftranslate.book.models import BookDocument

TermKind = Literal["caps", "name"]

_NOTE = re.compile(r"^\d+\.\s")
_CAPS = re.compile(r"\b[A-Z][A-Z\-]{1,15}\b")
_UPPER = r"[A-ZÀ-ÖØ-ÞĀ-Ž]"
_LOWER = r"[a-zß-öø-ÿā-ž]"
_WORD_PART = rf"{_UPPER}{_LOWER}+(?:['’]{_LOWER}+)?"
_NAME = re.compile(
    rf"\b{_WORD_PART}"
    rf"(?:(?:\s+|-)(?:(?:de|von|van|der|of|the|al|la|le|d’)\s*)?{_WORD_PART})*"
)
_POSSESSIVE = re.compile(r"['’]s?$")
_LOWER_WORD = re.compile(r"\b[a-z]+\b")
_SENTENCE_START = re.compile(r"(?:^|[.!?:;]\s+|[“\"‘(]\s*)$")


@dataclass(frozen=True)
class TermCandidate:
    term: str
    kind: TermKind
    count: int
    example: str


def extract_terms(
    book: BookDocument, *, min_count: int = 3, include_notes: bool = False
) -> list[TermCandidate]:
    """Rank capitalised words and phrases that are not ordinary English words.

    A word counts as ordinary when the book also uses it in lower case more often than
    capitalised mid-sentence; that removes "The", "Party" and similar noise while keeping
    names and transliterated Russian words. Note paragraphs are skipped by default because
    their bibliography adds many authors and titles that never appear in the text.
    """
    texts = [
        item.text
        for item in book.paragraphs
        if item.kind == "body" and (include_notes or not _NOTE.match(item.text))
    ]
    lower = Counter(word for text in texts for word in _LOWER_WORD.findall(text))
    # Words seen capitalised in mid-sentence, where capitals mean a name.
    named = Counter(
        re.split(r"\s+|-", match.group(0))[0]
        for text in texts
        for match in _NAME.finditer(text)
        if not _SENTENCE_START.search(text[: match.start()])
    )
    counts: Counter[tuple[str, TermKind]] = Counter()
    examples: dict[tuple[str, TermKind], str] = {}

    def add(term: str, kind: TermKind, text: str, start: int) -> None:
        key = (term, kind)
        counts[key] += 1
        if key not in examples:
            left = max(0, start - 60)
            examples[key] = " ".join(text[left : start + len(term) + 60].split())

    for text in texts:
        for match in _CAPS.finditer(text):
            token = match.group(0)
            if len(token.replace("-", "")) >= 2 and lower[token.casefold()] < 3:
                add(token, "caps", text, match.start())
        for match in _NAME.finditer(text):
            phrase = match.group(0)
            words = re.split(r"\s+|-", phrase)
            if _SENTENCE_START.search(text[: match.start()]):
                # Drop a sentence-initial ordinary word ("When Andropov ..." -> "Andropov").
                first = words[0]
                ordinary = lower[first.casefold()] >= 1
                if ordinary or (len(words) > 1 and not named[first]):
                    rest = phrase[len(first) :].lstrip(" -")
                    if not rest:
                        continue
                    phrase, words = rest, words[1:]
            phrase = _POSSESSIVE.sub("", phrase)
            core = [word for word in words if word[:1].isupper()]
            if all(lower[word.casefold()] >= 3 for word in core):
                continue
            add(phrase, "name", text, match.start())

    ranked = [
        TermCandidate(term, kind, count, examples[(term, kind)])
        for (term, kind), count in counts.items()
        if count >= min_count
    ]
    ranked.sort(key=lambda item: (-item.count, item.term))
    return ranked


def terms_to_tsv(terms: list[TermCandidate]) -> str:
    rows = ["term\tkind\tcount\texample"]
    rows += [f"{item.term}\t{item.kind}\t{item.count}\t{item.example}" for item in terms]
    return "\n".join(rows) + "\n"
