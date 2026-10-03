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
_LETTER = r"[A-Za-z\u0410-\u044F\u0401\u0451]"
_TRANSLATED_MARKER = re.compile(
    rf"^(\([0-9]{{1,2}}\)|\({_LETTER}\)|[0-9]{{1,2}}[.)]|{_LETTER}[.)])(\s+)"
)
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

    The source paragraph owns the structural marker; the translation provider owns only the
    semantic content. Leading translated marker prefixes are removed deterministically so a
    provider may translate, delete, duplicate, or restyle the marker without affecting the final
    structure. Prefixes of a different marker family are preserved as semantic content, so a
    legitimate initial such as ``A. Smith`` is never removed.
    """
    marker = detect_list_marker(source_text)
    if marker is None:
        return None
    content = _strip_translated_markers(
        translated_text,
        source_marker=marker.marker_text,
        source_family=marker.family,
    )
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


def _strip_translated_markers(
    translated_text: str, *, source_marker: str, source_family: str
) -> str:
    text = translated_text.lstrip()
    text = _strip_exact_source_markers(text, source_marker)
    for _ in range(_MAX_MARKER_STRIPS):
        prefix = _translated_marker_prefix(text, family=source_family)
        if prefix is None:
            break
        text = prefix[2].lstrip()
    return text


def _strip_exact_source_markers(text: str, source_marker: str) -> str:
    for _ in range(_MAX_MARKER_STRIPS):
        if not text.startswith(source_marker):
            break
        tail = text[len(source_marker) :]
        if tail and not tail[0].isspace():
            break
        text = tail.lstrip()
    return text


def _translated_marker_prefix(text: str, *, family: str) -> tuple[str, str, str] | None:
    """Return ``(marker_text, separation, rest)`` for a leading translated marker prefix.

    Bullet and dash glyphs are always structural. A numbered or letter prefix is stripped only
    when it belongs to the source marker's own family, so a provider-restyled marker is removed
    without deleting a semantic initial such as ``A. Smith``.
    """
    if not text:
        return None
    if text[0] in _BULLET_GLYPHS or text[0] in _DASH_BULLETS:
        separation = _separation(text[1:])
        if not separation:
            return None
        return text[0], separation, text[1 + len(separation) :]
    if family == "bullet":
        return None
    match = _TRANSLATED_MARKER.match(text)
    if match is None:
        return None
    marker = match.group(1)
    core = marker.lstrip("(").rstrip(")")
    if ("letter" if core[0].isalpha() else "numbered") != family:
        return None
    return marker, match.group(2), text[match.end() :]
