# PDFTR-2 Implementation Plan

1. Add and lock the current compatible PyMuPDF dependency.
2. Add strict domain models for bounding boxes, spans, blocks, pages, source
   identity, extracted documents, and inspection reports.
3. Add configurable page-classification thresholds to application settings.
4. Implement PDF-specific errors, one-based page-range parsing, PyMuPDF validation,
   source fingerprinting, block/span extraction, image coverage, and deterministic
   page classification.
5. Add analyzer and extractor services independent of Typer.
6. Add versioned UTF-8 JSON serialization with round-trip validation and protected,
   atomic output writes.
7. Add thin `inspect` and `extract` Typer commands with clean machine JSON and useful
   exit-code-2 errors.
8. Add generated PDF tests for text, multiple pages, empty, image-only, mixed,
   invalid, encrypted, order, ranges, Unicode paths, output protection, JSON, and CLI.
9. Update README and CHANGELOG, including thresholds and multi-column limitations.
10. Run formatting, lint, strict mypy, full tests/coverage, CLI smoke tests, PDF
    render inspection, CRG update/impact analysis, and Graphify refresh.
11. Create `review-PDFTR-2.md`, attach it to YouTrack with the existing ticket source,
    move the ticket to review/done as evidence permits, and commit only PDFTR-2 files.
