# Body-text reflow architecture

## Status

PDFTR-22 proves an isolated architecture for single-column body prose. It does not replace or
weaken the production fixed-layout renderer. The executable proof of concept is under
`scripts/reflow_poc/`; production integration belongs to PDFTR-23.

## Problem and verified boundary

The production renderer maps each schema 1.3 logical paragraph back to its anchor-page source
rectangle, reduces the font size, and optionally expands downward without crossing another source
block. PDFTR-20 correctly made unresolved overflow fatal before PDF mutation or publication, but
the planner cannot move excess text into a later region or page.

The current completed Robitzsch artifact contains 61 required paragraph occurrences. A source-
verified replay produced 40 rendered and 21 overflow states. The important PDFTR-22 correction is
that all 21 current overflows are `footnote` occurrences; all 26 `body` occurrences fit under the
current shrink-to-fit policy. Body reflow therefore does not, by itself, make that exact document
publishable. The PoC proves the missing body-flow mechanism on page 3 while retaining footnotes as
anchored/deferred content.

## Goals and non-goals

The architecture plans body prose sequentially through explicit rectangular regions, preserves
logical-paragraph occurrence identity across continuations, accounts for every translated character
before PDF mutation, keeps text selectable, preserves anchored source content by policy, emits
typed evidence, and fails closed for unsafe layouts or insufficient capacity.

The first implementation does not solve arbitrary columns, tables, sidebars, floating figures,
mathematical layout, verse, bibliography layout, automatic font matching, full typography,
complete footnote pagination, OCR, translation, GUI, or cloud layout services.

## Terminology and units

- A **logical paragraph occurrence** is the flow unit. Occurrence index, not paragraph ID alone,
  is authoritative because reconstructed split blocks can repeat an ID.
- A **flow region** is an explicitly classified rectangle on one target page, with column and
  document order.
- A **continuation segment** is the placement unit. It carries paragraph identity, exact character
  offsets, target page/rectangle, continuation index, font size, measured height, line count, and a
  `continued` or `complete` state.
- An **anchor** is non-flow content retained or separately handled at a stable page location.

The paragraph remains the semantic identity; line wrapping is a measurement result; continuation
segments are the physical placements.

## Content classification

| Category | PoC | PDFTR-23 |
| --- | --- | --- |
| Body prose | flowable | flowable |
| Section/chapter headings | anchored | flowable with one basic heading style |
| Block quotations | deferred | unsupported unless explicitly classified |
| Verse/poetry | unsupported | fail closed |
| Footnotes | anchored/deferred | fail closed; dedicated pagination follows later |
| Running headers | anchored/preserved | preserve or regenerate by explicit policy |
| Page numbers | anchored/preserved | preserve or regenerate by explicit policy |
| Watermarks | anchored/preserved | preserve |
| Captions | anchored | preserve with associated figure |
| Tables | unsupported | fail closed |
| Figures/images | anchored | preserve and exclude occupied geometry from flow regions |
| Unknown/ambiguous | unsupported by default | fail closed |

An explicit reviewed PoC selection can override reconstruction ambiguity for named occurrences. It
cannot override paragraph kind, repeated-element translation policy, source-page identity, region
containment, or image/drawing intersection checks.

## Robitzsch page evidence

Pages 1, 3, and 4 are each 432 x 648 points. PyMuPDF reported no image objects or vector drawings
on these pages. This supports the reviewed rectangles below but is not a general whitespace-based
region detector.

| Page | Ordered occurrences | Reviewed body rectangle | Anchored/deferred | Fixed result |
| ---: | ---: | --- | --- | --- |
| 1 | 22 | `(67.35, 54.50, 378.28, 405.46)` | running title, page number, footnotes | 12 rendered, 10 footnote overflow |
| 3 | 13 | `(67.35, 53.78, 378.32, 463.23)` | running title, page number, footnotes | 8 rendered, 5 footnote overflow |
| 4 | 12 | `(53.80, 53.78, 364.67, 475.70)` | section running title, page number, footnotes | 10 rendered, 2 footnote overflow |

On all three pages the running title/page number is currently classified as `body` because the
four-page selection provides insufficient repeated-element evidence. Region discovery therefore
must combine explicit content classification, stable source geometry, anchor policies, and object
intersection checks. Whitespace or `ParagraphKind.BODY` alone is unsafe.

## Typed model

The PoC models establish the intended boundary:

```text
FlowParagraph
  occurrence index and paragraph ID
  source page, kind, disposition, and exact translated text
  source rectangle and fragment rectangles

FlowRegion
  target page, rectangle, column index, order, and created-page flag

PlacementSegment
  paragraph occurrence and ID
  source and target pages and target rectangle
  continuation index, font size, measured height, and line count
  exact [text_start:text_end], segment text, and continuation state
```

`LayoutPlan` owns ordered regions, paragraphs, segments, and aggregate counts. Warning strings are
diagnostic presentation only; they are never authoritative placement state.

## Planning algorithm

1. Validate one controlled source page, ordered unique occurrences, body-only disposition,
   translation policy, explicit ambiguity overrides, region containment, and single-column regions.
2. Measure the remaining paragraph text in the current region without committing a PDF shape.
3. If it fits, create a completing segment and advance by measured height plus paragraph spacing.
4. If it does not fit, binary-search word boundaries for the largest fitting prefix. A single token
   can fall back to character boundaries so no token can disappear silently.
5. Record exact offsets and move the remainder to the next ordered region/page.
6. Reconstruct every paragraph from its segments and require exact Python-string equality.
7. Raise a capacity error instead of returning a partial plan when regions are exhausted.

The PyMuPDF adapter reserves one line of baseline safety beyond reported used height. PNG review
found that this is necessary: extraction succeeded with a smaller reserve while the final line of
one continuation visually collided with the next paragraph.

## Page strategy

Existing pages best preserve pagination and anchors but cannot guarantee translated capacity. New
pages only simplify layout but discard source-page relationships. PDFTR-23 should therefore use a
**hybrid** strategy: consume explicitly classified body regions on existing pages in document order,
then insert pages only when safe source capacity is exhausted. Inserted pages inherit page geometry
and a defined body region/style. Headers and page numbers may be regenerated only under a separate
explicit policy. A page that cannot be classified does not receive flow content.

The PoC uses this rule in a controlled form: it copies source page 3, preserves its running title,
page number, and footnotes, redacts only selected body fragments, fills the reviewed body region,
and appends one blank continuation page with the same geometry.

## Source-content preservation

- Source body text is redacted only through retained schema 1.3 fragment rectangles.
- Anchored text is left untouched in the PoC.
- Images and vector drawings are preserved; a candidate region intersecting either fails before
  planning.
- The PoC does not rasterize or flatten pages. Inserted text remains selectable.
- The controlled source page has a white body background. Production must sample/preserve
  backgrounds or reject unsafe regions rather than assume white.
- The source PDF is immutable. PoC PDF, debug PDF, and JSON plan use separate destinations and
  temporary sibling writes.

## Typography boundary

The PoC uses one body font, one size, one line-height multiplier, and paragraph spacing. The models
leave room for a style ID and future family, size, bold/italic, first-line indent, alignment,
heading/quotation/footnote styles, and widow/orphan rules. PDFTR-23 should add only body and basic
heading styles; full fidelity remains deferred.

## Diagnostics and validation

The JSON plan records source occurrence to ordered target continuation segments. Required metrics
are input paragraph/character counts, planned paragraph/continuation counts, output paragraph and
extracted-character counts, unplaced characters, and new pages.

Validation has three levels:

1. Pre-mutation exact accounting: concatenated segment text and offsets must equal each input
   paragraph exactly once.
2. Post-save validation: reopen the PDF, validate page count, extract each segment from a padded
   clip around its exact target rectangle, and require its normalized text in that local clip.
   Region-wide extraction remains diagnostic and contributes aggregate metrics, but is not success
   evidence.
3. Visual validation: render normal and debug PDFs to images and inspect boundaries, ordering,
   clipping, collisions, anchors, and page transitions.

For production split paragraphs, validation should retain exact pre-save offsets plus post-save
segment-local evidence. Region/page-wide substrings are not success evidence because they cannot
distinguish identical segment text placed at different target rectangles.

## PoC result

Controlled input: Robitzsch page 3, occurrence indexes 38–41, reviewed region
`(67.35, 53.78, 378.32, 463.23)`, 12 pt body style.

| Metric | Result |
| --- | ---: |
| Input logical paragraphs | 4 |
| Input translated characters | 2,153 |
| Planned paragraphs | 4 |
| Planned continuation count | 1 |
| Output paragraphs | 4 |
| Output extracted characters in body regions | 2,157 |
| Unplaced translated characters | 0 |
| New pages created | 1 |

The four selected paragraphs remained ordered and selectable. Occurrence 40 continued from copied
page 3 onto one added page; occurrence 41 followed it without overlap after the baseline-safety
correction. Running title, page number, and source footnotes remained on the copied page. The normal
and debug PDFs were visually inspected from Poppler PNG renders.

The output extracted count is a region-extraction diagnostic, not an equality target: PDF text
normalization and punctuation presentation can change character count. Exact no-loss authority is
the pre-save character-range reconstruction plus per-segment post-save presence.

## Failure behavior

The PoC fails before publication for missing schema 1.3 translation, source identity mismatch,
invalid or unordered occurrence selection, unreviewed ambiguity, non-body content, non-translate
policy, region escape, intersecting unselected text/images/drawings, multiple columns, insufficient
capacity, changed measurement at insertion, unreadable output, missing selectable segment text, or
destination conflicts.

## Required decisions

1. **Unit of flow:** logical paragraph occurrence; continuation segment is the placement unit.
2. **Body-region identification:** explicit classification plus source geometry, anchor policy, and
   object-intersection checks; never whitespace alone.
3. **Headings:** distinguish by reconstruction/style evidence; anchor them in the PoC and support a
   basic explicit heading style in PDFTR-23.
4. **Footnotes:** preserve/anchor and fail closed in PDFTR-23; do not inject them into body flow.
5. **Images/drawings:** keep them anchored and subtract/reject intersecting regions.
6. **Cross-page flow:** yes, only through ordered, safely classified regions.
7. **New pages:** create them after safe existing regions are exhausted and only under bounded,
   explicit single-column rules.
8. **Paragraph identity:** occurrence index + paragraph ID + exact segment character offsets.
9. **Post-save split validation:** validate every segment in a padded clip around its exact target
   rectangle and reconstruct the paragraph from ordered offsets. Region/page extraction is
   diagnostic only.
10. **Diagnostics mapping:** `LayoutPlan.paragraphs` and `segments` provide the direct source-to-
    target relation; metrics summarize completeness.
11. **Unsupported in PDFTR-23:** unsafe/unknown pages, arbitrary multi-column layouts, tables,
    sidebars, floating figures, verse, complex math, and footnote pagination.
12. **Unclassifiable page:** fail closed without redaction, insertion, or final publication.

## Proposed PDFTR-23 scope

Implement production body-text reflow for confidently classified single-column book pages:

- body prose and one basic heading style;
- ordered existing-page regions with bounded inserted-page continuation;
- explicit anchor preservation for headers, page numbers, figures, drawings, and backgrounds;
- paragraph occurrence/segment diagnostics and strict zero-unplaced completeness;
- selectable/searchable output and split-segment saved-PDF validation;
- deterministic fake-backed tests plus controlled real-PDF validation.

Footnote pagination remains outside PDFTR-23 and must continue to fail closed. Consequently,
PDFTR-23 body reflow alone is not expected to make the current four-page Robitzsch artifact pass;
a separate footnote-layout scope is required.
