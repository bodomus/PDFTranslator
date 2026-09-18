# PDFTR-22 implementation plan

## Objective

Design and prove a typed body-flow architecture without weakening or wiring around the current
fail-closed production renderer.

## Design

1. Add an isolated `scripts/reflow_poc` package with typed models for:
   - explicit content disposition;
   - ordered flow regions;
   - occurrence-identified flow paragraphs;
   - continuation placement segments with exact character ranges;
   - aggregate layout plan and measurements.
2. Implement a pure planner that consumes ordered paragraphs, ordered regions, and a measurement
   protocol. The planner will place text sequentially, split only into forward continuation
   segments, preserve exact text via `[start:end]` ranges, and fail closed when capacity is
   exhausted.
3. Implement a PyMuPDF measurement/render adapter. Measurement probes text without committing it;
   PDF mutation begins only after the complete plan has zero unplaced characters.
4. Implement the page-3 executable PoC:
   - read schema 1.3 JSON and source PDF;
   - validate explicit body occurrence selection and region safety;
   - copy the controlled source page;
   - redact selected source fragments only;
   - append bounded blank continuation pages as required;
   - insert selectable text and optional debug boxes/labels;
   - atomically write the PDF and JSON plan under caller-provided paths;
   - reopen and validate extraction and paragraph/segment coverage.
5. Add deterministic tests for sequential placement, region overflow, a long paragraph spanning
   multiple segments, rejection of non-flow content, unsupported layout/capacity, selectable PDF
   output, and page-3 artifact execution without a model download.
6. Create `docs/reflow-architecture.md` with the evidence, classifications, page-strategy
   comparison, twelve required decisions, validation model, failure behavior, and concrete PDFTR-23
   scope.
7. Update CHANGELOG and affected ProjectWiki pages, including a new reflow architecture page,
   cross-links, log entry, pilot result, and evidence-based Phase 1 decision.
8. Create the implementation report and review file.

## Page strategy to prove

Use a hybrid policy: consume explicitly safe source-page body regions first, then create bounded
continuation pages with the same geometry and body region. The PoC copies page 3 and creates a
blank continuation page only when necessary. Production PDFTR-23 should reuse classified source
regions, preserve anchors, and insert pages only under explicit single-column rules; it must not
flow into an unclassified page.

## Validation sequence

1. Focused planner tests.
2. Focused executable/PDF test and controlled Robitzsch page-3 PoC run using the persisted artifact.
3. Reopen output with PyMuPDF and record measurements.
4. Render output pages for visual inspection.
5. Run Wiki lint.
6. Run Ruff format check, Ruff lint, mypy, and `scripts/check.ps1`.
7. Update CRG and inspect changed-symbol blast radius.
8. Refresh Graphify because the isolated PoC introduces a meaningful new layout module boundary,
   then source-verify the resulting relationships.

## Stop conditions

- Do not broaden into production renderer integration.
- Do not silently reclassify footnotes, headings, tables, figures, or ambiguous blocks as body.
- Do not publish a PoC PDF when any selected input character is unplanned or post-save validation
  fails.
- Reassess before expanding beyond the explicit page-3 single-column demonstration.
