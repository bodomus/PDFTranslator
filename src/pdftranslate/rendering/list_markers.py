"""Conservative source-owned list-marker detection and reconstruction.

The translation model owns the semantic content of a translated list item. The source
PDF owns the structural marker and the marker-to-content separation. These helpers derive
both from retained source paragraph text and reconstruct the visible list item without
trusting the translated text to reproduce the marker.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_BULLET_GLYPHS = frozenset("•●○▪")
_DASH_BULLETS = frozenset("-–—*")
_WHITESPACE = re.compile(r"\s+")
_MARKER = re.compile(r"^(\([0-9]{1,2}\)|\([a-zA-Z]\)|[0-9]{1,2}[.)]|[a-zA-Z][.)])(\s+)")
_UPPERCASE_LETTER_PERIOD = re.compile(r"^[A-Z]\.$")
_MAX_MARKER_STRIPS = 3


@dataclass(frozen=True)
class ListMarker:
    """One confidently identified source-owned structural marker."""

    marker_text: str
    family: str
    separation: str
    content_start: int
    content_text: str


def detect_list_marker(source_text: str) -> ListMarker | None:
    """Return a supported marker at the start of one logical paragraph, or ``None``.

    Detection is deliberately conservative. Ambiguous prose prefixes such as years, decimal
    numbers, negative temperatures, and uppercase initials in names are left alone.
    """
    text = source_text.lstrip()
    if not text:
        return None
    bullet = _detect_bullet(text)
    if bullet is not None:
        return bullet
    match = _MARKER.match(text)
    if match is None:
        return None
    marker = match.group(1)
    separation = match.group(2)
    content = text[match.end() :]
    if not content:
        return None
    if _UPPERCASE_LETTER_PERIOD.match(marker) and len(content.split()) < 2:
        return None
    core = marker.lstrip("(").rstrip(")")
    return ListMarker(
        marker_text=marker,
        family="letter" if core[0].isalpha() else "numbered",
        separation=separation,
        content_start=match.end(),
        content_text=content,
    )


def reconstruct_list_item_text(source_text: str, translated_text: str) -> str | None:
    """Reconstruct marker + translated content, or ``None`` when there is no content.

    Leading translated marker-like prefixes are removed deterministically, so a provider may
    translate, delete, duplicate, or restyle the marker without affecting the final structure.
    """
    marker = detect_list_marker(source_text)
    if marker is None:
        return None
    content = _strip_translated_markers(translated_text, source_marker=marker.marker_text)
    if not content:
        return None
    return f"{marker.marker_text}{marker.separation}{content}"


def _detect_bullet(text: str) -> ListMarker | None:
    character = text[0]
    if character not in _BULLET_GLYPHS and character not in _DASH_BULLETS:
        return None
    separation = _separation(text[1:])
    if not separation:
        return None
    content = text[1 + len(separation) :]
    if not content:
        return None
    return ListMarker(
        marker_text=character,
        family="bullet",
        separation=separation,
        content_start=1 + len(separation),
        content_text=content,
    )


def _separation(text: str) -> str:
    match = _WHITESPACE.match(text)
    return match.group(0) if match is not None else ""


def _strip_translated_markers(translated_text: str, *, source_marker: str) -> str:
    text = translated_text.lstrip()
    for _ in range(_MAX_MARKER_STRIPS):
        if text.startswith(source_marker):
            tail = text[len(source_marker) :]
            if not tail or tail[0].isspace():
                text = tail.lstrip()
                continue
        marker = detect_list_marker(text)
        if marker is None:
            break
        text = marker.content_text.lstrip()
    return text
