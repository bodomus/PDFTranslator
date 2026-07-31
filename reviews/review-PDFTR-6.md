# Implementation Report

## Ticket

PDFTR-6 - Add OCR preprocessing for scanned and mixed PDFs

## Workflow

- Level: 2
- Graphify: used before implementation and refreshed after the architectural change
- CRG: used before implementation, fully rebuilt after implementation, and queried for affected flows
- Working tree before changes: contained only the user-provided untracked ticket source under `Tasks/`

## Scope

- Modules: new `pdftranslate.ocr` package; CLI; pipeline models, runner, workspace, and exit codes
- Pipeline stages: inspect -> OCR -> extract -> translate -> render -> validate
- Dependency impact: no Python dependencies added; OCRmyPDF, Tesseract, Ghostscript, and optional
  unpaper remain external system tools
- Model/device impact: none; dry-run and OCR occur before translation model construction
- OCR impact: controlled OCRmyPDF subprocess, dependency/language diagnostics, logs, validation,
  conservative mixed-PDF behavior, and resumable artifacts
- CLI/public contract impact: required OCR flags, doctor diagnostics, sixth progress stage, and exit
  code 9 for OCR execution failures
- PDF/output integrity impact: source remains immutable; OCR output and final output are reopened and
  validated; page count and geometry must remain stable

## Investigation

- Current behavior: selected scanned pages stopped the pipeline with `OCR_REQUIRED` because no OCR
  implementation existed.
- Expected behavior: `auto`, `on`, and `off` decisions before extraction with safe external-tool
  integration and reusable workspace output.
- Root gap: there was no OCR adapter, stage, artifact, option identity, diagnostic probe, or output
  validation.
- Main symbols: `OcrProcessor`, `OcrOptions`, `OcrDependencies`, `validate_ocr_output`, `_ocr`,
  `PipelineStage.OCR`, and `PipelineWorkspace.completed_artifact`.
- Expected blast radius: root CLI, doctor, end-to-end stage order, resume manifest identity,
  extraction/render source path, exit-code table, and generated-PDF tests.

## Changes

- Added external executable discovery, version probing, Tesseract language inspection, installation
  guidance, bounded subprocess execution, non-shell list arguments, captured stdout/stderr, and
  retained UTF-8 OCR logs.
- Added conservative OCRmyPDF `skip` mode by default, explicit force mode, English language,
  deskew, clean, rotation, and selected-page arguments.
- Added automatic classification decisions: text and reliable mixed pages skip OCR; scanned pages
  run in auto; off fails with exit code 4; on invokes OCRmyPDF while preserving text pages.
- Added atomic workspace `ocr.pdf`, sidecar/log paths, OCR settings in run identity, and resume
  validation/reuse.
- Added page-count/geometry checks, post-OCR re-extraction/classification, text-improvement warnings,
  and rendering from the validated OCR working PDF.
- Extended `doctor`, CLI progress/summary, README, CHANGELOG, and tests.

## Graph and source validation

- Graphify preflight found the existing `run_pipeline`/`PipelineWorkspace` boundary; the refreshed
  graph contains 1,044 nodes, 2,116 edges, and 63 communities.
- Graphify warned that `hooks.json` produced zero nodes; it is unrelated to the Python OCR path.
- CRG confirmed that `run_pipeline` now reaches `_ocr`, extraction, translation, rendering, and
  validation, and that doctor is a separately affected CLI flow.
- Source validation confirmed OCR settings participate in the workspace hash, subprocess calls use
  argument arrays, source/output aliases are rejected, and fake adapters cover unit tests.
- Context7 current OCRmyPDF documentation confirmed `--mode skip` as the conservative mixed-PDF
  behavior and `force` as a rasterizing explicit mode.

## Post-change impact

- CRG updated: yes, full rebuild after staging new source files
- Blast radius: expected CLI, pipeline/workspace, PDF extraction/render source, doctor, and tests
- Unexpected dependants: none
- Compatibility: prior numeric exit codes remain stable; OCR failure adds code 9. Existing resume
  state uses a different run identity because OCR options are now behavior-affecting.

## Validation

- Focused OCR/pipeline/CLI tests: passed
- Full tests: 103 passed, 1 optional integration test skipped
- Coverage: 84.71% (required minimum 80%)
- Ruff format: passed
- Ruff lint: passed
- mypy: passed for 43 source files
- Bootstrap/check scripts: `scripts/check.ps1` passed
- CLI smoke tests: `pdftranslate doctor`, root help, and hidden run help passed
- Real-model/CUDA validation: not required for this OCR ticket
- PDF validation: generated fixtures exercised source immutability, page geometry/count, OCR working
  PDFs, rendering, publication, Unicode paths, and reopen checks
- OCR integration validation: not run because OCRmyPDF, Tesseract, and Ghostscript are unavailable
  on this machine; the optional test requires `PDFTRANSLATE_RUN_OCR_INTEGRATION=1`

## Documentation

- Updated `README.md`, `CHANGELOG.md`, CLI help, `investigation.md`, and
  `implementation-plan.md`.

## Remaining risks

- Real OCR quality and vendor-specific Windows executable discovery still require an opt-in run on
  a machine with OCRmyPDF, Tesseract `eng`, and any version-required Ghostscript/unpaper tools.
- Complex mixed pages intentionally preserve reliable existing text rather than rasterizing it;
  explicit `--ocr-force` remains available for known-bad text layers.
