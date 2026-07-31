# Investigation — PDFTR-7

## Current behavior

- `pdftranslate` runs the six-stage pipeline for one PDF at a time.
- `run_pipeline()` owns a source-specific resumable workspace and atomic output publication.
- `PipelineServices.translator_factory` is called inside `_translate()` and `TranslationCache` is
  opened for every document, so a loop around `run_pipeline()` would reload the NLLB model.
- There is no directory discovery, batch orchestration, batch report, or partial-failure exit code.

## Expected behavior

- Add `pdftranslate batch INPUT_DIR` with deterministic recursive/non-recursive discovery.
- Preserve relative paths below an output root and never overwrite source PDFs.
- Exclude the output tree and `.ru.pdf` files from processing, and record skip reasons.
- Initialize one translator and one translation-cache connection for all processed documents.
- Keep per-file pipeline workspaces, resume validation, OCR behavior, and atomic publication.
- Write an atomic JSON report and print a human-readable summary.
- Stop after the first file failure by default; `--continue-on-error` processes remaining files.
- Return a non-zero batch exit code whenever a file failed.

## Root cause / missing capability

The single-document pipeline has the required stages and safety checks, but its translation
resources have document scope and there is no domain-level directory coordinator.

## Smallest coherent change

1. Add a focused `pdftranslate.batch` package for discovery, typed reports, report writing, and
   sequential orchestration.
2. Add an explicit translation runtime that can be opened once and injected into repeated
   `run_pipeline()` calls; retain the existing per-run lifetime when no runtime is supplied.
3. Add a thin Typer `batch` command and a dedicated partial-failure exit category.

## Affected contracts

- CLI: new `batch` command and required options.
- Pipeline: optional shared translation runtime; existing single-PDF invocation remains compatible.
- Filesystem: deterministic relative output paths and atomic JSON report publication.
- Resume: remains per source through existing source/options-derived workspace identities.
- Cache: the same SQLite cache object and database are reused for the batch.
- Model/device: one translator instance per batch, sequential inference only.
- OCR: existing per-file `auto`/`on`/`off` behavior is reused unchanged.

## Safety and compatibility

- Sources remain immutable and output names use `<stem>.ru.pdf` under a separate/default output
  root or an explicitly selected root.
- Output-tree and `.ru.pdf` discovery exclusions prevent feedback loops.
- Existing output PDFs are reported as skipped unless `--overwrite` or `--resume` is selected.
- No schema migration or new dependency is required.
- No parallel model use, distributed processing, GUI, cloud job, or folder watching is introduced.

## Graph/source validation

- Graphify identified `run_pipeline()`, `PipelineServices`, `PipelineWorkspace`,
  `TranslationCache`, and `translate_pdf()` as the central boundary.
- CRG full build completed at baseline commit `53732cf8a13c` with 497 nodes and 3658 edges.
- Source confirmed that translator/cache construction occurs in `_translate()` and that
  workspaces and atomic PDF publication are already per file.

## Expected blast radius

- New batch package and tests.
- Narrow changes to pipeline runner/models/exports, CLI, exit codes, README, and CHANGELOG.
- Existing extraction, translation algorithms, OCR subprocess, and renderer remain unchanged.

## Validation plan

- Focused discovery, orchestration, report, cache-reuse, model-lifetime, failure-policy, resume,
  Unicode/spaced-path, and CLI tests.
- Existing end-to-end tests plus `scripts/check.ps1`.
- CLI help smoke tests and post-change Graphify/CRG refresh and impact review.
