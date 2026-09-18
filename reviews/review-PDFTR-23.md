# Review PDFTR-23

## Outcome

Implemented production body-text reflow for conservatively classified single-column book pages on
`codex/PDFTR-23-production-body-reflow`.

## Review summary

- Production code is isolated under `src/pdftranslate/rendering/reflow/` and has no dependency on
  `scripts/reflow_poc`.
- Body prose and one basic heading style use typed, exact continuation segments with pure planning,
  bounded Strategy A inserted pages, baseline safety, and a minimal heading orphan rule.
- Eligibility combines kind, occurrence identity/order, repeated policy, fragment columns,
  geometry, margin anchors, footnote boundary, and image/drawing intersections. Unsafe evidence
  fails closed.
- Fixed-layout rendering remains active for other content. Footnotes never enter body flow and
  required footnote overflow still blocks publication.
- Redaction/mutation starts only after fixed and reflow completeness passes. Existing source PDF and
  later source pages remain intact; atomic output behavior is preserved.
- Saved continuation evidence is segment-local. Duplicate text elsewhere on the same page cannot
  prove a missing placement.
- Diagnostics expose strategy, occurrence mapping, final pages/rectangles, offsets, continuation,
  inserted-page, unsupported-page, and unplaced-text evidence.

## Validation reviewed

- Focused production/PoC/rendering/diagnostics/pipeline tests: 60 passed.
- Full quality gate: 263 passed, 1 skipped, 88.51% coverage; Ruff, mypy, Wiki lint passed.
- Real Robitzsch: pages 3/4 produced 7 valid body segments and zero unplaced body characters.
  Normal publication still failed correctly on 21 footnote overflows and left no output.
- Diagnostic footnote-preserve copy was rendered to PNG and visually checked: body text was
  selectable, anchors/footnotes remained present, and no overlap or clipping was observed.

## Scope boundary

This review does not claim a publishable full Robitzsch document. Footnote pagination, arbitrary
columns, tables, sidebars, figures/floats, verse, math, bibliography typography, OCR redesign, and
translation changes remain outside PDFTR-23.
