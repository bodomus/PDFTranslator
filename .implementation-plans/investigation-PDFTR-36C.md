# Investigation — PDFTR-36C Final list geometry and artifact compatibility

## Answers

### 1. Where is first-line list content width measured today?

`_paragraph_geometry` in `reflow/planner.py` computes `usable_x0 = region.x0 + left_indent` and
`usable_width = usable_x1 - usable_x0`. For a list item today the marker is embedded in the text and
`first_line_indent = marker_x - content_x` (negative), so `PyMuPdfMeasurer.measure` widens the first
segment box to `right_edge - marker_x`; the first semantic word starts after the rendered marker
advance, not at `content_x`.

### 2. Where is first-line list content inserted today?

`insert_reflow_segments` in `reflow/pymupdf_layout.py` builds `<p>marker + content</p>` via
`build_rich_text` and inserts it at the segment rect (shifted left by the negative
`first_line_indent`).

### 3. Why does hanging indent preserve continuation `content_x` but not first-line `content_x`?

`left_indent = content_x - region.x0` anchors every continuation line at `content_x`. The marker is
embedded at the start of the text, so the first semantic word sits at `marker_x + rendered marker
advance`, which equals `content_x` only when the renderer font advance happens to match the source
gap.

### 4. What shared representation can encode independent `marker_x` and `content_x` without tables?

The marker must be a separate run carried on `FlowParagraph`/`PlacementSegment`
(`list_marker` text + `list_marker_offset = content_x - marker_x`). The semantic content becomes the
paragraph `text` with `left_indent = content_x - region.x0` and `first_line_indent = 0`, so the
planner measures the true first-line width `right_edge - content_x`.

### 5. How will planner and insertion consume the same geometry?

Both read the same fields: planner measures `text` with `left_indent`/`first_line_indent=0`; insertion
renders the marker at `target_rect.x0 - list_marker_offset` and the content at `target_rect.x0`
(same `content_x`). No table, no whitespace padding.

### 6. How does saved-PDF validation observe the resulting X positions?

`validate_saved_segments` normalizes `segment.text` (semantic-only) and checks it appears in the
clipped page text. The content is at `content_x`; the marker is a separate insert outside the content
text, so no "2)Install" collapse can occur.

### 7. Which wide-gap test was removed/replaced in PDFTR-36B?

`test_renderer_anchors_first_line_content_to_source_edge` was replaced with a single-fragment
fixture; the true two-fragment wide-gap (`marker_x << content_x`) case was reduced to a
discover-level style assertion.

### 8. How will the real wide-gap regression be restored?

Build a source PDF with the marker and content as separate text objects (marker at ~48pt, content at
~130pt), then render through the full pipeline and assert word X positions: marker ≈ 48, first-line
semantic ≈ 130, continuation ≈ 130, no clipping, saved-PDF validation passes. The source document is
constructed with an explicit two-fragment `LogicalParagraph` so `_source_content_x` returns the
source `content_x` (130), not the renderer-font fallback.

### 9. Where is `TRANSLATION_BEHAVIOR_REVISION` persisted in translated artifacts?

`TranslationMetadata.behavior_revision` (`domain/document.py`), written by `translate_paragraphs`
(schema 1.3) and `translate_document` (schema 1.1). The cache key also embeds the revision.

### 10. Where does the renderer validate artifact/schema compatibility?

`_validate_document` in `renderer.py` is the first render-time validation (schema, status,
identity). It is the correct place to add the revision gate.

### 11. Smallest place to reject incompatible revision-5 list artifacts?

In `_validate_document`, before any reattachment: if `schema_version == "1.3"` and
`metadata.behavior_revision < TRANSLATION_BEHAVIOR_REVISION` and the document contains a supported
list item, raise `RenderingInputError`.

### 12. Can non-list revision-5 artifacts remain renderable safely?

Yes. The gate is list-conditional, so non-list revision-5 artifacts keep existing compatibility
behavior.

### 13. Exact production files to change?

- `src/pdftranslate/rendering/reflow/models.py` — add `list_marker`/`list_marker_offset` to
  `ReflowStyle` and `PlacementSegment`.
- `src/pdftranslate/rendering/reflow/planner.py` — propagate the marker fields to the first segment.
- `src/pdftranslate/rendering/reflow/regions.py` — semantic-only `text`, `first_line_indent=0`,
  set `list_marker`/`list_marker_offset`.
- `src/pdftranslate/rendering/reflow/pymupdf_layout.py` — render the marker as a separate run.
- `src/pdftranslate/rendering/renderer.py` — G2 revision gate.

### 14. Existing PDFTR-36B code that must remain untouched?

`src/pdftranslate/list_markers.py` (marker parsing, `detect_list_marker`, `reattach_list_marker`),
`translation/paragraphs.py` semantic-only provider input, R4 ambiguity logic, and
`TRANSLATION_BEHAVIOR_REVISION = 6`.
