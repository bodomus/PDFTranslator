# PDFTR-23 Investigation

## Workflow and baseline

- Level 2 structural rendering change.
- Branch: `codex/PDFTR-23-production-body-reflow`, created from `master` at `f7ad03d5ad25dfbf9a15fb6d2f13942110c1ca1a`.
- Pre-existing working-tree change preserved: `temp/.agents.zip` is deleted.
- Python: 3.12.10 through uv 0.5.26.
- Graphify and CRG were queried; CRG was rebuilt on the ticket branch.

## Current behavior

Production schema 1.3 rendering plans every logical paragraph occurrence into its source-backed
rectangle. It may reduce the font and optionally expand a rectangle, but cannot continue body text
onto another page. Required overflow fails before redaction, insertion, saving, or publication.
Saved-PDF validation is local to each fixed-layout render rectangle. Pipeline publication is atomic.

PDFTR-22 supplies an isolated, side-effect-free region planner and PyMuPDF adapter under
`scripts/reflow_poc`. It is not reachable from production and supports only explicit reviewed body
occurrences on one source page.

## Expected behavior

Confident single-column body prose and one basic heading style should be classified into explicit
regions, planned as exact typed segments, and continued forward through bounded inserted pages.
Anchors and unsupported content remain outside body flow. All required translated text must reach
one terminal state before mutation, and every saved segment must validate in its own padded clip.

## Implementation gap

Production has no reflow models, eligibility/region discovery, continuation planner, measurement
adapter, mutation path, segment validation, or reflow diagnostics. Directly importing the PoC would
couple production to `scripts/` and leave its manual selection assumptions intact.

## Source-verified boundaries

- Entry point: `PdfRenderer.render`, reached by CLI `render` and pipeline `_render`.
- Publication: renderer writes a sibling temporary PDF, reopens it, then replaces the requested
  output; pipeline performs its own validate-and-publish step for end-to-end runs.
- Occurrence identity: schema 1.3 tuple index is authoritative; paragraph IDs are not unique.
- Paragraph evidence: kind, ambiguity, fragments, columns, geometry, spans, and source mappings are
  available on `LogicalParagraph`.
- Repeated policy: fragment classifications resolve to translate/preserve/skip/remove.
- Images: page-level counts exist in the model; exact image and drawing rectangles require the open
  PyMuPDF page.
- Completeness: `BlockRenderResult` and `_ensure_render_complete` are the existing production gate.
- Foreign text: `translated_text` is authoritative and must be passed through byte-for-character
  without normalization.

## PoC disposition

- Promote concepts and invariants: `FlowRegion`, `FlowParagraph`, `PlacementSegment`, exact
  accounting, forward-only planning, bounded page capacity, and segment-local validation.
- Adapt: dispositions, heading style/orphan rule, source-page relationship, diagnostics, and final
  document page numbering.
- Rewrite: region discovery, production mutation, background handling, integration, and errors.
- Leave PoC-only: manual occurrence/rectangle CLI, standalone plan/debug outputs, and imports from
  `scripts/reflow_poc`.

## Chosen page strategy

Strategy A: each eligible source page consumes its source body region, then receives bounded blank
continuation pages inserted immediately after it. Planning computes final page numbers with prior
insertions accounted for. Later source pages and their anchors shift intact and are never used as
capacity for an earlier page. Inserted pages copy source geometry, use white background, and do not
regenerate headers or page numbers.

## Smallest coherent production change

Add a focused `pdftranslate.rendering.reflow` package for typed contracts, pure planning,
conservative region discovery, PyMuPDF measurement/mutation, and saved-segment validation. Compose
it from `PdfRenderer` while retaining the existing fixed-layout path for all other units. Extend
render results/report summaries with strategy and aggregate reflow evidence.

## Safety and blast radius

- Source PDF remains immutable.
- Redaction is limited to fragments in a complete reflow plan.
- Planning/capacity failure occurs before mutation.
- Footnotes remain fixed and required footnote overflow remains fatal.
- Ambiguity, multiple columns, unsafe geometry, and image/drawing intersections reject reflow.
- No dependency, translation, cache, resume, OCR, or schema-version change.
- Affected areas: rendering package, diagnostics builder/models, rendering tests, end-to-end report
  assertions, README/CHANGELOG, reflow docs, and affected Wiki pages.

## Required validation

Focused reflow/rendering/diagnostics/end-to-end tests; exact foreign-text regression; atomic failure
regression; Wiki lint; Ruff format/lint; mypy; full `scripts/check.ps1`; CRG refresh and Graphify
refresh because a production module boundary is added; controlled real-PDF machine and PNG review.
