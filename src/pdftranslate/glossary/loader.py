"""Strict UTF-8 glossary loading, validation, and semantic fingerprinting."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import defaultdict
from pathlib import Path

from pydantic import ValidationError

from pdftranslate.glossary.errors import GlossaryError
from pdftranslate.glossary.models import (
    GLOSSARY_BEHAVIOR_REVISION,
    GLOSSARY_PLACEHOLDER_PREFIX,
    GlossaryDocument,
    GlossaryEntry,
    GlossaryEntryMode,
    GlossaryInflection,
    GlossaryMatchType,
    LoadedGlossary,
)

# TSV kinds whose source is matched case-sensitively; "term" entries ignore case.
_CASE_SENSITIVE_KINDS = frozenset({"abbr", "codename", "name", "ocr"})
_TSV_KINDS = _CASE_SENSITIVE_KINDS | {"term"}


def load_glossary(path: Path) -> LoadedGlossary:
    """Load one strict glossary and compute a path-independent behavior fingerprint.

    A ``.tsv`` file is the hand-editable book form: ``source<TAB>target<TAB>kind`` per line,
    ``#`` comments allowed. Its entries are translated, inflected by the model and matched as
    whole phrases.
    """
    selected = path.expanduser().resolve()
    if selected.suffix.casefold() == ".tsv":
        return _load_tsv(selected)
    try:
        payload = selected.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise GlossaryError(f"glossary is not valid UTF-8: {selected}: {error}") from error
    except OSError as error:
        raise GlossaryError(f"cannot read glossary {selected}: {error}") from error
    try:
        document = GlossaryDocument.model_validate_json(payload)
    except ValidationError as error:
        raise GlossaryError(f"invalid glossary {selected}: {error}") from error
    _validate_entries(document.entries)
    return LoadedGlossary(document=document, fingerprint=glossary_fingerprint(document))


def glossary_fingerprint(document: GlossaryDocument) -> str:
    """Hash canonical effective content, including version and behavior revision."""
    entries = sorted(
        (
            {
                "id": item.id,
                "source": _effective_source(item),
                "target": unicodedata.normalize("NFC", item.target),
                "mode": item.mode.value,
                "case_sensitive": item.case_sensitive,
                "match": item.match.value,
                "inflection": item.inflection.value,
                "priority": item.priority,
            }
            for item in document.entries
        ),
        key=lambda item: str(item["id"]),
    )
    canonical = {
        "schema_version": document.schema_version,
        "glossary_version": document.glossary_version,
        "source_language": document.source_language,
        "target_language": document.target_language,
        "behavior_revision": GLOSSARY_BEHAVIOR_REVISION,
        "entries": entries,
    }
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_entries(entries: tuple[GlossaryEntry, ...]) -> None:
    ids: defaultdict[str, list[str]] = defaultdict(list)
    effective: defaultdict[tuple[str, str, bool], list[GlossaryEntry]] = defaultdict(list)
    by_source: defaultdict[str, list[GlossaryEntry]] = defaultdict(list)
    for item in entries:
        ids[item.id].append(item.id)
        normalized = _effective_source(item)
        effective[(normalized, item.match.value, item.case_sensitive)].append(item)
        by_source[_normalize(item.source).casefold()].append(item)
        if GLOSSARY_PLACEHOLDER_PREFIX in item.source or GLOSSARY_PLACEHOLDER_PREFIX in item.target:
            raise GlossaryError(f"placeholder collision in glossary entry {item.id!r}")

    duplicate_ids = sorted(key for key, values in ids.items() if len(values) > 1)
    if duplicate_ids:
        raise GlossaryError(f"duplicate glossary entry IDs: {', '.join(duplicate_ids)}")

    for values in effective.values():
        if len(values) > 1:
            entry_ids = ", ".join(sorted(item.id for item in values))
            raise GlossaryError(f"duplicate or conflicting normalized entries: {entry_ids}")

    for values in by_source.values():
        modes = {item.mode for item in values}
        if len(modes) > 1:
            entry_ids = ", ".join(sorted(item.id for item in values))
            raise GlossaryError(f"preserve/translate conflict between entries: {entry_ids}")


def _effective_source(entry: GlossaryEntry) -> str:
    value = _normalize(entry.source)
    return value if entry.case_sensitive else value.casefold()


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def _load_tsv(path: Path) -> LoadedGlossary:
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    except UnicodeDecodeError as error:
        raise GlossaryError(f"glossary is not valid UTF-8: {path}: {error}") from error
    except OSError as error:
        raise GlossaryError(f"cannot read glossary {path}: {error}") from error
    entries: list[GlossaryEntry] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = [field.strip() for field in line.split("\t")]
        if len(fields) != 3 or not fields[0] or not fields[1] or fields[2] not in _TSV_KINDS:
            raise GlossaryError(
                f"{path}:{number}: expected source, target and kind "
                f"({', '.join(sorted(_TSV_KINDS))}) separated by tabs"
            )
        source, target, kind = fields
        entries.append(
            GlossaryEntry(
                id=f"{kind}-{number:05d}",
                source=source,
                target=target,
                mode=GlossaryEntryMode.TRANSLATE,
                case_sensitive=kind in _CASE_SENSITIVE_KINDS,
                match=GlossaryMatchType.PHRASE,
                inflection=GlossaryInflection.ALLOW_MODEL,
                priority=0,
            )
        )
    if not entries:
        raise GlossaryError(f"glossary has no entries: {path}")
    document = GlossaryDocument(
        schema_version="1.0",
        glossary_version="1.0.0",
        source_language="en",
        target_language="ru",
        entries=tuple(entries),
    )
    _validate_entries(document.entries)
    return LoadedGlossary(document=document, fingerprint=glossary_fingerprint(document))
