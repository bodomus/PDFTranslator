# PDFTR-29 implementation plan

1. Extend the compact reflow style and placement-segment contracts with BODY typography fields,
   keeping backward-compatible defaults for headings and footnotes.
2. Add a BODY-only adapter from `ResolvedParagraphStyle` to renderer-facing style and color values.
3. Reconstruct typography once in `PdfRenderer.render()`, create an occurrence-index map, and pass
   it only into body discovery.
4. Update body discovery to use resolved styles for BODY paragraphs while retaining existing
   heading and footnote behavior.
5. Update the planner so indents and before/after spacing participate in measurement, pagination,
   heading-orphan checks, and continuation semantics exactly once.
6. Make PyMuPDF measurement and insertion share the same HTML/CSS style representation without
   automatic downscaling; preserve strict saved-segment validation.
7. Extend block diagnostics with applied typography, mixed-style/fallback information, and explicit
   requested-versus-applied bold/italic fields.
8. Add deterministic regression tests for occurrence mapping, BODY-only activation, alignment,
   indent/spacing continuation behavior, pagination, diagnostics, completeness, and atomic failure.
9. Run focused tests, render the cached Robitzsch artifact, inspect required PNG pages, then run the
   complete `scripts/check.ps1` quality gate.
10. Update affected documentation, ProjectWiki pages, CHANGELOG, implementation report, and ticket
    review artifact; lint ProjectWiki and attach the review to PDFTR-29.
