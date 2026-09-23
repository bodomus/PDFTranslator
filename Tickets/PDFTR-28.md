# PDFTR-28 — Style model / style reconstruction

## Goal

Introduce a production paragraph-style reconstruction layer that converts the typography evidence produced by PDFTR-27 into a stable, renderer-facing style contract.

PDFTR-27 answered:

```text
What typography evidence exists in the source PDF?
How confident are we in each property?
What is direct vs inferred vs unknown?
```

PDFTR-28 must answer:

```text
Given that evidence, what style should production rendering actually use?
```

The reconstructed style must explicitly distinguish source evidence, resolved style, fallback decisions, and uncertainty. This ticket builds the style contract and policy; it must not yet materially change production rendering.

---

## Branch

Create a new branch from current `master` after PDFTR-27 is merged:

```text
codex/PDFTR-28-style-model-reconstruction
```

Workflow:

```text
master
  ↓
PDFTR-28 branch
  ↓
PR
  ↓
merge to master
```

Do not branch from the old PDFTR-27 branch.

---

# Current baseline

Assume PDFTR-27 is merged.

Current production has a typed typography baseline with concepts such as:

```text
TypographyBaseline
ParagraphTypographyEvidence
TypographyProperty[T]
TypographyConfidence
TypographyProvenance
TypographyFallback
TypographyRole
TextAlignment
MixedStyleEvidence
```

Real Robitzsch evidence currently shows approximately:

```text
body:
    source font ≈ AGaramondPro-Regular
    source size ≈ 10.959 pt
    line height ≈ 12.472 pt
    line-height ratio ≈ 1.138
    first-line indent ≈ 11 pt
    alignment = justified

footnotes:
    source size ≈ 7.970 pt
```

Mixed inline evidence and unknown properties are preserved.

The current renderer still uses its simplified reflow style contract and does not consume the PDFTR-27 baseline.

---

# Scope

Implement a production style reconstruction layer that:

1. consumes `TypographyBaseline`;
2. derives role-aware document style baselines;
3. resolves incomplete/ambiguous paragraph evidence into stable renderer-facing styles;
4. records how every resolved property was chosen;
5. applies explicit fallback rules;
6. preserves occurrence identity and mixed-style evidence;
7. remains independent of Typer;
8. does not materially change rendered PDF output in this ticket.

Support at minimum:

```text
BODY
HEADING
FOOTNOTE
OTHER
```

---

# Non-goals

Do NOT yet:

- redesign body rendering;
- apply justification in final PDF rendering;
- apply first-line indents in production reflow;
- apply paragraph spacing in final rendering;
- implement rich inline style runs;
- resolve/download exact source fonts;
- regenerate headers/page numbers;
- redesign continuation pages;
- change body/footnote pagination;
- change translation;
- change OCR;
- add GUI options;
- add cloud font lookup.

Small inert integration hooks are allowed if they are disabled by default.

---

# Required investigation

Follow `.codex/PRE_TICKET_WORKFLOW.md`.

Inspect at minimum:

- `pdftranslate.typography`;
- `TypographyBaseline`;
- `ParagraphTypographyEvidence`;
- `TypographyProperty`;
- current `ReflowStyle`;
- body reflow region discovery;
- footnote reflow style construction;
- renderer font discovery/validation;
- `RenderOptions`;
- diagnostics;
- Robitzsch typography evidence;
- existing typography and reflow tests.

Determine the cleanest production module boundary for style policy, for example:

```text
src/pdftranslate/typography/style.py
```

or:

```text
src/pdftranslate/typography/reconstruction.py
```

Do not put style policy into CLI code or PyMuPDF adapters.

---

# Core style model

Introduce a typed renderer-facing style contract.

Suggested shape:

```text
ResolvedParagraphStyle
    occurrence_index
    paragraph_id
    role

    source_font_name
    source_font_family_group
    font_role

    font_size_points
    bold
    italic
    color_rgb

    alignment
    line_height_ratio

    first_line_indent_points
    left_indent_points
    right_indent_points

    space_before_points
    space_after_points

    mixed_styles
    decisions
```

Exact naming may follow project conventions.

Occurrence index remains authoritative.

---

# Style decision metadata

Every resolved property must retain traceable decision evidence.

Suggested model:

```text
StyleDecision[T]
    value
    source
    confidence
    used_fallback
    fallback_reason
```

Possible decision sources:

```text
TYPOGRAPHY_EVIDENCE
ROLE_BASELINE
DOCUMENT_BASELINE
SAFE_RENDER_DEFAULT
NORMALIZED_SOURCE_VALUE
UNRESOLVED
```

Prefer enums/typed constants over free-form strings.

---

# Resolution precedence

Define deterministic precedence for every property.

General policy should be explicit, for example:

```text
high-confidence direct source evidence
→ acceptable medium-confidence evidence
→ same-role document baseline
→ global document baseline where safe
→ renderer-safe fallback
```

Do not treat low-confidence or unknown evidence as authoritative.

The implementation report must document precedence per property.

---

# Document-level style baseline

Create a role-aware document style baseline from the PDFTR-27 evidence.

Conceptually:

```text
DocumentStyleBaseline
    body
    heading
    footnote
    other
```

For each role derive stable aggregate values where possible:

```text
source font family/group
font size
bold
italic
color
alignment
line-height ratio
first-line indent
left/right indent
spacing
```

Use robust aggregation. A single anomalous paragraph must not redefine a document role baseline.

---

# Stability thresholds

A role baseline property may only be considered stable when enough evidence exists.

Define deterministic rules such as:

```text
minimum sample count
dominant share
allowed spread/tolerance
confidence floor
```

Do not create a strong role baseline from one questionable observation.

For the current Robitzsch excerpt there is no classified heading occurrence, therefore real-document processing must not fabricate a HEADING baseline.

Synthetic tests may cover heading behavior.

---

# Role isolation

Fallback must remain role-aware.

Examples:

```text
BODY font size unknown
→ use BODY baseline

FOOTNOTE font size unknown
→ use FOOTNOTE baseline
→ never BODY baseline while a valid FOOTNOTE baseline exists

HEADING alignment unknown
→ use HEADING baseline only if it exists and is stable
```

Do not leak BODY typography into FOOTNOTE or HEADING by convenience.

---

# Unknown vs fallback

Preserve the distinction between:

```text
source says LEFT
```

and:

```text
source unknown
renderer resolved LEFT by fallback
```

Example:

```text
alignment.value = LEFT
used_fallback = true
fallback_reason = no reliable geometry evidence
```

This distinction is mandatory for future diagnostics and tuning.

---

# Font identity and font role

PDFTR-28 must NOT perform final local font resolution.

Keep separate concepts:

```text
source_font_name
source_font_family_group
font_role
```

Possible `font_role` values:

```text
SERIF
SANS_SERIF
MONOSPACE
UNKNOWN
```

Infer a generic role only when source metadata/name provides reasonable evidence.

Do not:

- claim exact source font is installed;
- scan the OS font registry;
- download fonts;
- resolve font paths;
- substitute fonts silently.

Font resolution belongs to a later rendering ticket.

---

# Font-name grouping

Investigate conservative family grouping for source names such as:

```text
AGaramondPro-Regular
AGaramondPro-Italic
AGaramondPro-Bold
```

Keep the original source identity as well as any normalized family group.

Do not over-normalize arbitrary font names.

---

# Bold / italic reconstruction

Resolve paragraph-level bold/italic from paragraph evidence and role baseline.

Examples:

```text
HIGH direct true
→ true

MEDIUM mixed dominant false
→ false, but mixed evidence remains visible

UNKNOWN
→ same-role baseline only when stable
→ otherwise safe fallback with explicit decision metadata
```

Do not infer bold solely because the role is HEADING unless the fallback policy explicitly says so.

---

# Font size reconstruction

Resolve a final style font size in points.

Policy:

```text
paragraph evidence
→ same-role baseline
→ renderer-safe default
```

Keep source value separate from resolved value.

Example:

```text
source_font_size = 10.959
resolved_font_size = 10.959
decision = TYPOGRAPHY_EVIDENCE
```

or:

```text
source_font_size = unknown
resolved_font_size = 10.959
decision = ROLE_BASELINE
```

---

# Line height reconstruction

Prefer source `line_height_ratio` when sufficiently reliable.

Suggested policy:

```text
paragraph ratio
→ same-role ratio baseline
→ renderer-safe line-height fallback
```

Renderer-facing style should expose a ratio clearly.

Do not reuse absolute line height blindly if font size changes.

---

# Alignment reconstruction

Resolve:

```text
LEFT
CENTER
RIGHT
JUSTIFIED
```

During evidence aggregation `UNKNOWN` remains valid.

Renderer-facing style must either contain a resolved alignment or an explicit safe fallback decision.

Do not silently map every unknown to LEFT without recording fallback.

---

# Indentation reconstruction

Resolve:

```text
first-line indent
left indent
right indent
```

Preferred policy:

```text
paragraph evidence
→ same-role baseline
→ zero-indent fallback
```

Do not copy BODY first-line indentation into FOOTNOTE/HEADING.

---

# Paragraph spacing reconstruction

PDFTR-27 intentionally stores canonical `space_before` and leaves `space_after` unknown.

PDFTR-28 must define a renderer-facing invariant.

Recommended baseline:

```text
resolved space_before_points = evidence/baseline/fallback
resolved space_after_points = 0
```

unless source-backed policy justifies something else.

Do not double-count the same physical gap.

Document explicitly:

```text
one observed physical gap is represented once
```

---

# Color reconstruction

Resolve source text color while preserving whether the paragraph contains mixed inline colors.

Paragraph-level resolved color may use a dominant source color.

Mixed inline color reproduction remains future scope.

---

# Mixed inline styles

The resolved style must preserve PDFTR-27 mixed-style evidence:

```text
mixed_font_family
mixed_font_size
mixed_weight
mixed_italic
mixed_color
```

The paragraph style may use dominant values for now.

Do not discard evidence merely because the first renderer integration will not reproduce inline runs.

---

# API

Expose deterministic production APIs, preferably split into document aggregation and paragraph resolution.

Conceptually:

```text
build_document_style_baseline(typography) -> DocumentStyleBaseline
```

and:

```text
resolve_paragraph_style(evidence, baseline) -> ResolvedParagraphStyle
```

or:

```text
reconstruct_styles(typography) -> ResolvedStyleDocument
```

The policy must be testable independently from rendering.

---

# Serialization

The style reconstruction output should be JSON-serializable for diagnostics/debugging.

Prefer a versioned derived contract, for example:

```text
ResolvedStyleDocument
schema_version = 1.0
```

Do not embed it automatically into `ExtractedDocument` unless investigation finds a concrete need.

Avoid cache/resume changes in this ticket.

---

# Developer inspection

Extend the PDFTR-27 inspection workflow.

Preferred interface:

```powershell
uv run python -m scripts.typography_inspect <pdf> --resolved
```

or another developer-only command if cleaner.

Allow side-by-side output:

```text
source evidence
resolved style
decision source
fallback used
```

Example:

```text
occurrence 38
role: body

font_size:
    evidence: 10.959 / high
    resolved: 10.959
    decision: typography_evidence

alignment:
    evidence: justified / medium
    resolved: justified
    decision: typography_evidence

space_before:
    evidence: unknown
    resolved: 0
    decision: safe_render_default
```

---

# Robitzsch validation

Run style reconstruction against the real Robitzsch artifact.

Inspect representative occurrences from:

```text
page 1
page 3
page 4
```

Include:

```text
multiple BODY paragraphs
multiple FOOTNOTE paragraphs
mixed-style BODY paragraphs
```

There is currently no classified HEADING occurrence; do not fabricate one.

Record for each selected occurrence:

```text
source evidence
resolved style
fallbacks used
```

Expected body baseline should remain close to observed evidence:

```text
AGaramondPro-Regular
≈ 10.959 pt
line-height ratio ≈ 1.138
first-line indent ≈ 11 pt
alignment = justified
```

Expected footnote baseline should remain close to:

```text
≈ 7.970 pt
```

Do not hard-code these numbers into production.

---

# Cross-paragraph consistency report

Produce a compact role-level stability summary for the real artifact.

Example:

```text
BODY
font family: stable
font size: stable
alignment: predominantly justified
line-height ratio: stable
first-line indent: commonly ~11 pt

FOOTNOTE
font size: stable
alignment: predominantly left / some unknown
```

This report should justify which properties are safe for PDFTR-29 renderer integration.

---

# Diagnostics

Expose optional resolved-style diagnostics.

At minimum:

```text
occurrence index
role
resolved font size
source font identity/family group
font role
bold
italic
color
alignment
line-height ratio
indentation
spacing
fallback count
mixed-style flags
```

Detailed per-property decision metadata may be debug-only if normal reports become too verbose.

---

# Rendering integration boundary

PDFTR-28 may add an adapter from resolved style to rendering concepts, but production output must remain visually unchanged by default.

A future conversion may conceptually be:

```text
ResolvedParagraphStyle
→ ReflowStyle
```

Do not activate it for normal rendering unless the mapping is proven no-op relative to current behavior.

Actual BODY typography application belongs to PDFTR-29.

---

# No rendering regression

The existing Robitzsch PDF must remain publishable with the established completeness baseline:

```text
required occurrences = 61
overflow = 0
unplaced text = 0
final pages = 9
```

Existing body/footnote reflow and validation tests must remain green.

Pagination behavior must not change.

---

# Deterministic tests

Add tests at minimum for:

### 1. Direct high-confidence evidence wins

### 2. Medium-confidence evidence follows documented acceptance policy

### 3. Low-confidence evidence does not silently override a stable role baseline

### 4. Unknown BODY font size falls back to BODY baseline

### 5. FOOTNOTE font size falls back to FOOTNOTE baseline, not BODY

### 6. HEADING baseline absent when no heading evidence exists

### 7. Stable role baseline aggregation

### 8. Outlier does not redefine role baseline

### 9. Source font identity retained separately from family grouping

### 10. Font-role inference

### 11. Bold reconstruction

### 12. Italic reconstruction

### 13. Mixed-style flags survive reconstruction

### 14. Color reconstruction

### 15. JUSTIFIED alignment retained

### 16. CENTER alignment retained

### 17. Unknown alignment uses explicit fallback metadata

### 18. Line-height ratio reconstruction

### 19. First-line indent reconstruction

### 20. Left/right indent reconstruction

### 21. Spacing physical gap represented only once

### 22. Duplicate paragraph IDs preserve occurrence identity

### 23. Serialization round-trip

### 24. Reconstruction does not mutate typography input

### 25. Existing rendering regression remains unchanged

### 26. Robitzsch completeness remains 61 / 0 overflow / 0 unplaced / 9 pages

---

# Performance

Style reconstruction must be cheap and deterministic.

Do not:

- reopen PDFs;
- rasterize pages;
- use OCR;
- run model inference;
- query the web;
- scan local font installations;
- perform expensive per-paragraph global searches.

Operate on the already built `TypographyBaseline` in memory.

---

# ProjectWiki

Before implementation inspect affected knowledge for:

```text
typography evidence
reflow architecture
render completeness
system overview
```

After implementation document:

```text
style reconstruction boundary
resolution precedence
role-aware baselines
stability thresholds
fallback policy
font identity vs future font resolution
spacing invariant
mixed-style limitations
```

Update Wiki log and run:

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

---

# Required artifacts

Create:

```text
.implementation-plans/investigation-PDFTR-28.md
.implementation-plans/implementation-plan-PDFTR-28.md
.implementation-reports/implementation-report-PDFTR-28.md
reviews/review-PDFTR-28.md
```

Add/update documentation, preferably:

```text
docs/style-reconstruction.md
```

Update:

```text
CHANGELOG.md
affected ProjectWiki pages
```

README only if the developer inspection workflow changes visibly.

---

# Quality gates

Run focused tests first, then:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src
.\scripts\check.ps1
```

Also:

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

Update CRG.

Refresh Graphify if module boundaries change materially.

---

# Acceptance criteria

PDFTR-28 is complete when:

- a typed renderer-facing paragraph style model exists;
- a typed document role-baseline model exists;
- every resolved property records decision source/fallback status;
- style resolution is deterministic;
- sufficiently reliable paragraph evidence has precedence over fallback baselines;
- role-aware baselines are robust against outliers;
- BODY/HEADING/FOOTNOTE fallback policies remain isolated;
- Robitzsch does not fabricate a heading baseline when no heading evidence exists;
- source font identity remains separate from future font resolution;
- font-size reconstruction is stable;
- bold/italic/color reconstruction is explicit;
- alignment reconstruction preserves source evidence where supported;
- unknown alignment fallback remains traceable;
- line-height ratio reconstruction exists;
- first-line/left/right indentation reconstruction exists;
- physical paragraph spacing is represented once without double counting;
- mixed inline-style evidence remains visible;
- occurrence index remains authoritative;
- reconstructed style output is serializable;
- developer inspection can compare source evidence with resolved style and fallback decisions;
- production rendering output remains unchanged by default;
- Robitzsch remains publishable with 61 required occurrences, zero overflow, zero unplaced text, and 9 pages;
- focused and full quality gates pass;
- docs and ProjectWiki describe reconstruction policy and limitations;
- the resulting contract is ready for **PDFTR-29 — Body typography fidelity**, where production body reflow can begin consuming the resolved style model.
