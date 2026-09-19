# Implementation Report

## Ticket

PDFTR-23 — Production body-text reflow for single-column book pages

## Workflow

- Level: 2.
- Graphify: preflight queries used; post-change refresh succeeded with 3,021 nodes, 6,153 edges,
  and 206 communities.
- CRG: stale PDFTR-22 graph rebuilt before implementation; post-change update succeeded on the
  PDFTR-23 branch. Final graph reports 1,214 nodes, 10,784 edges, and 131 files.
- Working tree before changes: dirty only because user-owned `temp/.agents.zip` was already deleted;
  that deletion was preserved and not included in this work.

## Scope

- Modules: new `pdftranslate.rendering.reflow` boundary; renderer composition; rendering and
  diagnostics models/builders; tests; docs and ProjectWiki.
- Pipeline stages: render planning, PDF mutation, saved-PDF validation, diagnostics, atomic output.
- Dependency impact: none.
- Model/device impact: none; NLLB/CUDA was not run.
- OCR impact: none.
- CLI/public contract impact: no new switch; safe reflow is selected internally.
- PDF/output integrity impact: exact segment accounting, bounded inserted pages, local saved
  validation, and existing atomic publication are mandatory.

## Investigation

- Current behavior: production rendered every occurrence into its source rectangle and failed
  required overflow before mutation. PDFTR-22 reflow existed only under `scripts/reflow_poc`.
- Expected behavior: safe body/heading occurrences flow through explicit regions and bounded
  continuation pages while anchors and fixed-layout completeness remain intact.
- Root gap: no production models, classification/region discovery, planner, adapter, mutation,
  validation, or diagnostics existed for continuation segments.
- Main symbols: `PdfRenderer.render`, `_plan_reflow_document`, `discover_reflow_page`, `plan_flow`,
  `PyMuPdfMeasurer`, `LayoutPlan`, `PlacementSegment`, `validate_saved_segments`, `RenderStrategy`.
- Configuration/schema: schema 1.3 remains unchanged; `RenderOptions.max_reflow_pages` bounds page
  creation. Translation/cache/resume identities are unchanged.
- Expected blast radius: rendering and diagnostics only, with pipeline behavior inherited through
  the existing renderer service.

## Changes

- Added production `FlowRegion`, `FlowParagraph`, `PlacementSegment`, styles, exact offsets, terminal
  state, and aggregate plan contracts without importing `scripts/reflow_poc`.
- Added deterministic pure forward planning with word-boundary splitting, single-token character
  fallback, exact reconstruction, capacity failure, per-style measurement, baseline reserve, and a
  basic heading-plus-following-body orphan rule.
- Added conservative region discovery from occurrence kind/order, fragments/columns, repeated
  policy, page geometry, margin anchors, footnote boundary, and live image/drawing rectangles.
- Added a source-verified ambiguity rule: partial/isolated ambiguity rejects reflow; a homogeneous
  group of at least three all-ambiguous occurrences can be resolved only by the remaining complete
  page evidence. This makes reviewed Robitzsch pages 3/4 reachable without a manual override while
  preserving the insufficient-evidence regression.
- Implemented Strategy A. A source page consumes its safe region first; bounded blank pages with
  matching geometry are inserted immediately afterward. Final page indexes include earlier
  insertions, so later source pages remain intact. Inserted pages do not regenerate headers/numbers.
- Composed fixed and reflow plans before any mutation. Reflow fragments alone use their retained
  source boxes; existing production background sampling handles source-page redaction. Footnotes
  remain fixed/preserved and overflow remains fatal.
- Reopened the candidate once and validated every reflow segment only in its padded target clip
  (`max(2.0, font_size * 0.8)`). Page text is diagnostic only.
- Extended render/report evidence with strategy, final target pages/rectangles, offsets, segment and
  continuation counts, inserted pages, fixed paragraphs, unsupported pages, and unplaced count.
- Added production regressions covering sequential order, cross-page continuation, following
  paragraphs, heading orphaning, anchor/footnote behavior, ambiguity, image/drawing rejection,
  exact reconstruction, duplicate local validation, foreign Latin/Greek exactness, atomic output,
  and fixed-layout compatibility (existing suite).

## Graph and source validation

- Graphify identified the renderer/pipeline/diagnostics boundary and, after refresh, the new
  `discover_reflow_page`, `_plan_reflow_document`, production measurer, and production tests.
- CRG update found no affected execution flow beyond the intended rendering/report neighborhood.
  Its generic gap list includes dataclasses/enums and PoC CLI parsing; production behavior is
  directly covered by `test_reflow_production.py` plus existing rendering/pipeline suites.
- Source validation confirmed CLI and pipeline reach `PdfRenderer`, pipeline publication remains
  atomic, occurrence index is authoritative, and no schema/cache/translation/OCR boundary changed.
- Graphify initially failed inside the sandbox with Windows access denied; the same confirmed
  command succeeded with repository write permission.

## Post-change impact

- CRG updated: yes.
- Blast radius: rendering, diagnostics serialization, and documentation as planned.
- Unexpected dependants: none.
- Compatibility: schema 1.1 and non-eligible schema 1.3 units retain fixed-layout behavior. No
  dependency or migration is required.

## Validation

- Focused tests: 60 passed across production reflow, PoC regression, rendering, diagnostics, and
  end-to-end pipeline suites.
- Full tests through `scripts/check.ps1`: 263 passed, 1 skipped; coverage 88.51% (minimum 80%).
- Ruff format: passed (210 files already formatted in final gate).
- Ruff lint: passed.
- mypy: passed, 89 source files.
- ProjectWiki lint: 13 pages, 74 links, zero errors/warnings.
- Bootstrap/check scripts: `scripts/check.ps1` passed.
- CLI smoke tests: covered by the full suite; no CLI contract change.
- Real-model/CUDA validation: not rerun; reused the persisted completed PDFTR-21 artifact.
- OCR validation: not applicable.

### Controlled Robitzsch validation

- Normal production render: correctly failed with 21 required footnote overflows; requested output
  remained absent.
- Production planning selected 7 body occurrences on pages 3/4 (occurrences 38–41 and 51–53), 7
  local segments, zero unplaced characters, and zero inserted pages for their current translated
  lengths/font evidence.
- For visual body-only evidence, a diagnostic copy changed only footnote policy to preserve. This
  was not treated as publishable output. Saved segment-local validation passed and page text stayed
  selectable.
- Poppler PNG review at 150 DPI found no body/footnote overlap, clipping, or lost running/page
  anchors on pages 3/4. Existing sampled redaction backgrounds remain visible; no debug overlay was
  used.
- Synthetic production integration separately proved a selectable multi-page continuation with an
  inserted page, exact Latin/Greek text, later paragraph ordering, and local validation.

## Documentation

- Updated `README.md`, `CHANGELOG.md`, `docs/reflow-architecture.md`, ProjectWiki reflow/system/
  completeness pages, and Wiki log.
- Saved the ticket text, investigation, implementation plan, this report, and ticket review.

## Remaining risks

- Footnote pagination remains the actual Robitzsch publication blocker and belongs to PDFTR-24.
- Conservative eligibility intentionally leaves mixed ambiguity, multi-column pages, tables,
  figures intersecting body regions, verse, and complex layouts on the fixed/fail-closed path.
- Production preserves existing background sampling behavior; typography/background fidelity beyond
  safe text placement remains outside this ticket.
