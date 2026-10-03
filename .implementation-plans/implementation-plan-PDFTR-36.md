# PDFTR-36 Implementation Plan

## Goal

Source-owned list markers survive translation-model changes and render once, in source form, with
source-derived hanging indentation, for confidently classified list items.

## Approach

Keep the current translation flow unchanged. Derive marker metadata deterministically from retained
source paragraph text at render time, reconstruct the visible text from source marker + translated
semantic content, and route confident list items through the existing body reflow when the page is
already body-reflow-eligible. Otherwise preserve the marker in the existing fixed-layout path.

## Changes

1. `src/pdftranslate/rendering/list_markers.py`
   - `detect_list_marker(source_text) -> ListMarker | None` for bullets
     (`• ● ○ ▪ - – — *`) and numbered/letter forms (`N. N) (N) a. a) (a) A. A) (A)` with
     `N` limited to one or two digits).
   - Fail closed on `2026.`, `3.14`, `-5 °C`, `12.5`, and single-word uppercase-letter-period
     names such as `A. Smith`.
   - `reconstruct_list_item_text(source_text, translated_text) -> str | None` strips leading
     translated marker-like prefixes and returns `marker + separation + content`, or `None` when
     no content remains.

2. `src/pdftranslate/rendering/reflow/typography.py`
   - Add `list_reflow_style()` for OTHER-role resolved list items using the existing shared
     resolved-to-reflow mapping with `heading=False`.

3. `src/pdftranslate/rendering/reflow/regions.py`
   - Include confidently detected `LIST_ITEM` paragraphs in body-flow selection and flow building.
   - Reconstruct `FlowParagraph.text` from the source marker and stripped translated content.
   - Override `left_indent`/`first_line_indent` from retained source fragment geometry relative to
     the body flow region, producing a safe hanging indent where continuation geometry exists.
   - Fail closed (return `None`) when marker geometry is unsafe or content is empty.

4. `src/pdftranslate/rendering/reflow/pymupdf_layout.py`
   - Emit `margin-left` when `first_line_indent` is negative.
   - Shift the inserted HTML box origin left by the hang amount and widen the measured box
     accordingly so the marker is never clipped.
   - Extend saved-segment validation clip left for hanging indents.

5. `src/pdftranslate/rendering/renderer.py`
   - Reconstruct fixed-layout list-item `translated_text` in `_paragraph_block()`.
   - Add `list_marker_candidates` / `list_markers_applied` / `list_markers_deferred` counters to
     `RenderResult`.

6. Diagnostics
   - Add the same three counters to `ReportSummary` and the HTML report table.

7. Tests
   - Pure marker detection and reconstruction tests, including false-positive fail-closed cases.
   - Planner tests for list-item hanging indentation.
   - Render integration test proving exactly one source marker survives duplicate/removed/changed
     translated markers and that saved output contains the marker.
   - Regression tests for body/heading/footnote reflow and diagnostics counters.

8. Docs
   - `CHANGELOG.md` and the affected ProjectWiki reflow/typography pages.

## Validation

- `uv run pytest tests/test_list_markers.py tests/test_reflow_production.py tests/test_rendering.py`
- `uv run pytest`
- `uv run python scripts/project_wiki/wiki_lint.py`
- `.\scripts\check.ps1`
