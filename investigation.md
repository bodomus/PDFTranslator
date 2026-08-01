# Investigation — PDFTR-9
## Baseline

- Workflow level: 2.
- Branch: `codex/PDFTR-9-translation-quality-benchmark` from PDFTR-8 commit `d16ed0e`.
- Working tree was clean before the ticket file was added.
- Python: 3.12 through uv; no dependency change is required.
- PDFTR-9 is In Progress and its augmented Markdown ticket is attached in YouTrack.

## Current behavior

PDFTranslate can protect tokens, segment blocks, run NLLB, cache completed block translations and
render PDFs. It has no versioned quality dataset, benchmark runner, deterministic diagnostic model,
human scoring schema, baseline comparison, or JSON/Markdown benchmark report.

The production translation path combines protection, segmentation, inference and recombination.
Consequently, a bad final PDF does not by itself prove whether a defect originated in extraction,
segmentation, the model, token restoration, terminology, or rendering.

## Mandatory PDFTR-8 inputs

1. Historical NLLB output damaged protected token `1900-1`.
2. A page-7 observation damaged numbers/dates and introduced junk such as `F￾`.

Both must remain explicit regression cases. The current ASCII placeholder mitigation does not
remove their value as benchmark inputs.

## Expected behavior

- Validate a safe, versioned 50–100 sample dataset.
- Run a reusable `Translator` once over the dataset without requiring PDF rendering.
- Preserve raw protected/segmented/model outputs in evidence.
- Detect token, numeric, unit, URL, path, option, segment-count, untranslated, length-ratio and
  suspicious-character problems deterministically.
- Attribute findings to extraction, segmentation, protected-token, model, terminology, or
  rendering stages.
- Record version/commit/backend/model/tokenizer/device/settings/timing/cache counters.
- Accept documented human review fields and compare a current report with a prior baseline.
- Produce atomic JSON and Markdown reports.

## Smallest coherent design

Create an isolated `pdftranslate.benchmark` package composed of:

- Pydantic models for dataset, trace observations, findings, reviews and reports;
- pure diagnostic functions for stage-aware checks;
- a runner using the existing `Translator`, `protect_text()` and `segment_text()` contracts;
- atomic JSON/Markdown reporting and baseline comparison;
- one thin Typer `benchmark-translation` command;
- a 60-sample synthetic dataset and fake-backed tests.

No renderer or extraction algorithm is changed. Optional stage observations in the dataset are
diagnostic evidence, not instructions to alter production output.

## Graph and source evidence

- Graphify connected `NllbTranslator`, `ProtectedText`, `segment_text()`, `TranslationCache`,
  `translate_document()`, CLI and report patterns. Source inspection confirmed these boundaries.
- CRG is current at 647 nodes / 5,067 edges / 76 files on `d16ed0e`.
- CRG found production caller `translate_document()` plus direct tests for `protect_text()` and
  `segment_text()`. A new benchmark runner will be a deliberate second caller.
- Graphify still contains ignored historical `Tasks/PDFTR-9...` nodes; current YouTrack text,
  `Tickets/PDFTR-9...`, source and tests are authoritative.

## Contracts and risks

- CLI: adds one command; existing commands and exit codes remain unchanged.
- Dataset/report schemas: new, versioned 1.0 contracts.
- Cache: benchmark uses an in-run exact-source cache for deterministic hit/miss reporting; it does
  not mutate production translation memory.
- Model: one loaded translator per run; fake backend in tests; NLLB only in explicit runs.
- PDF integrity: no PDF is opened, written or rendered by benchmark execution.
- OCR/CUDA: unaffected; device metadata is recorded when a real translator is used.
- Main risk: deterministic checks cannot decide semantic adequacy or fluency. Those remain explicit
  human scores and must not be inferred from token preservation alone.
