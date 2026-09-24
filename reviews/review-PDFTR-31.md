# Review PDFTR-31 - Footnote typography fidelity

## Completed

- Activated authoritative reconstructed FOOTNOTE typography in production reflow by occurrence
  index, with paragraph id retained only as validation.
- Added a FOOTNOTE-role adapter over the shared BODY/HEADING conversion and preserved
  `heading=False`, normalized RGB, requested/unapplied bold/italic, mixed-style state, and fallback
  counts.
- Applied resolved size, line height, alignment, indents, and one-time spacing to measurement,
  pagination, continuations, insertion, saved validation, and diagnostics.
- Preserved duplicate-id safety and fail-closed handling for missing/mismatched/wrong-role/unknown-
  alignment styles and unsafe geometry.
- Preserved footnote-region eligibility, separator ownership, BODY/HEADING pagination,
  continuation ordering, capacity limits, exact accounting, disabled downscaling, source
  immutability, strict saved validation, and atomic publication.
- Kept inline-run rendering and font-face resolution out of scope.
- Updated README, CHANGELOG, architecture/style documentation, ProjectWiki, investigation, plan,
  and implementation report.

## Validation

- Focused production reflow suite: 30 passed.
- Full quality gate: 340 passed, 1 skipped, 89.19% coverage.
- ProjectWiki lint, Ruff format/check, and strict mypy: clean.
- Robitzsch: 35 FOOTNOTE occurrences, 37 segments, stable 7.970 pt, four footnote continuation
  pages, zero BODY/FOOTNOTE unplaced characters, zero overflow, eight final pages, unchanged source
  hash.
- Poppler visual review of all output pages found no visible clipping, overlap, missing note text,
  or separator collision.

## Review status

LOCAL IMPLEMENTATION COMPLETE - CI PENDING

`READY FOR REVIEW` is intentionally withheld until GitHub Windows and Ubuntu jobs pass.
