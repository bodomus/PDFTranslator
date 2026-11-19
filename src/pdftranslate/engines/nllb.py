"""NLLB engine: sentence-level segments, beam search, paragraph recombination."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path

from pdftranslate.engines.base import (
    EngineCapabilities,
    EngineRequest,
    EngineResult,
    EngineSettings,
)
from pdftranslate.translation.errors import TranslationError
from pdftranslate.translation.protocol import Translator
from pdftranslate.translation.text import Segment, recombine_segments, segment_text

# NLLB quality drops sharply on long inputs; translate roughly sentence by sentence.
SEGMENT_TOKENS = 160
BATCH_SIZE = 8

_SENTENCE_END = re.compile(r"[.!?][”\"’')\]]*\s+(?=[“\"‘'(\[]?[A-Z0-9])")
_INITIAL = re.compile(r"(?:[A-Z]\.)+")
_ABBREVIATIONS = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "dr",
        "st",
        "gen",
        "col",
        "lt",
        "capt",
        "maj",
        "sgt",
        "prof",
        "rev",
        "vol",
        "ch",
        "chs",
        "p",
        "pp",
        "no",
        "nos",
        "fig",
        "e.g",
        "i.e",
        "cf",
        "vs",
        "etc",
        "al",
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "sept",
        "oct",
        "nov",
        "dec",
        "u.s",
        "u.k",
        "jr",
        "sr",
        "co",
        "inc",
        "ltd",
    }
)


class NllbEngine:
    """Adapter from the paragraph engine contract to an NLLB-style batch translator."""

    def __init__(self, translator: Translator, *, beams: int) -> None:
        self._translator = translator
        self._beams = beams

    @property
    def engine_id(self) -> str:
        return f"nllb:{self._translator.model_name}:b{self._beams}:s{SEGMENT_TOKENS}"

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities()

    def translate(self, requests: Sequence[EngineRequest]) -> list[EngineResult]:
        results: list[EngineResult] = []
        for request in requests:
            try:
                segments = sentence_segments(request.text, self._translator.count_tokens)
                texts = [segment.text for segment in segments]
                translated: list[str] = []
                for offset in range(0, len(texts), BATCH_SIZE):
                    translated.extend(
                        self._translator.translate_batch(texts[offset : offset + BATCH_SIZE])
                    )
                results.append(EngineResult(recombine_segments(segments, translated).strip()))
            except (TranslationError, ValueError) as error:
                results.append(EngineResult(None, str(error)))
        return results


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences without breaking after common abbreviations or initials."""
    sentences: list[str] = []
    start = 0
    for match in _SENTENCE_END.finditer(text):
        before = text[start : match.start() + 1]
        word = before.rsplit(maxsplit=1)[-1] if before.split() else ""
        if word.rstrip(".").casefold() in _ABBREVIATIONS or _INITIAL.fullmatch(word):
            continue
        sentences.append(text[start : match.end()].strip())
        start = match.end()
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def sentence_segments(
    text: str, count_tokens: Callable[[str], int], max_tokens: int = SEGMENT_TOKENS
) -> tuple[Segment, ...]:
    """Translate units of single sentences; only overlong sentences are split further."""
    segments: list[Segment] = []
    for sentence in split_sentences(text):
        if count_tokens(sentence) <= max_tokens:
            segments.append(Segment(sentence, " "))
            continue
        parts = segment_text(sentence, count_tokens=count_tokens, max_tokens=max_tokens)
        segments.extend(Segment(part.text, " ") for part in parts.segments)
    if not segments:
        return (Segment(text),)
    segments[-1] = Segment(segments[-1].text)
    return tuple(segments)


def create_nllb_engine(settings: EngineSettings) -> NllbEngine:
    from pdftranslate.config import Settings
    from pdftranslate.translation.nllb import DEFAULT_NLLB_MODEL, DeviceRequest, NllbTranslator

    root = Path(settings.cache_dir) if settings.cache_dir else Settings().cache_dir
    device: DeviceRequest = "cuda" if settings.device == "cuda" else "cpu"
    if settings.device == "auto":
        device = "auto"
    translator = NllbTranslator(
        model_name=settings.model or DEFAULT_NLLB_MODEL,
        device=device,
        cache_dir=root.expanduser() / "models",
        offline=settings.offline,
        num_beams=settings.beams,
    )
    return NllbEngine(translator, beams=settings.beams)
