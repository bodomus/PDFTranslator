"""Typed glossary contracts and privacy-safe translation evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

GLOSSARY_BEHAVIOR_REVISION = 1
GLOSSARY_PLACEHOLDER_PREFIX = "__PDFTR_GLOSSARY_"


class GlossaryModel(BaseModel):
    """Strict immutable JSON-safe base without importing the document package."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class GlossaryEntryMode(StrEnum):
    TRANSLATE = "translate"
    PRESERVE = "preserve"


class GlossaryMatchType(StrEnum):
    WHOLE_WORD = "whole_word"
    PHRASE = "phrase"
    EXACT = "exact"


class GlossaryInflection(StrEnum):
    FIXED = "fixed"
    ALLOW_MODEL = "allow_model"


class GlossaryEntry(GlossaryModel):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    mode: GlossaryEntryMode
    case_sensitive: bool
    match: GlossaryMatchType
    inflection: GlossaryInflection
    priority: int = Field(ge=-10000, le=10000)
    notes: str | None = None

    @field_validator("source", "target")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("glossary source and target cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_policy(self) -> GlossaryEntry:
        if self.mode is GlossaryEntryMode.PRESERVE and self.target != self.source:
            raise ValueError("preserve entry target must exactly equal source")
        if (
            self.mode is GlossaryEntryMode.PRESERVE
            and self.inflection is not GlossaryInflection.FIXED
        ):
            raise ValueError("preserve entries require fixed inflection")
        return self


class GlossaryDocument(GlossaryModel):
    schema_version: Literal["1.0"]
    glossary_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    source_language: Literal["en"]
    target_language: Literal["ru"]
    entries: tuple[GlossaryEntry, ...] = Field(min_length=1)


@dataclass(frozen=True)
class LoadedGlossary:
    document: GlossaryDocument
    fingerprint: str


class GlossaryOccurrenceEvidence(GlossaryModel):
    entry_id: str
    mode: GlossaryEntryMode
    match: GlossaryMatchType
    inflection: GlossaryInflection
    priority: int
    compliance: Literal["compliant", "violation"]


class ParagraphGlossaryEvidence(GlossaryModel):
    paragraph_id: str
    occurrences: tuple[GlossaryOccurrenceEvidence, ...] = ()
    compliance: Literal["not_matched", "compliant", "violation"] = "not_matched"
    warning_codes: tuple[str, ...] = ()

    @property
    def entry_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.entry_id for item in self.occurrences))


class GlossaryStatistics(GlossaryModel):
    total_entries: int = Field(ge=0)
    matched_entries: int = Field(ge=0)
    unmatched_entries: int = Field(ge=0)
    applied_occurrences: int = Field(ge=0)
    preserved_occurrences: int = Field(ge=0)
    mandatory_translation_occurrences: int = Field(ge=0)
    violations: int = Field(ge=0)
    conflicts: int = Field(ge=0)
    ambiguous_matches: int = Field(ge=0)


class GlossaryTranslationEvidence(GlossaryModel):
    enabled: Literal[True] = True
    schema_version: Literal["1.0"]
    glossary_version: str
    source_language: Literal["en"]
    target_language: Literal["ru"]
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    behavior_revision: int = Field(ge=1)
    matched_entry_ids: tuple[str, ...] = ()
    unmatched_entry_ids: tuple[str, ...] = ()
    paragraphs: tuple[ParagraphGlossaryEvidence, ...] = ()
    statistics: GlossaryStatistics

    def by_paragraph_id(self) -> dict[str, ParagraphGlossaryEvidence]:
        return {item.paragraph_id: item for item in self.paragraphs}
