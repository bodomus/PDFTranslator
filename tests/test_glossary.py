"""Focused glossary loading, matching, processing, and identity tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdftranslate.glossary import (
    GLOSSARY_PLACEHOLDER_PREFIX,
    GlossaryComplianceError,
    GlossaryDocument,
    GlossaryEntry,
    GlossaryEntryMode,
    GlossaryError,
    GlossaryInflection,
    GlossaryMatchType,
    LoadedGlossary,
    find_glossary_matches,
    glossary_fingerprint,
    load_glossary,
    prepare_glossary_text,
)
from pdftranslate.translation.text import protect_text


def _entry(
    identifier: str,
    source: str,
    target: str,
    *,
    mode: str = "translate",
    case_sensitive: bool = True,
    match: str = "whole_word",
    inflection: str = "fixed",
    priority: int = 100,
) -> dict[str, object]:
    return {
        "id": identifier,
        "source": source,
        "target": target,
        "mode": mode,
        "case_sensitive": case_sensitive,
        "match": match,
        "inflection": inflection,
        "priority": priority,
    }


def _payload(entries: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "glossary_version": "1.0.0",
        "source_language": "en",
        "target_language": "ru",
        "entries": entries,
    }


def _write(path: Path, entries: list[dict[str, object]]) -> LoadedGlossary:
    path.write_text(json.dumps(_payload(entries), ensure_ascii=False), encoding="utf-8")
    return load_glossary(path)


def test_loads_valid_glossary_and_fingerprint_is_path_and_order_independent(
    tmp_path: Path,
) -> None:
    entries = [
        _entry("kgb", "KGB", "КГБ"),
        _entry("isbn", "ISBN", "ISBN", mode="preserve"),
    ]
    first = _write(tmp_path / "first.json", entries)
    second = _write(tmp_path / "nested.json", list(reversed(entries)))

    assert first.fingerprint == second.fingerprint
    assert first.document.glossary_version == "1.0.0"
    changed = first.document.model_copy(update={"glossary_version": "1.0.1"})
    assert glossary_fingerprint(changed) != first.fingerprint


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"{broken", "invalid glossary"),
        (b"\xff\xfe", "not valid UTF-8"),
    ],
)
def test_rejects_malformed_json_and_invalid_utf8(
    tmp_path: Path, payload: bytes, message: str
) -> None:
    path = tmp_path / "invalid.json"
    path.write_bytes(payload)
    with pytest.raises(GlossaryError, match=message):
        load_glossary(path)


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        (
            [_entry("same", "KGB", "КГБ"), _entry("same", "CIA", "ЦРУ")],
            "duplicate glossary entry IDs.*same",
        ),
        (
            [_entry("a", "KGB", "КГБ"), _entry("b", "KGB", "Комитет")],
            "duplicate or conflicting normalized entries.*a, b",
        ),
        (
            [
                _entry("a", "ISBN", "ISBN", mode="preserve"),
                _entry("b", "isbn", "ИСБН", case_sensitive=False),
            ],
            "preserve/translate conflict.*a, b",
        ),
    ],
)
def test_rejects_duplicate_ids_targets_and_modes(
    tmp_path: Path, entries: list[dict[str, object]], message: str
) -> None:
    path = tmp_path / "conflict.json"
    path.write_text(json.dumps(_payload(entries), ensure_ascii=False), encoding="utf-8")
    with pytest.raises(GlossaryError, match=message):
        load_glossary(path)


def test_rejects_unsupported_language_and_placeholder_collision(tmp_path: Path) -> None:
    unsupported = _payload([_entry("kgb", "KGB", "КГБ")])
    unsupported["target_language"] = "de"
    path = tmp_path / "unsupported.json"
    path.write_text(json.dumps(unsupported), encoding="utf-8")
    with pytest.raises(GlossaryError, match="target_language"):
        load_glossary(path)

    with pytest.raises(GlossaryError, match="placeholder collision"):
        _write(
            tmp_path / "collision.json",
            [_entry("bad", GLOSSARY_PLACEHOLDER_PREFIX, "value")],
        )


def test_case_boundaries_phrase_exact_punctuation_and_multiple_occurrences(tmp_path: Path) -> None:
    glossary = _write(
        tmp_path / "matching.json",
        [
            _entry("kgb", "KGB", "КГБ"),
            _entry(
                "service",
                "Secret Service",
                "Секретная служба",
                case_sensitive=False,
                match="phrase",
                priority=50,
            ),
            _entry("title", "Exact title", "Точное название", match="exact"),
        ],
    )
    matches = find_glossary_matches("KGB, not XKGB; secret   service and KGB.", glossary.document)
    assert [item.entry.id for item in matches] == ["kgb", "service", "kgb"]
    assert find_glossary_matches("Exact title", glossary.document)[0].entry.id == "title"
    assert not find_glossary_matches("prefix Exact title suffix", glossary.document)


def test_overlap_resolution_uses_priority_then_length(tmp_path: Path) -> None:
    glossary = _write(
        tmp_path / "overlap.json",
        [
            _entry("short", "Service", "Служба", priority=10),
            _entry("long", "Secret Service", "Секретная служба", match="phrase", priority=10),
            _entry("priority", "Secret", "Секрет", priority=20),
        ],
    )
    matches = find_glossary_matches("Secret Service", glossary.document)
    assert [item.entry.id for item in matches] == ["priority", "short"]


def test_fixed_and_preserve_terms_are_nested_inside_generic_token_protection(
    tmp_path: Path,
) -> None:
    glossary = _write(
        tmp_path / "protected.json",
        [
            _entry("kgb", "KGB", "КГБ"),
            _entry("isbn", "ISBN", "ISBN", mode="preserve"),
        ],
    )
    prepared = prepare_glossary_text("KGB ISBN 1900-1", glossary)
    assert prepared.value.count(GLOSSARY_PLACEHOLDER_PREFIX) == 2
    protected = protect_text(prepared.value)
    assert GLOSSARY_PLACEHOLDER_PREFIX not in protected.value
    model_output = protected.value.replace(" ", " translated ")
    restored_tokens = protected.restore(model_output)
    final, evidence = prepared.restore_and_validate(restored_tokens, "p1")
    assert "КГБ" in final
    assert "ISBN" in final
    assert "1900-1" in final
    assert GLOSSARY_PLACEHOLDER_PREFIX not in final
    assert evidence.entry_ids == ("kgb", "isbn")


def test_allow_model_validates_preferred_target_without_claiming_inflection(tmp_path: Path) -> None:
    glossary = _write(
        tmp_path / "model.json",
        [_entry("service", "service", "служба", inflection="allow_model")],
    )
    prepared = prepare_glossary_text("The service works.", glossary)
    assert GLOSSARY_PLACEHOLDER_PREFIX not in prepared.value
    final, evidence = prepared.restore_and_validate("Эта служба работает.", "p1")
    assert final == "Эта служба работает."
    assert evidence.compliance == "compliant"
    with pytest.raises(GlossaryComplianceError, match="service") as caught:
        prepared.restore_and_validate("Организация работает.", "p1")
    assert caught.value.code == "GLOSSARY_TARGET_MISSING"


def test_missing_or_leaked_placeholder_fails_closed(tmp_path: Path) -> None:
    glossary = _write(tmp_path / "leak.json", [_entry("kgb", "KGB", "КГБ")])
    prepared = prepare_glossary_text("KGB", glossary)
    with pytest.raises(GlossaryComplianceError) as caught:
        prepared.restore_and_validate("damaged", "p1")
    assert caught.value.code == "GLOSSARY_PLACEHOLDER_LEAK"


def test_typed_models_reject_invalid_preserve_and_inflection() -> None:
    with pytest.raises(ValueError, match="preserve entry target"):
        GlossaryEntry(
            id="isbn",
            source="ISBN",
            target="ИСБН",
            mode=GlossaryEntryMode.PRESERVE,
            case_sensitive=True,
            match=GlossaryMatchType.WHOLE_WORD,
            inflection=GlossaryInflection.FIXED,
            priority=1,
        )

    document = GlossaryDocument(
        schema_version="1.0",
        glossary_version="1.0.0",
        source_language="en",
        target_language="ru",
        entries=(
            GlossaryEntry(
                id="kgb",
                source="KGB",
                target="КГБ",
                mode=GlossaryEntryMode.TRANSLATE,
                case_sensitive=True,
                match=GlossaryMatchType.WHOLE_WORD,
                inflection=GlossaryInflection.FIXED,
                priority=1,
            ),
        ),
    )
    assert len(document.entries) == 1
