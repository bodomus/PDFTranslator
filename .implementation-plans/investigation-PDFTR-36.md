# PDFTR-36 Investigation

## Scope

Preserve source-owned list markers and source-derived list indentation when translated
paragraphs are rendered back into the PDF, without trusting translation-model output for the
structural marker.

## Answers to required investigation questions

1. **Where are logical paragraphs finalized before translation?**
   `src/pdftranslate/reconstruction/reconstructor.py` builds `LogicalParagraph` units from
   extracted page fragments. `_paragraph_from_fragments()` strips each fragment and joins text;
   `_kind()` already classifies source prefixes matching `_LIST_MARKER` as
   `ParagraphKind.LIST_ITEM`. Translation then runs in
   `src/pdftranslate/translation/paragraphs.py` and writes `translated_text` back onto the same
   `LogicalParagraph` model.

2. **Where is paragraph occurrence identity assigned?**
   Occurrence identity is the list index of each paragraph in `ExtractedDocument.paragraphs`.
   Rendering and typography consistently use that index (`occurrence_index`), while
   `paragraph_id` only validates the selected occurrence.

3. **Where are BODY / HEADING / FOOTNOTE indentation values reconstructed?**
   `src/pdftranslate/typography/extractor.py` derives first-line/left/right indent evidence from
   retained fragment geometry relative to a role region; `typography/reconstruction.py` resolves
   them into `ResolvedParagraphStyle`. `rendering/reflow/typography.py` converts resolved styles
   into `ReflowStyle`. The planner applies `left_indent` to every line and `first_line_indent`
   only to the first segment.

4. **Where does translated paragraph text enter production reflow?**
   `src/pdftranslate/rendering/reflow/regions.py` `discover_reflow_page()` selects BODY/HEADING
   occurrences and builds `FlowParagraph.text` from `paragraph.translated_text`. Body and footnote
   plans are planned in `rendering/reflow/planner.py` and inserted/validated in
   `rendering/reflow/pymupdf_layout.py`.

5. **Can source marker metadata be attached without changing public schemas?**
   Yes. Source `LogicalParagraph.text` is already retained immutably in schema 1.3 and validated
   against the source PDF. Marker detection can be derived deterministically at render time from
   that retained source text, so no schema 1.3 field, cache key, or resume artifact changes.

6. **Can the marker be removed before translation safely?**
   Not without broad changes to the translation pipeline (foreign-language, glossary, cache,
   resume, and work-deduplication paths all consume `paragraph.text`). The ticket's acceptable
   alternative is chosen: keep the current translation flow, then discard any translated marker
   representation and reconstruct the visible marker from source-owned structure at render time.

7. **If not, where can translated markers be discarded deterministically?**
   In a pure marker module consumed by both rendering paths:
   - reflow path: `discover_reflow_page()` builds `FlowParagraph.text` from the reconstructed
     marker + stripped translated content;
   - fixed-layout path: `renderer._paragraph_block()` rewrites `translated_text` the same way for
     list items that are not reflowed.
   The same deterministic function is used in both places. Stripping is source-evidenced: exact
   copies of the source marker are removed first, then leading translated marker prefixes are
   removed only when the retained source content does not itself begin with a marker-like prefix.
   The translated-prefix matcher accepts Cyrillic letter markers so a Latin `a)` translated to
   Cyrillic `а)` is stripped, while marker-deleted content such as `A. Smith` is preserved.

8. **How are hanging indents currently represented?**
   `ReflowStyle.left_indent` shifts every line right and `ReflowStyle.first_line_indent` shifts only
   the first line relative to that edge. The planner accepts a safe negative `first_line_indent`
   (`test_body_typography_allows_safe_hanging_indent`). The shared HTML/CSS builder currently emits
   only `text-indent`, so a negative first-line indent is clipped at the box edge by PyMuPDF. This
   must be fixed by emitting `margin-left` together with a negative `text-indent` and adjusting the
   measured/inserted box origin.

9. **Which measurement/insertion path should own marker width?**
   The existing shared `build_rich_text()` plus `PyMuPdfMeasurer.measure()` and
   `insert_reflow_segments()` path. List indentation is derived from retained source fragment
   geometry (marker edge and continuation-line edge), not from translated text or a second layout
   system.

10. **How do inline style runs interact with the first characters of a paragraph?**
    `map_inline_styles()` maps exact preserved source substrings into translated-text offsets.
    For list items the final text is reconstructed, so translated offsets can shift or the marker
    itself can be a styled source run. For PDFTR-36 the smallest safe integration is to defer
    inline-style mapping for reconstructed list items (empty `InlineStyleMapping`) and keep the
    resolved paragraph base style. Marker text and geometry are preserved first; marker-specific
    inline styling is documented as a limitation.

11. **Which existing saved-PDF validation can verify marker presence?**
    `validate_saved_segments()` already checks that each segment-local expected text is present in
    the saved PDF. Reconstructed list-item text is the segment text, so the source marker is
    verified as part of exact segment accounting. The clip must be extended left for hanging
    indents so the marker glyph falls inside the validation clip.

12. **What is the minimum coherent file set for this change?**
    - new `src/pdftranslate/rendering/list_markers.py` (pure detection/reconstruction);
    - `src/pdftranslate/rendering/reflow/typography.py` (`list_reflow_style`);
    - `src/pdftranslate/rendering/reflow/regions.py` (include confident list items in body flow);
    - `src/pdftranslate/rendering/reflow/pymupdf_layout.py` (hanging-indent HTML/CSS, clip, insert);
    - `src/pdftranslate/rendering/renderer.py` (fixed-layout reconstruction + diagnostics counters);
    - `src/pdftranslate/rendering/models.py`, `src/pdftranslate/diagnostics/models.py`,
      `src/pdftranslate/diagnostics/builder.py`, `src/pdftranslate/diagnostics/reporting.py`
      (diagnostic counters);
    - tests: new focused unit tests plus reflow/render regression tests;
    - docs: `CHANGELOG.md`, affected ProjectWiki page(s).

## Source-verified key facts

- `ParagraphKind.LIST_ITEM` already exists and reconstruction already marks list prefixes, but the
  reconstruction regex is broad and would classify `2026.` and `A.` names; PDFTR-36 needs a
  stricter render-time detector, not a broader one.
- `discover_reflow_page()` currently rejects any page where a list item intersects the body region,
  because list items are not in the selected set. Confident list items must join the selected set
  and the body flow.
- The planner already supports safe hanging indents, but the shared HTML/CSS builder clips negative
  `text-indent`. A negative indent needs `margin-left` plus a left-shifted box origin.
