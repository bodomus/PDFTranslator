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
   `reviews/review-PDFTR-8.md` before moving the ticket to `In Review`.
9. Correct the rejected real-world proof: replace the NLLB-fragile Unicode protected-token
   sentinel, conservatively coalesce split paragraph blocks with dehyphenation, add regression
   tests, and validate a full English paragraph on real page 7.
10. Render and visually inspect page 7, verify Russian search/extraction/selectability/copyability
    and absence of the source English paragraph, record page 3 as a mapping/rendering defect, then
    remove all `Tasks/` paths from Git tracking while preserving the local files.
