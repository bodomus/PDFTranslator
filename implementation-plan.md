# Implementation Plan — PDFTR-10

1. Add centralized diagnostic codes and versioned report models for run, summary, page, block, warning and failure evidence.
2. Add deterministic atomic JSON and self-contained HTML writers with privacy-safe defaults.
3. Add a builder combining inspection, translated document, translation statistics, OCR, render, validation, file and measurable memory evidence.
4. Extend pipeline options/results and preserve `RenderResult`; emit best-effort failure reports without hiding primary errors.
5. Enable and publish the renderer debug PDF, adding visible block IDs and state labels.
6. Add `--report`, `--report-format`, `--report-dir`, `--debug-layout` and `--include-report-text` to the thin CLI boundary.
7. Add focused diagnostics, pipeline, renderer and CLI tests using fakes and generated PDFs.
8. Update README, CHANGELOG and CLI help.
9. Run focused tests, full pytest, Ruff, mypy and `scripts/check.ps1`; inspect generated artifacts and report unavailable real-model/CUDA/OCR checks honestly.
10. Refresh CRG and Graphify, inspect blast radius, then write `implementation-report.md` and `reviews/review-PDFTR-10.md`.
11. After merging PDFTR-9A through master, reserve a unique diagnostic directory for every pipeline
    execution and publish JSON, HTML and debug PDF only inside it.
12. Make diagnostic file publication fail if a target already exists; never use replace semantics
    for diagnostic artifacts.
13. Convert success-report/debug publication errors into a stable pipeline error while retaining the
    already validated translated PDF, then cover the contract with focused tests.
14. Repeat focused and full gates and update the PDFTR-10 report/review with the combined PDFTR-9A
    test count.
