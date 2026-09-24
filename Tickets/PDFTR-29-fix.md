# PDFTR-29 — Follow-up fix: heading orphan + hanging indent safety

## Context

Branch:

```text
codex/PDFTR-29-body-typography-fidelity
```

PDFTR-29 is functionally complete and passed its current quality gate, but code review found two narrow planner-safety issues that should be fixed before merge.

Do not redesign the typography architecture.

Keep the existing PDFTR-29 approach:

```text
ResolvedParagraphStyle
→ BODY-only ReflowStyle adapter
→ planner
→ shared PyMuPDF HTML/CSS measurement/insertion
```

This ticket is a small correctness follow-up only.

---

# Problem 1 — heading orphan check is not fully style-aware

Current `_would_orphan_heading()` effectively estimates the following BODY line using:

```text
body.font_size * body.line_height
```

plus vertical spacing.

That checks vertical capacity but does not verify whether the first line of the following BODY paragraph can actually be laid out using its resolved typography.

PDFTR-29 introduced:

```text
left_indent
right_indent
first_line_indent
alignment
font_size
line_height
```

The orphan rule must not leave a heading at the bottom of a region when the following BODY paragraph cannot place its required first line there.

Example:

```text
Heading
----------------

remaining vertical space appears sufficient

following BODY:
    large left/right indent
    large first-line indent

→ effective first-line width is too small
→ BODY moves to next region/page
→ heading remains orphaned
```

This violates the intended heading/body orphan guarantee.

---

# Required fix

Make the heading-orphan decision use the same style-aware measurement model as normal reflow planning.

Do not create a second approximation.

Preferred behavior:

```text
heading fits
+
minimum required part of following BODY also fits
using:
    effective BODY width
    left/right indents
    first-line indent
    BODY font size
    BODY line height
    BODY alignment
    BODY space_before
```

The orphan decision should use the existing `TextMeasurer` / `ReflowStyle` contract where practical.

The planner must remain:

```text
pure
deterministic
forward-only
bounded
PDF-mutation free
```

---

# Minimum BODY requirement

Preserve the current semantic rule:

```text
minimum_body_after_heading_lines = 1
```

But evaluate that requirement through actual layout measurement rather than only:

```text
font_size * line_height
```

Do not require the whole following paragraph to fit.

Only enough text for the configured minimum BODY line count must fit after the heading.

If necessary, determine the smallest meaningful prefix that produces the required number of rendered lines using the existing measurer.

Avoid introducing a divergent layout algorithm.

---

# Important spacing semantics

The check must continue to account for:

```text
heading.space_after
following_body.space_before
```

BODY `space_before` must still apply only once at true paragraph start.

First-line indent must be active because this is the true first segment of the BODY paragraph.

Do not double-count paragraph spacing.

---

# Problem 2 — negative first-line indent / hanging indent safety

Typography evidence can legitimately produce:

```text
first_line_indent < 0
```

for hanging-indent geometry.

Current width validation conceptually does:

```text
first_line_width = usable_width - first_line_indent
```

For a negative indent this increases the apparent width.

However the CSS renderer uses:

```css
text-indent: -Npt
```

which can move the first-line start outside the effective textbox / safe flow region.

That geometry must not be accepted silently.

---

# Required hanging-indent safety rule

Validate the physical first-line geometry.

Conceptually:

```text
effective_x0 = region.x0 + left_indent
effective_x1 = region.x1 - right_indent

first_line_start = effective_x0 + first_line_indent
```

Require safe geometry such that the first line does not escape the intended flow region.

At minimum reject cases where:

```text
first_line_start < region.x0
```

or where the effective first-line geometry otherwise becomes non-positive or unsafe.

Use the existing fail-closed policy.

Preferred failure:

```text
UnsupportedLayoutError
```

with a clear diagnostic mentioning first-line/hanging indent geometry.

Do not silently clamp the indent.

Do not rewrite the resolved typography value.

Do not prepend spaces.

---

# Measurement/render consistency

The following must remain identical between measurement and insertion:

```text
font
font size
line height
alignment
first-line indent
left/right indent geometry
```

Continue using the shared HTML/CSS path.

Do not weaken:

```text
scale_low=1
```

Automatic PyMuPDF downscaling must remain disabled.

---

# Regression tests

Add deterministic regression coverage.

At minimum:

## 1. Heading orphan caused by BODY first-line geometry

Create a case where:

```text
heading itself fits near bottom of region
simple vertical estimate suggests one BODY line fits
but BODY first-line indent / usable width causes the required first line not to fit
```

Expected:

```text
heading moves with BODY to next region
```

and does not remain orphaned.

---

## 2. Normal heading/body case still works

A normal BODY style with safe indents should preserve existing behavior.

No regression to the old orphan test.

---

## 3. Negative hanging indent within safe geometry

If supported safely:

```text
first_line_indent < 0
```

but the physical first-line start remains inside the allowed region.

Expected:

```text
planning succeeds
measurement/insertion semantics remain consistent
```

If the chosen architecture intentionally rejects all negative first-line indents, document that decision explicitly and test it.

Prefer preserving valid hanging indents when safe.

---

## 4. Unsafe hanging indent fails closed

Example:

```text
left_indent = 4 pt
first_line_indent = -12 pt
```

such that the first line would extend left of the allowed region.

Expected:

```text
UnsupportedLayoutError
```

before PDF mutation.

---

## 5. Continuation behavior unchanged

For continued BODY paragraphs:

```text
first_line_indent = 0
space_before = 0
```

on continuation segments.

Regression test must remain green.

---

# Non-goals

Do not:

* change typography reconstruction policy;
* modify PDFTR-27 evidence rules;
* modify PDFTR-28 fallback rules;
* activate typography for headings;
* activate typography for footnotes;
* implement inline style runs;
* implement font-face resolution;
* synthesize bold/italic;
* change continuation-page strategy;
* weaken segment-local validation;
* weaken exact accounting;
* weaken atomic publication;
* redesign planner architecture.

---

# Validation

Run focused tests for:

```text
planner
BODY typography
heading orphan behavior
indents
continuations
saved-segment validation
renderer production reflow
```

Then run full:

```powershell
scripts/check.ps1
```

All existing PDFTR-29 tests must remain green.

Expected invariants:

```text
overflow = 0
BODY unplaced = 0
footnote unplaced = 0
exact segment accounting preserved
saved-segment validation preserved
atomic output preserved
```

Re-run the existing cached Robitzsch validation if available.

Pagination may remain unchanged or change only if justified by corrected layout behavior.

---

# Deliverables

Update:

```text
implementation-report-PDFTR-29.md
review-PDFTR-29.md
```

Add a short section describing this follow-up fix.

Report:

```text
files changed
tests added/updated
focused test result
full scripts/check.ps1 result
Robitzsch result if rerun
```

Final review status should be:

```text
READY FOR REVIEW
```

only if both issues are covered by deterministic regression tests and the full quality gate passes.
