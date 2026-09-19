# PDFTR-23 — Production body-text reflow for single-column book pages

## Goal

Implement the first production reflow path for translated body prose on confidently classified single-column book pages.

PDFTR-22 proved the architecture in an isolated PoC:

```text
LogicalParagraph occurrence
        ↓
FlowParagraph
        ↓
ordered FlowRegion(s)
        ↓
PlacementSegment(s)
        ↓
cross-page continuation
        ↓
selectable PDF text
```

The PoC demonstrated:

```text
4 body paragraphs
2,153 translated characters
1 continuation
1 added page
0 unplaced characters
```

It also established the production constraints:

- paragraph occurrence index is authoritative; paragraph ID alone is not unique;
- placement is segment-based with exact character offsets;
- planning happens before PDF mutation;
- body flow must never be inferred from whitespace or `ParagraphKind.BODY` alone;
- unknown/unsafe layouts fail closed;
- post-save validation is segment-local, not page-wide or region-wide;
- translated text remains selectable/searchable;
- page strategy is hybrid: safe existing regions first, then bounded inserted pages.

PDFTR-23 moves this architecture from PoC into the production renderer for **body prose and one basic heading style**.

This ticket does **not** solve footnote pagination. PDFTR-22 established that the current Robitzsch regression has 21 overflowing footnote occurrences and zero body overflows under the fixed renderer. Therefore a fully publishable Robitzsch PDF is not an acceptance criterion for PDFTR-23.

---

## Branch

Create from current `master`:

```text
codex/PDFTR-23-production-body-reflow
```

---

## ProjectWiki

ProjectWiki Phase 1 decision after PDFTR-22 is:

```text
keep as-is
```

Use the existing workflow normally.

Before implementation:

1. read `knowledge/wiki/index.md`;
2. read `architecture/reflow-layout.md`, `failure-modes/render-completeness.md`, `components/foreign-language-preservation.md`, and relevant system architecture pages;
3. search for reflow, rendering, completeness, paragraph occurrence, continuation, inserted page, and saved-PDF validation;
4. source-verify implementation-critical claims.

Do not expand ProjectWiki infrastructure in this ticket.

---

# Scope

Implement production body-text reflow for confidently classified:

```text
single-column text-heavy book pages
body prose
one basic heading style
```

The renderer must be able to:

```text
identify safe body-flow regions
collect flowable occurrences in reading order
plan before PDF mutation
continue translated prose across regions/pages
create bounded continuation pages when needed
preserve anchored content
emit typed placement evidence
enforce zero-unplaced completeness
validate every saved continuation segment locally
atomically publish only a complete result
```

The existing fixed-layout renderer remains required for non-reflow content. Do not delete it.

---

# Required investigation

Follow `.codex/PRE_TICKET_WORKFLOW.md`.

Inspect and source-verify at minimum:

- `scripts/reflow_poc/models.py`
- `scripts/reflow_poc/planner.py`
- `scripts/reflow_poc/pymupdf_adapter.py`
- production rendering models/renderer/layout/errors;
- diagnostics models/builder;
- pipeline publication;
- paragraph reconstruction;
- repeated-element policies;
- schema 1.3 occurrence handling;
- PDFTR-18 saved-PDF validation;
- PDFTR-20 completeness;
- PDFTR-21 foreign-language exactness.

Determine which PoC pieces should be:

```text
promoted
adapted
rewritten
left PoC-only
```

Do not import production runtime logic from `scripts/reflow_poc`.

Production code belongs under `src/pdftranslate/...`.

---

# Architecture direction

Prefer a dedicated production reflow boundary under rendering, for example:

```text
src/pdftranslate/rendering/reflow/
    models.py
    planner.py
    regions.py
    pymupdf_layout.py
```

Exact structure may differ.

Keep these concerns separated:

```text
eligibility/classification
region discovery
pure planning
PyMuPDF measurement
PDF mutation
post-save validation
diagnostics
```

Avoid turning `renderer.py` into one giant file.

---

# Reflow eligibility

A page is eligible only when the renderer can confidently establish:

```text
single-column body layout
safe body region
known flowable occurrences
known anchored exclusions
no unsupported object intersections
```

At minimum consider:

- paragraph kind;
- occurrence order;
- repeated-element policy;
- source geometry;
- known header/page-number zones;
- footnote zone;
- image intersections;
- vector drawing intersections;
- ambiguous reconstruction evidence.

Do not use `ParagraphKind.BODY` alone as proof of flowability.

PDFTR-22 showed that running titles/page numbers can be misclassified as body in short selections.

---

# Content disposition

Use an explicit production disposition model or equivalent.

At minimum:

```text
FLOWABLE_BODY
FLOWABLE_HEADING
ANCHORED_PRESERVE
FIXED_LAYOUT
DEFERRED_UNSUPPORTED
```

Required behavior:

### Body prose
Eligible for reflow.

### Basic heading
Support one deterministic heading style.

### Running headers / page numbers
Anchored/preserved.

### Images / vector drawings / captions
Anchored; flow regions must not overwrite them.

### Footnotes
Do not flow in this ticket. Keep fixed-layout/fail-closed behavior.

### Tables / verse / multi-column / unknown
Fail closed or stay on fixed layout only when that path is safe.

Never silently reinterpret unsupported content as body prose.

---

# Region discovery

Move from PDFTR-22 explicit rectangles toward production-safe region determination.

Use structured evidence such as:

```text
source paragraph geometry
body occurrence union
header/page-number exclusion
footnote start boundary
page margins
image/drawing exclusion
page dimensions
```

A universal page-layout detector is not required.

A conservative single-column rule is acceptable:

```text
one primary body column
stable x-range
body occurrences form one vertical flow region
no image/drawing intersection
footnotes clearly below body zone
```

If evidence is insufficient, do not reflow that page.

---

# FlowRegion

Promote a production equivalent of PDFTR-22 `FlowRegion`.

Include at minimum:

```text
target page number
rect
column index
order
created-page flag
source-page relationship
```

Keep future multi-column compatibility in the model even though PDFTR-23 accepts only column 0.

---

# FlowParagraph

Promote a production equivalent of `FlowParagraph`.

Retain:

```text
occurrence index
paragraph ID
source page
paragraph kind
translated text
source bbox
source fragment bboxes
style/disposition
```

Schema 1.3 translated text is authoritative.

Do not re-translate or normalize preserved Latin/Greek content from PDFTR-21.

---

# PlacementSegment

Promote a production equivalent of `PlacementSegment`.

Each physical placement must contain:

```text
occurrence index
paragraph ID
source page
target page
target rect
continuation index
text_start
text_end
segment text
font/style evidence
measured height
line count
terminal state
```

Exact offsets are required.

A paragraph may generate multiple segments across pages.

---

# Pure planner

Production planning must remain side-effect-free.

Required properties:

```text
deterministic
forward-only
zero text loss
zero duplication
no PDF mutation
capacity failure instead of partial plan
```

Planner output must be a typed layout plan.

Preserve the exact reconstruction invariant:

```text
concat(all segments for occurrence in order) == exact translated paragraph text
```

---

# Continuation behavior

When text does not fit:

```text
split at safe boundary
place prefix
continue suffix in next region/page
```

Prefer word boundaries.

Character fallback is acceptable only for a single unbreakable token when needed to guarantee no loss.

No segment may silently disappear.

---

# Existing pages + inserted pages

Implement the PDFTR-22 hybrid recommendation.

Use safe existing body regions in document order first.

When safe capacity is exhausted, create bounded continuation pages.

Inserted pages must:

- match source page geometry;
- use explicit body regions;
- remain selectable/searchable;
- use an explicit header/page-number policy;
- not pretend to preserve anchors that do not exist there.

Acceptable PDFTR-23 inserted-page policy:

```text
no regenerated running header
no regenerated source page number
plain continuation page geometry
```

unless investigation establishes a safer simple policy.

---

# Interaction with later source pages

This is critical.

Continuation from source page N must not overwrite source content belonging to source page N+1.

Explicitly choose and document one strategy:

### Strategy A
Insert continuation page(s) between source pages.

### Strategy B
Reflow all eligible pages as one ordered stream.

### Strategy C
Another source-verified strategy.

The chosen strategy must preserve document order and anchored source content.

Do not leave this implicit.

---

# Basic heading support

Support one heading style.

At minimum:

```text
heading is flowable
heading starts a new vertical block
heading uses distinct style/size
heading is not split unless unavoidable
```

If there is insufficient space for the heading plus minimal following body content, move the heading to the next region/page.

Avoid orphan headings.

---

# Source text redaction

Redact only source fragments belonging to reflow-managed occurrences.

Do not erase:

```text
headers
page numbers
footnotes
captions
figures
unselected text
```

Redaction occurs only after successful complete planning.

If planning fails:

```text
no mutation
no publication
```

---

# Background handling

The PoC assumed white.

Production must not silently assume white.

For existing source pages, reuse existing renderer background sampling/preservation behavior where appropriate.

For inserted blank continuation pages, white is acceptable for PDFTR-23 unless a safer background-copy strategy is proven.

---

# Images and vector drawings

Flow regions must not intersect anchored images or vector drawings.

If they do:

```text
page is not eligible for PDFTR-23 reflow
```

Do not move, crop, resize, or rasterize figures.

---

# Footnotes

Footnotes are intentionally out of scope.

PDFTR-22 proved:

```text
all 21 current Robitzsch overflows are footnotes
```

Therefore PDFTR-23 must not claim that body reflow alone makes the current Robitzsch artifact publishable.

Footnotes remain under PDFTR-20 completeness. If they overflow, publication still fails.

---

# Render strategy selection

Introduce a deterministic production decision such as:

```text
fixed-layout
reflow-layout
anchored/preserved
unsupported
```

The final render result/diagnostics must expose the chosen strategy.

---

# Diagnostics

For each reflowed occurrence expose:

```text
occurrence index
paragraph ID
source page
render strategy
target pages
segment count
continuation count
target rects
font/style
text offsets
final state
```

Document summary should include at least:

```text
reflowed paragraphs
reflow segments
continued paragraphs
inserted pages
fixed-layout paragraphs
unsupported pages
unplaced text count
```

---

# Strict completeness

PDFTR-20 remains authoritative.

For reflow-managed content:

```text
every required translated character must belong to exactly one valid PlacementSegment
```

Before mutation:

```text
unplaced_text_count == 0
```

After save:

```text
every segment validates locally
```

Any failure prevents publication.

---

# Post-save validation

Mandatory.

For every reflow segment:

1. reopen saved PDF;
2. extract from a local clip around `segment.target_rect`;
3. use padding similar to:

```text
max(2.0, font_size * 0.8)
```

4. normalize;
5. require expected segment text in that local extraction.

Do not use whole-page or whole-region text as authoritative evidence.

Preserve the duplicate-text regression:

```text
two identical segments in same region
one missing
validation must fail for the missing segment
```

---

# Visual validation

Extraction validation alone is insufficient.

For controlled real-PDF validation, render relevant pages to images and inspect:

```text
overlap
clipping
heading placement
continuation boundaries
source anchors
inserted pages
```

Visual inspection is required for the implementation report, not CI.

---

# Atomic publication

Reuse existing atomic output semantics.

On failure:

```text
requested final output absent
or existing output remains byte-for-byte unchanged under overwrite
```

Temporary/debug artifacts must never masquerade as successful output.

---

# Production integration

Integrate reflow into the normal render pipeline.

Prefer internal automatic strategy selection:

```text
safe eligible page → reflow
non-eligible safe content → fixed layout
unsafe required content → fail closed
```

Do not add a user-facing switch unless investigation proves a concrete need.

Normal user flow remains:

```powershell
uv run pdftranslate input.pdf --output translated.pdf
```

---

# Deterministic tests

Add focused production tests.

At minimum:

### 1. Single-page body reflow
Several body paragraphs fit one region.

### 2. Cross-page continuation
One paragraph continues to an inserted page.

### 3. Multiple paragraphs after continuation
A continues, then B follows in order.

### 4. Heading + body
Heading style and minimal orphan rule.

### 5. Anchored header/page number
Anchors survive and do not enter body flow.

### 6. Footnote exclusion
Footnote never enters body reflow; overflow remains fatal.

### 7. Image/drawing intersection
Unsafe page rejected from reflow.

### 8. Ambiguous classification
No automatic reflow when evidence is insufficient.

### 9. Exact character accounting
Every paragraph reconstructs exactly from segments.

### 10. Segment-local saved-PDF validation
Duplicate text at two locations; one missing must fail.

### 11. Atomic output
Failure does not publish partial output or destroy existing output.

### 12. PDFTR-21 exact foreign text
Preserved Latin/Greek remains exact through reflow.

### 13. Fixed-layout regression
Non-reflow content still works through existing renderer.

---

# Real regression validation

Reuse the persisted translated Robitzsch artifact when safe.

Do not rerun NLLB/CUDA unless translation compatibility changed.

Validate at least:

```text
page 3 body occurrences
page 4 body occurrences
```

Expected evidence:

```text
body prose can reflow with zero unplaced body text
continuations remain selectable
running title/page number/footnotes remain anchored
segment-local validation passes
visual layout has no overlap/clipping
```

Overall document publication may still fail because of footnote overflow.

The report must clearly separate:

```text
body reflow success
overall publication failure due deferred footnotes
```

Do not weaken footnote completeness to obtain a final PDF.

---

# Performance boundary

Avoid:

- unbounded page creation;
- exponential fitting search;
- repeated full-document reopening per segment;
- per-character probing except single-token fallback.

Use a bounded maximum continuation-page limit and fail clearly when exceeded.

---

# Do not include

Do NOT implement:

- footnote pagination;
- arbitrary multi-column layout;
- tables;
- sidebars;
- floating figures;
- verse/poetry layout;
- complex math;
- bibliography-specific layout;
- full typography fidelity;
- full widow/orphan support beyond basic heading handling;
- advanced regenerated headers/page numbers;
- OCR redesign;
- translation changes;
- GUI;
- cloud layout services.

---

# Expected follow-up

After PDFTR-23, the next high-value ticket should address the actual remaining Robitzsch blocker:

```text
PDFTR-24 — Footnote reflow / pagination
```

Do not implement PDFTR-24 work preemptively.

---

# ProjectWiki update

After implementation:

1. update only affected Wiki pages;
2. convert reflow docs from PoC-only wording to production behavior where applicable;
3. document strategy selection and unsupported layouts;
4. document inserted-page policy;
5. document segment-local validation;
6. record the footnote limitation;
7. append a concise Wiki log entry;
8. run:

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

Do not change the Phase 1 decision unless a concrete retrieval failure justifies it.

---

# Required artifacts

Create:

```text
.implementation-plans/investigation-PDFTR-23.md
.implementation-plans/implementation-plan-PDFTR-23.md
.implementation-reports/implementation-report-PDFTR-23.md
reviews/review-PDFTR-23.md
```

Update:

```text
docs/reflow-architecture.md
CHANGELOG.md
affected ProjectWiki pages
```

README only if user-visible behavior changes.

---

# Quality gates

Run focused tests first, then:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src
.\scripts\check.ps1
```

Update CRG after implementation.
Refresh Graphify if production module boundaries change materially.

---

# Acceptance criteria

PDFTR-23 is complete when:

- production code contains a dedicated reflow boundary and does not depend on `scripts/reflow_poc`;
- confidently classified single-column body prose can use reflow;
- one basic heading style is supported;
- body regions use structured evidence, not whitespace/body-kind alone;
- unsafe/ambiguous pages do not silently enter reflow;
- paragraph occurrence identity is preserved;
- cross-page continuation uses typed segments with exact offsets;
- hybrid existing-page + bounded inserted-page strategy works;
- later source pages are not overwritten by earlier continuation;
- anchored headers/page numbers/images/drawings remain protected;
- footnotes remain excluded and fail closed when they overflow;
- every reflow paragraph reconstructs exactly from its segments;
- zero-unplaced completeness is enforced before mutation;
- saved-PDF validation is segment-local;
- duplicate-text false-positive regression remains covered;
- output remains selectable/searchable;
- atomic publication remains intact;
- PDFTR-17/18/20/21 invariants remain intact;
- controlled real-PDF body reflow passes machine and visual validation;
- full Robitzsch publication is not falsely claimed while footnotes remain unresolved;
- full repository quality gate passes;
- docs and ProjectWiki accurately describe production behavior and remaining limits.
