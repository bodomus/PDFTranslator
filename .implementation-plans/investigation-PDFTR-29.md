# PDFTR-29 investigation

## Scope and sources

The investigation followed `.codex/PRE_TICKET_WORKFLOW.md`, ProjectWiki, Graphify, and
code-review-graph. Implementation claims below were verified against the production renderer,
reflow models/planner/region discovery/PyMuPDF adapter, typography evidence and reconstruction
contracts, diagnostics, and the existing production reflow tests.

## Required architecture answers

1. **Where should typography reconstruction be invoked?**
   In `PdfRenderer.render()`, after input validation and font selection but before document-level
   reflow planning. The resulting occurrence-index map is passed into body discovery; the planner
   remains dependent only on its renderer-facing style contract.
2. **Once per document or once per page?**
   Once per translated `ExtractedDocument`. Evidence extraction and style reconstruction are both
   document operations and must not be repeated in the page loop.
3. **How does occurrence index map to `FlowParagraph`?**
   Build `{style.occurrence_index: style}` and look up the enumerated paragraph occurrence used by
   body discovery. Validate that the returned style has the same occurrence index and paragraph id.
   Paragraph id alone is never used as the key because ids are not guaranteed unique.
4. **Which properties can the PyMuPDF rendering layer apply?**
   Font size, line-height ratio, RGB color, physical alignment, first-line indent, and left/right
   indents can be expressed by the HTML/CSS textbox path. Paragraph spacing is represented in the
   planner rather than in the textbox. The selected Cyrillic-capable font remains authoritative.
5. **Which properties require planner changes?**
   Left/right indents change usable width. First-line indent changes only the first segment.
   Space-before is consumed once before the first segment; space-after is consumed once after the
   final segment. These values therefore affect fitting, segment bounds, continuation count, and
   pagination. Measurement must receive the same effective style used by insertion.
6. **Which properties remain deferred?**
   Exact source font identity and safe bold/italic variant selection. The source identity remains in
   typography evidence. BODY diagnostics record requested bold/italic and `applied=false`; no
   synthetic stroke or unsafe font substitution is performed. Mixed inline runs remain represented
   by the paragraph-dominant style plus an explicit diagnostic flag.
7. **How does style application affect pagination?**
   Resolved font size, line height, indents, and spacing all alter capacity. Planning therefore uses
   those values before any PDF mutation. First-line indent and space-before are disabled on
   continuation segments, while left/right indents remain active. Space-after is added only when the
   paragraph completes. The existing continuation-page allocator consumes the resulting plan.
8. **How do completeness guarantees remain authoritative?**
   The planner keeps contiguous source offsets and exact text reconstruction checks. Capacity
   exhaustion remains a hard error. Rendering still happens only after a complete pre-mutation
   document plan exists. Saved-PDF segment-local validation, `unplaced_text_count == 0`, block
   completeness checks, reopen validation, and atomic replacement remain mandatory.

## Boundary and risk notes

- The new adapter is BODY-only and translates `ResolvedParagraphStyle` into the compact reflow
  contract. Heading and footnote discovery do not consume the style map.
- Alignment is physical (left/right), not locale-relative.
- Measurement and insertion must share one HTML/CSS construction helper to avoid a split-brain
  layout model.
- Unsupported or missing BODY style mappings fail closed before source mutation.
- No cache or serialized document schema changes are required because reconstructed styles are
  derived during rendering.
