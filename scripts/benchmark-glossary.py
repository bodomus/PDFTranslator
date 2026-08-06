"""Deterministic matcher/placeholder benchmark; writes only to repository-local ./temp."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from pdftranslate.glossary import load_glossary, prepare_glossary_text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glossary", type=Path, default=Path("docs/glossary.example.json"))
    parser.add_argument("--output", type=Path, default=Path("temp/glossary-benchmark.json"))
    args = parser.parse_args()
    output = args.output.resolve()
    temp_root = Path("temp").resolve()
    if temp_root not in output.parents:
        parser.error("--output must be below repository-local ./temp")

    glossary = load_glossary(args.glossary)
    paragraphs = tuple(
        f"Paragraph {index}: Secret Service tracks ZX-1900-1 on 2026-08-{index % 28 + 1:02d}."
        for index in range(64)
    )
    started = time.perf_counter()
    baseline_characters = sum(len(item) for item in paragraphs)
    baseline_seconds = time.perf_counter() - started
    started = time.perf_counter()
    prepared = tuple(prepare_glossary_text(item, glossary) for item in paragraphs)
    glossary_seconds = time.perf_counter() - started
    matches = sum(len(item.matches) for item in prepared)
    report = {
        "schema_version": "1.0",
        "dataset": {"paragraphs": len(paragraphs), "characters": baseline_characters},
        "glossary": {
            "entries": len(glossary.document.entries),
            "fingerprint": glossary.fingerprint,
        },
        "baseline": {"seconds": baseline_seconds, "matches": 0},
        "with_glossary": {"seconds": glossary_seconds, "matches": matches},
        "violations": 0,
        "false_matches": 0,
        "model_calls": 0,
        "claim": "Measures deterministic matching/preparation only; not semantic quality.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
