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
- ../../../Tickets/PDFTR-22-reflow-architecture-poc.md
- ../../../docs/reflow-architecture.md
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

PDFTR-22 proves a forward-only, region-based layout boundary for single-column body prose. A logical
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

## Page policy

The recommended production strategy is hybrid: consume safe body regions on existing pages, then
insert bounded continuation pages with matching geometry. Anchored headers, page numbers, figures,
drawings, backgrounds, captions, and footnotes remain outside body flow according to explicit
policy. A page that cannot be safely classified receives no flow content.

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

PDFTR-23 should implement body prose plus one basic heading style for confidently classified
single-column book pages, anchored-object preservation, hybrid continuation, strict segment
completeness, and selectable post-save validation. Footnote pagination, tables, arbitrary columns,
sidebars, floating figures, verse, and complex mathematical layout remain explicit fail-closed
follow-ups. See `docs/reflow-architecture.md` for the full decision record and PoC command.
