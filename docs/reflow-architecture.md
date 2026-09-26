# Body and footnote reflow architecture

## Status

PDFTR-23 promotes the PDFTR-22 proof into a production boundary under
`src/pdftranslate/rendering/reflow/`. The normal renderer automatically selects reflow only for
confidently classified single-column body prose and headings. The fixed-layout
renderer remains authoritative for other content, and the isolated executable PoC remains under
`scripts/reflow_poc/` as historical evidence rather than a production dependency.

PDFTR-24 extends that boundary to conservatively discovered, ordered footnote groups. It uses the
source footnote region first and then bounded dedicated continuation pages, coordinated through one
document layout plan with body continuation pages.

PDFTR-29 activates the PDFTR-28 reconstructed style contract for BODY occurrences. PDFTR-30 extends
the same role-aware, occurrence-indexed adapter to HEADING, and PDFTR-31 extends it to FOOTNOTE.
Typography evidence and reconstruction still run once per document.

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

The production implementation does not solve arbitrary columns, tables, sidebars, floating figures,
mathematical layout, verse, bibliography layout, automatic font matching, full typography,
multi-column footnotes, endnotes, marginal notes, OCR, translation, GUI, or cloud layout services.

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

| Category | PoC | Production PDFTR-23 |
| --- | --- | --- |
| Body prose | flowable | flowable |
| Section/chapter headings | anchored | flowable with per-occurrence resolved typography |
| Block quotations | deferred | unsupported unless explicitly classified |
| Verse/poetry | unsupported | fail closed |
| Footnotes | anchored/deferred | ordered source-region flow plus bounded dedicated continuation |
| Running headers | anchored/preserved | preserve or regenerate by explicit policy |
| Page numbers | anchored/preserved | preserve or regenerate by explicit policy |
| Watermarks | anchored/preserved | preserve |
| Captions | anchored | preserve with associated figure |
| Tables | unsupported | fail closed |
| Figures/images | anchored | preserve and exclude occupied geometry from flow regions |
| Unknown/ambiguous | unsupported by default | fail closed |

Production has no manual ambiguity override. Partial/isolated ambiguous reconstruction, multiple
columns, unstable body geometry, unrecognized policies, or an image/drawing intersection make a
page ineligible. A group of at least three occurrences whose boundaries are all ambiguous may
become eligible only when the complete page-level evidence still proves one stable column, known
exclusions, and no object intersection. Such content otherwise stays on the fixed path only when
that path is complete; otherwise publication fails.

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
3. If it fits, create a completing segment and advance by measured height plus space-after.
4. If it does not fit, binary-search word boundaries for the largest fitting prefix. A single token
   can fall back to character boundaries so no token can disappear silently.
5. Record exact offsets and move the remainder to the next ordered region/page.
6. Reconstruct every paragraph from its segments and require exact Python-string equality.
7. Raise a capacity error instead of returning a partial plan when regions are exhausted.

The PyMuPDF adapter uses the same HTML/CSS textbox representation for fitting and insertion, with
automatic downscaling disabled. The target rectangle is sized from the measured result, avoiding a
second layout interpretation between planning and PDF mutation.

## Production page strategy

Production uses **Strategy A**: consume the explicit body region on a source page, then insert a
bounded number of blank continuation pages immediately after that source page. Each inserted page
inherits its source page geometry and body region but does not regenerate a running header or page
number. Final page indexes are computed with earlier insertions included, so continuation from page
N cannot overwrite source content from page N+1. A page that cannot be classified receives no flow
content.

The PoC uses this rule in a controlled form: it copies source page 3, preserves its running title,
page number, and footnotes, redacts only selected body fragments, fills the reviewed body region,
and appends one blank continuation page with the same geometry.

## PDFTR-24 footnote continuation strategy

Production uses a hybrid source-attached strategy: each source page's ordered footnote group first
uses the safely discovered lower-page region. If it does not fit, the remainder continues on one or
more blank pages inserted before the next original source page. The deterministic order is source
page, body continuation pages, footnote continuation pages, then the next source page. Continuation
pages match source geometry and use a conservative full-width region from 8% to 90% of page height;
they contain no body content and do not regenerate a running header, source page number, or
separator.

Eligibility requires schema 1.3 `ParagraphKind.FOOTNOTE` occurrences, translate policy, source-page
and column-zero mappings, an ordered single-column x-range, a safe body-to-footnote gap, bottom
margin, and no conflicting image or drawing. An existing horizontal separator is treated as an
anchor: body capacity stops above it, footnote redaction touches only source text fragments, and
the rule itself remains in the PDF.

`DocumentLayoutPlan` is the single authority for body and footnote plans, inserted-page count, and
source-to-output page mapping. Body and footnote segment rectangles, fixed-layout units, and
unselected anchors are checked for collisions before any redaction or insertion. Body and footnote
continuations have independent document-wide bounds (`max_reflow_pages=4` and
`max_footnote_pages=8`) because the four-page Robitzsch artifact needs one body page and four
footnote pages; sharing the body limit would reject otherwise complete content.

## Source-content preservation

- Source body text is redacted only through retained schema 1.3 fragment rectangles and only after
  both fixed and reflow plans are complete.
- Repeated headers/page numbers with preserve policy are left untouched; other non-flow units retain
  fixed-layout completeness behavior.
- Images and vector drawings are preserved; a candidate region intersecting either fails before
  planning.
- The PoC does not rasterize or flatten pages. Inserted text remains selectable.
- Existing-page redactions reuse production background sampling. Inserted blank pages are white by
  explicit PDFTR-23 policy.
- The source PDF is immutable. PoC PDF, debug PDF, and JSON plan use separate destinations and
  temporary sibling writes.

## BODY, HEADING, and FOOTNOTE typography boundary

Production reconstructs paragraph styles once per schema 1.3 document and keys them by occurrence
index. Role-validating BODY, HEADING, and FOOTNOTE adapters share one mapping that applies resolved font size,
line-height ratio, RGB color, physical
left/center/right/justified alignment, left/right indents, first-line indent, and before/after
spacing. Indents affect available width; space-before and first-line indent apply only to the first
segment, while space-after applies only after the completing segment. These values therefore
participate in pagination before mutation.

Safe negative first-line indents remain supported when the resulting first-line start stays inside
the flow region. A hanging indent that escapes the region, or any indent combination that leaves
non-positive line geometry, fails before PDF mutation. The heading orphan guard measures the
minimum following BODY content with this same style-aware geometry and `TextMeasurer` contract;
it does not rely on a separate font-size/line-height estimate. Production PyMuPDF measurement
counts the physical text-line objects emitted by the shared HTML layout, so a larger inline span on
one line cannot masquerade as several following BODY lines.

The renderer continues to use the selected Cyrillic-capable font rather than source font identity.
Bold and italic are retained as requested values but reported as unapplied until a safe local font
variant resolver exists. The resolved paragraph style remains the base for mixed paragraphs.
PDFTR-32 applies only exact, order-preserving source-backed inline font-size and RGB-color runs;
missing, ambiguous, overlapping, invalid, or face/family-only candidates are deferred. Source
offsets are never reused as target offsets, and equal repeated source/target counts are not treated
as proof of occurrence identity.

Inline runs are immutable translated-text ranges. Every prefix measurement and continuation
segment clips and rebases them before calling the same escaped HTML/CSS builder used for insertion,
with downscaling disabled. Post-save validation retains the strict segment-local text check and,
when extracted spans align unambiguously, also checks run size and color. Diagnostics expose
candidate/applied/deferred counts, applied-character totals, mapping/confidence/reason metadata,
and SHA-256 text evidence without run plaintext.

Each HEADING must have an occurrence-index match with the same occurrence index and paragraph id,
and the resolved role must remain HEADING. Missing or mismatched styles make the page ineligible.
The former uniform-heading-size gate is removed because planning, geometry validation, measurement,
insertion, and saved-PDF validation are already per occurrence; heterogeneous headings therefore do
not need a synthetic common style to remain safe.

Each FOOTNOTE follows the same occurrence-index and paragraph-id validation boundary and must retain
the FOOTNOTE role. When the authoritative map is present, missing, mismatched, wrong-role, or
nonphysical-alignment styles make footnote discovery ineligible; the renderer does not fall back to
the prior synthetic `font_size * 0.25` spacing. Resolved left/right indents and true-first-segment
indent are checked by the shared planner geometry before mutation. Resolved space-before applies
only to the true first segment and space-after only to completion, while alignment and side indents
persist through continuation pages. Separator geometry remains independent of paragraph spacing.

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

Footnote occurrences are reported with `reflow_footnote`, source occurrence index and page,
paragraph ID, target pages and rectangles, segment count, continuation count, offsets, and terminal
state. They also expose applied size, line height, alignment, indents, spacing, color,
requested/applied face state, mixed-style state, and fallback count. Document totals distinguish reflowed footnotes, footnote segments and continuations,
continuation pages, fixed-layout and unsupported footnote units, and unplaced text.

## PDFTR-31 Robitzsch validation

The cached four-page Robitzsch artifact contains 35 naturally classified FOOTNOTE occurrences.
PDFTR-31 rendered all 35 as 37 selectable segments at a stable resolved 7.970 pt, with four
footnote continuation pages, zero BODY or FOOTNOTE unplaced characters, zero overflow, and eight
final pages. The eight-page result matches the already style-aware BODY baseline: the historical
PDFTR-24 nine-page result included one BODY continuation that later resolved BODY metrics no longer
require. Poppler review covered all eight output pages and the source footnote pages; footnotes stay
below body content, continuations preserve order, and no clipping, overlap, or separator collision
was observed.

## PDFTR-24 controlled result

The current four-page Robitzsch artifact now publishes as nine pages. All 61 required occurrences
reach terminal rendered states: 7 body-reflow occurrences, 35 footnote-reflow occurrences, and 19
fixed-layout occurrences. Planning inserts one body continuation page and four footnote
continuation pages, with zero overflow and zero unplaced text. The 21 footnote overflows measured
before PDFTR-24 are reduced to zero. Poppler PNG review covered output pages 1 and 3 plus body and
footnote continuation pages; it confirmed preserved anchors, deterministic transitions, selectable
text, and no clipping or overlap.

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
3. **Headings:** distinguish by reconstruction/style evidence; anchor them in the PoC and apply
   authoritative per-occurrence reconstructed typography in production.
4. **Footnotes:** keep them separate from body flow; PDFTR-24 uses an ordered source-page group and
   bounded dedicated continuation pages.
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
11. **Unsupported:** unsafe/unknown pages, arbitrary multi-column layouts, multi-column footnotes,
    endnotes, marginal notes, tables, sidebars, floating figures, verse, and complex math.
12. **Unclassifiable page:** fail closed without redaction, insertion, or final publication.

## Implemented production boundary

Production body-text reflow covers confidently classified single-column book pages:

- body prose and headings with authoritative per-occurrence reconstructed typography;
- ordered existing-page regions with bounded inserted-page continuation;
- explicit anchor preservation for headers, page numbers, figures, drawings, and backgrounds;
- paragraph occurrence/segment diagnostics and strict zero-unplaced completeness;
- selectable/searchable output and split-segment saved-PDF validation;
- deterministic fake-backed tests plus controlled real-PDF validation.
- ordered source-page footnote groups with source-region-first placement and bounded dedicated
  continuation pages;
- one authoritative body/footnote page map, pre-mutation collision checks, source separator
  preservation, and footnote-specific diagnostics.

The pure planner applies a minimal, style-aware heading-plus-following-body orphan rule and emits
exact segment offsets. Saved candidates are reopened once and every
segment is checked only in its padded target clip; page-wide text is diagnostic. Render results and
reports expose strategy, target pages and rectangles, offsets, segments, continuations, inserted
pages, unsupported pages, zero-unplaced state, applied BODY/HEADING typography,
mixed-style/fallback state,
requested-versus-applied bold/italic state, and privacy-safe inline-run decisions.

PDFTR-24 adds ordered footnote-group pagination without broadening the body eligibility boundary.
Unsafe or multi-column footnotes remain fixed-layout only when complete; otherwise strict render
completeness aborts publication before mutation.
