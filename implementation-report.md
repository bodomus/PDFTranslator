# Implementation Report

## Ticket

PDFTR-8 — Real PDF end-to-end validation

## Workflow

- Level: 2
- Branch: `codex/PDFTR-8-real-pdf-end-to-end-validation`, created from local `master` at
  `1ddd6bc3596aa13947cd44789b164b5590ed0227`
- Graphify: used for preflight; structural code graph refreshed post-change to 1,349 nodes,
  2,746 edges, and 78 communities
- CRG: rebuilt preflight at 562 nodes / 4,282 edges / 68 tracked files; post-change limitation
  recorded below
- Working tree before changes: dirty only because of preserved user-owned untracked files under
  `Tasks/`
- Ticket preparation: `Tickets/PDFTR-8-real-pdf-end-to-end-validation.md` created and attached;
  YouTrack state moved from Open to In Progress

## Scope

- Modules: new `pdftranslate.validation` models, runner, reporting, stdlib CLI, and module entry point
- Pipeline stages: existing inspect, OCR, extract, translate, render, validate stages reused without
  algorithm changes
- Dependency impact: none; `pyproject.toml` and `uv.lock` unchanged
- Model/device impact: opt-in only; one existing shared translation runtime per corpus; no model
  downloads in tests/CI
- OCR impact: existing OCR boundary reused; no installation or subprocess behavior changed
- CLI/public contract impact: new opt-in `scripts/validate-real-pdfs.ps1` and
  `python -m pdftranslate.validation`; existing Typer commands and exit codes unchanged
- PDF/output integrity impact: sources are SHA-256/size checked before and after every attempt;
  existing atomic output publication remains authoritative

## Investigation

- Current behavior: the single-document pipeline and PDFTR-7 shared runtime already provided safe
  execution, resume, cache, and atomic publication, but no corpus validation schema or evidence
  coordinator existed.
- Expected behavior: reproducible private-corpus discovery/manifest, dry-run, subset selection,
  continue-on-error, per-stage timing, JSON/Markdown results, copied logs, manual review, defects,
  and source preservation.
- Root cause or implementation gap: evidence existed across pipeline objects/workspaces but was not
  normalized or published as one validation result.
- Main symbols: `ValidationOptions`, `CorpusManifest`, `ManualReview`, `ValidationSummary`,
  `DocumentValidationResult`, `run_validation()`, `_validate_document()`, `write_json()`, and
  `write_markdown()`.
- Configuration/schema: new validation schema 1.0; optional corpus manifest and manual-review
  manifest 1.0; existing extracted/translated/workspace schemas unchanged.
- Expected blast radius: isolated validation package, script, tests, docs, changelog, ignore rules,
  ticket artifacts, and reports.

## Changes

- Added deterministic manifest or recursive PDF discovery with `.ru.pdf` and results-tree
  exclusions, relative-path safety, unique document IDs, and category/ID/glob subset selection.
- Added model-free dry-run that records classifications, OCR planning, checksums, and complete report
  structure without loading NLLB, invoking OCR, or creating pipeline workspaces.
- Added sequential full validation using one shared `TranslationRuntime`, continue-on-error by
  default, explicit fail-fast, cache/resume evidence, stage status/timing, diagnostics copying, and
  source identity verification after both success and failure.
- Added atomic `validation-summary.json`, `validation-summary.md`,
  `document-results/<document-id>.json`, `logs/<document-id>.log`, outputs, and
  `manual-review-template.json`.
- Added strict PDF-XChange checklist fields and automatic defect mapping for failed manual checks.
- Added deterministic failure defects with severity, stage, reproducibility, root cause, and
  recommended follow-up; translation failures map to PDFTR-9.
- Added PowerShell and Python CLIs with explicit dry-run, subset, model, CPU/CUDA, OCR, offline,
  resume, overwrite, cache, font, and page controls.
- Added 11 harness tests covering text/image success, corrupt/extraction failure, translation,
  rendering, OCR, final validation, continuation, Unicode paths, reports, source checksums, model
  lifetime/cache reuse, resume, manual failure mapping, and CLI validation.
- Updated README, CHANGELOG, ignore rules, and detailed reproduction/manual-review documentation.

## Graph and source validation

- Graphify preflight identified `run_pipeline()`, `PipelineWorkspace`, `TranslationCache`,
  `OcrProcessor`, `PdfRenderer`, batch reporting, and end-to-end tests as adjacent boundaries.
- Post-change Graphify query found the isolated validation community and confirmed
  `run_validation()` links to `plan_pipeline()`, `run_pipeline()`, the shared cache/runtime, OCR,
  renderer, report models, and focused tests.
- CRG preflight found 17 callers/tests around `run_pipeline()` and five callers/tests around
  `run_batch()`; source inspection verified all important relationships.
- CRG post-change limitation: this version indexes tracked files only. Full/incremental rebuilds
  stayed at 68 files and therefore cannot analyze the new untracked files until they are staged or
  committed. No staging was performed solely to satisfy the tool. Graphify, source, focused tests,
  full tests, and runtime evidence provide the post-change verification.
- CRG `detect-changes --brief` also reaches its analysis result but fails printing the final Windows
  panel under cp1251 (`UnicodeEncodeError`); graph database builds completed.
- Discrepancies: Graphify represents the new code; CRG does not yet. Current source and executable
  evidence are authoritative.

## Post-change impact

- CRG updated: attempted with both incremental and full confirmed commands; limitation above
- Blast radius: new opt-in package/script/docs/tests only; no existing production function changed
- Unexpected dependants: none found by Graphify, source imports, or full regression tests
- Compatibility or migration concerns: none; validation schema is new and versioned 1.0

## Validation

### Focused and regression tests

- `uv run pytest tests/test_validation_harness.py -q --no-cov`: 11 passed
- Pipeline/OCR/batch/validation focused regression: 40 passed
- `git diff --check`: passed; only line-ending conversion warnings were reported

### Full quality gates

- `.\scripts\check.ps1`: passed
  - Ruff format: 85 files already formatted
  - Ruff lint: passed
  - mypy: no issues in 54 source files
  - pytest: 129 passed, 1 skipped
  - coverage: 86.78% (required 80%)
- `.\scripts\test.ps1`: passed with the same 129 passed / 1 skipped / 86.78%
- `uv run pdftranslate --version`: `PDFTranslate 0.1.0`
- `uv run pdftranslate doctor`: Status OK; OCR dependencies unavailable; CUDA unavailable to the
  installed CPU-only Torch build
- `uv run python -m pdftranslate.validation --help`: passed

### Real-PDF dry-run

Source:
`tests/The_Sword_And_The_Shield_The_Mitrokhin_Archive_And_The_Secret_History_1.pdf`

- 10 pages, 73,160 bytes, SHA-256
  `801d700f6aaf4dbc27774b4a857c56db42ede309e3bea15d051156f02f65dfce`
- Classifications: 3 scanned (pages 1, 2, 8), 5 mixed, 2 text
- OCR plan: would run for pages 1, 2, 8
- Source checksum/size after dry-run: unchanged
- Result: `C:\tmp\pdftr8-real-dry-run`

### Real-model deterministic failure

Pages 3–7, CPU, OCR off, offline, existing local NLLB cache:

- First run: 76.62 s; inspect/OCR/extract passed; translate failed deterministically because NLLB
  did not preserve protected token `1900-1`
- Cache at failure: 2 hits / 38 misses; effective device CPU
- Render/validate did not run; no final/partial PDF was published
- Source checksum/size remained unchanged
- Resume run: 8.16 s; inspect/OCR/extract reused; translation failed on the same token; OCR correctly
  reported skipped
- Defect: major, translation, deterministic, mapped to PDFTR-9 — Translation quality benchmark
- Result: `C:\tmp\pdftr8-real-full`

### Real-model successful text + image run

Pages 3 and 5, CPU, OCR off, offline, existing local NLLB cache:

- Page 3: mixed with an image; page 5: text
- All six stages passed in 5.05 s
- Effective device CPU; cache 2 hits / 1 miss
- Output: 682,136 bytes; reopens as PDF; 10 output pages match 10 source pages
- Russian text: 41 extractable Cyrillic characters; search for `страница` and `пустой` each returns
  one hit
- Image preservation: source page 3 image count 1; output page 3 image count 1
- Source checksum/size remained unchanged
- Resume run: 0.49 s; all six stages reused; output remained valid
- Result: `C:\tmp\pdftr8-real-success`

### Environment-specific validation

- Real-model validation: executed from an existing local cache; no model was downloaded for this
  ticket
- CUDA validation: not run; NVIDIA RTX 4080 is present, but installed Torch is `2.13.0+cpu` and
  reports CUDA unavailable
- OCR integration validation: not run; OCRmyPDF, Tesseract, Ghostscript, and English OCR data are
  unavailable. Generated/mock OCR tests passed; dry-run recorded the real document's OCR need.
- PDF-XChange manual validation: pending human review. PDF-XChange Editor is installed, the template
  is generated, and automated reopen/page-count/text-search/image/checksum evidence passed, but
  visual usability/select/copy judgments were not falsely claimed.

## Documentation

- Updated: `README.md`, `CHANGELOG.md`, `.gitignore`, `docs/real-pdf-validation.md`, and
  `docs/validation-corpus.example.json`
- CLI help: new stdlib validation CLI documented and smoke-tested
- Existing main CLI/config/schema docs: unchanged because existing contracts were not modified

## Acceptance status

- Reusable validation harness: complete
- JSON and Markdown reports: complete
- Real text PDF end to end: complete (page 5 in successful run)
- Real image-containing PDF: complete (mixed page 3; image count preserved 1→1)
- Scanned/OCR-required behavior: evaluated; real dependencies unavailable and recorded
- PDF-XChange manual result: template/result state recorded as pending human review
- Search/copy/cache/resume: automated extract/search, cache, and resume complete; PDF-XChange copy
  judgment pending
- Source files unchanged: complete across dry-run, failure, success, and resume
- Defects mapped: real protected-token failure mapped to PDFTR-9
- All automated checks: passed

## Consolidated remarks

1. A real deterministic translation defect was found: pages 3–7 fail because NLLB does not
   preserve protected token `1900-1`. It reproduces after resume, is classified major, and is
   mapped to PDFTR-9.
2. The positive real run is intentionally narrower (pages 3 and 5) and proves text + mixed/image
   E2E behavior, not correctness of the failing pages 3–7 or the whole document.
3. PDF-XChange Editor is installed, but its visual, selection, clipboard, column, and table checks
   still require a human. They remain explicitly `not_checked` in the generated template.
4. Automated PDF evidence passed for the positive output: reopen, 10/10 page count, extractable and
   searchable Russian text, page-3 image count 1→1, valid output size, source checksum, and resume.
5. OCR is required for real pages 1, 2, and 8, but OCRmyPDF, Tesseract, Ghostscript, and English OCR
   data are unavailable. The opt-in OCR integration test is the single skipped test.
6. The machine has an NVIDIA RTX 4080, but the installed Torch build is CPU-only
   (`2.13.0+cpu`), so CUDA validation was not possible.
7. The current real corpus is one pre-existing 10-page, 73,160-byte document. It does not cover a
   full private 100–300-page, table-heavy, and two-column matrix. No new copyrighted or large PDF
   was added by PDFTR-8.
8. The real model was loaded offline from an existing Hugging Face cache through the temporary
   junction `C:\tmp\pdftr8-real-cache\models`; no model weights or cache artifacts were added to
   the repository.
9. Transformers printed that both `max_new_tokens=1024` and its default `max_length=200` were set;
   `max_new_tokens` took precedence. Hugging Face also printed an unauthenticated-request warning
   even in the offline/cache-backed run. These warnings did not prevent the successful pages 3/5
   run, but are retained as runtime observations.
10. CRG rebuilt successfully but ignores new untracked files, so it cannot provide post-change
    symbol reachability until the work is staged/committed. Its Windows brief panel also has a
    cp1251 `UnicodeEncodeError`. Graphify and executable/source evidence were used instead.
11. Graphify refreshed the structural code graph successfully. It warned that two non-code JSON
    files (`hooks.json` and the example corpus manifest) produced zero graph nodes; this does not
    affect runtime validation.
12. `git diff --check` passed, while Git reported expected LF/CRLF conversion warnings for
    `.gitignore`, README, and CHANGELOG. No whitespace errors were reported.
13. User-owned untracked `Tasks/` files and archive were preserved unchanged. No staging, commit,
    push, ticket creation, dependency installation, OCR installation, or next-ticket work was
    performed.
14. All automated quality gates passed: 129 passed, 1 environment-dependent OCR integration test
    skipped, 86.78% coverage, Ruff clean, and strict mypy clean.

## Remaining risks

- Human PDF-XChange review remains necessary for visual layout, usability, selection, and clipboard
  behavior.
- Full scanned-page OCR cannot be validated until system dependencies are installed.
- CUDA cannot be validated with the current CPU-only Torch environment.
- The real document exposed a deterministic protected-token failure on pages 3–7; this is evidence
  for PDFTR-9, not silently fixed outside PDFTR-8 scope.
- The current local corpus has one 10-page representative document, not the complete 100–300 page,
  tables, two-column, and diverse private corpus described by the target matrix. The manifest and
  harness are ready for those inputs when supplied.
