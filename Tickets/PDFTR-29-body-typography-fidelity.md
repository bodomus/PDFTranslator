# PDFTR-29 — Body typography fidelity

## Goal

Activate the PDFTR-27/PDFTR-28 typography pipeline for **production BODY reflow**.

PDFTR-27 established source typography evidence.

PDFTR-28 established deterministic, role-aware style reconstruction:

```text
TypographyBaseline
→ DocumentStyleBaseline
→ ResolvedParagraphStyle
```

PDFTR-29 must make BODY reflow consume the resolved style model so translated prose visually tracks the source more closely while preserving all correctness guarantees from PDFTR-20 through PDFTR-24.

Priority:

```text
visual fidelity
without sacrificing
completeness
pagination safety
segment-local validation
atomic publication
```

The first production target is BODY prose only.

---

## Branch

Create a new branch from current merged `master`:

```text
codex/PDFTR-29-body-typography-fidelity
```

Expected workflow:

```text
master
  ↓
PDFTR-29 branch
  ↓
PR / review
  ↓
merge
```

Do not branch from the PDFTR-28 worktree branch after merge.

---

# Current baseline

Assume PDFTR-28 is merged.

Production currently has:

```text
PDFTR-20 strict render completeness
PDFTR-21 foreign-language preservation
PDFTR-23 production body reflow
PDFTR-24 production footnote reflow/pagination
PDFTR-27 typography evidence
PDFTR-28 style reconstruction
```

Current renderer still constructs BODY `ReflowStyle` from simplified local logic and does not consume `ResolvedParagraphStyle`.

Robitzsch currently remains publishable:

```text
required occurrences = 61
overflow = 0
unplaced text = 0
final pages = 9
```

Observed BODY baseline from the real source is approximately:

```text
family: AGaramondPro
font size: 10.959 pt
line-height ratio: 1.138
first-line indent: ~11 pt
alignment: mostly justified at paragraph level
```

Do not hard-code these values.

---

# Scope

Apply reconstructed BODY style to production body reflow.

At minimum support:

```text
font size
line-height ratio
alignment
first-line indent
left indent
right indent
space before
space after
text color
bold paragraph baseline
italic paragraph baseline
```

Exact source-font-file substitution is NOT required yet.

Use the existing renderer-selected Cyrillic-capable font file unless investigation supports a safe minimal improvement.

---

# Non-goals

Do NOT yet implement:

- inline rich-text span rendering;
- per-word bold/italic runs;
- exact embedded-source-font reuse;
- font download;
- font installation lookup beyond existing renderer behavior;
- heading typography activation;
- footnote typography activation;
- continuation-page furniture redesign;
- running header/page-number regeneration;
- multi-column body reflow;
- list/table/caption typography;
- OCR redesign;
- translation changes;
- GUI controls.

Mixed inline styles must remain diagnosable but may still render using the paragraph-dominant style.

---

# Required investigation

Follow `.codex/PRE_TICKET_WORKFLOW.md`.

Inspect at minimum:

```text
pdftranslate.typography
ResolvedParagraphStyle
DocumentStyleBaseline
ReflowStyle
FlowParagraph
body region discovery
planner
PyMuPDF measurement
segment insertion
renderer orchestration
RenderOptions
saved-segment validation
Robitzsch real evidence
existing body reflow tests
```

Answer explicitly:

1. Where should typography reconstruction be invoked?
2. Should it run once per document or once per page?
3. How will occurrence index map resolved styles to `FlowParagraph`?
4. Which `ResolvedParagraphStyle` properties can current PyMuPDF textbox rendering apply directly?
5. Which properties require planner changes?
6. Which properties must remain deferred?
7. How does style application affect pagination and continuation-page count?
8. How will old completeness guarantees remain authoritative?

---

# Architecture requirement

Typography reconstruction must happen once per document.

Preferred flow:

```text
ExtractedDocument
→ extract_typography_evidence(...)
→ reconstruct_styles(...)
→ style_by_occurrence
→ body reflow discovery/planning
```

Do not recompute typography evidence separately per page or paragraph.

Occurrence index remains authoritative.

---

# Production integration boundary

Introduce a clear adapter between typography and reflow.

Conceptually:

```text
ResolvedParagraphStyle
→ BodyReflowStyle
```

This adapter should produce the minimal style subset needed by the planner and PyMuPDF layer.

Do not make planner depend directly on the entire typography contract if a smaller rendering contract is cleaner.

---

# ReflowStyle evolution

Investigate whether current `ReflowStyle` should be extended.

Likely renderer-facing fields:

```text
font_size
line_height
paragraph_spacing_before
paragraph_spacing_after
first_line_indent
left_indent
right_indent
alignment
bold
italic
```

If text color remains on `FlowParagraph`, keep it there.

Avoid duplicating style state between `FlowParagraph` and `ReflowStyle` without a clear reason.

Document the decision.

---

# Font size

BODY production reflow must use:

```text
ResolvedParagraphStyle.font_size_points
```

instead of the old independent median/default logic.

Requirements:

- style is selected by occurrence index;
- source-backed resolved size wins;
- renderer-safe fallback remains available through PDFTR-28;
- do not hard-code Robitzsch values;
- measurement and insertion must use the same resolved size.

---

# Line height

Use:

```text
ResolvedParagraphStyle.line_height_ratio
```

for both measurement and final insertion.

No measure/render mismatch.

---

# First-line indent

Apply BODY first-line indentation.

This likely requires planner/measurement support because the first rendered line has reduced width.

Do not fake first-line indent by prepending spaces.

Preferred approaches:

```text
layout-aware first-line width
or
split first-line geometry
```

Investigate PyMuPDF capabilities first.

The chosen method must remain deterministic.

---

# Left/right indents

Apply paragraph-level left/right indents relative to the flow region:

```text
effective_x0 = region.x0 + left_indent
effective_x1 = region.x1 - right_indent
```

Reject unsafe geometry if:

```text
effective_x1 <= effective_x0
```

Do not silently clamp away pathological source values without diagnostics.

---

# Alignment

BODY alignment should consume resolved alignment:

```text
LEFT
CENTER
RIGHT
JUSTIFIED
```

Investigate PyMuPDF textbox alignment support and use it where reliable.

Measurement and insertion must use the same alignment mode.

If PyMuPDF measurement behavior differs materially for justification, add tests.

Unknown alignment should never reach this stage because PDFTR-28 resolves it.

---

# Paragraph spacing

Apply resolved:

```text
space_before_points
space_after_points
```

while preserving the PDFTR-28 invariant that a physical source gap is represented once.

Planner must account for spacing in capacity.

Avoid double-counting:

```text
previous space_after + current space_before
```

unless that is explicitly the new representation.

For current policy:

```text
space_after is normally 0
```

---

# Color

BODY reflow should consume:

```text
ResolvedParagraphStyle.color_rgb
```

Convert to PyMuPDF float RGB consistently.

Do not use source packed integer color directly.

Preserve existing default black fallback.

---

# Bold / italic

PDFTR-29 must investigate paragraph-level bold/italic rendering.

Important constraint:

The current renderer uses one selected local Cyrillic-capable font file.

Do not falsely claim bold/italic fidelity if that font file does not expose corresponding faces.

Choose one of these explicit outcomes:

### A
Safe local font-face resolution exists and can select regular/bold/italic variants.

### B
Current font resolver cannot safely provide style variants, so bold/italic remains recorded but not physically applied in PDFTR-29.

If B is chosen, document it clearly and do not synthesize fake bold/italic through stroke tricks.

---

# Mixed inline styles

If:

```text
mixed_styles.*
```

is true, paragraph-level style may still be applied.

Diagnostics must retain that fidelity is partial.

Do not drop the mixed-style signal.

Inline style fidelity belongs to a later ticket.

---

# BODY-only activation

Only BODY should consume reconstructed typography in PDFTR-29.

Do NOT activate reconstructed style for:

```text
HEADING
FOOTNOTE
OTHER
```

Footnote path must remain current PDFTR-24 behavior.

Heading-specific typography belongs to a later ticket.

---

# Body discovery integration

Current body discovery creates `FlowParagraph` values.

Update it so BODY paragraphs obtain style from the authoritative occurrence-index style mapping.

Do not match by paragraph ID.

Duplicate paragraph IDs must remain safe.

---

# Planner changes

Update the pure planner only where necessary to represent typography.

Potential requirements:

```text
effective horizontal indents
space-before
space-after
first-line indentation
alignment-aware measurement
```

Keep planner pure, forward-only, deterministic, bounded, and exact-accounting.

No PDF mutation inside planner.

---

# Measurement API

Current `TextMeasurer.measure(...)` may be insufficient.

Investigate extending the contract to receive style-aware inputs.

Possible shape:

```text
measure(
    text,
    width,
    height,
    font_size,
    line_height,
    alignment,
    first_line_indent,
)
```

or pass a typed measurement style.

Prefer a cohesive style argument over an expanding list if that improves clarity.

Measurement API must remain testable with synthetic measurers.

---

# Continuation semantics

When a paragraph continues onto another region/page:

- left/right indents remain active;
- alignment remains active;
- font size remains active;
- line height remains active;
- first-line indent applies only to the first segment / true paragraph start;
- continuation segments must NOT repeat first-line indent;
- space-before applies once;
- space-after applies once after final segment.

This behavior must be explicit and tested.

---

# Heading orphan behavior

Existing heading/body orphan logic must not regress.

PDFTR-29 is BODY-only, but planner changes may touch shared code.

Run heading/orphan regression tests.

Do not activate heading typography.

---

# Saved-segment validation

Keep segment-local saved-PDF validation authoritative.

If style changes cause different line wrapping:

```text
expected segment text
must still be found in its local clip
```

Duplicate-text regression must remain green.

Do not weaken validation to accommodate visual changes.

---

# Strict completeness

PDFTR-20 semantics remain unchanged.

Before mutation:

```text
all required text
must have terminally safe placement
```

Typography fidelity must never override completeness.

If a resolved style makes layout exceed bounded capacity:

```text
fail closed
```

Do not silently shrink style beyond the resolved/fallback policy unless explicitly designed and diagnosed.

---

# Capacity and pagination

Style activation may change wrapping and inserted page counts.

This is acceptable if:

```text
all required text is placed
page order is correct
validation passes
```

But real validation must report before/after:

```text
body segments
continued body paragraphs
inserted body pages
footnote continuation pages
total pages
overflow
unplaced text
```

Do not require the output to remain 9 pages if faithful typography legitimately changes pagination.

However:

```text
overflow = 0
unplaced = 0
```

remain mandatory.

---

# Robitzsch real validation

Run a real translation/render using the cached Robitzsch artifact.

Compare source vs new BODY typography on representative pages:

```text
1
3
4
```

Inspect at least:

```text
normal justified body
indented body
centered body occurrence if classified BODY
mixed-style BODY
continued BODY paragraph
```

Record for each:

```text
occurrence index
resolved style
target pages
font size
line height
alignment
first-line indent
left/right indent
spacing
color
fallback count
```

---

# Visual comparison

Render source and translated output to PNG with a deterministic tool.

Compare:

```text
paragraph density
line count
left/right margins
first-line indentation
line spacing
alignment
page breaks
body/footnote boundary
continuation pages
```

Do not rely only on text extraction.

Store generated evidence only under ignored `temp/`.

Do not commit PNG/PDF outputs.

---

# Visual fidelity metrics

Add practical machine-readable metrics where possible.

For representative BODY occurrences, record:

```text
source font size
resolved font size
source line-height ratio
resolved line-height ratio
source first-line indent
resolved first-line indent
source alignment
resolved alignment
source line count
translated rendered line count
```

Do not create a fake universal "visual similarity score".

---

# Diagnostics

Extend render diagnostics for BODY reflow with applied typography.

At minimum per occurrence expose:

```text
applied font size
applied line-height ratio
alignment
first-line indent
left/right indent
space before/after
color
bold requested/applied
italic requested/applied
mixed-style indicator
style fallback count
```

Distinguish:

```text
resolved style
physically applied style
```

where they differ.

This is especially important for bold/italic if font-face application is deferred.

---

# Font handling

Do not regress Cyrillic safety.

The final selected render font must still pass the existing glyph coverage validation.

If style variants are introduced:

```text
regular
bold
italic
bold-italic
```

each used face must be validated for required glyphs.

Do not assume family variants exist.

---

# Failure behavior

Any new style-related failure must remain atomic.

Examples:

```text
invalid effective width
measurement/insertion mismatch
missing glyphs
unbounded pagination
segment validation failure
```

Result:

```text
no partial final output
pre-existing output unchanged
```

---

# Performance

Typography integration should add negligible cost compared with translation/rendering.

Do not:

- extract typography repeatedly;
- reopen source PDF per paragraph;
- run font scans per occurrence;
- rasterize during normal production;
- use model inference.

Build style maps once.

---

# Deterministic tests

Add tests covering at least:

1. BODY uses resolved font size.
2. BODY uses resolved line-height ratio.
3. BODY uses resolved color.
4. LEFT alignment.
5. CENTER alignment.
6. RIGHT alignment.
7. JUSTIFIED alignment.
8. Left/right indents reduce effective width.
9. Unsafe indents fail closed.
10. First-line indent applies to first segment only.
11. Continued paragraph does not repeat first-line indent.
12. Space-before applies once.
13. Space-after applies once.
14. Measurement and insertion use same style.
15. Duplicate paragraph IDs use occurrence index.
16. Mixed-style BODY retains diagnostics.
17. BODY style does not leak into FOOTNOTE.
18. BODY style does not leak into HEADING.
19. Existing heading orphan rule regression.
20. Existing footnote pagination regression.
21. Exact text reconstruction.
22. Segment-local duplicate-text validation.
23. Atomic failure preservation.
24. Latin/Greek preserved text regression.
25. Renderer-safe fallback style path.
26. Real Robitzsch completeness.

---

# Regression invariants

The following must remain true:

```text
occurrence identity
exact text accounting
foreign-language preservation
fixed-layout compatibility
body reflow safety
footnote pagination safety
source anchor preservation
segment-local saved validation
atomic publication
```

Do not weaken existing tests.

---

# ProjectWiki

Before implementation inspect:

```text
typography evidence
style reconstruction
reflow layout
render completeness
system overview
```

After implementation document:

```text
BODY style activation boundary
resolved style → applied style mapping
planner typography semantics
continuation style semantics
font-face limitations
diagnostics
visual validation
```

Update Wiki log.

Run:

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

---

# Documentation

Update/add:

```text
docs/style-reconstruction.md
docs/reflow-architecture.md
```

Optionally add:

```text
docs/body-typography-fidelity.md
```

if the implementation is substantial enough.

Update:

```text
CHANGELOG.md
affected ProjectWiki pages
```

README only if user-visible behavior/options change.

---

# Required artifacts

Create:

```text
.implementation-plans/investigation-PDFTR-29.md
.implementation-plans/implementation-plan-PDFTR-29.md
.implementation-reports/implementation-report-PDFTR-29.md
reviews/review-PDFTR-29.md
```

---

# Quality gates

Run focused tests first, then:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src
.\scripts\check.ps1
```

Also run:

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

Update CRG.

Refresh Graphify if planner/reflow/style boundaries materially change.

---

# Acceptance criteria

PDFTR-29 is complete when:

- production BODY reflow consumes `ResolvedParagraphStyle`;
- style mapping uses occurrence index, not paragraph ID;
- BODY font size comes from reconstructed style;
- BODY line-height ratio comes from reconstructed style;
- BODY text color comes from reconstructed style;
- BODY alignment is physically applied where supported;
- left/right indents are physically applied;
- first-line indent is physically applied once per paragraph;
- continuation segments do not repeat first-line indent;
- paragraph spacing is applied exactly once;
- measurement and insertion use the same effective typography;
- mixed inline evidence remains visible in diagnostics;
- bold/italic are either safely applied or explicitly reported as unresolved physical fidelity;
- BODY style does not leak into HEADING/FOOTNOTE paths;
- strict completeness remains authoritative;
- overflow remains zero on the controlled Robitzsch artifact;
- unplaced text remains zero;
- any changed pagination is documented and justified;
- saved-segment validation remains local and strict;
- atomic publication remains intact;
- real source/output PNG comparison is completed;
- full quality gates pass;
- docs and ProjectWiki describe BODY typography activation and limitations;
- the implementation is ready for the next typography ticket, likely HEADING fidelity.
