"""Glossary placeholder preparation, restoration, and compliance evidence."""

from __future__ import annotations

from dataclasses import dataclass

from pdftranslate.glossary.errors import GlossaryComplianceError
from pdftranslate.glossary.matcher import GlossaryMatch, find_glossary_matches
from pdftranslate.glossary.models import (
    GLOSSARY_BEHAVIOR_REVISION,
    GLOSSARY_PLACEHOLDER_PREFIX,
    GlossaryEntryMode,
    GlossaryInflection,
    GlossaryOccurrenceEvidence,
    GlossaryStatistics,
    GlossaryTranslationEvidence,
    LoadedGlossary,
    ParagraphGlossaryEvidence,
)


@dataclass(frozen=True)
class PreparedGlossaryText:
    value: str
    matches: tuple[GlossaryMatch, ...]
    replacements: tuple[tuple[str, str], ...]

    def restore_and_validate(
        self, translated: str, paragraph_id: str
    ) -> tuple[str, ParagraphGlossaryEvidence]:
        result = translated
        for placeholder, target in self.replacements:
            if placeholder not in result:
                raise GlossaryComplianceError(
                    f"paragraph {paragraph_id}: glossary placeholder was not preserved",
                    code="GLOSSARY_PLACEHOLDER_LEAK",
                )
            result = result.replace(placeholder, target)
        if GLOSSARY_PLACEHOLDER_PREFIX in result:
            raise GlossaryComplianceError(
                f"paragraph {paragraph_id}: unresolved glossary placeholder",
                code="GLOSSARY_PLACEHOLDER_LEAK",
            )
        evidence = validate_glossary_output(result, paragraph_id, self.matches)
        return result, evidence


def prepare_glossary_text(text: str, glossary: LoadedGlossary) -> PreparedGlossaryText:
    """Replace fixed glossary-owned spans before generic token protection."""
    if GLOSSARY_PLACEHOLDER_PREFIX in text:
        raise GlossaryComplianceError(
            "source text collides with the internal glossary placeholder namespace",
            code="GLOSSARY_PLACEHOLDER_LEAK",
        )
    matches = find_glossary_matches(text, glossary.document)
    chunks: list[str] = []
    replacements: list[tuple[str, str]] = []
    cursor = 0
    for index, match in enumerate(matches):
        chunks.append(text[cursor : match.start])
        fixed = (
            match.entry.mode is GlossaryEntryMode.PRESERVE
            or match.entry.inflection is GlossaryInflection.FIXED
        )
        if fixed:
            placeholder = f"{GLOSSARY_PLACEHOLDER_PREFIX}{index:04d}__"
            chunks.append(placeholder)
            replacements.append((placeholder, match.entry.target))
        else:
            chunks.append(text[match.start : match.end])
        cursor = match.end
    chunks.append(text[cursor:])
    return PreparedGlossaryText("".join(chunks), matches, tuple(replacements))


def validate_glossary_output(
    translated: str,
    paragraph_id: str,
    matches: tuple[GlossaryMatch, ...],
) -> ParagraphGlossaryEvidence:
    """Require every selected preferred target and emit text-free evidence."""
    if not matches:
        return ParagraphGlossaryEvidence(paragraph_id=paragraph_id)
    required: dict[str, tuple[str, int]] = {}
    for match in matches:
        target, count = required.get(match.entry.id, (match.entry.target, 0))
        required[match.entry.id] = (target, count + 1)
    missing = [
        entry_id
        for entry_id, (target, count) in required.items()
        if translated.count(target) < count
    ]
    if missing:
        raise GlossaryComplianceError(
            f"paragraph {paragraph_id}: required glossary target missing for entries "
            + ", ".join(sorted(missing)),
            code="GLOSSARY_TARGET_MISSING",
        )
    occurrences = tuple(
        GlossaryOccurrenceEvidence(
            entry_id=match.entry.id,
            mode=match.entry.mode,
            match=match.entry.match,
            inflection=match.entry.inflection,
            priority=match.entry.priority,
            compliance="compliant",
        )
        for match in matches
    )
    return ParagraphGlossaryEvidence(
        paragraph_id=paragraph_id,
        occurrences=occurrences,
        compliance="compliant",
    )


def build_glossary_evidence(
    glossary: LoadedGlossary,
    paragraphs: tuple[ParagraphGlossaryEvidence, ...],
) -> GlossaryTranslationEvidence:
    """Aggregate deterministic run evidence without copying glossary text."""
    matched_ids = tuple(
        sorted({entry_id for paragraph in paragraphs for entry_id in paragraph.entry_ids})
    )
    all_ids = {item.id for item in glossary.document.entries}
    unmatched_ids = tuple(sorted(all_ids.difference(matched_ids)))
    occurrences = tuple(item for paragraph in paragraphs for item in paragraph.occurrences)
    return GlossaryTranslationEvidence(
        schema_version=glossary.document.schema_version,
        glossary_version=glossary.document.glossary_version,
        source_language=glossary.document.source_language,
        target_language=glossary.document.target_language,
        fingerprint=glossary.fingerprint,
        behavior_revision=GLOSSARY_BEHAVIOR_REVISION,
        matched_entry_ids=matched_ids,
        unmatched_entry_ids=unmatched_ids,
        paragraphs=paragraphs,
        statistics=GlossaryStatistics(
            total_entries=len(glossary.document.entries),
            matched_entries=len(matched_ids),
            unmatched_entries=len(unmatched_ids),
            applied_occurrences=len(occurrences),
            preserved_occurrences=sum(
                item.mode is GlossaryEntryMode.PRESERVE for item in occurrences
            ),
            mandatory_translation_occurrences=sum(
                item.mode is GlossaryEntryMode.TRANSLATE for item in occurrences
            ),
            violations=sum(paragraph.compliance == "violation" for paragraph in paragraphs),
            conflicts=0,
            ambiguous_matches=0,
        ),
    )
