# PDFTR-22 investigation

## Scope and workflow

- Workflow level: 2 (new layout architecture and executable proof of concept).
- Branch: `codex/PDFTR-22-reflow-architecture-poc`, created from `master` at
  `38812657bffa7f1374af96e5721b3c99cd6902e2`.
- Pre-existing working-tree change preserved: deleted `temp/.agents.zip`.
- Dependencies: no new dependency is required; the PoC can use the existing PyMuPDF adapter and
  installed Cyrillic font discovery.
- Production pipeline integration is explicitly out of scope.

## Sources consulted

- `knowledge/wiki/index.md`, `architecture/system-overview.md`,
  `failure-modes/render-completeness.md`, `components/foreign-language-preservation.md`, and
  `testing/pilot-evaluation.md`.
- PDFTR-20 and PDFTR-21 implementation reports and reviews.
- Reconstruction models and reconstructor, repeated-element models/classifier, renderer/layout,
  diagnostics, pipeline publication, serialization, and related tests.
- Persisted schema 1.3 Robitzsch workspace
  `a5de639d2daa2dff5617e5f240d378565c0f5e00e7bc6b99bfa5987795c0abf8`.
- Robitzsch source PDF pages 1, 3, and 4, inspected with PyMuPDF without mutation.

## Repository intelligence

- Graphify was available. A focused query connected `LogicalParagraph`, reconstruction,
  repeated-element policy, `_render_units_by_page`, `_plan_page`, completeness, saved-PDF
  validation, diagnostics, and pipeline publication. Source inspection confirmed the relevant
  relationships.
- CRG initially reported a graph built on the PDFTR-21 branch. A full build succeeded on the
  PDFTR-22 branch: 125 files, 1,139 nodes, and 10,156 edges.
- Graphify conclusions are architectural candidates only; the findings below were verified in
  current source and the persisted artifact.

## Current behavior

Schema 1.3 reconstruction produces ordered `LogicalParagraph` occurrences with stable source
fragments, kinds, anchor pages, source bounding boxes, and translated text. Paragraph IDs are not
occurrence-unique, so document-order occurrence index is already the authoritative completeness
identity.

The fixed renderer:

1. maps each translated paragraph back to its anchor-page bounding box;
2. probes successively smaller font sizes in that box;
3. optionally expands the box downward without crossing another source block;
4. records a typed terminal state;
5. aborts before redaction or publication if any required occurrence overflows;
6. otherwise redacts mapped source fragments, inserts translated text, saves to a temporary PDF,
   reopens it for local Cyrillic validation, and atomically publishes it.

This behavior is safe but cannot move excess text into a later region or page. Authoritative
planning is private `_BlockPlan` state tied one-to-one to a source box.

## Important evidence correction

Replaying the current production planner against the completed PDFTR-21 Robitzsch schema 1.3
artifact reproduced 40 rendered and 21 overflow occurrences. However, all 21 current overflows are
classified as `footnote`, not `body`:

| Kind | Rendered | Overflow |
| --- | ---: | ---: |
| body | 26 | 0 |
| footnote | 14 | 21 |

Distribution of overflow occurrences is page 1: 10, page 2: 4, page 3: 5, page 4: 2. Therefore a
body-reflow PoC must not claim that it resolves the current 21-overflow regression. It can prove the
new planning architecture on page 3 body prose while footnote pagination remains deferred and
fail-closed. Page 3 is still a currently failing document page because its five required footnote
occurrences prevent publication.

## Robitzsch structural analysis

All three pages are 432 x 648 points. PyMuPDF reports no image objects and no vector drawings on
pages 1, 3, or 4, so the candidate body rectangles do not intersect either kind of anchored object.
That absence is source-verified evidence for these pages only, not a general region-discovery rule.

### Page 1

- Ordered occurrences: 22 (8 body-classified, 14 footnote-classified).
- The first two `body` occurrences at y=33–45 are actually a page number and running title; the
  current four-page repeated-element evidence labels their source block as ordinary body/translate.
  Paragraph kind alone is therefore insufficient for safe flow classification.
- Source body prose/quotation occupies approximately x=67–378, y=54–405.
- Footnotes start at y=423 and continue through y=550.
- Fixed planner: 12 rendered, 10 overflow; all overflow occurrences are footnotes from
  `p0001-b0007`.
- Candidate controlled body region: `(67.35, 54.50, 378.28, 405.46)`.
- Anchored/deferred content: page number, running title, and footnote zone.

### Page 3

- Ordered occurrences: 13 (6 body-classified, 7 footnote-classified).
- The first two body-classified occurrences at y=33–45 are actually the page number and running
  title and must remain outside flow.
- Controlled body occurrence indexes are 38–41. Their source boxes occupy approximately
  x=67–378, y=54–463; they contain 2,153 translated characters in order.
- Footnotes start at y=486 and continue through y=550.
- Fixed planner: body indexes 38–41 render successfully, including index 40 only after shrinking
  to about 8.46 pt; five footnote occurrences overflow.
- Candidate controlled body region: `(67.35, 53.78, 378.32, 463.23)`.
- Anchored/deferred content: page number, running title, and footnote zone.

### Page 4

- Ordered occurrences: 12 (5 body-classified, 7 footnote-classified).
- The first two body-classified occurrences at y=33–45 are a section running title and page number,
  not ordinary body prose.
- Source body prose occupies approximately x=54–365, y=54–476.
- Footnotes start at y=497 and continue through y=550.
- Fixed planner: 10 rendered, 2 overflow; both overflow occurrences are footnotes from
  `p0004-b0004`.
- Candidate controlled body region: `(53.80, 53.78, 364.67, 475.70)`.
- Anchored/deferred content: running section title, page number, and footnote zone.

## Classification policy

| Content category | PoC disposition | First production disposition |
| --- | --- | --- |
| Body prose | flowable now | flowable |
| Section/chapter headings | anchored now | flowable with a basic heading style |
| Block quotations | deferred | fail closed until explicitly classified/styled |
| Verse/poetry | unsupported | fail closed |
| Footnotes | deferred and excluded from PoC input | fail closed; dedicated pagination is later scope |
| Running headers | anchored and preserved | anchored/preserved or regenerated by explicit policy |
| Page numbers | anchored and preserved | anchored/preserved or regenerated by explicit policy |
| Watermarks | anchored and preserved | anchored/preserved |
| Captions | anchored | anchored with associated figure |
| Tables | unsupported | fail closed |
| Figures/images | anchored | preserve and subtract their occupied rectangles from regions |
| Unknown/ambiguous blocks | unsupported | fail closed |

## Missing capability and smallest coherent change

The missing capability is a pure, typed, region-based planner whose flow unit is a logical
paragraph and whose placement unit is a continuation segment. It must carry occurrence identity and
exact character ranges, emit authoritative machine-readable evidence, and fail if configured
regions cannot account for every input character.

The smallest ticket-correct change is an isolated package under `scripts/reflow_poc/` plus focused
tests. It will not modify production renderer contracts. The executable demonstration will:

- load the persisted schema 1.3 artifact;
- require explicit controlled paragraph occurrence indexes and an explicit page-3 body region;
- reject non-body, ambiguous, non-translate, or geometrically outside selections;
- copy source page 3 into a diagnostic output, redact only the selected source fragments, and
  preserve all other source content;
- lay out the selected translated body paragraphs at one body style;
- append continuation pages under a bounded hybrid policy when capacity is insufficient;
- save the layout plan as JSON;
- reopen the output and validate page count, selectable text, occurrence coverage, segment order,
  exact pre-save character accounting, and normalized post-save extraction.

Explicit selection is intentional in the PoC. The current metadata misclassifies running titles and
page numbers as body on this short selection, so automatic body-region discovery is not yet safe.

## Blast radius and preserved contracts

- Production extraction, reconstruction, translation, cache, OCR, renderer, diagnostics, CLI, and
  publication behavior remain unchanged.
- No model loading, CUDA execution, OCR, cache invalidation, or dependency change is required.
- The source PDF is opened read-only and never overwritten.
- PDFTR-17 marker handling, PDFTR-18 saved-PDF validation principle, PDFTR-20 completeness, and
  PDFTR-21 exact foreign-language text remain unchanged.
- The PoC output is diagnostic and repository-local during validation; generated PDFs and plans are
  not committed.

## ProjectWiki pilot observations

The Wiki avoided rediscovery of the six-stage publication boundary, strict completeness invariant,
occurrence-index requirement, and foreign-language exactness constraint. Canonical source and the
persisted Robitzsch artifact were still necessary for exact geometry, private planner behavior,
content classification, and the discovery that all current overflows are footnotes. This is a real
Wiki gap: there is no durable reflow architecture page and the existing completeness page does not
classify the 21 overflows by paragraph kind.
