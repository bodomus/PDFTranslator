# Implementation Report — PDFTR-13A

## Ticket

PDFTR-13A — End-to-end glossary benchmark correction. This is a narrowly scoped follow-up to
PDFTR-13; no separate `PDFTR-13A` issue key exists in YouTrack.

## Workflow

- Level: 1, narrow benchmark correction.
- Branch: `codex/PDFTR-13A-glossary-benchmark`.
- Base: `38e90d3ee7d369f803be70761acde8f5c5f74063`, the completed PDFTR-13 branch plus the
  repository report-path rule update.
- Graphify: existing graph queried; no rebuild because package/module boundaries did not change.
- CRG: rebuilt before implementation to 941 nodes/8,151 edges; incrementally updated afterward.
- Working tree before changes: clean.

## Scope

- Changed benchmark: `scripts/benchmark-glossary.py`.
- Added test: `tests/test_glossary_benchmark.py`.
- Added ticket/plan/report/review and changelog entry.
- Production glossary modules: unchanged.
- Production translation/cache/repeated/protection/segmentation modules: unchanged.
- Dependency impact: none.
- CLI/public translation contract impact: none.
- Model/device impact: deterministic fake translator on CPU only; no model download.
- OCR/rendering/PDF impact: none.

## Investigation

- Previous behavior: the PDFTR-13 benchmark created 64 plain strings and called only
  `prepare_glossary_text()`. Its recorded `model_calls` value was correctly zero because it did not
  enter the translation pipeline.
- Reproduced previous result: 64 strings, 128 matcher/preparation matches, 0 model calls, and no
  SQLite cache evidence (`temp/pdftr13a-before.json`).
- Required behavior: execute `translate_paragraphs()` over 50–100 `LogicalParagraph` objects and
  measure glossary, translator, segmentation, and cache behavior.
- Source-verified path: `translate_paragraphs()` evaluates repeated policy, prepares glossary
  placeholders, calls `protect_text()`, segments model-facing text, calls the translator, restores
  generic and glossary placeholders, validates targets, and writes/reads `TranslationCache`.
- Smallest correct change: replace only the benchmark and add an executable test; do not change
  glossary or production pipeline behavior.

## Implementation

- Builds a deterministic schema 1.2 document with 8 pages and 64 `LogicalParagraph` objects:
  48 translatable, 8 preserved page numbers, and 8 skipped watermarks.
- Includes eight translated repeated headers so in-run reuse is observable.
- Includes eight near-match canary paragraphs to measure false matches.
- Includes dates, URLs, Windows paths, identifiers, and long text so protected-token restoration
  and segmentation execute before final validation.
- Uses a deterministic fake translator that records every batch and segment and preserves pipeline
  placeholders without semantic claims.
- Uses two newly created SQLite databases under a run-specific `./temp/` directory:
  - one dedicated empty baseline cache;
  - one dedicated empty glossary cache shared by cold, warm, and changed-target scenarios.
- Executes four scenarios in order: no glossary, glossary cold, same-glossary warm, and changed
  glossary target against the populated glossary cache.
- Fails immediately if paragraph count, repeated preserve/skip, protected-token restoration,
  segmentation, target count, placeholder safety, warm reuse, or changed-target invalidation is
  not demonstrated.
- JSON schema `2.0` reports every requested metric per scenario and explicitly limits the quality
  claim to the deterministic fake-backed pipeline behavior.

## Measured benchmark

Direct command:

```powershell
uv run python scripts\benchmark-glossary.py --output temp\pdftr13a-benchmark.json
```

Artifact: `temp/pdftr13a-benchmark.json` (ignored and intentionally not committed).

| Metric | No glossary | Glossary cold | Same glossary warm | Changed target |
|---|---:|---:|---:|---:|
| Paragraphs | 64 | 64 | 64 | 64 |
| Glossary matches | 0 | 56 | 56 | 56 |
| Required targets | 0 | 32 | 32 | 32 |
| Violations | 0 | 0 | 0 | 0 |
| False matches | 0 | 0 | 0 | 0 |
| Translator calls | 8 | 8 | 0 | 8 |
| Translated segments | 57 | 57 | 0 | 57 |
| Cache hits | 7 | 7 | 48 | 7 |
| Cache misses | 41 | 41 | 0 | 41 |
| Elapsed time, seconds | 0.1738984 | 0.1580279 | 0.0036910 | 0.1532870 |

Fingerprints:

- Original glossary: `f58090b8b5c41086cbab0151c51a915cef3ca131221725e82c9f7fd13935efbd`.
- Changed target: `1741484c6d0ea660f2172531e2322811b0d853fa28724e46f7aac184545a479a`.

Interpretation:

- Cold runs have 41 unique translatable source values and 7 reused repeated headers.
- The warm run resolves all 48 translatable paragraphs from SQLite and performs no fake-translator
  calls or segmentation work.
- Changing only the glossary target changes the semantic fingerprint and causes all 41 unique
  translations to miss the existing cache; 7 repeated headers are still reused within that run.

## Graph and source validation

- Graphify linked `LogicalParagraph`, `translate_paragraphs()`, `TranslationCache`, repeated
  classification, glossary preparation, protected text, segmentation, and the adjacent tests.
- Source inspection confirmed the exact required execution order in
  `src/pdftranslate/translation/paragraphs.py`.
- Post-change CRG updated 3 files and indexed 949 rows. It reported 0 affected production flows,
  risk 0.50, and 12 heuristic test gaps. Those gaps are false negatives for subprocess coverage:
  `tests/test_glossary_benchmark.py` executes the complete script and asserts its exact counters.
- No unexpected dependants or production blast radius were found.

## Validation

- Direct benchmark: passed; all nine embedded assertions are `true`.
- Focused test: `tests/test_glossary_benchmark.py` — 1 passed.
- Focused benchmark/glossary/translation/repeated matrix — 32 passed.
- Full `scripts/check.ps1` — 190 passed, 1 skipped.
- Coverage: 87.91% (required at least 80%).
- Ruff format: passed; 130 files verified.
- Ruff lint: passed.
- mypy: passed for 76 source files.
- GitHub Actions: [CI run #40](https://github.com/bodomus/PDFTranslator/actions/runs/31566034559)
  passed for commit `f9854a3` in 1m 39s; both Python 3.12 matrix jobs (`ubuntu-latest` and
  `windows-latest`) completed successfully.
- CI annotations: one warning per runner reports that `actions/checkout@v4` and
  `astral-sh/setup-uv@v6` target deprecated Node.js 20 and are being forced onto Node.js 24. This
  is a non-blocking infrastructure note, not a PDFTR-13A failure.

## Documentation

- Added `Tickets/PDFTR-13A-glossary-benchmark.md`.
- Added `.implementation-plans/implementation-plan-PDFTR-13A.md`.
- Added this report under the new `.implementation-reports/` rule.
- Added `reviews/review-PDFTR-13A.md`.
- Updated `CHANGELOG.md`.
- The earlier PDFTR-13 report was not overwritten.

## Remaining risks and limits

- Timings are local wall-clock observations and are not performance guarantees.
- The fake translator verifies orchestration, segmentation, placeholder survival, target
  restoration, validation, and cache behavior; it does not measure NLLB semantic quality.
- NLLB, CUDA, OCR, external real-world PDFs, and manual PDF-XChange selection/copy checks were not
  run for PDFTR-13A.
- The earlier generated-PDF validation remains fake-backed, which is acceptable for PDFTR-13 and
  is not reclassified as real-model evidence.

## Recommendation

- Ready for review and merge; local and remote quality gates are green.
