# PDFTR-31 implementation report

## Outcome

Production FOOTNOTE reflow now consumes the authoritative reconstructed typography contract for
each paragraph occurrence. The resolved font size, line-height ratio, RGB color, physical
alignment, indents, and one-gap spacing drive measurement, pagination, continuation splitting,
HTML/CSS insertion, saved-segment validation, and diagnostics without changing footnote-region or
separator ownership.

## Workflow

- Level: 2
- Graphify: existing graph queried and source-verified; no structural refresh required
- code-review-graph: full preflight rebuild and post-change incremental update completed
- Working tree before changes: dirty only for unrelated pre-existing `temp/.agents.zip` deletion
- Branch: `codex/PDFTR-31-footnote-typography-fidelity`, created from `master` at `e9fd949917d4`

## Scope

- Modules: reflow typography adapter, footnote discovery, renderer planning/diagnostics
- Pipeline stages: typography reconstruction handoff, footnote planning, PDF insertion/validation
- Dependency impact: none
- Model/device impact: none
- OCR impact: none
- CLI/public contract impact: none
- PDF/output integrity: exact accounting, saved validation, source immutability, and atomic
  publication remain enforced

## Investigation

- `PdfRenderer.render()` already reconstructed styles once and passed the occurrence-index map to
  BODY/HEADING discovery.
- `_plan_reflow_document()` omitted that map from the footnote discovery call.
- `discover_footnote_page()` consequently synthesized source-size/configured-line-height styling
  and added `font_size * 0.25` trailing spacing.
- The shared planner and PyMuPDF adapter already carried all required style fields with correct
  first/continuation/final segment semantics, so no new pagination or insertion path was needed.
- The expected blast radius was the adapter, footnote discovery, renderer diagnostics, tests, and
  affected documentation.

## Changes

- Added `footnote_reflow_style()` as a thin FOOTNOTE-role validator over the existing common
  resolved-style mapper, with `heading=False` and normalized RGB.
- Passed the existing style map into production footnote discovery.
- Kept occurrence index as the lookup authority and paragraph id as validation only; duplicate ids
  remain safe.
- Made missing, embedded-index-mismatched, paragraph-id-mismatched, BODY/HEADING-role, and unknown-
  alignment styles fail footnote discovery closed when the authoritative map is supplied.
- Retained the legacy synthesized path only when callers intentionally omit the style map.
- Replaced synthetic production footnote spacing with resolved before/after spacing.
- Exposed applied FOOTNOTE size, line height, alignment, indents, spacing, color, requested/applied
  face state, mixed-style state, and fallback count without changing BODY/HEADING diagnostics.
- Preserved separator discovery/ownership, region safety, continuation ordering, page limits,
  automatic-downscaling prohibition, exact offsets, and strict saved-PDF validation.

## Regression coverage

- FOOTNOTE adapter property mapping, normalized RGB, `heading=False`, and wrong-role rejection;
- occurrence-index discovery with a paragraph id duplicated across roles;
- missing occurrence, embedded-index mismatch, paragraph-id mismatch, BODY role, HEADING role, and
  unknown-alignment fail-closed cases;
- resolved font size, line height, alignment, indents, spacing, and color;
- true-first-segment indent/space-before, persistent side indents/alignment, final-only space-after,
  exact text offsets, and zero unplaced text;
- unsafe FOOTNOTE geometry rejection;
- separator-preserving production pagination with mixed Cyrillic/Latin/Greek selectable text;
- applied FOOTNOTE diagnostics and unchanged BODY/HEADING behavior;
- fatal capacity exhaustion preserving an existing destination.

## Graph and source validation

- Graphify confirmed `_plan_reflow_document()` as the production caller of
  `discover_footnote_page()` and the renderer/tests as the reverse blast radius.
- The refreshed code-review-graph contains 1,487 nodes and 13,219 edges on the PDFTR-31 branch.
- Post-change heuristic risk is 0.35 with no affected flow; its name-based test-gap heuristic did
  not associate five private production symbols with tests, but direct focused/full execution
  covers those paths.
- Source review confirmed the renderer path remains reachable and no translation, schema, cache,
  OCR, model, or CLI boundary changed.

## Validation

- Focused `tests/test_reflow_production.py`: 30 passed.
- ProjectWiki lint: 15 pages, 101 links, zero errors/warnings.
- Ruff format/check: clean.
- Strict mypy over 96 source files: clean.
- Full pytest: 340 passed, 1 skipped, 89.19% coverage.
- `scripts/check.ps1`: passed completely with repository-local UV and pytest temporary paths.

## Real Robitzsch validation

- Naturally classified FOOTNOTE occurrences: 35
- Rendered FOOTNOTE segments: 37
- Resolved font size: min/median/max 7.970 pt
- FOOTNOTE continuation pages: 4
- BODY unplaced characters: 0
- FOOTNOTE unplaced characters: 0
- Overflow count: 0
- Final page count: 8
- Inserted page count: 4
- Source SHA-256: unchanged

The eight-page result matches the already style-aware BODY baseline; the historical PDFTR-24
nine-page result included one BODY continuation that later resolved BODY metrics no longer need.
Poppler rendered all four source pages and all eight output pages. Visual review found readable
selectable footnotes below body content, correct continuation ordering, and no visible clipping,
overlap, missing text, or separator collision.

## Documentation

Updated README, CHANGELOG, reflow architecture, style reconstruction, affected ProjectWiki pages,
and the Wiki log. Added the ticket copy, investigation, implementation plan, implementation report,
and review artifact.

## Remaining external gate

GitHub Windows and Ubuntu CI have not run because the working branch has not been committed or
pushed. Per the ticket, `READY FOR REVIEW` is withheld until both jobs are green.

Current status: **LOCAL IMPLEMENTATION COMPLETE - CI PENDING**.
