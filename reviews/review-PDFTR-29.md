# Review PDFTR-29 — Body typography fidelity

## Completed

- Reconstructed paragraph typography once per document and activated it only for production BODY
  reflow.
- Mapped resolved styles by occurrence index, including duplicate paragraph-id coverage.
- Applied resolved font size, line height, color, physical alignment, left/right indents,
  first-line indent, and paragraph spacing to both measurement and insertion.
- Enforced first-line indent and space-before once at paragraph start and space-after once at
  completion, including continuation cases.
- Preserved existing heading and footnote style behavior.
- Added BODY diagnostics for applied typography, mixed-style/fallback state, and explicit
  requested/applied bold/italic values.
- Kept source font literal identity unchanged and safely deferred font-variant application.
- Updated reflow documentation, ProjectWiki, and CHANGELOG.

## Regression coverage

- occurrence-index mapping with duplicate paragraph ids;
- resolved BODY size/color/alignment/indents/spacing;
- first-segment and continuation semantics;
- unsafe indent geometry fails closed;
- bold/italic requested-versus-applied and mixed-style reporting;
- heading and footnote non-activation;
- exact segment accounting, local saved-PDF validation, capacity failure, and atomic output;
- real selectable Cyrillic/Greek production rendering.

## Validation result

- Focused tests: 40 passed.
- Full quality gate: 325 passed, 1 skipped, 89.15% coverage; Ruff, mypy, and ProjectWiki lint clean.
- Robitzsch: 61/61 units, overflow 0, unplaced 0, footnote unplaced 0, 8 output pages.
- Source pages 1/3/4 were visually compared with output pages 1/5/7; no clipping, overlap, missing
  BODY text, or anchor regression was found.

## Follow-up fix: heading orphan and hanging-indent safety

- The orphan guard now proves the configured following BODY line count through the production
  style-aware measurer instead of estimating height alone.
- Valid negative first-line indents remain supported, while geometry escaping the flow region is
  rejected before mutation.
- Added deterministic regressions for both fixes; the pre-existing heading and continuation tests
  remain authoritative.

### Follow-up validation

- Focused planner/rendering/diagnostics tests: 43 passed.
- Full quality gate: 328 passed, 1 skipped, 89.15% coverage; Ruff, mypy, and ProjectWiki lint clean.
- Cached Robitzsch: 61 units, 7 BODY segments, 4 inserted pages, overflow 0, BODY unplaced 0,
  footnote unplaced 0; pagination unchanged.

## CI determinism fix

- Production reflow tests now use the same bundled, OFL-licensed Liberation Sans Regular 2.1.5
  bytes on Windows and Ubuntu.
- Removed OS-dependent test font selection without changing production font handling, planner
  behavior, reflow limits, or completeness enforcement.
- Focused production reflow suite: 19 passed, including the pinned-path/hash regression and both
  formerly CI-failing tests.
- Full quality gate: 329 passed, 1 skipped, 89.15% coverage; Ruff, mypy, and ProjectWiki lint clean.

## Final review status

READY FOR REVIEW
