"""Cross-platform font discovery and required-glyph validation."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import pymupdf

from pdftranslate.rendering.errors import FontValidationError


def _font_candidates() -> tuple[Path, ...]:
    windows_root = Path(os.environ.get("WINDIR", "C:/Windows"))
    return (
        windows_root / "Fonts" / "segoeui.ttf",
        windows_root / "Fonts" / "arial.ttf",
        windows_root / "Fonts" / "calibri.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/freefont/FreeSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    )


def discover_font(explicit_path: Path | None = None) -> Path:
    """Resolve an explicit font or the first known system Cyrillic font."""
    if explicit_path is not None:
        candidate = explicit_path.expanduser().resolve()
        if not candidate.exists() or not candidate.is_file():
            raise FontValidationError(f"font file does not exist: {candidate}")
        return candidate

    for candidate in _font_candidates():
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    raise FontValidationError(
        "no Cyrillic font was found; pass --font with a TrueType or OpenType font path"
    )


def required_cyrillic_characters(texts: Iterable[str]) -> tuple[str, ...]:
    """Return the distinct Cyrillic code points used by translated text."""
    return tuple(
        sorted({character for text in texts for character in text if _is_cyrillic(character)})
    )


def validate_font(font_path: Path, texts: Iterable[str]) -> None:
    """Load a font and prove that it contains every required Cyrillic glyph."""
    try:
        font = pymupdf.Font(fontfile=str(font_path))  # type: ignore[no-untyped-call]
    except (OSError, RuntimeError, ValueError) as error:
        raise FontValidationError(f"cannot load font {font_path}: {error}") from error

    required = required_cyrillic_characters(texts)
    missing = tuple(
        character
        for character in required
        if font.has_glyph(ord(character)) == 0  # type: ignore[no-untyped-call]
    )
    if missing:
        rendered = " ".join(f"{character} (U+{ord(character):04X})" for character in missing[:12])
        suffix = " ..." if len(missing) > 12 else ""
        raise FontValidationError(
            f"font {font_path} lacks required Cyrillic glyphs: {rendered}{suffix}"
        )


def _is_cyrillic(character: str) -> bool:
    codepoint = ord(character)
    return 0x0400 <= codepoint <= 0x052F
