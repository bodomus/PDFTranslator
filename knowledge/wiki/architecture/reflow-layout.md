---
title: Body-text reflow architecture
type: architecture
status: active
created: 2026-09-18
updated: 2026-09-18
tags:
- rendering
- reflow
- layout
- paragraphs
- continuation
sources:
- ../../../Tickets/PDFTR-23-production-body-reflow.md
- ../../../Tickets/PDFTR-22-reflow-architecture-poc.md
- ../../../docs/reflow-architecture.md
- ../../../src/pdftranslate/rendering/reflow/models.py
- ../../../src/pdftranslate/rendering/reflow/planner.py
- ../../../src/pdftranslate/rendering/reflow/regions.py
- ../../../src/pdftranslate/rendering/reflow/pymupdf_layout.py
- ../../../scripts/reflow_poc/models.py
- ../../../scripts/reflow_poc/planner.py
- ../../../scripts/reflow_poc/pymupdf_adapter.py
- ../../../tests/test_reflow_poc.py
related:
- system-overview.md
- ../failure-modes/render-completeness.md
- ../testing/pilot-evaluation.md
---

# Body-text reflow architecture

PDFTR-23 implements the PDFTR-22 forward-only, region-based layout boundary in production for
confident single-column body prose and one basic heading style. A logical
paragraph occurrence is the semantic flow unit; a typed continuation segment is the physical
placement unit. Each segment retains occurrence identity, exact character offsets, target page and
rectangle, continuation index, font evidence, and terminal continuation state.

## Safety model

Flow regions are explicit classified rectangles. They are not inferred from whitespace or
`ParagraphKind.BODY` alone. The Robitzsch four-page artifact classifies running titles and page
numbers as body, demonstrating that safe discovery also needs stable geometry, anchor policy, and
image/drawing intersection checks. Unknown, ambiguous, multi-column, table, footnote-pagination,
or otherwise unsafe layouts fail closed.

Planning is pure and precedes PDF mutation. Concatenating ordered segment ranges must reproduce
each exact translated paragraph once. Exhausted regions raise a capacity error rather than return a
partial plan. Saved output is reopened, every segment is checked in a padded clip around its exact
target rectangle, and a separate debug PDF can show regions and continuation boxes. Region-wide
extraction is diagnostic only and cannot establish segment success.

## Production page policy

The production hybrid uses Strategy A: consume the safe body region on the source page, then insert
bounded blank continuation pages immediately after it. Inserted pages match source geometry and do
not regenerate a running header or page number. Final indexes account for previous insertions, so
earlier continuation cannot overwrite later source content. Anchored headers, page numbers,
figures, drawings, backgrounds, captions, and footnotes remain outside body flow. A page that cannot
be safely classified receives no flow content and remains fixed-layout only when complete.

## Robitzsch evidence

The current schema 1.3 artifact has 26 rendered body occurrences, 14 rendered footnote occurrences,
and 21 overflowing footnote occurrences. Body reflow therefore does not resolve the present
21-overflow regression by itself.

The controlled page-3 PoC flowed four reviewed body occurrences (2,153 translated characters) at
12 pt through the copied source-page region and one inserted continuation page. It produced one
continuation, zero unplaced characters, selectable text, preserved page anchors, machine-readable
JSON evidence, and visually inspected normal/debug PDFs. A one-line baseline reserve was added
after PNG review found an overlap that extraction-only validation did not reveal.

## Production boundary

`pdftranslate.rendering.reflow` separates typed contracts, pure planning, conservative region
discovery, PyMuPDF measurement/mutation, and saved validation. Eligibility requires stable
single-column geometry, known body/heading occurrences, column zero, translate policy, and no
intersecting unselected text, images, or drawings. Partial or isolated reconstruction ambiguity is
rejected; only an all-ambiguous group of at least three occurrences may be resolved by stronger
homogeneous page-level geometry. Planning reserves the last baseline, keeps headings with minimal
following body content, and enforces exact offsets.
Render diagnostics expose strategy, target pages/rectangles, segment and continuation counts,
inserted pages, unsupported pages, and unplaced count.

Footnote pagination, tables, arbitrary columns, sidebars, floating figures, verse, and complex
mathematical layout remain explicit fail-closed follow-ups. See `docs/reflow-architecture.md` for
the full decision record and historical PoC command.
