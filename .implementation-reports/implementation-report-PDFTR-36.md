# PDFTR-36 implementation report

## Outcome

Source-owned list markers now survive translation-model changes and render once, in source form,
with source-derived hanging indentation for confidently classified list items. The translation flow
is unchanged; marker metadata is derived deterministically from retained source paragraph text at
render time and reconstructed as `source marker + translated semantic content`. Confident list items
join the existing body reflow when a page is already body-reflow-eligible; otherwise the fixed-layout
path uses the same marker reconstruction.

## Workflow

- Level: 2, cross-cutting production reflow change.
- Branch: `pdftr-36-list-marker-fidelity`.
- Working tree before changes: clean.
- Graphify: existing architecture documentation and source were used; no new graph was required.
- code-review-graph: not rebuilt for this ticket; material conclusions were source-verified.

## Changes

- `src/pdftranslate/rendering/list_markers.py` (new): conservative marker detection and
  deterministic marker/content reconstruction.
- `src/pdftranslate/rendering/reflow/typography.py`: added `list_reflow_style()` for OTHER-role
  resolved list items.
- `src/pdftranslate/rendering/reflow/regions.py`: included confident list items in body flow,
  reconstructed their visible text, and derived hanging indentation from retained fragment geometry
  or measured marker width.
- `src/pdftranslate/rendering/reflow/pymupdf_layout.py`: fixed hanging-indent HTML/CSS by emitting
  `margin-left` for negative first-line indents, shifting the inserted box origin, widening the
  measurement box, and extending saved-segment validation clips left.
- `src/pdftranslate/rendering/renderer.py`: reconstructed fixed-layout list-item text and added
  list-marker diagnostics counters.
- `src/pdftranslate/rendering/models.py`, `src/pdftranslate/diagnostics/models.py`,
  `src/pdftranslate/diagnostics/builder.py`, `src/pdftranslate/diagnostics/reporting.py`: added
  `list_marker_candidates`, `list_markers_applied`, and `list_markers_deferred` counters to render
  and diagnostic summaries.
- Tests: `tests/test_list_markers.py` (new) plus reflow/render integration tests in
  `tests/test_reflow_production.py`.
- Docs: `CHANGELOG.md`, `knowledge/wiki/architecture/reflow-layout.md`, `knowledge/wiki/log.md`.

## Validation

- Focused tests:
  `uv run pytest tests/test_list_markers.py tests/test_reflow_production.py tests/test_rendering.py tests/test_diagnostics.py tests/test_translation.py --no-cov`
  passed.
- Full tests: `uv run pytest` passed (493 passed, 3 skipped, coverage 88.97%).
- `uv run python scripts/project_wiki/wiki_lint.py` passed (15 pages, 0 errors).
- `.\scripts\check.ps1` passed.
- Ruff format check, ruff check, and mypy strict all pass.

## Remaining risks

- List items are flowable only when the page is already body-reflow-eligible (at least two stable
  BODY paragraphs). Single list items or list-only pages use fixed-layout marker reconstruction
  without hanging indentation.
- Inline style runs inside reconstructed list items are deferred; the resolved paragraph base style
  is used for the marker and content.
- Upper-case letter-period markers (`A.`) require at least two content words to be applied; this
  fails closed for single-word names such as `A. Smith`.
