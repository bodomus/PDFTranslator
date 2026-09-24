# PDFTR-30 — Heading typography fidelity

## Goal

Extend the production single-column reflow pipeline so confidently classified `HEADING` paragraphs use the reconstructed typography contract created by PDFTR-27/PDFTR-28, in the same deterministic and fail-closed manner already implemented for BODY in PDFTR-29.

PDFTR-30 must improve heading visual fidelity without weakening render completeness, pagination safety, saved-PDF validation, or the existing BODY behavior.

---

## Context

Current production state after PDFTR-29:

```text
PDFTR-27  Typography evidence
    ↓
PDFTR-28  ResolvedParagraphStyle reconstruction
    ↓
PDFTR-29  BODY typography fidelity
    ↓
PDFTR-30  HEADING typography fidelity   ← this ticket
```

`ResolvedParagraphStyle` already exists for semantic roles including `HEADING`.

BODY currently consumes reconstructed values through the production reflow adapter.

HEADING still uses local renderer defaults in `discover_reflow_page()`:

```python
font_size = max(font_size, default_font_size * 1.15)
style = ReflowStyle(
    font_size=font_size,
    line_height=line_height,
    space_before=0.0,
    space_after=font_size * 0.65,
    heading=True,
)
color = paragraph_color(paragraph)
```

This means source-backed heading typography is reconstructed but not yet applied during production rendering.

FOOTNOTE typography remains outside the scope of this ticket.

---

## Required behavior

For every confidently classified production `HEADING` occurrence, use its authoritative `ResolvedParagraphStyle` by occurrence index.

At minimum apply the resolved:

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

while preserving:

```text
heading=True
ContentDisposition.FLOWABLE_HEADING
```

The same resolved heading style must participate in:

```text
measurement
pagination
heading-orphan protection
continuation planning
HTML/CSS insertion
saved-PDF validation
diagnostics
```

Measurement and insertion must continue to use the same HTML/CSS representation.

Automatic PyMuPDF downscaling must remain disabled.

---

## Adapter design

Do not duplicate the BODY conversion logic.

Refactor the current BODY-only adapter into a role-aware renderer-facing adapter, or add a dedicated HEADING adapter that shares the common conversion logic.

Preferred conceptual shape:

```text
ResolvedParagraphStyle
        ↓
common resolved-style → ReflowStyle mapping
        ↓
BODY adapter / HEADING adapter
```

The adapter must:

- validate the expected semantic role;
- require physical/known alignment;
- preserve occurrence-index authority;
- normalize RGB exactly as BODY does;
- propagate mixed-style/fallback diagnostics;
- preserve requested/applied bold and italic state;
- set `heading=True` only for HEADING.

Do not resolve local font files in this ticket.

---

## Occurrence mapping

Continue the PDFTR-29 rule:

```text
occurrence_index is authoritative
paragraph_id is validation only
```

A heading must fail closed / make the page ineligible when its resolved style is missing, mapped to the wrong occurrence, has the wrong paragraph id, or resolves to a role other than `HEADING`.

Duplicate paragraph IDs must remain safe.

Do not introduce paragraph-id lookup.

---

## Existing heading safety behavior

Preserve the heading-orphan behavior fixed in PDFTR-29.

The orphan decision must continue to use:

```text
production TextMeasurer
effective horizontal geometry
true heading measurement
following BODY style
following BODY first-line geometry
heading spacing
BODY spacing
minimum_body_after_heading_lines
```

Activating resolved heading typography must not reintroduce the previous height-only orphan estimate.

---

## Heading spacing semantics

Use the same paragraph-spacing invariant already established by PDFTR-28/PDFTR-29:

```text
one physical gap is represented once
```

Do not synthesize a second hard-coded heading gap on top of resolved spacing.

The existing:

```python
space_after = font_size * 0.65
```

must no longer override a reliable resolved heading style when the reconstructed contract is available.

First-line indent and `space_before` apply only to the true first segment.

`space_after` applies only after paragraph completion.

Continuation segments must not repeat first-line indent or `space_before`.

---

## Heading style eligibility

Review the current `_single_heading_style()` gate.

Today production reflow rejects a page when multiple headings differ by more than the old local size tolerance.

That gate was created before per-occurrence reconstructed HEADING typography existed.

Investigate whether it is still valid after PDFTR-30.

Required outcome:

- do not keep an obsolete uniform-heading restriction merely because the old renderer required one local heading style;
- do not relax safety blindly;
- if heterogeneous headings are now safe because each occurrence has an authoritative reconstructed style, replace or narrow the old gate with evidence-backed validation;
- if another ambiguity/safety reason still requires the gate, document that reason and add regression coverage.

The final behavior must be explicit and deterministic.

---

## Bold / italic boundary

Keep the same production boundary as PDFTR-29.

Resolved HEADING may request:

```text
bold=True
italic=True
```

but until a safe local font-variant resolver exists:

```text
bold_requested = resolved.bold
bold_applied = False

italic_requested = resolved.italic
italic_applied = False
```

Do not synthesize fake bold.

Do not synthesize italic.

Do not substitute an arbitrary local font variant.

Do not modify the source-font identity contract.

---

## Mixed styles

Inline run reconstruction remains out of scope.

Use the dominant resolved paragraph style and preserve:

```text
mixed_style
fallback_count
requested/applied bold/italic
```

in diagnostics.

Do not add per-span rendering in PDFTR-30.

---

## Diagnostics

Extend production diagnostics so HEADING render results expose the applied typography in the same way BODY does.

At minimum verify/report:

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

BODY diagnostics must remain unchanged.

FOOTNOTE diagnostics must remain unchanged.

---

## Planner and geometry safety

All PDFTR-29 geometry rules apply to HEADING:

- left/right indents reduce usable width;
- positive first-line indent must leave usable first-line width;
- safe negative hanging indent may remain supported;
- geometry escaping the flow region fails closed;
- no silent clamping;
- no inserted spaces to simulate indent;
- no automatic font shrinking;
- exact segment accounting remains mandatory.

Any unsafe resolved heading geometry must fail before PDF mutation.

---

## Production boundaries

Do not change:

- translation behavior;
- paragraph reconstruction;
- typography evidence extraction policy;
- PDFTR-28 fallback precedence;
- BODY typography behavior;
- FOOTNOTE rendering;
- continuation-page architecture;
- exact accounting;
- capacity failure;
- segment-local post-save validation;
- atomic destination replacement;
- deterministic bundled test-font setup introduced by PDFTR-29 CI follow-up.

---

## Tests

Add deterministic regression coverage.

At minimum include:

### 1. HEADING occurrence style mapping

Verify that production heading discovery uses the resolved style by occurrence index and not by paragraph id.

Include duplicate paragraph IDs.

---

### 2. Resolved HEADING properties

Verify application of:

```text
font size
line height
color
physical alignment
left/right indent
first-line indent
space before/after
```

and verify:

```text
heading=True
```

---

### 3. BODY remains unchanged

A page containing both HEADING and BODY must apply:

```text
resolved HEADING style to HEADING
resolved BODY style to BODY
```

without cross-role leakage.

---

### 4. FOOTNOTE remains unchanged

HEADING activation must not route FOOTNOTE through the new adapter.

---

### 5. Heading orphan regression

Create a case where a resolved heading style materially changes its height/spacing.

Verify that the heading still moves with the required following BODY content when necessary.

The test must exercise the production style-aware orphan path.

---

### 6. Continuation semantics

If a heading itself requires continuation:

```text
first segment:
    first_line_indent = resolved value
    space_before = resolved value

continuation:
    first_line_indent = 0
    space_before = 0

final segment:
    space_after = resolved value
```

Exact text accounting must remain zero-unplaced.

---

### 7. Unsafe heading geometry

Resolved heading indents that leave no usable geometry or escape the flow region must fail closed before mutation.

---

### 8. Requested bold / italic

Verify:

```text
requested = source/resolved value
applied = false
```

No synthetic face styling.

---

### 9. Heading-style gate behavior

Add regression coverage for the final decision around `_single_heading_style()`.

If heterogeneous resolved headings are allowed, prove that safe per-occurrence styles render correctly.

If the gate remains, prove the actual safety reason rather than preserving the legacy behavior accidentally.

---

### 10. Saved PDF

Render selectable Cyrillic/Latin/Greek heading text and verify:

```text
no missing heading text
no clipping
no overlap
correct target page
zero unplaced characters
```

Use the repository-bundled deterministic test font.

---

## Representative validation

The current cached Robitzsch typography baseline contains no classified HEADING occurrence, so it is not sufficient by itself to validate PDFTR-30 heading fidelity.

Do not manufacture a false Robitzsch heading result.

Use:

1. the existing deterministic synthetic production tests; and
2. a real cached/source PDF with confidently classified HEADING occurrences, if one already exists in repository/test assets.

If no suitable real heading artifact exists, explicitly document that limitation in the implementation report and rely on deterministic production fixture validation for this ticket.

Do not silently relabel BODY as HEADING just to satisfy the validation step.

For any real artifact used, inspect representative source/output pages and confirm:

```text
heading remains selectable
heading text complete
visual size/alignment/spacing visibly follows source evidence
no overlap with BODY
no clipping
pagination remains explainable
```

---

## Quality gate

Run focused tests for:

```text
typography adapter
region discovery
heading/body mixed pages
planner orphan behavior
continuations
diagnostics
saved segment validation
renderer production reflow
```

Then run:

```powershell
uv run pytest
scripts/check.ps1
```

Both GitHub CI jobs must pass:

```text
windows-latest
ubuntu-latest
```

Do not accept a platform-specific layout result.

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
```

Create/update:

```text
.implementation-plans/implementation-plan-PDFTR-30.md
.implementation-reports/implementation-report-PDFTR-30.md
reviews/review-PDFTR-30.md
```

Document the production boundary clearly:

```text
BODY    → resolved typography active
HEADING → resolved typography active after PDFTR-30
FOOTNOTE → unchanged / future ticket
```

---

## Acceptance criteria

PDFTR-30 is complete only when all of the following are true:

- production HEADING uses authoritative reconstructed typography;
- occurrence index remains the lookup authority;
- resolved heading size/line-height/color/alignment/indents/spacing affect measurement and insertion;
- BODY behavior remains unchanged;
- FOOTNOTE behavior remains unchanged;
- heading-orphan protection remains style-aware;
- unsafe heading geometry fails closed;
- requested/applied font-variant diagnostics remain explicit;
- no synthetic bold/italic is introduced;
- no inline-run rendering is introduced;
- exact accounting remains zero-unplaced for successful renders;
- saved-PDF validation remains strict;
- deterministic Windows/Linux test-font behavior is preserved;
- full local quality gate passes;
- GitHub CI is green on Windows and Ubuntu;
- implementation report and review artifact are updated.

Final implementation review status:

```text
READY FOR REVIEW
```

only after all acceptance criteria and CI checks pass.

---

## Non-goals

Explicitly out of scope:

- FOOTNOTE typography fidelity;
- continuation-page visual fidelity work beyond what is required for correct heading pagination;
- local font-family/face resolver;
- source font installation/discovery;
- synthetic bold or italic;
- per-span / inline style-run rendering;
- multi-column production reflow;
- arbitrary page-layout redesign;
- relaxing strict render completeness.
