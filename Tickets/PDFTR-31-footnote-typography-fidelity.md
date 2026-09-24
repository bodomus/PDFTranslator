# PDFTR-31 — Footnote typography fidelity

## Goal

Extend the production footnote reflow pipeline so confidently classified `FOOTNOTE` paragraphs consume the authoritative reconstructed typography contract from PDFTR-27/PDFTR-28, with the same deterministic, fail-closed behavior already established for BODY and HEADING.

PDFTR-31 must improve footnote visual fidelity without weakening:

- strict render completeness;
- footnote pagination;
- separator preservation;
- body/heading pagination;
- continuation-page ordering;
- saved-PDF validation;
- atomic output publication.

---

## Context

Production sequence after PDFTR-30:

```text
PDFTR-27  Typography evidence
    ↓
PDFTR-28  ResolvedParagraphStyle reconstruction
    ↓
PDFTR-29  BODY typography fidelity
    ↓
PDFTR-30  HEADING typography fidelity
    ↓
PDFTR-31  FOOTNOTE typography fidelity   ← this ticket
```

`ResolvedParagraphStyle` already supports the `FOOTNOTE` role.

Current footnote production rendering still synthesizes local style inside
`discover_footnote_page()`:

```python
source_size = paragraph_font_size(paragraph, default_font_size)
font_size = max(min_font_size, source_size)

style=ReflowStyle(
    font_size=font_size,
    line_height=line_height,
    space_before=0.0,
    space_after=font_size * 0.25,
)
color=paragraph_color(paragraph)
```

That means reconstructed footnote typography exists but is not yet applied to production footnote
measurement, pagination, insertion, or diagnostics.

---

## Required architecture

Use the same authoritative style reconstruction already performed once per schema-1.3 document.

Do not reconstruct typography again inside the footnote subsystem.

Pass the existing:

```text
dict[int, ResolvedParagraphStyle]
```

into footnote discovery/planning in the same way BODY/HEADING receive it.

Occurrence index remains the only lookup key.

`paragraph_id` remains validation only.

Duplicate paragraph IDs must remain safe.

---

## Footnote typography adapter

Extend the role-aware reflow typography adapter with a dedicated FOOTNOTE entry point:

```python
footnote_reflow_style(resolved: ResolvedParagraphStyle)
```

Preferred structure:

```text
ResolvedParagraphStyle
        ↓
common resolved-style → ReflowStyle mapper
        ↓
BODY adapter
HEADING adapter
FOOTNOTE adapter
```

The common mapper must continue to own:

```text
font size
line-height ratio
physical alignment
left/right indent
first-line indent
space before/after
RGB color
mixed-style flag
fallback count
requested/applied bold
requested/applied italic
```

The FOOTNOTE adapter must:

- require `TypographyRole.FOOTNOTE`;
- preserve `heading=False`;
- reject wrong-role input;
- use normalized renderer RGB exactly as BODY/HEADING do.

Do not duplicate conversion logic.

---

## Production footnote discovery

Update `discover_footnote_page()` so each `FOOTNOTE` occurrence uses its authoritative resolved
style when the style map is available.

Required validation:

```text
style exists for occurrence index
resolved.occurrence_index == occurrence index
resolved.paragraph_id == paragraph.id
resolved.role == FOOTNOTE
alignment is physical/known
geometry is safe
```

Any missing, mismatched, or wrong-role resolved style must make footnote production planning fail
closed before PDF mutation.

Do not silently fall back to the old synthesized style when an authoritative style map was supplied
but the mapped FOOTNOTE style is invalid.

The legacy local style path may remain only where the existing API intentionally supports discovery
without reconstructed styles in isolated tests or legacy callers.

---

## Applied FOOTNOTE properties

Production FOOTNOTE must use resolved:

```text
font_size_points
line_height_ratio
color_rgb
alignment
first_line_indent_points
left_indent_points
right_indent_points
space_before_points
space_after_points
```

These values must drive both:

```text
measurement
pagination
continuation splitting
HTML/CSS insertion
saved-segment validation
diagnostics
```

Measurement and insertion must continue to share the same HTML/CSS style representation.

Automatic PyMuPDF downscaling must remain disabled.

---

## Footnote spacing semantics

Preserve the PDFTR-28/PDFTR-29 one-gap invariant:

```text
one physical paragraph gap is represented once
```

The old synthetic footnote spacing:

```python
space_after = font_size * 0.25
```

must not be added on top of resolved spacing when reconstructed typography is active.

Continuation semantics must remain:

```text
true first segment:
    first_line_indent = resolved value
    space_before = resolved value

continuation segments:
    first_line_indent = 0
    space_before = 0

final segment only:
    space_after = resolved value
```

Left/right indent and alignment persist on every segment.

---

## Footnote region and separator behavior

Do not redesign footnote region discovery.

Preserve existing safety rules for:

```text
stable footnote group x-range
body-to-footnote gap
lower-anchor boundary
unsafe image/drawing intersection rejection
separator discovery
separator preservation
source footnote region
continuation footnote region
```

Resolved typography may change how much text fits inside the region, but must not weaken the geometry
eligibility checks.

The separator must remain anchored/preserved according to the existing PDFTR-24 behavior.

Do not turn separator geometry into paragraph spacing.

---

## Pagination and continuation ordering

Preserve existing deterministic page ordering:

```text
source page
BODY continuation page(s)
FOOTNOTE continuation page(s)
next original source page
```

Resolved FOOTNOTE metrics may change the number of required footnote continuation pages.

That is acceptable only when:

- text accounting remains exact;
- no footnote text is lost;
- body pagination remains correct;
- source-page mapping remains correct;
- separator behavior remains correct;
- capacity limits remain bounded.

Do not increase reflow page limits merely to hide a layout regression.

---

## Geometry safety

Apply the same physical geometry rules already used by BODY/HEADING:

- left/right indents reduce usable width;
- first-line indent affects only the true first segment;
- positive indent must leave usable width;
- safe negative hanging indent may remain supported;
- first-line geometry escaping the flow region fails closed;
- no silent clamping;
- no fake leading spaces;
- no automatic font shrinking.

Unsafe resolved FOOTNOTE geometry must fail before PDF mutation.

---

## Bold / italic boundary

Keep the existing deferred face-resolution boundary.

For resolved FOOTNOTE:

```text
bold_requested = resolved.bold
bold_applied = False

italic_requested = resolved.italic
italic_applied = False
```

Do not:

- synthesize fake bold;
- synthesize italic;
- select arbitrary local face variants;
- scan/install/download source fonts.

Source font identity remains evidence/diagnostic data only.

---

## Mixed styles

Inline run reconstruction remains out of scope.

Use the resolved paragraph-dominant style and preserve:

```text
mixed_style
fallback_count
bold requested/applied
italic requested/applied
```

Do not implement per-span footnote rendering in this ticket.

---

## Diagnostics

Extend production render diagnostics so `REFLOW_FOOTNOTE` exposes the same applied typography fields
already available for BODY/HEADING:

```text
font size
line height
alignment
first-line indent
left/right indent
space before/after
color
bold requested/applied
italic requested/applied
mixed-style state
fallback count
```

Do this through role/content-kind aware logic.

Do not accidentally classify FOOTNOTE as BODY.

BODY and HEADING diagnostics must remain unchanged.

---

## Important real-document evidence

Unlike PDFTR-30, the cached Robitzsch artifact is directly useful here.

Current reconstructed typography evidence contains:

```text
35 FOOTNOTE occurrences
FOOTNOTE family: AGaramondPro, stable
FOOTNOTE font size: approximately 7.970 pt, stable (35/35 inliers)
FOOTNOTE alignment/line-height: insufficient direct reliable evidence,
                                therefore explicit reconstruction fallback
```

This makes Robitzsch a required representative validation artifact for PDFTR-31.

Do not manufacture or relabel roles.

Use the naturally classified FOOTNOTE occurrences.

---

## Tests

Add deterministic regression coverage.

At minimum include all cases below.

### 1. FOOTNOTE occurrence mapping

Verify that production footnote discovery uses style by occurrence index.

Include duplicate paragraph IDs.

Verify paragraph id is validation only.

---

### 2. Missing/mismatched/wrong-role style

When an authoritative style map is supplied, verify fail-closed behavior for:

```text
missing occurrence
embedded occurrence-index mismatch
paragraph-id mismatch
BODY style supplied for FOOTNOTE
HEADING style supplied for FOOTNOTE
```

Failure must occur before PDF mutation.

---

### 3. Resolved FOOTNOTE properties

Verify application of:

```text
font size
line height
RGB color
physical alignment
left/right indent
first-line indent
space before/after
```

Verify:

```text
heading == False
ContentDisposition.FLOWABLE_FOOTNOTE
```

---

### 4. BODY / HEADING isolation

A document containing BODY, HEADING, and FOOTNOTE must use the correct resolved style for each role.

No cross-role adapter leakage.

---

### 5. Footnote continuation semantics

Force a translated footnote to span multiple regions/pages.

Verify:

```text
first-line indent only on true first segment
space-before only on true first segment
left/right indent on all segments
alignment on all segments
space-after only on completing segment
exact text offsets
zero unplaced characters
```

---

### 6. Footnote pagination

Use resolved metrics that materially change the measured height.

Verify that continuation page allocation follows actual resolved typography rather than old
`default line_height` / `font_size * 0.25` assumptions.

Do not assert fragile exact page counts unless the fixture intentionally fixes them.

Prefer semantic assertions:

```text
all text placed
continuation exists when required
ordering is correct
no body/footnote page collision
```

---

### 7. Separator preservation

Render a source footnote group with a separator.

Verify:

```text
separator remains preserved
separator is not treated as text
separator does not overlap resolved footnote content
resolved typography does not alter separator ownership
```

---

### 8. Unsafe FOOTNOTE geometry

Resolved indents that leave no usable line width or escape the footnote flow region must fail closed.

Verify no output mutation/publication.

---

### 9. Requested bold / italic

Verify:

```text
bold_requested / italic_requested reflect resolved style
bold_applied == False
italic_applied == False
```

No synthetic face styling.

---

### 10. FOOTNOTE diagnostics

Verify `RenderStrategy.REFLOW_FOOTNOTE` exposes applied typography fields and fallback metadata.

Verify BODY/HEADING diagnostic behavior remains unchanged.

---

### 11. Deterministic saved-PDF rendering

Using the repository-bundled deterministic test font, render selectable mixed-script footnote text,
for example:

```text
Сноска Latin terminus Ελληνικά
```

Verify:

```text
selectable text
strict saved-segment validation
zero missing text
zero unplaced characters
no clipping/overlap
correct target page(s)
```

---

## Real Robitzsch validation

Run PDFTR-31 against the cached Robitzsch artifact.

Record at minimum:

```text
FOOTNOTE occurrence count
FOOTNOTE rendered segment count
resolved font-size statistics
continuation page count
BODY unplaced count
FOOTNOTE unplaced count
overflow count
final page count
```

Expected semantic requirements:

```text
all naturally classified footnotes remain complete
zero FOOTNOTE unplaced characters
zero BODY unplaced characters
zero overflow
separator behavior remains correct where present
BODY and HEADING pagination remains valid
```

Perform representative visual comparison of source/output pages containing footnotes.

Check:

```text
footnote size visibly reflects source evidence
footnotes remain readable/selectable
footnotes stay below body content
no clipping
no overlap
no separator collision
no missing note text
```

If pagination changes because resolved metrics are more accurate, document why.

Do not force old pagination merely for snapshot compatibility.

---

## Deterministic test environment

Preserve the bundled OFL-licensed test font introduced by the PDFTR-29 CI determinism fix.

Do not return to OS-dependent Segoe UI / DejaVu selection.

Windows and Ubuntu CI must exercise identical test font bytes.

Do not change the pinned test font unless separately justified.

---

## Production boundaries

Do not change:

- translation logic;
- paragraph reconstruction;
- typography evidence extraction policy;
- PDFTR-28 resolution precedence;
- BODY resolved typography;
- HEADING resolved typography;
- body region eligibility;
- footnote separator ownership;
- continuation ordering;
- strict capacity failure;
- exact text accounting;
- segment-local saved-PDF validation;
- source immutability;
- atomic destination replacement.

---

## Code areas expected to change

Likely:

```text
src/pdftranslate/rendering/reflow/typography.py
src/pdftranslate/rendering/reflow/footnotes.py
src/pdftranslate/rendering/renderer.py
tests/test_reflow_production.py
```

Possibly related diagnostics/docs tests.

Do not broaden the implementation outside this blast radius without evidence from investigation.

---

## Documentation

Update as required:

```text
docs/reflow-architecture.md
docs/style-reconstruction.md
knowledge/wiki/architecture/reflow-layout.md
knowledge/wiki/architecture/style-reconstruction.md
knowledge/wiki/log.md
CHANGELOG.md
README.md
```

Create/update:

```text
.implementation-plans/implementation-plan-PDFTR-31.md
.implementation-reports/implementation-report-PDFTR-31.md
reviews/review-PDFTR-31.md
```

Document the final typography activation boundary:

```text
BODY     → resolved typography active
HEADING  → resolved typography active
FOOTNOTE → resolved typography active after PDFTR-31
```

---

## Quality gate

Run focused tests covering:

```text
footnote adapter
footnote discovery
role mapping
pagination
continuations
separator preservation
geometry failure
diagnostics
saved segment validation
production renderer
```

Then run:

```powershell
uv run pytest
scripts/check.ps1
```

GitHub CI must pass on:

```text
windows-latest
ubuntu-latest
```

No platform-specific layout failures are acceptable.

---

## Acceptance criteria

PDFTR-31 is complete only when all of the following are true:

- production FOOTNOTE consumes authoritative reconstructed typography;
- occurrence index remains the lookup authority;
- paragraph id remains validation only;
- resolved FOOTNOTE size/line-height/color/alignment/indents/spacing affect both measurement and insertion;
- FOOTNOTE continuation semantics remain exact;
- footnote pagination remains bounded and complete;
- separator preservation remains correct;
- BODY behavior remains unchanged;
- HEADING behavior remains unchanged;
- unsafe footnote geometry fails closed;
- requested/applied font-variant diagnostics remain explicit;
- no synthetic bold/italic is introduced;
- no inline-run rendering is introduced;
- successful renders have zero unplaced text;
- saved-PDF validation remains strict;
- deterministic bundled test font remains in use;
- Robitzsch footnotes are validated on the real cached artifact;
- full local quality gate passes;
- GitHub CI is green on Windows and Ubuntu;
- implementation report and review artifact are updated.

Final review status:

```text
READY FOR REVIEW
```

only after all acceptance criteria and CI checks pass.

---

## Non-goals

Explicitly out of scope:

- local font-family/face resolver;
- source font installation/discovery;
- synthetic bold/italic;
- per-span / inline style-run rendering;
- multi-column production reflow;
- redesign of footnote region discovery;
- redesign of separator detection;
- arbitrary page-layout redesign;
- relaxing render completeness;
- increasing continuation limits solely to hide capacity regressions.
