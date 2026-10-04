"""Conservative list evidence from immutable source spans, independent of rendering."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

from pdftranslate.domain.text_block import BoundingBox
from pdftranslate.reconstruction.models import LogicalParagraph, ParagraphFragment, ParagraphKind

_PREFIX = re.compile(r"^\s*(?P<marker>[•\-–*]|\d+[.)]|[A-Za-z][.)])\s+(?=\S)")
_INITIAL_NAME = re.compile(r"^[A-Z]\.\s+[A-Z][a-z]+(?:\s|$)")
_NAME_QUALIFIER = re.compile(r"[([]|[,;:]|\s[-–—/]\s")
_APOSTROPHE_NAME_PREFIX = re.compile(r"^[a-z]+['’](?=[A-Z])")
_NAME_PARTICLES = frozenset(
    [
        "al",
        "and",
        "bin",
        "bint",
        "da",
        "das",
        "de",
        "del",
        "della",
        "den",
        "der",
        "di",
        "do",
        "dos",
        "du",
        "el",
        "et",
        "ibn",
        "la",
        "le",
        "of",
        "ten",
        "ter",
        "van",
        "von",
        "y",
    ]
)


def is_list_marker(text: str) -> bool:
    """Recognize a marker token; this alone never authorizes source classification."""
    match = _PREFIX.match(f"{text} x")
    return match is not None and match.group("marker") == text


@dataclass(frozen=True)
class SourceListItem:
    marker_text: str
    marker_source_rect: BoundingBox
    content_source_rect: BoundingBox
    semantic: LogicalParagraph

    def semantic_output(self, text: str) -> str:
        """Replace provider structure only after source geometry has proved a list item."""
        match = _PREFIX.match(text)
        if match is None or _INITIAL_NAME.match(text.lstrip()):
            return text
        # A semantic nested prefix belongs to the content, even in a confirmed list.
        source_prefix = _PREFIX.match(self.semantic.text)
        if source_prefix is not None and source_prefix.group("marker") == match.group("marker"):
            return text
        return text[match.end() :]

    def translated_text(self, text: str) -> str:
        return f"{self.marker_text} {self.semantic_output(text)}"

    def rendered_text(self, text: str) -> str:
        """Read canonical serialized output, or a legacy provider value, as semantic text."""
        canonical = f"{self.marker_text} "
        if text.startswith(canonical):
            return text[len(canonical) :]
        return self.semantic_output(text)


def source_list_item(
    paragraph: LogicalParagraph,
    paragraphs: Sequence[LogicalParagraph] = (),
) -> SourceListItem | None:
    """Return evidence only for independently bounded marker/content on one source line.

    A regex-only list kind, a combined span or guessed font advance is insufficient.
    Letter-dot prefixes require prose content and neighboring sequential source evidence.
    """
    candidate = _source_candidate(paragraph)
    if candidate is None or _initial_name(candidate):
        return None
    marker = candidate.marker_text
    if len(marker) == 2 and marker[0].isalpha() and marker[1] == ".":
        try:
            index = next(i for i, item in enumerate(paragraphs) if item is paragraph)
        except StopIteration:
            return None
        for other_index in (index - 1, index + 1):
            if not 0 <= other_index < len(paragraphs):
                continue
            other = paragraphs[other_index]
            witness = _source_candidate(other)
            if (
                witness is not None
                and not _initial_name(witness)
                and len(witness.marker_text) == 2
                and witness.marker_text[1] == "."
                and ord(witness.marker_text[0]) - ord(marker[0]) == other_index - index
                and other.anchor_page_number == paragraph.anchor_page_number
                and other.fragments[0].column == paragraph.fragments[0].column
                and abs(witness.marker_source_rect.x0 - candidate.marker_source_rect.x0) <= 0.5
                and abs(witness.content_source_rect.x0 - candidate.content_source_rect.x0) <= 0.5
            ):
                return candidate
        return None
    return candidate


def source_letter_prefix(paragraph: LogicalParagraph) -> bool:
    """Prove a letter-dot prefix/content source line for text joining, never list ownership."""
    candidate = _source_candidate(paragraph)
    return (
        candidate is not None
        and len(candidate.marker_text) == 2
        and candidate.marker_text[0].isalpha()
        and candidate.marker_text[1] == "."
    )


def source_list_continuation(
    item: SourceListItem,
    previous: ParagraphFragment,
    fragment: ParagraphFragment,
    max_vertical_gap_ratio: float,
) -> bool:
    """Prove ownership of a following source line, without crossing raw blocks."""
    first = item.semantic.fragments[0]
    if (
        fragment.mapping.source_block_id != first.mapping.source_block_id
        or fragment.mapping.page_number != first.mapping.page_number
        or fragment.column != first.column
        or not fragment.spans
        or not _valid_box(fragment.bbox)
        or not _contains(fragment.mapping.bbox, fragment.bbox)
        or any(
            not _valid_box(span.bbox) or not _contains(fragment.bbox, span.bbox)
            for span in fragment.spans
        )
        or "".join(span.text for span in fragment.spans).strip() != fragment.text.strip()
        or abs(fragment.bbox.x0 - item.content_source_rect.x0) > 0.5
        or _PREFIX.match(fragment.text) is not None
    ):
        return False
    height = min(previous.bbox.y1 - previous.bbox.y0, fragment.bbox.y1 - fragment.bbox.y0)
    gap = fragment.bbox.y0 - previous.bbox.y1
    return -height * 0.35 <= gap <= height * max_vertical_gap_ratio


def _initial_name(candidate: SourceListItem) -> bool:
    marker = candidate.marker_text
    if len(marker) != 2 or not marker[0].isalpha() or marker[1] != ".":
        return False
    # Qualifiers after a name do not prove prose/list ownership. Name particles
    # and apostrophe/hyphen components belong to the name, not to list evidence.
    # Lowercase apostrophe prefixes need no particle/surname allowlist; only
    # the ambiguity check normalizes them, never the semantic text itself.
    # An aligned A/B sequence still cannot distinguish these semantic initials.
    name = _NAME_QUALIFIER.split(candidate.semantic.text, maxsplit=1)[0]
    words = tuple(
        part
        for word in name.split()
        for part in (
            (word,)
            if word[0].isupper()
            else re.split(r"['’\-]+", _APOSTROPHE_NAME_PREFIX.sub("", word))
        )
        if part
    )
    return any(word[0].isupper() for word in words) and all(
        (word[0].isupper() or word.casefold().rstrip(".") in _NAME_PARTICLES)
        and all(char.isalpha() or char in "'-’." for char in word)
        for word in words
    )


def _source_candidate(paragraph: LogicalParagraph) -> SourceListItem | None:
    if paragraph.ambiguous or paragraph.kind not in {ParagraphKind.BODY, ParagraphKind.LIST_ITEM}:
        return None
    first = paragraph.fragments[0]
    if first.mapping.page_number != paragraph.anchor_page_number:
        return None
    match = _PREFIX.match(paragraph.text)
    if match is None:
        return None
    marker = match.group("marker")
    separate_line = first.text.strip() == marker
    if separate_line:
        if len(paragraph.fragments) < 2 or len(first.spans) != 1:
            return None
        content_first = paragraph.fragments[1]
        if content_first.mapping.source_block_id != first.mapping.source_block_id:
            return None
        spans = (*first.spans, *content_first.spans)
    else:
        content_first = first
        spans = first.spans
        if not first.text.startswith(paragraph.text[: match.end()]):
            return None
    if len(spans) < 2 or spans[0].text.strip() != marker or not spans[1].text.strip():
        return None
    semantic_first_text = content_first.text if separate_line else first.text[match.end() :]
    if "".join(span.text for span in spans[1:]).strip() != semantic_first_text.strip():
        return None
    if any(not _valid_box(span.bbox) for span in spans):
        return None
    marker_box = spans[0].bbox
    content_box = _union(tuple(span.bbox for span in spans[1:]))
    boxes = (paragraph.bbox, first.bbox, marker_box, content_box, *(span.bbox for span in spans))
    if any(not _valid_box(box) for box in boxes):
        return None
    if (
        marker_box.x1 > content_box.x0
        or not (marker_box.y0 < content_box.y1 and content_box.y0 < marker_box.y1)
        or not _contains(first.bbox, marker_box)
        or any(not _contains(content_first.bbox, span.bbox) for span in spans[1:])
        or not _contains(paragraph.bbox, first.bbox)
        or any(
            previous.bbox.x1 > current.bbox.x0
            for previous, current in zip(spans[1:], spans[2:], strict=False)
        )
    ):
        return None
    # Every semantic span on this fragment must really share the marker's source line.
    if any(
        not (marker_box.y0 < span.bbox.y1 and span.bbox.y0 < marker_box.y1) for span in spans[1:]
    ):
        return None
    semantic_first = content_first.model_copy(
        update={"text": semantic_first_text, "bbox": content_box, "spans": spans[1:]}
    )
    fragments = (semantic_first, *paragraph.fragments[2 if separate_line else 1 :])
    if any(
        fragment.mapping.page_number != paragraph.anchor_page_number
        or fragment.column != first.column
        or not _valid_box(fragment.bbox)
        or not _contains(paragraph.bbox, fragment.bbox)
        for fragment in fragments
    ):
        return None
    semantic = paragraph.model_copy(
        update={
            "text": paragraph.text[match.end() :],
            "kind": ParagraphKind.BODY,
            "bbox": _union(tuple(fragment.bbox for fragment in fragments)),
            "fragments": fragments,
            "spans": tuple(span for fragment in fragments for span in fragment.spans),
        }
    )
    return SourceListItem(marker, marker_box, content_box, semantic)


def _valid_box(box: BoundingBox) -> bool:
    return (
        all(isfinite(value) for value in (box.x0, box.y0, box.x1, box.y1))
        and box.x1 > box.x0
        and box.y1 > box.y0
    )


def _contains(outer: BoundingBox, inner: BoundingBox) -> bool:
    return (
        inner.x0 >= outer.x0 - 0.5
        and inner.y0 >= outer.y0 - 0.5
        and inner.x1 <= outer.x1 + 0.5
        and inner.y1 <= outer.y1 + 0.5
    )


def _union(boxes: tuple[BoundingBox, ...]) -> BoundingBox:
    return BoundingBox(
        x0=min(box.x0 for box in boxes),
        y0=min(box.y0 for box in boxes),
        x1=max(box.x1 for box in boxes),
        y1=max(box.y1 for box in boxes),
    )
