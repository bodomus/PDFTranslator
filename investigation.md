# Investigation — PDFTR-8

## Current behavior

- `run_pipeline()` already owns the safe six-stage single-document path: inspect, OCR, extract,
  translate, render, and validate/publish.
- `plan_pipeline()` provides a model-free classification and OCR decision, while
  `open_translation_runtime()` allows repeated documents to share one translator and SQLite cache.
- `PipelineWorkspace` records resumable artifacts and `run_pipeline()` returns output, cache,
  OCR, page, and reused-stage counters.
- The batch feature reports coarse per-file success/failure data, but it does not create the
  validation evidence required by PDFTR-8: immutable source checksums, stage timing, per-document
  JSON, Markdown compatibility matrix, manual-review results, or normalized defects.
- No reusable real-PDF validation command or PowerShell harness exists.

## Expected behavior

- Add a local, opt-in harness that discovers or reads a manifest of representative PDFs, supports
  dry-run and subset selection, continues after individual failures, and writes outside source
  files.
- Produce `validation-summary.json`, `validation-summary.md`, one JSON result per document, and
  retained logs.
- Record source identity before and after each run, page classifications, stage outcomes and
  durations, backend/effective device, OCR decision, output/workspace sizes, cache/resume data,
  warnings, failures, and manual PDF-XChange checklist state.
- Convert deterministic failures and source-integrity violations into severity/stage/reproduction/
  root-cause/follow-up defect records.
- Keep real model, CUDA, OCR, and GUI/manual work explicit and opt-in; unit tests use generated PDFs,
  injected fakes, and mocks only.

## Root cause / missing capability

The production pipeline exposes the necessary safe execution and test-injection boundaries, but
there is no validation-domain coordinator or report schema that combines planning evidence,
execution evidence, integrity checks, manual observations, and defects across a corpus.

## Smallest coherent change

1. Add a focused `pdftranslate.validation` package with typed versioned report models, corpus
   discovery/manifest loading, sequential orchestration, and atomic JSON/Markdown reporting.
2. Reuse `plan_pipeline()`, `run_pipeline()`, and one shared `TranslationRuntime`; do not alter
   extraction, translation, OCR, rendering, or publication algorithms.
3. Add a stdlib CLI entry point behind `scripts/validate-real-pdfs.ps1`; keep it separate from
   Typer so validation remains callable and testable as domain code.
4. Add generated-PDF/fake-translator tests for success, subset/dry-run, continuation and stage
   failures, OCR-required behavior, Unicode paths, resume/cache evidence, reports, and checksum
   preservation.

## Affected contracts

- New opt-in script/API only; existing `pdftranslate` CLI contracts and exit codes remain stable.
- New validation report schema version 1.0 and optional corpus/manual-observation JSON schemas.
- Filesystem writes are limited to the selected results root and ordinary pipeline cache/output
  roots; source PDFs are hashed again after every attempt.
- The existing translated-document and workspace schemas remain unchanged.
- One model/cache runtime is shared across the corpus, preserving the PDFTR-7 lifetime guarantee.

## PDF, model, OCR, and environment assessment

- Source PDFs must never be overwritten; output aliases and partial publication remain guarded by
  the existing pipeline, with an additional before/after SHA-256 assertion in the harness.
- A pre-existing 10-page representative PDF is available in `tests/` (73,160 bytes); no external
  `J:\PdfTestCorpus` directory is present.
- A Hugging Face NLLB cache exists, but the application-specific model cache is absent; no model
  download will occur during tests or standard checks.
- Installed PyTorch is CPU-only (`2.13.0+cpu`); CUDA is unavailable.
- `ocrmypdf`, `tesseract`, and `gswin64c` are unavailable on `PATH`.
- PDF-XChange Editor 10 is installed, but visual/select/search/copy judgments require an explicit
  manual observation and cannot be inferred from automated PDF reopening.

## Graph and source validation

- Graphify (existing graph) linked `run_pipeline()`, `PipelineWorkspace`, `TranslationCache`,
  `OcrProcessor`, `PdfRenderer`, batch reporting, and end-to-end tests. Source inspection confirmed
  those boundaries.
- CRG was rebuilt on branch `codex/PDFTR-8-real-pdf-end-to-end-validation` at commit
  `1ddd6bc3596a`: 562 nodes, 4,282 edges, 68 files.
- CRG found 17 direct callers/tests around `run_pipeline()` and five batch tests calling
  `run_batch()`; its `tests_for` heuristic returned no explicit links, so direct caller evidence
  and source tests are authoritative.
- `code-review-graph detect-changes --base master --brief` analyzed the preflight diff but its final
  panel hit a Windows cp1251 encoding error; the graph build itself completed successfully.

## Expected blast radius

- New validation package, PowerShell wrapper, focused tests, README, CHANGELOG, workflow reports,
  ticket/review artifacts, and ignore rules for generated validation output.
- No existing package boundary, document schema, model loader, OCR subprocess, renderer, or public
  Typer command needs modification.

## Validation plan

- Focused validation-harness tests first, then existing end-to-end/OCR/batch tests.
- Generated text, image, scanned, mixed, failure, Unicode, cache, and resume scenarios with fakes.
- Controlled dry-run/real-PDF execution on the available representative document without model
  download; real-model execution only if the existing cache can be consumed safely.
- `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy src`, full pytest, CLI/script
  smoke tests, and final `.\scripts\check.ps1`.

## Review correction: real-world proof

- The pages 3/5 output is not positive translation evidence. Page 3 contains only two extracted
  text fragments over a graphical title, so rendering inserted isolated Russian fragments while
  leaving the source title design intact. Page 5 contains only an intentional-blank-page label.
- Page 7 is the first available page with a full English paragraph. Its paragraph is split across
  three adjacent extraction blocks, ending one block with `infor-` and starting the next with
  `mation`; translating the final fragment independently produces degenerate NLLB output.
- The current Unicode protected-token sentinel is also stripped by NLLB. A real-model probe
  confirmed that collision-safe ASCII sentinels are preserved.
- The smallest coherent correction is to use ASCII protected-token sentinels and conservatively
  merge only vertically adjacent, similarly aligned/width text blocks into a single paragraph,
  including deterministic dehyphenation. Page 3 does not satisfy the merge heuristic and remains
  a separately reported mapping/rendering defect.
- Positive evidence requires a rendered page 7 with a coherent Russian paragraph, no visible or
  extractable English source beneath it, correct placement, searchable/selectable/copyable Russian
  text, unchanged source checksum, and a reopened valid PDF.
