# PDFTR-20 investigation

## Classification

- Workflow level: 2.
- Risk: final-PDF content integrity and atomic publication.
- User-visible contract: a fixed-layout render with unresolved required content must fail instead of publishing a partial translation.

## ProjectWiki pilot before implementation

- Read `knowledge/wiki/index.md`.
- Searched for rendering, paragraph reconstruction, output validation, overflow, and translation completeness.
- Useful pages: `architecture/system-overview.md`, `workflows/development-workflow.md`, and `testing/wiki-validation.md`.
- Gap: the Wiki describes the pipeline boundary and validation workflow but has no rendering/content-completeness invariant or failure-mode page.

## Graph and source findings

- Graphify located the production path `LogicalParagraph` → `PdfRenderer.render` → `_plan_page` / `_fit` → `_insert_page` → `_validate_saved_pdf` → pipeline `_validate_and_publish`.
- CRG was stale on the PDFTR-19 branch and was rebuilt successfully on `codex/PDFTR-20-strict-render-completeness` (`124 files`, `1101 nodes`, `9716 edges`).
- Source verification shows schema 1.3 paragraphs are converted to render blocks in document order. `PRESERVE`, `SKIP`, and `REMOVE` are excluded from fitting; `REMOVE` is redacted while `PRESERVE` and `SKIP` remain in the source PDF.
- `_fit` returns `None` after bounded attempts down to `min_font_size`. `_insert_page` skips such plans.
- Current `PdfRenderer.render` records overflow as a warning, excludes overflow units from PDFTR-18 post-save validation, saves the file, and atomically replaces the renderer output. The pipeline subsequently publishes that incomplete candidate.
- `BlockRenderResult` has booleans but no authoritative terminal state or policy accounting. `RenderResult` can report overflow yet still be successful.
- Diagnostics index render results by `block_id`; schema 1.3 split paragraphs can share an ID, so dictionary lookup collapses occurrences and is not safe as a completeness invariant.

## Robitzsch evidence

- Reused the completed schema 1.3 translated artifact and rendered PDF from the prior real CUDA run.
- Replayed current `_plan_page` with production defaults against all 61 logical paragraphs.
- Result: 40 rendered plans and 21 overflow plans.
- Confirmed missing translated prose corresponds to overflow plans on the manually reported pages, including ten `p0001-b0007` occurrences on page 1, five `p0003-b0005` / `p0003-b0006` occurrences on page 3, and two `p0004-b0004` occurrences on page 4. Additional overflow exists elsewhere in the four-page sample.
- Every overflow had `font_size=None`, reached the configured 6 pt minimum after five fitting attempts, was not expanded under the current default, was skipped by `_insert_page`, and was excluded from `_validate_saved_pdf`.
- This proves overflow is the direct cause for the observed blank regions. Non-Cyrillic marker-only units are rendered/pass-through units but are intentionally outside the Cyrillic-specific PDFTR-18 text check.

## Constraints

- Do not implement reflow, cross-page flow, repagination, new pages, language detection, or translation policy changes.
- Preserve PDFTR-17 marker handling and PDFTR-18 local saved-PDF validation.
- Preserve source immutability and prevent any incomplete candidate from reaching the requested output path.
