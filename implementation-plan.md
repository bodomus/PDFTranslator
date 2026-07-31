# PDFTR-4 Implementation Plan

1. Mirror the attached ticket Markdown under `Tickets/`.
2. Add rendering errors, typed options/results, font discovery, glyph validation, and fitting helpers.
3. Implement a PyMuPDF renderer that validates source identity/schema/page/block contracts.
4. Redact original text while retaining image/vector objects and sampling background colors.
5. Insert embedded Cyrillic text with deterministic wrapping, font reduction, bounded expansion, and explicit overflow warnings.
6. Save through a temporary sibling, reopen and validate, then atomically publish the PDF.
7. Generate separate debug-layout PDFs with source/final/expanded/overflow annotations.
8. Add a thin `pdftranslate render` command with font, fitting, padding, mismatch override, overwrite, expansion, and debug options.
9. Add runtime-generated tests for replacement, images, geometry, fitting, overflow, glyph rejection, source mismatch, reopening, debug output, and Unicode paths.
10. Update README and CHANGELOG with usage, font discovery, safety behavior, and limitations.
11. Run focused tests, CLI smoke checks, full `scripts/check.ps1`, CRG analysis, and Graphify refresh.
12. Create and attach `review-PDFTR-4.md`, update YouTrack to `In Review`, and commit only PDFTR-4 files while preserving unrelated user files.
