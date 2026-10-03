# PDFTR-36 implementation report

## Outcome

Source-owned list markers now survive translation-model changes and render once, in source form,
with source-derived hanging indentation. Marker detection is derived from retained source paragraph
text for BODY, HEADING, and LIST_ITEM paragraphs, so every supported marker family reaches
production even when reconstruction did not label the paragraph `LIST_ITEM`. List-only pages and
isolated list items reflow through the existing measurement/insertion infrastructure, not only pages
that already had at least two stable BODY paragraphs. Marker/content separation is source-evidenced:
translated marker representations (including Cyrillic letter markers) are stripped deterministically
without deleting legitimate semantic content such as `A. Smith`.

## Workflow

- Level: 2, cross-cutting production reflow change.
- Branch: `pdftr-36-list-marker-fidelity`.
- Working tree before changes: clean.
- Graphify: existing architecture documentation and source were used; no new graph was required.
- code-review-graph: not rebuilt for this ticket; material conclusions were source-verified.

## Attempt-2 reviewer findings addressed

- R1 (`discover_reflow_page`): marker detection no longer keys on `ParagraphKind.LIST_ITEM`.
  `detect_list_marker()` runs against retained source text for BODY, HEADING, and LIST_ITEM
  paragraphs, so `●`, `○`, `–`, `—`, `(a)`, and `(A)` prefixes reach reflow reconstruction and the
  fixed-layout `_paragraph_block()` reconstruction. Kind-appropriate reflow style adapters preserve
  BODY/HEADING/OTHER typography.
- R2 (`discover_reflow_page`): list-only pages and isolated items now reflow. A new
  `_stable_list_column()` accepts list columns whose items are intentionally narrower than the body
  width guard, while retaining edge-stability, margin, policy, region, intersection, and PDF-object
  safety checks. BODY pages still require at least two stable BODY paragraphs as before.
- R3 (`_strip_translated_markers`): stripping is source-evidenced. Exact source-marker copies are
  removed first; then, only when the retained source content does not itself begin with a marker-like
  prefix, leading translated marker prefixes (extended to Cyrillic letters) are removed. This strips
  a Cyrillic `а)` translation of `a)` while preserving marker-deleted `A. Smith` content.

## Changes

- `src/pdftranslate/rendering/list_markers.py`: source-evidenced translated-marker stripping with
  Cyrillic letter support; exact source-marker stripping separated from translated-prefix stripping.
- `src/pdftranslate/rendering/reflow/regions.py`: detect markers from retained source text for BODY,
  HEADING, and LIST_ITEM; kind-aware list flow styles; list-only and isolated-item reflow via
  `_stable_list_column()`; body pages keep the two-BODY minimum.
- `src/pdftranslate/rendering/renderer.py`: fixed-layout marker reconstruction and diagnostics
  counters now cover BODY, HEADING, and LIST_ITEM paragraphs.
- Tests: extended `tests/test_list_markers.py` and `tests/test_reflow_production.py` with
  Cyrillic/restyled marker stripping, `A. Smith` content preservation, all marker families through a
  real rendered PDF, list-only-page hanging indentation, isolated-item hanging indentation, and a
  margin-positioned fixed-layout marker check.
- Docs: `knowledge/wiki/architecture/reflow-layout.md` updated for list-only/isolation reflow and
  source-evidenced separation.

## Validation

- Focused tests: `uv run pytest tests/test_list_markers.py tests/test_reflow_production.py -o addopts=""`
  passed (72 tests).
- Full tests: `uv run pytest` passed (499 passed, 3 skipped, coverage 88.94%).
- `uv run python scripts/project_wiki/wiki_lint.py` passed (15 pages, 0 errors, 0 warnings).
- Ruff format check, ruff check, and mypy strict all pass.

## Remaining risks / limitations

- A BODY page with exactly one stable BODY paragraph and no confident list items is still not
  reflowed (unchanged behavior).
- Inline style runs inside reconstructed list items are deferred; the resolved paragraph base style
  is used for the marker and content.
- Upper-case letter-period markers (`A.`) require at least two content words to be applied; this
  fails closed for single-word names such as `A. Smith`.
- A page whose only content is a HEADING-classified marker paragraph falls back to fixed layout
  (marker preserved, no hanging indent); mixed BODY/LIST_ITEM list columns provide the reflow
  stability evidence.
