# PDFTR-24 Implementation Report

## Outcome

Production rendering now paginates conservatively classified schema 1.3 footnotes. The controlled
Robitzsch artifact publishes successfully with every required occurrence placed, zero overflow,
and zero unplaced text.

## Implemented design

- Selected the hybrid source-attached strategy: use the source-page footnote region, then bounded
  dedicated continuation pages.
- Defined deterministic per-source ordering: source page, body continuation pages, footnote
  continuation pages, next original source page.
- Added `FootnotePage` discovery from `ParagraphKind.FOOTNOTE`, source-page/column mappings,
  translate policy, stable grouped x-ranges, body boundary, bottom anchors, page margins, font/color
  evidence, images, drawings, and optional separator geometry.
- Reused the pure forward-only planner with `ReflowContentKind.FOOTNOTE`, exact occurrence identity,
  character offsets, continuation indexes, target rectangles, and exact reconstruction.
- Added `DocumentLayoutPlan` as the authority for body/footnote plans, selected occurrences,
  inserted pages, and final source-to-output page mapping.
- Added pre-mutation body/footnote, footnote/fixed-layout, and footnote/anchor collision checks.
- Kept redaction fragment-local, preserving source separator drawings and unrelated anchors.
- Added a separate document-wide `max_footnote_pages=8` bound. The existing body budget remains
  `max_reflow_pages=4`; sharing it would reject the real artifact, which needs one body and four
  footnote continuation pages.
- Added `REFLOW_FOOTNOTE`, occurrence-level diagnostics, and footnote-specific document totals.
  Blank continuation pages do not synthesize separators, running headers, or source page numbers.

## Compatibility and failure behavior

Fixed-layout content and existing body reflow retain their previous paths. Unsupported footnote
geometry, unstable/multi-column groups, unsafe anchored-object intersections, exhausted capacity,
collisions, changed insertion measurements, or missing saved segments fail closed before atomic
publication. A pre-existing output remains unchanged on failure.

## Deterministic coverage

Tests cover ordered shared regions, long-note continuation, following-note placement, duplicate
paragraph IDs, exact character reconstruction, source separator and running-title preservation,
unsafe image/drawing rejection, source/body/footnote continuation ordering, foreign Latin/Greek
text, segment-local duplicate-text validation, bounded capacity failure, atomic output preservation,
diagnostic occurrence identity and counters, body reflow regression, and fixed-layout compatibility.

## Controlled Robitzsch evidence

Input source: `tests/Robitzsch Jan Maximilian - Epicurean Justice. Nature, Agreement, and Virtue -
2024_50.pdf` with the completed cached schema 1.3 translation artifact.

| Metric | Result |
| --- | ---: |
| Required occurrences | 61 |
| Body-reflow occurrences | 7 |
| Footnote occurrences / reflowed | 35 / 35 |
| Footnote segments | 35 |
| Individually split footnotes | 0 |
| Inserted body pages | 1 |
| Inserted footnote pages | 4 |
| Fixed-layout occurrences | 19 |
| Unsupported body pages | 2 |
| Unsupported footnote pages | 0 |
| Required overflow | 0 |
| Unplaced body/footnote text | 0 / 0 |
| Final render state | published |
| Final output pages | 9 |

Before PDFTR-24, 21 of the 35 footnote occurrences overflowed fixed layout. After PDFTR-24 all 35
are placed. No individual note required a split in this artifact; each page's footnote group still
continues onto one dedicated page, so four footnote continuation pages are created.

Poppler PNG inspection covered output pages 1, 2, 3, 6, and 7: original pages 1 and 2 after mapping,
one body continuation, and footnote continuations. The inspection confirmed source/continuation
ordering, preserved running titles/page numbers on original pages, no generated anchors on blank
pages, readable selectable text, and no clipping or overlap. The real output is retained only under
the ignored repository-local `temp/pdftr24-real/` evidence directory.

## Validation

- Focused rendering/diagnostics tests: 36 passed.
- `scripts/check.ps1`: 269 passed, 1 skipped; 88.55% coverage.
- Ruff formatting and lint: passed.
- Mypy: passed for 90 source files.
- ProjectWiki lint: 13 pages, 77 links, zero errors/warnings.
- CRG updated: 1,308 indexed rows; 44 changed symbols; risk score 0.55.
- Graphify refreshed: 3,143 nodes, 6,337 edges, 228 communities.

## Remaining scope

Multi-column footnotes, endnotes, marginal notes, table notes, arbitrary floating note boxes, and
full typography fidelity remain explicitly unsupported. Visual typography improvements can now be
handled separately from render completeness.
