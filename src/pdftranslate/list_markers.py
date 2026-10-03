"""Conservative source-owned list-marker detection and reattachment.

The translation model owns the semantic content of a translated list item. The source PDF owns
the structural marker, its family, and the marker-to-content separation. ``detect_list_marker``
derives those from retained source paragraph text; ``reattach_list_marker`` joins the source-owned
marker to semantic-only translated text. Neither the translation provider nor the renderer infers
structural ownership from translated text.

This module is a leaf shared by the translation and rendering stages, so it must not import from
``pdftranslate.domain``, ``pdftranslate.reconstruction``, ``pdftranslate.translation``, or
``pdftranslate.rendering``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_BULLET_GLYPHS = frozenset("•●○▪")
_DASH_BULLETS = frozenset("-–—*")
_WHITESPACE = re.compile(r"\s+")
_MARKER = re.compile(r"^(\([0-9]{1,2}\)|\([a-zA-Z]\)|[0-9]{1,2}[.)]|[a-zA-Z][.)])(\s+)")
_UPPERCASE_LETTER_PERIOD = re.compile(r"^[A-Z]\.$")


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


def reattach_list_marker(source_text: str, translated_text: str) -> str | None:
    """Join a source-owned marker to semantic-only translated content, or ``None``.

    This is the only reconstruction step: the marker comes from the source, and the translated
    text is already semantic-only (the provider never saw the marker). No translated-prefix
    stripping is performed.
    """
    marker = detect_list_marker(source_text)
    if marker is None or not translated_text.strip():
        return None
    return f"{marker.marker_text}{marker.separation}{translated_text}"


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
