# Implementation plan — PDFTR-8

1. Define versioned validation options, document/stage/integrity/manual/defect result models and
   stable JSON serialization.
2. Implement deterministic corpus manifest/discovery and subset selection while excluding result
   trees and translated outputs.
3. Implement sequential dry-run and full validation orchestration around `plan_pipeline()`,
   `run_pipeline()`, and one shared translation runtime, capturing stage timing and source hashes.
4. Implement atomic per-document JSON, summary JSON, summary Markdown, logs, and manual-review
   template output.
5. Add a stdlib validation CLI and `scripts/validate-real-pdfs.ps1` wrapper with explicit corpus,
   output, subset, dry-run, model/device/OCR/cache/resume options.
6. Add generated-PDF/fake-backed tests for success, text/image/scanned/mixed classification,
   extraction/translation/render/OCR/validation failures, continuation, reports, Unicode paths,
   cache/resume, and checksum preservation.
7. Update README, CHANGELOG, ignore rules, and reproduction instructions.
8. Run focused tests, controlled representative-PDF validation, full quality checks, post-change
   Graphify/CRG impact review, and create `implementation-report.md` plus
   `review-PDFTR-8.md` before moving the ticket to `In Review`.
