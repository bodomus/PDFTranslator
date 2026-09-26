# Review PDFTR-32 - Safe inline style runs for mixed-style paragraphs

## Completed

- Added immutable source-backed inline candidate/run/defer contracts with strict translated-range,
  ordering, non-overlap, and auditable-text invariants.
- Implemented exact, deterministic preserved-text mapping without source-offset reuse, fuzzy
  matching, semantic alignment, translation rewriting, or schema changes.
- Kept resolved paragraph typography as the base and activated only safe font-size/RGB-color
  overlays; bold, italic, and source font family remain diagnostic/requested-only.
- Integrated runs into BODY, HEADING, and FOOTNOTE discovery, all planner measurements, prefix
  fitting, heading-orphan checks, continuation clipping/rebasing, insertion, and saved validation.
- Unified measurement and insertion through one escaped HTML/CSS representation with automatic
  downscaling disabled.
- Added privacy-safe applied/deferred diagnostics and document/block aggregates.
- Added deterministic tests for shifted offsets, repeated ambiguity, partial mapping, run-aware
  fitting, crossing continuations, headings, footnotes, invalid contracts, escaping, diagnostics,
  and saved selectable size/color.
- Follow-up: removed count-equality/ordinal identity assumptions for repeated tokens and changed
  production line counting to PyMuPDF's physical rendered lines, with `2→2` and real-measurer
  heading-orphan regressions.
- Updated README, CHANGELOG, architecture/style docs, ProjectWiki, investigation, plan, and
  implementation report.

## Validation

- Original PDFTR-32 focused suites: 49 passed.
- Original PDFTR-32 full gate: 354 passed, 1 skipped, 89.08% coverage.
- ProjectWiki lint: 15 pages, 104 links, zero errors/warnings.
- Ruff format/check and strict mypy over 97 source files: clean.
- `scripts/check.ps1`: passed.
- Follow-up focused suites: 46 passed. Current full gate: 356 passed, 1 skipped, 89.10% coverage;
  Ruff, strict mypy, and ProjectWiki lint passed.
- Follow-up CRG update: 1,548 nodes / 13,859 edges / 149 files, with no affected known flow.
- Original PDFTR-32 post-change graph: 1,496 nodes / 13,356 edges; no affected known flow.
- Real Robitzsch render: 46 mixed-style paragraphs, 167 candidates, 0 safely applicable runs,
  167 deferred (37 not preserved, 130 unsupported-property-only), zero BODY/FOOTNOTE unplaced
  characters, zero overflow, four inserted pages, eight final pages.
- Poppler review of all eight real-output pages found no new clipping, overlap, or pagination
  corruption. No real-document inline fidelity is claimed because no run met the safe contract.
- Deterministic saved-PDF validation proves isolated selectable size/color application.

## Review status

LOCAL IMPLEMENTATION COMPLETE - CI PENDING

`READY FOR REVIEW` is intentionally withheld until GitHub Windows and Ubuntu jobs pass.
