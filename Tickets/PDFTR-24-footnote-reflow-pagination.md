# PDFTR-24 — Footnote reflow / pagination

## Goal

Implement production footnote reflow and pagination so translated footnotes can grow beyond their original fixed source rectangles without being silently truncated or blocking publication solely because translated footnote text requires more space.

PDFTR-23 established production body-text reflow for confidently classified single-column book pages. It also confirmed the remaining Robitzsch blocker:

```text
21 required overflow occurrences
all 21 are footnotes
```

The body text on the validated pages can now be placed safely, but the document still fails closed because footnotes remain on the fixed-layout path.

PDFTR-24 must solve this next missing capability while preserving all existing safety guarantees.

The core target is:

```text
source page body
source page footnotes
        ↓
body layout / body region
footnote layout / footnote region
        ↓
translated footnotes grow within reserved footnote capacity
        ↓
if capacity is insufficient:
continue footnotes onto inserted continuation page(s)
        ↓
all required footnote text accounted exactly once
        ↓
selectable/searchable output
```

This ticket is specifically about **footnote reflow and pagination**. It must not become a general page-layout rewrite.

---

## Branch

Create from current `master`:

```text
codex/PDFTR-24-footnote-reflow-pagination
```

---

# Current production baseline

Assume PDFTR-23 has been merged.

Current important behavior:

- schema 1.3 logical paragraph occurrences are authoritative;
- body prose can use production reflow;
- reflow placement uses typed continuation segments with exact text offsets;
- post-save validation is segment-local;
- inserted continuation pages are bounded;
- body and fixed-layout planning complete before PDF mutation;
- unsupported/unsafe layouts fail closed;
- atomic publication remains mandatory;
- Latin/Greek preserved text from PDFTR-21 remains exact;
- the source PDF is immutable.

Current Robitzsch evidence:

```text
body occurrences:
    safe production reflow available

footnotes:
    14 rendered
    21 overflow

overflow distribution:
    page 1 = 10
    page 2 = 4
    page 3 = 5
    page 4 = 2
```

PDFTR-24 must verify these numbers again from the current merged code/artifact before relying on them.

---

# ProjectWiki

Use ProjectWiki under the existing `keep as-is` Phase 1 decision.

Before implementation:

1. read `knowledge/wiki/index.md`;
2. inspect production reflow architecture, render completeness, system overview, foreign-language preservation, and any footnote-related knowledge;
3. search for `footnote`, `rendering`, `reflow`, `pagination`, `continuation`, `completeness`, and `inserted pages`;
4. source-verify implementation-critical claims.

Do not expand ProjectWiki infrastructure unless this ticket reveals a concrete retrieval failure.

---

# Required investigation

Follow `.codex/PRE_TICKET_WORKFLOW.md`.

Inspect at minimum:

- production reflow package introduced by PDFTR-23;
- `PdfRenderer.render`;
- fixed-layout `_plan_page`;
- reflow planning integration;
- page insertion order;
- final source-page → output-page mapping;
- diagnostics/render results;
- footnote `LogicalParagraph` evidence;
- paragraph ordering and source mappings;
- footnote source bboxes;
- font sizes/colors/styles;
- separator lines or vector rules above footnotes;
- repeated-element policy;
- saved-PDF validation;
- atomic publication.

Inspect Robitzsch pages 1–4 in detail.

For each page record:

```text
page dimensions
body region
footnote region
number of footnote occurrences
source footnote ordering
source footnote bboxes
footnote font sizes
translated character counts
current fixed-layout states
separator rule / drawing evidence
page number and running header position
images/drawings intersecting footnote area
```

Do not assume all academic PDFs use the same footnote geometry.

---

# Primary design question

Determine how production rendering should paginate footnotes when translated footnote text exceeds the source footnote area.

Compare at least:

### Option A — stay attached to source page
Use source-page footnote capacity, then continue overflow on inserted page(s) immediately after that source page.

### Option B — flow into later footnote regions
Continue overflow into the next source page's footnote region.

### Option C — dedicated continuation pages
Create dedicated footnote continuation page(s) when source capacity is insufficient.

### Option D — hybrid
Use source footnote capacity first, then bounded dedicated continuation pages.

Compare these against:

```text
footnote/source-page association
reading order
citation meaning
visual expectations
interaction with body reflow
interaction with later source pages
page-number anchors
strict completeness
implementation complexity
```

The ticket must make and implement an explicit production decision.

---

# Required semantic rule

Footnotes belong to the source page that references them.

Every footnote segment must retain:

```text
occurrence index
paragraph ID
source page number
target page number
continuation index
exact text_start/text_end
target rect
style evidence
terminal state
```

Do not lose source-page identity after pagination.

---

# Footnote grouping

Prefer planning footnotes as an **ordered footnote group per source page**, because multiple notes share the same lower-page region.

A page-level footnote plan must preserve:

```text
original occurrence order
spacing between notes
continuation order
exact text accounting
```

---

# Footnote region discovery

Implement conservative footnote-region discovery using structured evidence:

```text
ParagraphKind.FOOTNOTE
source footnote bboxes
body-region lower boundary
page dimensions
stable footnote x-range
footnote font-size evidence
separator rule geometry
page-bottom margin
images/drawings
```

Do not classify arbitrary small text near the bottom as a footnote solely by font size.

A page is eligible only when the renderer can confidently establish:

```text
one footnote column
ordered footnote occurrences
safe footnote region
no unsupported intersection
```

Unsafe layouts must fail closed or retain fixed layout only when that is safe.

---

# Footnote separator line

Investigate whether the Robitzsch source contains a horizontal separator rule above footnotes and how PyMuPDF exposes it.

Required behavior:

- preserve a source separator if it exists and is outside redacted text fragments;
- do not erase it accidentally;
- inserted footnote continuation pages may use no separator or a simple deterministic separator only if explicitly documented.

Do not fabricate source-like decoration without a defined policy.

---

# Footnote style

Support a minimal production footnote style based on source evidence:

```text
font size
line height
text color
paragraph spacing
```

Use source-derived font size where reliable, subject to safe minimums.

Full typography fidelity is out of scope.

---

# Footnote numbering / markers

Footnote numbers or markers may be embedded in the footnote text.

PDFTR-24 must preserve stored schema 1.3 text exactly.

Do not generate or renumber footnote markers unless the existing model explicitly separates and requires that behavior.

---

# Body/footnote coordination

Body reflow and footnote reflow must not independently claim overlapping page space.

For every eligible source page establish:

```text
body region
footnote region
gap / separator area
```

These regions must not overlap.

If body reflow uses space down to the footnote boundary, footnote pagination must honor that boundary.

If footnote capacity grows, it must not silently push into the already planned body region.

Planning must be coordinated before mutation.

---

# Suggested production model

Introduce or extend typed models rather than warning strings.

Possible contracts:

```text
FootnoteRegion
FootnoteParagraph
FootnotePlacementSegment
FootnoteLayoutPlan
```

or generalize existing production reflow models if that remains clear and safe.

Avoid unnecessary duplication, but do not force footnotes through body abstractions if it obscures their distinct semantics.

The implementation report must explain the chosen approach.

---

# Planner requirements

The footnote planner must be:

```text
deterministic
forward-only
side-effect-free
bounded
exact-accounting
```

For every footnote occurrence:

```text
concat(ordered segments) == exact translated footnote text
```

No character may be lost or duplicated.

Prefer word-boundary splitting; allow single-token character fallback only when necessary.

---

# Continuation pages

Footnote continuation behavior must be explicit.

Define:

```text
where pages are inserted
page geometry
footnote region
body region behavior
header/page-number policy
separator policy
maximum inserted pages
```

Preferred conservative strategy:

```text
source page
→ source footnote region
→ dedicated footnote continuation page(s)
→ next original source page
```

On a dedicated footnote continuation page:

```text
no body content
no regenerated running header
no regenerated source page number
footnote text uses a defined continuation region
```

Investigation may refine this.

---

# Interaction with PDFTR-23 body continuation pages

Handle pages where PDFTR-23 already inserts body continuation pages.

Final ordering must be deterministic.

For example:

```text
source page 3
body continuation page(s)
footnote continuation page(s)
source page 4
```

or another justified order.

Do not let independently created page mappings conflict.

Prefer one unified per-source-page insertion plan.

---

# Final page mapping

PDFTR-24 must ensure that:

```text
all body segments
all footnote segments
all fixed-layout anchors
diagnostics
saved validation
```

agree on the same final output page numbers.

No module should independently calculate incompatible page positions.

If needed, introduce one authoritative page-layout/page-mapping plan.

---

# Mutation order

Required high-level order:

```text
1. validate source/artifact
2. classify body and footnote eligibility
3. build all body plans
4. build all footnote plans
5. build final page insertion map
6. verify zero-unplaced completeness
7. only then mutate/redact
8. insert continuation pages
9. insert body + footnote segments
10. save temporary candidate
11. reopen and validate
12. atomically publish
```

Exact internal ordering may differ, but no mutation may occur before all required translated content has a terminal safe plan.

---

# Source redaction

Redact only source fragments actually replaced by reflow.

For footnotes:

```text
redact original footnote fragments
preserve separator line
preserve page number
preserve unrelated footer content
```

Do not erase the entire lower-page region.

---

# Segment-local post-save validation

Mandatory.

Every footnote placement segment must validate in its own target clip:

```text
target_rect
+ padding
→ extract local text
→ normalize
→ require expected segment text locally
```

Do not use whole-page or whole-footnote-region text as authoritative success evidence.

Add a duplicate-text regression:

```text
same footnote text appears in two target positions
only one physically exists
validation of the missing segment must fail
```

---

# Cross-type collision validation

Add explicit checks ensuring:

```text
body segment rects do not overlap footnote segment rects
footnote segment rects do not overlap anchors
footnote segment rects do not overlap page numbers
```

Successful text extraction alone is not sufficient.

---

# Visual validation

Required on the real Robitzsch artifact.

Render affected pages to PNG and inspect:

```text
body/footnote boundary
separator line
footnote ordering
footnote continuation
page transitions
running title/page number preservation
clipping
overlap
inserted continuation pages
```

At minimum inspect pages 1 and 3 and at least one continuation page if created.

Do not add visual-image checks to normal CI.

---

# Diagnostics

Extend production diagnostics so every footnote occurrence exposes:

```text
source occurrence index
paragraph ID
source page
render strategy
target pages
segment count
continuation count
target rects
text offsets
final state
```

Add document aggregates:

```text
footnotes reflowed
footnote segments
continued footnotes
footnote continuation pages
footnote fixed-layout units
footnote unsupported pages
footnote unplaced text count
```

If generic reflow counters include footnotes, preserve a way to distinguish body vs footnote evidence.

---

# Render strategy

Extend or reuse `RenderStrategy`.

Footnote results must be distinguishable, for example:

```text
REFLOW_FOOTNOTE
```

or by a separate content-kind field.

Do not make diagnostics ambiguous between body and footnote reflow.

---

# Strict completeness

PDFTR-20 remains non-negotiable.

For every required footnote occurrence:

```text
exactly one terminal safe state
```

For reflowed footnotes:

```text
all translated characters accounted
all segments planned
all saved segments validated
```

If any required footnote remains unplaced, publication fails.

No warning-only escape hatch.

---

# Atomic output

Preserve existing atomic behavior.

On any planning/insertion/validation failure:

```text
no partial final PDF
pre-existing output unchanged when overwrite is enabled
```

Add explicit regression coverage.

---

# Real Robitzsch target

This ticket should attempt to remove the actual publication blocker.

Expected target:

```text
21 previously overflowing footnote occurrences
→ all terminally placed
→ 0 required overflows
→ 0 unplaced required text
```

If no other unsupported layout remains, the current Robitzsch artifact should become publishable.

Do not fake success. If another blocker is discovered, report it and fail closed.

---

# Required real-document evidence

For the Robitzsch run report:

```text
required paragraph occurrences
body reflow occurrences
footnote occurrences
footnote segments
continued footnotes
inserted body pages
inserted footnote pages
fixed-layout occurrences
unsupported occurrences/pages
unplaced text count
final render state
final output page count
```

Also record:

```text
before PDFTR-24:
21 footnote overflows

after PDFTR-24:
expected 0 required footnote overflows
```

If results differ, report actual evidence.

---

# Deterministic tests

Add focused tests for at least:

### 1. Multiple footnotes fit one region
Ordered, non-overlapping, exact accounting.

### 2. One footnote continues
Long footnote splits across source region and continuation page.

### 3. Multiple footnotes after continuation
Footnote A continues; footnote B follows correctly.

### 4. Exact occurrence identity
Duplicate paragraph IDs do not collapse occurrences.

### 5. Footnote ordering
Output order matches logical occurrence order.

### 6. Separator preservation
Source separator remains intact where expected.

### 7. Body-footnote non-overlap
Regions/segments cannot collide.

### 8. Anchor preservation
Page number/running header/unrelated footer survive.

### 9. Unsafe image/drawing intersection
Page rejected when footnote region conflicts with unsupported anchored object.

### 10. Exact character reconstruction
Every footnote reconstructs exactly from ordered segments.

### 11. Segment-local validation
Duplicate text elsewhere cannot satisfy a missing footnote segment.

### 12. Continuation-page ordering
Later source page remains after all continuation pages associated with the previous source page.

### 13. Body + footnote continuation together
Final page map remains deterministic.

### 14. Atomic failure
Capacity or post-save failure does not publish partial output.

### 15. Foreign text
Latin/Greek content inside footnotes remains exact.

### 16. Existing body reflow regression
PDFTR-23 body behavior remains unchanged.

### 17. Fixed-layout compatibility
Non-reflow pages remain supported.

---

# Performance constraints

Keep pagination bounded.

Do not:

- create unlimited continuation pages;
- reopen the entire PDF for every footnote segment;
- use quadratic/exponential fitting algorithms;
- re-run translation;
- re-run OCR unnecessarily.

Add or reuse an internal maximum page-expansion limit.

If body and footnote continuation share one limit, document the semantics. If separate limits are needed, justify them.

---

# Do not include

Do NOT implement:

- endnotes;
- arbitrary marginal notes;
- multi-column footnotes;
- side-note layouts;
- floating footnote boxes;
- table-note layout;
- bibliography pagination redesign;
- full typography reproduction;
- superscript citation remapping;
- automatic citation renumbering;
- OCR redesign;
- translation changes;
- GUI;
- cloud layout services.

---

# Expected follow-up

If PDFTR-24 makes Robitzsch publishable, the next stage should return to visual fidelity and typography quality rather than another completeness workaround.

Likely future areas:

```text
font/style fidelity
paragraph indentation
heading typography
spacing
page-number/header regeneration on inserted pages
background fidelity
```

Do not implement these preemptively.

---

# ProjectWiki update

After implementation:

1. add/update durable footnote pagination knowledge;
2. document chosen continuation strategy;
3. document body/footnote coordination;
4. document unified final page mapping;
5. document footnote validation/failure behavior;
6. update render-completeness knowledge if Robitzsch becomes publishable;
7. append a Wiki log entry;
8. run:

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

Do not change ProjectWiki architecture without concrete evidence.

---

# Required artifacts

Create:

```text
.implementation-plans/investigation-PDFTR-24.md
.implementation-plans/implementation-plan-PDFTR-24.md
.implementation-reports/implementation-report-PDFTR-24.md
reviews/review-PDFTR-24.md
```

Update:

```text
docs/reflow-architecture.md
CHANGELOG.md
affected ProjectWiki pages
```

README only if user-visible behavior or command semantics change.

---

# Quality gates

Run focused tests first, then:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src
.\scripts\check.ps1
```

Run ProjectWiki lint.

Update CRG after implementation.

Refresh Graphify if production rendering/page-layout module boundaries change materially.

---

# Acceptance criteria

PDFTR-24 is complete when:

- production footnote reflow/pagination exists;
- footnotes remain associated with their source page in diagnostics;
- footnote regions are derived from structured evidence;
- unsafe layouts fail closed;
- footnotes are planned as ordered typed segments with exact offsets;
- multiple footnotes share a region without overlap;
- long footnotes can continue to bounded inserted pages;
- body and footnote planning use non-overlapping capacity;
- body and footnote inserted pages share one deterministic final page mapping;
- later source pages are never overwritten;
- separator lines and anchors are preserved according to explicit policy;
- source redaction removes only replaced footnote fragments;
- every required footnote reconstructs exactly from its segments;
- zero-unplaced footnote completeness is enforced before mutation;
- saved-PDF validation is segment-local;
- duplicate-text validation false positives are covered;
- body/footnote collision checks exist;
- output remains selectable/searchable;
- atomic publication semantics remain intact;
- PDFTR-17/18/20/21/23 guarantees remain intact;
- controlled real Robitzsch validation is performed;
- the 21 current footnote overflows are either resolved to zero or any remaining blocker is explicitly documented and fails closed;
- full repository quality gate passes;
- docs and ProjectWiki accurately describe production behavior and remaining limits.
