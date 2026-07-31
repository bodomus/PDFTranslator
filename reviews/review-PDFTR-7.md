# Implementation Report

## Ticket

PDFTR-7 — Add recursive folder batch processing

## Workflow

- Level: 2
- Graphify: existing graph queried before implementation and structurally refreshed afterward
- CRG: full preflight and full post-change rebuild used
- Context7: current Typer option/list/path/exit documentation checked
- Working tree before changes: clean at `53732cf8a13ce29dd3c400e7a621e8d4f8ab40bb`

## Scope

- Modules: new `pdftranslate.batch` package, pipeline translation-resource lifetime, CLI, exit
  codes, tests, README, and CHANGELOG
- Pipeline stages: existing six per-file stages reused without algorithm changes
- Dependency impact: none; `pyproject.toml` and `uv.lock` unchanged
- Model/device impact: one lazily initialized translator per sequential batch
- OCR impact: existing per-file `auto`/`on`/`off` semantics reused unchanged
- CLI/public contract impact: new `pdftranslate batch` command and exit code 10
- PDF/output integrity impact: existing source immutability, validation, and atomic publication
  remain active for every output PDF

## Investigation

- Current behavior: a single `run_pipeline()` call created its translator and opened its cache in
  `_translate()`.
- Expected behavior: deterministic folder discovery, preserved relative outputs, one model/cache,
  per-file resume, failure policy, and a complete report.
- Root gap: no batch coordinator and no externally shareable translation-resource lifetime.
- Main symbols: `BatchOptions`, `discover_pdfs()`, `run_batch()`, `BatchReport`,
  `TranslationRuntime`, `open_translation_runtime()`, and `run_pipeline()`.
- Configuration/schema: batch report schema 1.0; single-document and translated-document schemas
  unchanged.
- Expected blast radius: batch/CLI plus a narrow optional parameter in the central runner.

## Changes

- Added case-insensitive recursive/non-recursive PDF discovery with deterministic relative-path
  ordering, repeatable excludes, glob matching, output-tree protection, and `.ru.pdf` filtering.
- Added relative output mapping to `<output-root>/<relative>/<stem>.ru.pdf`, including duplicate
  names in different directories and Unicode/spaced paths.
- Added a lazy `TranslationRuntime` that owns one open `TranslationCache` and creates at most one
  compatible translator; standalone PDF processing retains its former per-run lifecycle.
- Added sequential batch orchestration, per-file workspace/resume reuse, existing-output skips,
  fail-fast default, `--continue-on-error`, Ctrl+C preservation, and final exit code 10 for file
  failures.
- Added atomic UTF-8 JSON reports with timestamps, roots, discovery/results/skips, pages, OCR
  pages, translated blocks, cache hits, elapsed time, errors, diagnostic/output paths, and final
  exit code.
- Added human-readable CLI summaries and documented every required option and default policy.
- Protected report publication by requiring a `.json` destination and rejecting source/output
  aliases.

## Graph and source validation

- Graphify preflight identified `run_pipeline()`, `PipelineServices`, `PipelineWorkspace`,
  `TranslationCache`, and `translate_pdf()` as the controlling boundary; source confirmed the
  translator/cache were previously document-scoped.
- Post-change Graphify code graph: 1,206 nodes, 2,439 edges, 73 communities.
- Graphify reported that `hooks.json` produced no nodes; it also notes that documentation semantic
  extraction requires the AI update workflow. The structural code graph completed successfully.
- Post-change CRG full build: 68 files, 565 nodes, 4,325 edges; graph status exposes 561 nodes and
  4,257 persisted edges.
- CRG change risk was 0.65 because `run_pipeline()` is central; two-hop impact reported 275 nodes
  and 50 additional files. Source review confirmed the broad reach is from the optional shared
  runtime parameter, not stage-algorithm changes.
- CRG's aggregate `tests_for` heuristic reported gaps, while exact `callers_of` queries found four
  direct discovery tests and five direct `run_batch()` tests. Source and executed pytest results
  resolve that discrepancy.

## Post-change impact

- CLI reaches `run_batch()`, which reaches `discover_pdfs()`, opens one runtime, and calls the
  existing per-document pipeline sequentially.
- Existing direct `run_pipeline()` callers remain source-compatible because the runtime argument
  is optional.
- Per-file workspace identity still includes source and behavior-affecting options, so batch resume
  cannot cross-contaminate documents.
- The model and cache are shared only inside one synchronous batch; no concurrent SQLite/model use
  was introduced.

## Validation

- Focused batch tests: passed
- Full tests: 118 passed, 1 skipped
- Coverage: 85.74% (required minimum 80%)
- Ruff format: passed
- Ruff lint: passed
- mypy strict: passed for 48 source files
- Bootstrap/check script: `scripts/check.ps1` passed
- CLI smoke tests: root help and `pdftranslate batch --help` passed
- Generated PDF validation: recursive outputs, duplicate names, Unicode/spaces, shared cache,
  resume, failure continuation, fail-fast, and existing-output protection passed
- Real-model/CUDA validation: not run; doctor reported CUDA unavailable despite an RTX 4080 being
  detected, and tests intentionally use a fake translator
- OCR integration validation: not run; OCRmyPDF, Tesseract, Ghostscript, and English OCR data are
  unavailable on this machine

## Documentation

- Updated `README.md` with batch usage, options, discovery, model/cache lifetime, resume, failure
  policy, report contract, and exit code 10.
- Updated `CHANGELOG.md` with the complete user-visible feature.
- Saved the ticket text under `Tickets/PDFTR-7-folder-batch-processing.md`; the matching Markdown
  attachment already existed in YouTrack.

## Remaining risks

- Real NLLB loading, GPU inference, and very large real-world directory performance were not
  exercised in this environment.
- OCR behavior in a batch is covered through the already tested per-file pipeline but could not be
  run against installed OCR system tools here.
- Glob behavior is deliberately case-insensitive and normalized to `/`; unusually platform-specific
  wildcard expectations should be documented before expanding the pattern language.
