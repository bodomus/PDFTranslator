"""Pure text preparation, protection, and token-aware segmentation."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from pdftranslate.translation.errors import ProtectedTokenError

_PAGE_NUMBER = re.compile(r"^\s*\d+\s*$")
_IDENTIFIER = re.compile(r"^\s*[A-Z0-9][A-Z0-9_.:/\\-]*\s*$")
_PDF_LIGATURES = str.maketrans(
    {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb05": "st",
        "\ufb06": "st",
    }
)
_PATH_PART = r"[\w.-]*[\w-]"
_RELATIVE_PATH = rf"(?<!\w)\.{{1,2}}/(?:{_PATH_PART}/)*{_PATH_PART}"
_ABSOLUTE_POSIX_PATH = rf"(?<!\w)/(?:{_PATH_PART}/)+{_PATH_PART}"
_BARE_FILE_PATH = rf"(?<!\w)(?=[\w./-]*(?:[._-]|\d))(?:{_PATH_PART}/)+{_PATH_PART}"
_MEASUREMENTS_ONLY = re.compile(
    r"^\s*(?:\d+(?:[.,]\d+)?\s*(?:%|mm|cm|m|km|mg|g|kg|ml|l|°C|°F)"
    r"(?:\s*[,;/x×]\s*)?)+\s*$",
    re.IGNORECASE,
)
_CODE_LINE = re.compile(
    r"^\s*(?:```|def\s+\w+\s*\(|class\s+\w+|import\s+\w+|from\s+\w+\s+import|"
    r"SELECT\s+.+\s+FROM|(?:if|for|while)\s*\(.+\)|[{}[\];]{2,})",
    re.IGNORECASE | re.DOTALL,
)
_PROTECTED = re.compile(
    r"__PDFTR_GLOSSARY_\d{4}__"
    r"|https?://[^\s<>()]+"
    r"|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"
    r"|[A-Za-z]:\\(?:[^\\\s]+\\)*[^\\\s]+"
    rf"|{_RELATIVE_PATH}"
    rf"|{_ABSOLUTE_POSIX_PATH}"
    rf"|{_BARE_FILE_PATH}"
    r"|\b\d+(?:[.,]\d+)?\s?(?:%|mm|cm|km|mg|kg|ml|°C|°F)\b"
    r"|\b(?:[A-Z]{1,8}[-_/])?\d{3,}(?:[-_/]\d+)*\b",
    re.IGNORECASE,
)
_PARAGRAPH_BREAK = re.compile(r"\n(?:[ \t]*\n)+")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ProtectedText:
    """Text with stable placeholders and exact source replacements."""

    value: str
    replacements: tuple[tuple[str, str], ...]

    def restore(self, translated: str) -> str:
        result = translated
        for placeholder, original in self.replacements:
            if placeholder not in result:
                raise ProtectedTokenError(
                    f"translator did not preserve protected token {original!r}"
                )
            result = result.replace(placeholder, original)
        return result


@dataclass(frozen=True)
class Segment:
    """One inference input and the deterministic separator following it."""

    text: str
    separator_after: str = ""


@dataclass(frozen=True)
class SegmentationResult:
    """Segments plus a warning flag for forced non-sentence splits."""

    segments: tuple[Segment, ...]
    quality_warning: bool = False


def normalize_source_text(text: str) -> str:
    """Normalize cache identity without discarding paragraph structure."""
    normalized = _normalize_pdf_text(text).replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return normalized.strip()


def should_skip_translation(text: str) -> bool:
    """Return true for content that must pass through without model inference."""
    stripped = _normalize_pdf_text(text).strip()
    if not stripped or _PAGE_NUMBER.fullmatch(stripped):
        return True
    if _MEASUREMENTS_ONLY.fullmatch(stripped):
        return True
    if _IDENTIFIER.fullmatch(stripped) and (
        any(char.isdigit() for char in stripped) or "/" in stripped
    ):
        return True
    return bool(_CODE_LINE.search(stripped))


def protect_text(text: str) -> ProtectedText:
    """Replace sensitive tokens with deterministic sentinels."""
    protected_source = _normalize_pdf_text(text)
    replacements: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        placeholder = f"__PDFTR_{len(replacements):04d}__"
        while placeholder in protected_source:
            placeholder = f"_{placeholder}_"
        replacements.append((placeholder, match.group(0)))
        return placeholder

    return ProtectedText(_PROTECTED.sub(replace, protected_source), tuple(replacements))


def _normalize_pdf_text(text: str) -> str:
    return unicodedata.normalize("NFC", text.translate(_PDF_LIGATURES))


def segment_text(
    text: str,
    *,
    count_tokens: Callable[[str], int],
    max_tokens: int,
) -> SegmentationResult:
    """Split without truncation, preferring paragraph and sentence boundaries."""
    if max_tokens < 8:
        raise ValueError("max_tokens must be at least 8")
    if count_tokens(text) <= max_tokens:
        return SegmentationResult((Segment(text),))

    paragraphs = _PARAGRAPH_BREAK.split(text)
    segments: list[Segment] = []
    forced = False
    for paragraph_index, paragraph in enumerate(paragraphs):
        sentences = [part for part in _SENTENCE_BREAK.split(paragraph.strip()) if part]
        paragraph_chunks: list[str] = []
        current = ""
        for sentence in sentences:
            candidate = sentence if not current else f"{current} {sentence}"
            if count_tokens(candidate) <= max_tokens:
                current = candidate
                continue
            if current:
                paragraph_chunks.append(current)
                current = ""
            if count_tokens(sentence) <= max_tokens:
                current = sentence
            else:
                forced = True
                paragraph_chunks.extend(
                    _split_oversized(sentence, count_tokens=count_tokens, max_tokens=max_tokens)
                )
        if current:
            paragraph_chunks.append(current)
        for chunk_index, chunk in enumerate(paragraph_chunks):
            is_last = chunk_index == len(paragraph_chunks) - 1
            separator = "\n\n" if is_last and paragraph_index < len(paragraphs) - 1 else ""
            if not is_last:
                separator = " "
            segments.append(Segment(chunk, separator))

    if not segments:
        return SegmentationResult((Segment(text),))
    if any(count_tokens(segment.text) > max_tokens for segment in segments):
        raise ValueError("segmentation failed to respect the tokenizer limit")
    return SegmentationResult(tuple(segments), forced)


def recombine_segments(segments: tuple[Segment, ...], translated: list[str]) -> str:
    """Recombine translated segments in source order."""
    if len(segments) != len(translated):
        raise ValueError("translated segment count does not match source segments")
    return "".join(
        translated_text + segment.separator_after
        for segment, translated_text in zip(segments, translated, strict=True)
    )


def _split_oversized(
    text: str,
    *,
    count_tokens: Callable[[str], int],
    max_tokens: int,
) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if count_tokens(candidate) <= max_tokens:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if count_tokens(word) <= max_tokens:
            current = word
        else:
            chunks.extend(_split_token(word, count_tokens=count_tokens, max_tokens=max_tokens))
    if current:
        chunks.append(current)
    return chunks


def _split_token(
    token: str,
    *,
    count_tokens: Callable[[str], int],
    max_tokens: int,
) -> list[str]:
    chunks: list[str] = []
    remaining = token
    while remaining:
        low, high = 1, len(remaining)
        best = 0
        while low <= high:
            middle = (low + high) // 2
            if count_tokens(remaining[:middle]) <= max_tokens:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        if best == 0:
            raise ValueError("tokenizer limit cannot fit a single source character")
        chunks.append(remaining[:best])
        remaining = remaining[best:]
    return chunks
