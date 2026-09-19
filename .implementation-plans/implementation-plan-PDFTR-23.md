# PDFTR-23 Implementation Plan

1. Add production reflow contracts and errors under `src/pdftranslate/rendering/reflow/`.
2. Port the PDFTR-22 pure forward planner without production imports from `scripts/`; add per-style
   measurement and a basic heading orphan rule.
3. Implement conservative eligibility and single-column region discovery from paragraph,
   repeated-element, page, image, drawing, and footnote evidence.
4. Implement PyMuPDF measurement, bounded inserted-page planning, source-fragment redaction,
   selectable segment insertion, and segment-local post-save validation.
5. Compose reflow planning with the existing fixed-layout renderer before any PDF mutation, using
   inserted continuation pages directly after each source page and retaining fixed-layout handling
   for anchors, footnotes, and non-eligible content.
6. Extend typed render evidence and diagnostics with strategy, segment/continuation/inserted-page
   counts, target pages/rectangles, exact offsets, and zero-unplaced state.
7. Add deterministic production regressions for fit, continuation, ordering, heading orphaning,
   anchors, footnotes, image/drawing and ambiguity rejection, exact accounting, duplicate local
   validation, atomic publication, foreign text, and fixed-layout compatibility.
8. Run focused tests and inspect failures before broad checks.
9. Update production reflow docs, README, CHANGELOG, affected ProjectWiki pages, and Wiki log; run
   Wiki lint.
10. Run controlled Robitzsch page 3/4 body validation without NLLB when the persisted schema 1.3
    artifact is available; render PNGs and inspect them visually. Keep footnote failure explicit.
11. Refresh CRG and Graphify, inspect blast radius, run Ruff, mypy, and `scripts/check.ps1`.
12. Write the implementation report and ticket review. Ask for confirmation immediately before
    posting comments, changing YouTrack state, or uploading completion artifacts.
