# PDFTR-24 Investigation

## Workflow and baseline

- Level: 2 structural rendering change.
- Branch: `codex/PDFTR-24-footnote-reflow-pagination` from `master` at `8f1c4e1`.
- Pre-existing unrelated change preserved: deleted `temp/.agents.zip`.
- Graphify reused the existing graph and identified `PdfRenderer`, `_plan_reflow_document`,
  `_plan_page`, `LayoutPlan`, `PlacementSegment`, region discovery, and saved-segment validation.
- CRG was rebuilt successfully for the ticket branch: 1,291 nodes, 11,331 edges, 137 files.
- Canonical sources checked: current renderer/reflow source, tests, ProjectWiki, reflow architecture,
  the Robitzsch PDF, and the saved schema 1.3 translation artifact.

## Current behavior and root cause

Production body reflow owns only body/heading occurrences. Footnotes remain on the fixed-layout
planner, so translated footnotes that do not fit their original line-sized rectangles become fatal
overflow states. The renderer has no typed footnote group, footnote-region discovery, footnote
continuation pages, or body/footnote-aware document page plan.

The saved Robitzsch artifact contains 61 logical paragraph occurrences. Pages 1–4 contain 35
footnote occurrences; the current fixed planner renders 14 and overflows 21, distributed 10/4/5/2.
All four pages are 432 x 648 points. Observed footnote bounds are:

| Source page | Footnotes | Footnote bounds | Body bottom | Images/drawings |
| ---: | ---: | --- | ---: | --- |
| 1 | 14 | `(67.35, 423.10, 378.28, 549.61)` | 405.46 | none |
| 2 | 7 | `(53.80, 485.86, 364.69, 549.61)` | 464.25 | none |
| 3 | 7 | `(67.35, 485.86, 378.22, 549.61)` | 463.23 | none |
| 4 | 7 | `(53.80, 496.85, 364.60, 549.61)` | 475.70 | none |

The dominant source footnote size is about 7.97 pt; marker spans may be about 5.64 pt. PyMuPDF
reported no horizontal separator drawing on these pages. Running titles/page numbers are near the
top margin and do not intersect the footnote areas.

## Design decision

- Option A preserves source association but is underspecified once source capacity is exhausted.
- Option B risks moving a note beneath references from another source page and conflicts with page
  anchors and later source-page capacity.
- Option C is simple but wastes safe source-page footnote capacity.
- Option D is selected: use the source footnote region first, then bounded dedicated blank
  continuation pages belonging to that source page.

Per-source ordering is authoritative: source page, body continuation pages, footnote continuation
pages, next source page. Continuation pages have source geometry, no regenerated running header or
page number, and no fabricated separator. A source separator is preserved because only source text
fragments are redacted and PyMuPDF graphics are retained.

## Safety and blast radius

The smallest coherent change adds a dedicated footnote discovery boundary but reuses the proven
pure planner, exact offsets, PyMuPDF measurer/inserter, and segment-local saved validation. A typed
document layout plan will own body plans, footnote plans, selected occurrences, insertions, and the
source-to-final page map. Planning and collision checks complete before any redaction or insertion.

Affected areas: rendering models, reflow typed models/discovery, renderer orchestration,
diagnostics aggregates, production reflow tests, docs, changelog, and ProjectWiki. Translation,
cache, OCR, model loading, CUDA, CLI options, and serialized document schema are unchanged.

Risks: conservative region eligibility, page insertion index drift, overlapping body/footnote
segments, anchors inside the lower-page region, and local-text validation false positives. These
are covered with fail-closed discovery, one document page map, explicit collision validation,
bounded insertion, exact reconstruction, and segment-local post-save checks.
