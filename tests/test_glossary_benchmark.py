"""Executable evidence that the PDFTR-13A benchmark covers the full paragraph path."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


def test_glossary_benchmark_measures_pipeline_and_cache_scenarios() -> None:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "temp" / f"pdftr13a-test-{uuid4().hex}.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(repository / "scripts" / "benchmark-glossary.py"),
            "--output",
            str(output),
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema_version"] == "2.0"
    assert report["pipeline"] == [
        "LogicalParagraph",
        "repeated policy",
        "glossary",
        "protect_text",
        "segmentation",
        "deterministic fake translator",
        "restore",
        "glossary validation",
        "TranslationCache",
    ]
    assert report["dataset"] == {
        "pages": 8,
        "paragraphs": 64,
        "translatable_paragraphs": 48,
        "preserved_paragraphs": 8,
        "skipped_paragraphs": 8,
        "canary_paragraphs": 8,
    }
    assert report["cache_isolation"]["database_count"] == 2
    assert report["glossary"]["fingerprint"] != report["glossary"]["changed_fingerprint"]

    runs = report["runs"]
    baseline = runs["baseline_no_glossary"]
    cold = runs["glossary_cold"]
    warm = runs["glossary_warm_same_fingerprint"]
    changed = runs["glossary_changed_target"]
    required_fields = {
        "paragraphs",
        "glossary_matches",
        "required_targets",
        "violations",
        "false_matches",
        "translator_calls",
        "translated_segments",
        "cache_hits",
        "cache_misses",
        "elapsed_seconds",
    }
    assert all(set(run) == required_fields for run in runs.values())
    assert baseline["cache_hits"] == cold["cache_hits"] == changed["cache_hits"] == 7
    assert baseline["cache_misses"] == cold["cache_misses"] == changed["cache_misses"] == 41
    assert cold["glossary_matches"] == warm["glossary_matches"] == changed["glossary_matches"] == 56
    assert cold["required_targets"] == warm["required_targets"] == changed["required_targets"] == 32
    assert cold["violations"] == warm["violations"] == changed["violations"] == 0
    assert cold["false_matches"] == warm["false_matches"] == changed["false_matches"] == 0
    assert baseline["translator_calls"] > 0
    assert cold["translator_calls"] > 0
    assert changed["translator_calls"] > 0
    assert cold["translated_segments"] > cold["cache_misses"]
    assert warm["translator_calls"] == warm["translated_segments"] == 0
    assert warm["cache_hits"] == 48
    assert warm["cache_misses"] == 0
    assert all(report["assertions"].values())
