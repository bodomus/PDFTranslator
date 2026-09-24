---
title: Body and footnote reflow architecture
type: architecture
status: active
created: 2026-09-18
updated: 2026-09-23
tags:
- rendering
- reflow
- layout
- paragraphs
- continuation
sources:
- ../../../Tickets/PDFTR-29-body-typography-fidelity.md
- ../../../Tickets/PDFTR-23-production-body-reflow.md
- ../../../Tickets/PDFTR-24-footnote-reflow-pagination.md
- ../../../Tickets/PDFTR-22-reflow-architecture-poc.md
- ../../../docs/reflow-architecture.md
- ../../../src/pdftranslate/rendering/reflow/models.py
- ../../../src/pdftranslate/rendering/reflow/planner.py
- ../../../src/pdftranslate/rendering/reflow/regions.py
- ../../../src/pdftranslate/rendering/reflow/footnotes.py
- ../../../src/pdftranslate/rendering/reflow/pymupdf_layout.py
- ../../../scripts/reflow_poc/models.py
- ../../../scripts/reflow_poc/planner.py
- ../../../scripts/reflow_poc/pymupdf_adapter.py
- ../../../tests/test_reflow_poc.py
- ../../../docs/typography-evidence.md
related:
- system-overview.md
- style-reconstruction.md
- ../failure-modes/render-completeness.md
- ../testing/pilot-evaluation.md
---

# Body and footnote reflow architecture

PDFTR-23 implements the PDFTR-22 forward-only, region-based layout boundary in production for
confident single-column body prose and one basic heading style. A logical
paragraph occurrence is the semantic flow unit; a typed continuation segment is the physical
placement unit. Each segment retains occurrence identity, exact character offsets, target page and
rectangle, continuation index, font evidence, and terminal continuation state.

## Safety model

Flow regions are explicit classified rectangles. They are not inferred from whitespace or
`ParagraphKind.BODY` alone. The Robitzsch four-page artifact classifies running titles and page
numbers as body, demonstrating that safe discovery also needs stable geometry, anchor policy, and
image/drawing intersection checks. Unknown, ambiguous, multi-column, table, or otherwise unsafe
layouts fail closed.

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
figures, drawings, backgrounds, and captions remain outside body flow. Footnotes use a separate
ordered flow group. The group consumes a structured lower-page region first, then bounded blank
footnote-continuation pages. Per source page the fixed order is source page, body continuations,
footnote continuations, next original page. Continuation pages do not regenerate headers, page
numbers, or separators.

One `DocumentLayoutPlan` owns all body and footnote plans plus the final source-to-output page map.
It checks body/footnote, footnote/fixed-layout, and footnote/anchor intersections before mutation.
Only selected text fragments are redacted, so a source separator rule remains intact. Unsafe
images, drawings, unstable x-ranges, multiple footnote columns, or insufficient capacity fail
closed.

## Robitzsch evidence

Before PDFTR-24, the schema 1.3 artifact had 26 rendered body occurrences, 14 rendered footnote
occurrences, and 21 overflowing footnote occurrences. The controlled PDFTR-24 render accounts for
all 61 occurrences as 7 body-reflow, 35 footnote-reflow, and 19 fixed-layout occurrences. It creates
one body continuation page and four footnote continuation pages, producing nine output pages with
zero overflow and zero unplaced text.

The controlled page-3 PoC flowed four reviewed body occurrences (2,153 translated characters) at
12 pt through the copied source-page region and one inserted continuation page. It produced one
continuation, zero unplaced characters, selectable text, preserved page anchors, machine-readable
JSON evidence, and visually inspected normal/debug PDFs.

## Production boundary

`pdftranslate.rendering.reflow` separates typed contracts, pure planning, conservative region
discovery, PyMuPDF measurement/mutation, and saved validation. Eligibility requires stable
single-column geometry, known body/heading occurrences, column zero, translate policy, and no
intersecting unselected text, images, or drawings. Partial or isolated reconstruction ambiguity is
rejected; only an all-ambiguous group of at least three occurrences may be resolved by stronger
homogeneous page-level geometry. Planning reserves the last baseline, keeps headings with minimal
following body content, and enforces exact offsets. Measurement and insertion share one PyMuPDF
HTML/CSS representation with downscaling disabled.
Render diagnostics expose strategy, target pages/rectangles, segment and continuation counts,
inserted pages, unsupported pages, and unplaced count.

Multi-column footnotes, endnotes, marginal notes, tables, arbitrary columns, sidebars, floating
figures, verse, and complex mathematical layout remain explicit fail-closed follow-ups. See
`docs/reflow-architecture.md` for the full decision record and historical PoC command.

PDFTR-27 adds a separate derived typography-evidence contract over the same logical occurrences.
It does not replace or feed `ReflowStyle` yet, so the production size, spacing, pagination, and
placement behavior documented here remain unchanged. See
[Typography evidence architecture](typography-evidence.md) for the downstream style-input boundary.

PDFTR-28 resolves that evidence into a role-aware renderer-facing contract with traceable
fallbacks. PDFTR-29 activates a minimal BODY-only adapter once per document. Resolved size, line
height, color, physical alignment, left/right and first-line indents, and before/after spacing all
participate in planning. First-line indent and space-before apply only to a paragraph's first
segment; space-after applies only after completion. Heading and footnote styles do not consume the
adapter. Diagnostics retain mixed-style/fallback state and distinguish requested from applied
bold/italic. See [Paragraph style reconstruction](style-reconstruction.md).

The heading orphan decision uses the same BODY `TextMeasurer`, effective width, first-line indent,
alignment, font size, line height, and one-time spacing as ordinary planning. It requires only the
configured minimum following BODY lines, not the whole paragraph. Negative first-line indents are
accepted when their physical start remains inside the flow region; unsafe hanging-indent geometry
fails closed before mutation rather than being clamped.
