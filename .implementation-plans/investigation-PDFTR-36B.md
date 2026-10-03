# Investigation — PDFTR-36B Structural list-marker separation

## Summary

PDFTR-36/36A recovered list structure *after* translation (translated-prefix stripping) and laid
out the marker with an HTML-table workaround. Both are structurally wrong. PDFTR-36B separates the
source marker from the translatable content *before* the provider, and represents the marker as a
separate source-backed run in the shared reflow path.

## Answers

### 1. Where is the earliest reliable point at which a supported list marker is known?

`detect_list_marker(source_text)` in `src/pdftranslate/list_markers.py` operates on the retained
source paragraph text. It is already available at reconstruction time, but the earliest point that
*must* act on it is translation preparation: `translate_paragraphs` in
`src/pdftranslate/translation/paragraphs.py`, which iterates `document.paragraphs` (schema 1.2)
and fills each `LogicalParagraph.translated_text`.

### 2. Where is the semantic paragraph text constructed for translation?

In `translate_paragraphs`, the whole `paragraph.text` flows into `normalize_source_text`,
`prepare_glossary_text`, `prepare_foreign_language_text`, then `protect_text`/`segment_text` (via
`foreign_language.translatable_parts()`), whose segment texts are sent to
`translator.translate_batch`.

### 3. Can source marker metadata be attached there without changing public schemas?

The marker is deterministic from `paragraph.text`, so it can be re-derived at render time via
`detect_list_marker(paragraph.text)`. No new schema field is required; the only content change is
that `translated_text` becomes semantic-only for list items. This is a content change, not a schema
bump (`schema_version` stays `1.3`).

### 4. What object currently crosses extraction → translation → reflow?

`LogicalParagraph` (`src/pdftranslate/reconstruction/models.py`): `text` (source), `translated_text`
(filled by translation), `kind`, `fragments`, `spans`, `bbox`. The renderer re-derives list
structure from `paragraph.text`.

### 5. Where can semantic-only provider input be produced?

In `translate_paragraphs`, compute a per-paragraph `translation_source`:

- if `detect_list_marker(paragraph.text)` returns a marker and `paragraph.kind` is in
  `{BODY, HEADING, LIST_ITEM}`, `translation_source = marker.content_text`;
- otherwise `translation_source = paragraph.text`.

Use `translation_source` for every pass-through/translate decision (policy, `should_skip_translation`,
`normalize_source_text`, glossary/foreign-language preparation, and the eventual segments).

### 6. How will translated semantics be re-associated with the original paragraph occurrence?

`translated_text` stays on the same `LogicalParagraph` (same `id`, same index). Rendering re-derives
`detect_list_marker(paragraph.text)` and reattaches the source marker to `translated_text` through
the shared hanging-indent geometry (`left_indent` / `first_line_indent`).

### 7. Which existing tests mock/capture provider input?

`tests/test_translation.py` uses a fake `Translator` whose `translate_batch` records every input
batch. Provider-input assertions already exist for protected tokens/segments; new tests assert
semantic-only inputs for list items without a real provider.

### 8. Which code currently depends on `_strip_translated_markers`?

Only `reconstruct_list_item_text` in `list_markers.py`, which is called from
`regions.py::discover_reflow_page`, `renderer.py::_paragraph_block`, and
`renderer.py::_list_marker_counters`.

### 9. Can `_strip_translated_markers` be removed for supported list items?

Yes. Once `translated_text` is semantic-only, there is no translated marker to strip.
`_strip_translated_markers`, `_translated_marker_prefix`, and `reconstruct_list_item_text` can be
removed; a small `reattach_list_marker` helper remains for the fixed-layout path.

### 10. Where is first-line available width measured?

`_paragraph_geometry` in `reflow/planner.py` computes `usable_x0 = region.x0 + left_indent`,
`usable_width = usable_x1 - usable_x0`. With `left_indent = content_x - region.x0`, the semantic
content is measured with width `content_x .. right_edge` on every line, so the first line is
correctly narrowed by the marker gap.

### 11. Where are first-line segments inserted?

`insert_reflow_segments` in `reflow/pymupdf_layout.py` inserts each `PlacementSegment` via
`insert_htmlbox`. The first segment of a list item must additionally insert the marker at
`target_rect.x0 - list_marker_offset` on the same line.

### 12. Where are continuation lines measured/inserted?

The same `plan_flow`/`insert_reflow_segments` path. Continuation segments carry
`continuation_index > 0` and `list_marker=""`, so only the content is measured/inserted at
`content_x`.

### 13. What existing shared representation can encode marker and semantic runs without a table?

The source marker is reattached to the semantic-only translated text and embedded at the start of
the paragraph text. The existing hanging-indent representation (`left_indent = content_x - region.x0`
and `first_line_indent = marker_x - content_x`) places the marker at the source marker edge while
anchoring continuation lines at the source content edge. Measurement and insertion both use this
single representation, so there is no table, inline-block, or whitespace padding.

### 14. How does saved-PDF validation identify list logical text today?

`validate_saved_segments` normalizes `segment.text` and checks it appears in the clipped page text.
The marker and content remain in one text block, so extraction order is preserved and the
marker-plus-content text validates against the rendered block.

### 15. What exact files must change?

- `src/pdftranslate/list_markers.py` — new leaf module (moved from `rendering/list_markers.py`) with
  `detect_list_marker` and `reattach_list_marker` only; the stripping heuristics are removed.
- `src/pdftranslate/translation/paragraphs.py` — semantic-only provider input; policy/pass-through
  use `translation_source`.
- `src/pdftranslate/translation/cache.py` — bump `TRANSLATION_BEHAVIOR_REVISION` (5 → 6).
- `src/pdftranslate/rendering/reflow/regions.py` — use semantic-only list text, reattach the marker,
  and keep the source-backed hanging indent.
- `src/pdftranslate/rendering/reflow/pymupdf_layout.py` — remove the table branch and the separate
  marker insert.
- `src/pdftranslate/rendering/reflow/models.py` / `planner.py` — remove the `list_marker` /
  `list_marker_offset` carrier fields.
- `src/pdftranslate/rendering/renderer.py` — `_paragraph_block` reattaches the marker; counters via
  `detect_list_marker`.
- focused tests; `CHANGELOG.md`.

### 16. What code from PDFTR-36A must be removed rather than patched?

- The HTML-table marker block in `pymupdf_layout.py::build_rich_text`.
- The separate marker `insert_htmlbox` run and its `list_marker` / `list_marker_offset` fields.
- The family-aware `_strip_translated_markers` / `_translated_marker_prefix` heuristics in
  `list_markers.py`.
