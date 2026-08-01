# PDFTR-10 — Layout diagnostics and translation report

## Summary

Add structured run diagnostics and visual layout debugging for successful and failed translations.

## Dependencies

Requires completion of PDFTR-1 through PDFTR-9 unless this ticket explicitly refers to findings that can be gathered in parallel.

## Goal

Make extraction, translation, OCR, fitting, rendering, cache and validation problems diagnosable without manually reading the entire PDF.

## Deliverables

- `translation-report.json`
- `translation-report.html`
- `debug-layout.pdf`

## Requirements

- Report summary metrics for page types, blocks, cache, OCR, fitting, overflow, rendering, validation, durations, file sizes and measurable peak memory.
- Add stable page/block diagnostics with IDs, bounding boxes, font sizes, fitting attempts, segmentation count, cache status, warning codes and final state.
- Exclude source and translated text by default; include it only with explicit opt-in.
- Centralize stable codes including `READING_ORDER_AMBIGUOUS`, `TRANSLATION_TOKEN_MISMATCH`, `FONT_REDUCED`, `BLOCK_OVERFLOW`, `OCR_LOW_TEXT_GAIN`, and `OUTPUT_VALIDATION_FAILED`.
- Produce a self-contained offline HTML report with no external assets.
- Produce a debug PDF that marks source/final rectangles, overflow, expansion, skipped blocks, OCR pages and IDs without altering normal output.
- Add CLI options for report generation, output format/directory, debug layout and opt-in text inclusion.
- Keep machine-readable output free of Rich markup.

## Tests

Cover success and failure reports, overflow, cache hits, OCR status, warning-code stability, offline HTML, debug PDF, privacy defaults, opt-in text and Cyrillic content. Unit tests and CI must use fixtures/fakes/mocks and must not download models or require CUDA/OCR system tools.

## Acceptance criteria

- [x] JSON reports exist for success and failure when possible.
- [x] Offline HTML report works.
- [x] Stable warning/error codes exist.
- [x] Page/block diagnostics are available.
- [x] Debug PDF marks problem blocks.
- [x] Text is excluded by default.
- [x] Cache/OCR/fitting/overflow/validation data is included.
- [x] Existing CLI remains compatible.
- [x] All checks pass.

## Non-goals

No report editor, hosted dashboard, telemetry upload, automatic issue submission, or embedded full PDFs.

## Workflow and completion report

Treat as Level 2 under `.codex/PRE_TICKET_WORKFLOW.md`. Run Graphify and CRG preflight, source-verify findings, create `investigation.md` and `implementation-plan.md`, implement the smallest coherent change, run focused/full quality gates, and produce `implementation-report.md` plus `reviews/review-PDFTR-10.md` with all limitations and validation results.
