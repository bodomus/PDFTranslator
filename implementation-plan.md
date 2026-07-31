# PDFTR-6 Implementation Plan

1. Add a focused `pdftranslate.ocr` package with typed options/results/errors, dependency discovery, safe OCRmyPDF command construction, subprocess execution, retained logs, and PDF validation.
2. Add an OCR stage and workspace artifact between inspect and extract; include OCR settings in run identity and validate resumed artifacts.
3. Make extraction and rendering use the OCR working PDF when OCR ran while preserving the immutable original source identity.
4. Expose the required root-command options and extend `doctor` with executable paths, versions, and English language availability.
5. Add mocked unit/end-to-end tests and a separately marked optional integration test.
6. Update README and CHANGELOG, run focused tests and `scripts/check.ps1`, refresh CRG and Graphify, then write the ticket review report.
