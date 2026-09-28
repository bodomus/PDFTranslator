# Investigation — PDFTR-34 Human-readable inline-style diagnostics summary

Level: 1 (local presentation change in one diagnostics module).

## 1. Where are the four document-level inline-style totals populated?

`ReportSummary.inline_style_*` is defined in
`src/pdftranslate/diagnostics/models.py` (lines 208-211) with default `0` and `ge=0`.

It is populated exclusively in `src/pdftranslate/diagnostics/builder.py`:

- `build_success_report` (lines 390-395) copies `render.inline_style_*`, where `render` is the
  render-stage summary, or `0` when `render is None`.
- `build_failure_report` (lines 459-481) constructs `ReportSummary` without those fields, so they
  take the model defaults (`0`).

The render-stage document totals themselves come from
`src/pdftranslate/rendering/renderer.py` (lines 302-312), which sums per-block results; block-level
totals are set at `reporting`-independent sites in the renderer (lines 1196-1199) and copied into
`BlockDiagnostic` in `builder.py` (lines 252-260).

## 2. Are they already correct for success reports?

Yes. For success reports the four fields come directly from the authoritative render summary. No
recomputation is needed or wanted; the HTML renderer must read `report.summary.inline_style_*`.

## 3. Does the HTML renderer currently read only `report.summary` for its top table?

Yes. `_render_html` in `src/pdftranslate/diagnostics/reporting.py` builds the top `<table>` purely
from `report.summary.*` (plus `report.status`/`report.run_id` for the header) and then embeds the
full JSON in `<pre>` as machine-readable details.

## 4. Which existing tests cover `_render_html()` / `write_report()`?

- `tests/test_diagnostics.py::test_report_writer_never_replaces_an_existing_artifact` is the only
  test that asserts on HTML content. It renders an HTML report via `write_report(...,
  report_format="html")` and asserts footnote rows are present in the human-readable table.
- `tests/test_end_to_end_pipeline.py` patches `pdftranslate.pipeline.runner.write_report` to
  simulate publication failure; it does not assert HTML structure.

## 5. Can this ticket remain isolated to diagnostic presentation?

Yes. Only `_render_html` needs additional rows. No builder, model, renderer, translation, cache,
OCR, or document-domain change is required.

## 6. Is a diagnostics schema/version change unnecessary?

Yes. All four fields already exist on `ReportSummary` and are persisted in JSON. `TranslationReport`
`schema_version` stays `"1.0"`; no fields are added, renamed, or duplicated.

## 7. Smallest test fixture that proves the new rows are human-visible?

Build a `ReportSummary` with the four values, wrap it in a minimal `TranslationReport`, call
`write_report(report, tmp_path, report_format="html")`, read the HTML, and assert the exact
`<th>…</th><td>N</td>` fragments for the four label/value pairs. This proves the values are in the
summary table, distinct from the escaped JSON blob (which is still present). Same fixture pattern as
the existing footnote HTML assertions.

## 8. Does any failed-report path require special handling?

No. `build_failure_report` produces `ReportSummary` with the four fields defaulting to `0`, and
`_render_html` reads them unconditionally, so failed/interrupted reports render explicit zero rows
without extra branches. No rendering-side special case is introduced.

## 9. Which documentation needs updating?

- `README.md` "Translation diagnostics" section: note the inline-style rows in the HTML summary.
- `CHANGELOG.md` `[Unreleased]` → `Added`: new HTML summary rows.
- ProjectWiki: presentation-only change to existing evidence. Update only if durable knowledge
  changes; otherwise append a short `knowledge/wiki/log.md` note and leave pages unchanged.

## 10. Exact expected blast radius?

- `src/pdftranslate/diagnostics/reporting.py` (`_render_html` table rows only).
- `tests/test_diagnostics.py` (new focused HTML tests).
- `README.md`, `CHANGELOG.md`.
- Optional ProjectWiki log entry.

No change to: diagnostics models/schema, builder, rendering, translation, glossary, OCR, cache,
document schema, CLI contracts, or the embedded JSON.
