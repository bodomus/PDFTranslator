# Investigation — PDFTR-36D Final marker-run safety closure

## Answers

### 1. Which exact code path measures marker width today?

None. `_list_item_style` (`reflow/regions.py`) derives `content_x` and `list_marker_offset` from
source geometry, but never measures the marker glyph width. The first place marker fit is observed
is `_insert_list_marker` (`reflow/pymupdf_layout.py`), which raises `OutputPdfError` when the
`insert_htmlbox` of the marker returns `remaining < 0`.

### 2. Which style/font data does `_insert_list_marker` use?

`font_path` (the selected renderer font), `segment.font_size`, `segment.line_height`, and
`segment.alignment` (inherited from the semantic paragraph), via `build_rich_text`.

### 3. Where can marker fit be checked before insertion?

In `_list_item_style`, using `pymupdf.Font(fontfile=str(font_path)).text_length(marker_text,
fontsize=font_size)` — the same font and size insertion will use — and fail closed (return `None`)
when the measured width exceeds `content_x - marker_x` (`list_marker_offset`).

### 4. Why does current saved validation only observe semantic text?

`validate_saved_segments` checks `segment.text` (semantic-only) against the content clip. The
marker is a separate run outside that clip, so it is never verified.

### 5. What occurrence identity is available for saved marker evidence?

`PlacementSegment.occurrence_index`, `continuation_index`, `list_marker`, and `list_marker_offset`.
Only the first segment (`continuation_index == 0`) carries a marker; the marker region is
`[target_rect.x0 - list_marker_offset, target_rect.x0]`.

### 6. How can validation detect marker absence without relying on translated semantic text?

Extract text only in the marker region (a geometry-bounded clip left of `content_x`) and require the
normalized marker text to be present. This does not touch the semantic content.

### 7. How can continuation-page duplication be detected?

A continuation segment (`continuation_index > 0`) has `list_marker == ""`, so it inserts no marker.
The marker region belongs to the first segment's page; the same geometry check on the first segment
plus requiring the marker region to contain the marker exactly once catches a duplicated marker on
the first line. Repetition across pages is excluded because only the first segment emits a marker.

### 8. Why does marker insertion inherit CENTER / RIGHT alignment?

`_insert_list_marker` builds `marker_style` with `alignment=segment.alignment`, so `build_rich_text`
emits `text-align: center|right` for the marker `<p>`.

### 9. Smallest change to make marker placement always left-anchored to source `marker_x`?

Pass `alignment=ReflowAlignment.LEFT` to `_insert_list_marker`'s marker style, so the marker run is
always left-anchored at its insertion rect regardless of semantic paragraph alignment.

### 10. Which production files must change?

- `src/pdftranslate/rendering/reflow/regions.py` — M1 marker-fit check in `_list_item_style`.
- `src/pdftranslate/rendering/reflow/pymupdf_layout.py` — M2 marker validation in
  `validate_saved_segments`; M3 left-anchored marker style in `_insert_list_marker`.

### 11. Which validated PDFTR-36B/36C code must remain untouched?

`src/pdftranslate/list_markers.py`, `translation/paragraphs.py`, R4 ambiguity logic, the renderer
revision gate, `TRANSLATION_BEHAVIOR_REVISION`, and the wide-gap geometry already in place.
