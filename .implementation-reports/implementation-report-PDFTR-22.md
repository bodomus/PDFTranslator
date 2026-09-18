# Implementation Report

## Ticket

PDFTR-22 — Reflow architecture + proof of concept for body text

## Workflow

- Level: 2
- Branch: `codex/PDFTR-22-reflow-poc`, created from `master` at `38812657bffa`.
- Graphify: used before implementation; refreshed after the new PoC boundary.
- CRG: rebuilt before and after implementation.
- Working tree before changes: dirty only because the user-owned `temp/.agents.zip` deletion was
  already present; it was preserved.
- PDF visual workflow: Poppler-rendered normal and debug PDFs were inspected after the controlled
  Robitzsch run.

## Scope

- Modules: isolated `scripts/reflow_poc` models, planner, PyMuPDF adapter, and CLI; no production
  package integration.
- Pipeline stages: reads completed schema 1.3 evidence and the immutable source PDF; production
  extraction, translation, rendering, diagnostics, and publication remain unchanged.
- Dependency impact: none.
- Model/device impact: none; the persisted completed artifact was reused, with no NLLB/CUDA run.
- OCR impact: none.
- CLI/public contract impact: no `pdftranslate` command changed; a developer-facing
  `python -m scripts.reflow_poc` command was added and documented.
- PDF/output integrity impact: PoC redacts only selected source fragments in a copied page, appends
  bounded continuation pages, inserts selectable text, reopens the output, validates planned region
  text, and uses temporary sibling files. The source remains immutable.

## Investigation

### Current behavior

The production renderer plans every schema 1.3 occurrence into its anchor-page source rectangle,
shrinks the font, optionally expands downward, enforces typed completeness before mutation, then
redacts/inserts/saves/reopens/atomically publishes. It cannot move excess text into a later region.

### Expected behavior

The PoC needed a typed, side-effect-free planner for ordered body paragraphs and ordered regions,
exact continuation offsets, forward page flow, zero unplaced text, selectable output, machine-
readable evidence, and explicit rejection of non-body/unsafe layouts.

### Root cause or implementation gap

The production private `_BlockPlan` is one-to-one with a source rectangle. It has no flow-region,
continuation, or cross-page identity model. `ParagraphKind.BODY` is also insufficient for automatic
selection: running titles and page numbers on the four-page Robitzsch selection are classified as
body because repeated-element evidence is too short.

### Corrected Robitzsch evidence

Replaying the fixed planner reproduced 40 rendered and 21 overflow occurrences, but all 21 current
overflows are footnotes:

- body: 26 rendered, 0 overflow;
- footnote: 14 rendered, 21 overflow;
- overflow distribution: page 1 = 10, page 2 = 4, page 3 = 5, page 4 = 2.

Body reflow therefore does not resolve the present 21-overflow regression by itself. Page 3 remains
a failing document page due to footnotes and is still valid for proving the separate body-flow
mechanism.

### Pages 1, 3, and 4

- All are 432 x 648 points with no PyMuPDF image objects or vector drawings.
- Page 1: 22 occurrences; reviewed body rectangle `(67.35,54.50,378.28,405.46)`; running title,
  page number, and footnotes are non-flow; fixed result 12 rendered / 10 footnote overflow.
- Page 3: 13 occurrences; body indexes 38–41 and rectangle `(67.35,53.78,378.32,463.23)`; running
  title, page number, and footnotes are non-flow; fixed result 8 rendered / 5 footnote overflow.
- Page 4: 12 occurrences; reviewed body rectangle `(53.80,53.78,364.67,475.70)`; section running
  title, page number, and footnotes are non-flow; fixed result 10 rendered / 2 footnote overflow.

### Main symbols and contracts

- `FlowParagraph`: occurrence identity, exact translated text, source and fragment geometry.
- `FlowRegion`: target page, rectangle, column, order, and page-creation evidence.
- `PlacementSegment`: exact offsets/text, target page/rectangle, continuation index, font and
  measurement evidence, continuation state.
- `plan_flow`: pure forward-only placement and exact pre-mutation accounting.
- `PyMuPdfMeasurer`: uncommitted textbox probing behind `TextMeasurer`.
- `run_poc`: source/artifact validation, safe selection, bounded hybrid planning, rendering,
  post-save validation, plan/debug publication.

Expected blast radius is confined to the isolated script package, its tests, documentation,
ProjectWiki, and changelog. No cache/schema/translation/OCR/production CLI contract changed.

## Changes

- Hardened follow-up: post-save success evidence is now segment-local. Each placement is extracted
  from a padded clip around `PlacementSegment.target_rect`; region-wide extraction remains only an
  aggregate diagnostic. A duplicate-text regression proves that one physical occurrence cannot
  satisfy two planned segments.
- Added typed content disposition, region, paragraph, continuation, metrics, and plan models.
- Added a pure planner with word-boundary binary search, single-token character fallback, exact
  range reconstruction, one-column validation, and capacity failure rather than partial output.
- Added a PyMuPDF adapter that validates source identity and explicit selections, rejects unsafe
  regions/intersections, preserves anchors, creates bounded continuation pages, emits selectable
  text, writes JSON evidence, and creates a separate debug PDF.
- Added an argparse module entry point for explicit reviewed PoC execution.
- Added deterministic tests for sequential placement, region overflow, multi-segment paragraphs,
  non-flow rejection, exhausted capacity, and selectable end-to-end output.
- Added the durable architecture document with content policy, hybrid page strategy, source
  preservation, validation, failure behavior, twelve core decisions, and PDFTR-23 scope.
- Updated README, CHANGELOG, and affected Wiki pages.

## Controlled PoC evidence

Input: persisted PDFTR-21 schema 1.3 artifact, Robitzsch source page 3, occurrence indexes 38–41,
reviewed body region `(67.35,53.78,378.32,463.23)`, 12 pt body style.

- input logical paragraphs: 4;
- input translated characters: 2,153;
- planned paragraphs: 4;
- planned continuation count: 1;
- output paragraphs: 4;
- output extracted characters in planned regions: 2,157;
- unplaced translated characters: 0;
- new pages created: 1.

Occurrence 40 continues onto the inserted page, then occurrence 41 follows in order. The first PNG
review exposed a baseline collision even though extraction validation passed. Reserving one line of
baseline safety fixed the overlap; regenerated normal and debug PDFs show no clipping or collision.
The copied page retains its running title, page number, and source footnotes. The PDFs and JSON plan
remain under ignored repository-local `temp/pdftr22/` and are not committed.

## Graph and source validation

- Graphify preflight found reconstruction, occurrence completeness, renderer planning, saved-PDF
  validation, diagnostics, and publication boundaries; every material conclusion was verified in
  source and runtime evidence.
- Initial CRG graph was stale on PDFTR-21. A pre-implementation full build succeeded. The final full
  build reports 1,135 nodes, 10,066 edges, 125 files, and the PDFTR-22 branch/commit baseline. CRG
  discovery does not include the new untracked PoC files before they are Git-tracked, so their exact
  relationships were source-verified and covered by tests.
- Final Graphify refresh succeeded: 2,790 nodes, 5,694 edges, 192 communities. Its focused query
  found `FlowParagraph`, `FlowRegion`, `PlacementSegment`, `plan_flow`, `run_poc`,
  `PyMuPdfMeasurer`, serialization/font/source-identity dependencies, and all six new tests.
- No production `PdfRenderer`, CLI, translation, cache, OCR, or pipeline caller was added.

## Post-change impact

- CRG updated: yes, with the untracked-file limitation noted above.
- Graphify refreshed: yes, because a meaningful isolated module boundary was added.
- Blast radius: isolated PoC/scripts, tests, README/CHANGELOG, architecture docs, and Wiki.
- Unexpected dependants: none.
- Compatibility or migration concerns: none; schema 1.3 and production behavior are unchanged.

## Validation

- Focused tests: `tests/test_reflow_poc.py tests/test_rendering.py` — 27 passed.
- PoC-specific tests: 7 passed, including the duplicate-text segment-local regression.
- Controlled real-artifact run: passed without model/CUDA execution.
- PDF reopen/selectable-text/segment-local validation: passed.
- Poppler PNG visual validation: initial overlap found; corrected output and debug pages inspected
  with no remaining overlap/clipping.
- Wiki lint: 13 pages, 69 links, 0 errors, 0 warnings.
- Ruff format: passed for 200 files.
- Ruff lint: passed.
- mypy production source: passed for 84 source files.
- mypy isolated PoC: passed for 5 source files; PyMuPDF's untyped calls are explicitly scoped out
  in its adapter while typed project boundaries remain checked.
- Full `scripts/check.ps1`: 257 passed, 1 skipped, total coverage 88.70%.
- Real-model validation: not rerun; reused completed artifact as required.
- CUDA validation: not rerun; no model/device change.
- OCR integration validation: not applicable.

## Documentation

- Added `docs/reflow-architecture.md`.
- Added `knowledge/wiki/architecture/reflow-layout.md`.
- Updated Wiki navigation, system overview, render completeness, pilot evaluation, and log.
- Updated README for the developer-facing PoC command and CHANGELOG for user-visible project
  history.

## ProjectWiki pilot

- Pages consulted: index, system overview, render completeness, foreign-language preservation, and
  pilot evaluation.
- Canonical/raw sources additionally opened: reconstruction/repeated/rendering/pipeline/diagnostic
  source and tests, PDFTR-20/21 reports, source PDF, persisted artifact, CRG, and Graphify.
- Missing/stale knowledge: no reflow architecture and no paragraph-kind breakdown of the 21
  overflows.
- Pages updated: new reflow page, index, system overview, render completeness, pilot evaluation,
  and log.
- The Wiki avoided rediscovery of high-level safety/publication/exactness boundaries. Exact geometry
  and overflow classification still correctly required canonical evidence.
- Review exposed both the footnote-evidence gap and the need for visual PDF inspection.
- Final Phase 1 decision: **keep as-is**. Three tickets support curated source-backed Markdown plus
  lexical search; there is no measured justification for embeddings, semantic search, MCP, QMD,
  automated ingestion, or Wiki graph expansion.

## Remaining risks

- Region selection is intentionally explicit; safe automatic classification remains PDFTR-23 work.
- The PoC assumes the controlled white body background. Production needs background policy.
- PyMuPDF extraction normalization is not exact byte equality; exact authority remains pre-save
  offset reconstruction plus post-save segment presence and visual review.
- Footnotes are the actual current overflow source and remain fail-closed; a dedicated footnote
  layout scope is necessary after or alongside PDFTR-23.
- The hybrid recommendation still needs production decisions for inserted-page headers/page
  numbers, citations, and interaction with later pages/back matter.
