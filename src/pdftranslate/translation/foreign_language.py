"""Conservative foreign-language unit classification and span preservation."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from pdftranslate.domain.document import ForeignLanguageClassification
from pdftranslate.translation.errors import ProtectedTokenError

FOREIGN_PLACEHOLDER_PREFIX = "__PDFTR_FOREIGN_"

_WORD = re.compile(r"[A-Za-z]+(?:[’'][A-Za-z]+)?")
_GREEK_WORD = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff][\u0300-\u036f\u0370-\u03ff\u1f00-\u1fff]*")
_ACADEMIC_TERMS = (
    "faute de mieux",
    "magistratus",
    "nomos",
    "ipsi",
    "sibi",
    "lex",
    "ius",
)
_ACADEMIC_TERM = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(item) for item in _ACADEMIC_TERMS) + r")(?!\w)",
    re.IGNORECASE,
)
_LATIN_FUNCTION_WORDS = frozenset(
    {
        "acrius",
        "atque",
        "cuiusque",
        "enim",
        "est",
        "et",
        "ex",
        "hanc",
        "inde",
        "nam",
        "nunc",
        "ob",
        "partim",
        "pro",
        "quam",
        "quisque",
        "quo",
        "quod",
        "rem",
        "se",
        "sua",
        "sub",
        "ut",
        "vi",
    }
)


@dataclass(frozen=True)
class ForeignLanguageDecision:
    classification: ForeignLanguageClassification
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreparedForeignLanguageText:
    """Model-facing text plus exact source spans restored after translation."""

    value: str
    decision: ForeignLanguageDecision
    replacements: tuple[tuple[str, str], ...] = ()

    @property
    def preserved_span_count(self) -> int:
        return len(self.replacements)

    def restore(self, translated: str, paragraph_id: str) -> str:
        result = translated
        for placeholder, original in self.replacements:
            if placeholder not in result:
                raise ProtectedTokenError(
                    f"paragraph {paragraph_id}: translator did not preserve foreign-language span"
                )
            result = result.replace(placeholder, original)
        if FOREIGN_PLACEHOLDER_PREFIX in result:
            raise ProtectedTokenError(
                f"paragraph {paragraph_id}: unresolved foreign-language placeholder"
            )
        return result

    def validate_restored(self, translated: str, paragraph_id: str) -> None:
        originals = tuple(original for _, original in self.replacements)
        for original in dict.fromkeys(originals):
            if translated.count(original) < originals.count(original):
                raise ProtectedTokenError(
                    f"paragraph {paragraph_id}: cached translation is missing a preserved "
                    "foreign-language span"
                )

    def translatable_parts(self) -> tuple[str, ...]:
        """Return only model-facing text, excluding every preserved source span."""
        if not self.replacements:
            return (self.value,)
        parts: list[str] = []
        cursor = 0
        for placeholder, _ in self.replacements:
            start = self.value.find(placeholder, cursor)
            if start < 0:
                raise ProtectedTokenError("foreign-language placeholder map is inconsistent")
            parts.append(self.value[cursor:start])
            cursor = start + len(placeholder)
        parts.append(self.value[cursor:])
        return tuple(parts)

    def restore_parts(self, translated_parts: tuple[str, ...], paragraph_id: str) -> str:
        """Interleave translated prose with exact spans never submitted to the model."""
        expected = len(self.replacements) + 1
        if len(translated_parts) != expected:
            raise ProtectedTokenError(
                f"paragraph {paragraph_id}: translated foreign-language part count mismatch"
            )
        chunks: list[str] = []
        for index, translated_part in enumerate(translated_parts):
            chunks.append(translated_part)
            if index < len(self.replacements):
                chunks.append(self.replacements[index][1])
        return "".join(chunks)


def prepare_foreign_language_text(
    text: str,
    *,
    allow_whole_unit: bool = True,
    whole_unit_text: str | None = None,
) -> PreparedForeignLanguageText:
    """Classify a unit and protect deterministic Greek/academic spans."""
    normalized = unicodedata.normalize("NFC", text)
    if FOREIGN_PLACEHOLDER_PREFIX in normalized:
        raise ProtectedTokenError("source text collides with foreign-language placeholders")

    if allow_whole_unit:
        classification_source = unicodedata.normalize("NFC", whole_unit_text or text)
        whole_reason = _whole_unit_reason(classification_source)
        if whole_reason is not None:
            return PreparedForeignLanguageText(
                value=normalized,
                decision=ForeignLanguageDecision(
                    ForeignLanguageClassification.PRESERVE_FOREIGN_UNIT,
                    (whole_reason,),
                ),
            )

    spans = _protected_spans(normalized)
    if not spans:
        return PreparedForeignLanguageText(
            value=normalized,
            decision=ForeignLanguageDecision(
                ForeignLanguageClassification.TRANSLATE,
                ("no_confident_foreign_language_evidence",),
            ),
        )

    chunks: list[str] = []
    replacements: list[tuple[str, str]] = []
    reasons: list[str] = []
    cursor = 0
    for index, (start, end, reason) in enumerate(spans):
        placeholder = f"{FOREIGN_PLACEHOLDER_PREFIX}{index:04d}__"
        chunks.extend((normalized[cursor:start], placeholder))
        replacements.append((placeholder, normalized[start:end]))
        reasons.append(reason)
        cursor = end
    chunks.append(normalized[cursor:])
    return PreparedForeignLanguageText(
        value="".join(chunks),
        decision=ForeignLanguageDecision(
            ForeignLanguageClassification.TRANSLATE_WITH_PRESERVED_SPANS,
            tuple(dict.fromkeys(reasons)),
        ),
        replacements=tuple(replacements),
    )


def _whole_unit_reason(text: str) -> str | None:
    letters = [character for character in text if character.isalpha()]
    greek_letters = [character for character in letters if _is_greek(character)]
    if len(greek_letters) >= 4 and len(greek_letters) / max(1, len(letters)) >= 0.70:
        return "greek_script_unit"

    words = [match.group(0).casefold() for match in _WORD.finditer(text)]
    hits = [word for word in words if word in _LATIN_FUNCTION_WORDS]
    if len(words) >= 10 and len(hits) >= 4 and len(set(hits)) >= 3:
        return "latin_function_word_evidence"
    return None


def _protected_spans(text: str) -> tuple[tuple[int, int, str], ...]:
    candidates = [
        (match.start(), match.end(), "greek_script_span") for match in _GREEK_WORD.finditer(text)
    ]
    candidates.extend(
        (match.start(), match.end(), "academic_foreign_term")
        for match in _ACADEMIC_TERM.finditer(text)
    )
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0]), item[2]))
    selected: list[tuple[int, int, str]] = []
    for candidate in candidates:
        if selected and candidate[0] < selected[-1][1]:
            continue
        selected.append(candidate)
    return tuple(selected)


def _is_greek(character: str) -> bool:
    return "GREEK" in unicodedata.name(character, "")
