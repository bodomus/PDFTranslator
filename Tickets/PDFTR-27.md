# PDFTR-27 — Typography evidence extraction & style baseline

## Goal

Build a production typography-evidence layer that reconstructs the **source visual text style** of schema 1.3 logical paragraph occurrences from existing PDF extraction evidence.

PDFTR-20 through PDFTR-24 solved correctness and completeness:

```text
translation completeness
exact occurrence accounting
body reflow
footnote reflow
pagination
segment-local saved-PDF validation
atomic publication
```

The next phase is visual fidelity.

Before the renderer can reproduce typography reliably, the pipeline must answer:

```text
What typography did the source PDF actually contain?
How confident are we about each reconstructed property?
What fallback should production use when evidence is incomplete?
```

PDFTR-27 is therefore an **evidence and style-baseline ticket**.

It must not significantly change rendered PDF appearance yet.

The primary output is a typed, machine-readable typography baseline that later tickets can consume.

---

## Branch

Create a new branch from current `master`:

```text
codex/PDFTR-27-typography-evidence-style-baseline
```

Do not branch from PDFTR-24.

Expected workflow:

```text
master
  ↓
PDFTR-27 branch
  ↓
PR
  ↓
merge to master
  ↓
PDFTR-28 branch from updated master
```

---

# Scope

Implement source-backed typography evidence for schema 1.3 logical paragraphs.

At minimum determine, where evidence permits:

```text
font family / source font name
font size
bold
italic
text color
alignment
line height / line spacing
first-line indent
left indent
right indent
paragraph spacing before
paragraph spacing after
role / paragraph kind
```

Each property must expose:

```text
value
confidence
evidence source
fallback behavior
```

The baseline should support at least:

```text
body
heading
footnote
```

It should remain extensible for future:

```text
caption
quote
bibliography
list
```

---

# Non-goals

Do NOT implement full visual rendering changes in this ticket.

Do not:

- redesign body rendering;
- change footnote pagination;
- implement font substitution policy beyond evidence discovery;
- apply bold/italic runs in final rendering;
- implement justification;
- implement first-line indentation in production rendering;
- regenerate headers/page numbers;
- redesign continuation pages;
- change translation;
- change OCR;
- add GUI controls;
- add cloud font services.

Small diagnostic/debug visualization is allowed if needed for validation.

---

# Required investigation

Follow `.codex/PRE_TICKET_WORKFLOW.md`.

Inspect current source models and extraction pipeline.

At minimum review:

- `TextSpan`;
- `TextBlock`;
- `LogicalParagraph`;
- `ParagraphFragment`;
- reconstruction logic;
- PyMuPDF extraction backend;
- font metadata currently captured from PyMuPDF;
- paragraph kind classification;
- production reflow `FlowParagraph`;
- `ReflowStyle`;
- renderer font-size selection;
- diagnostics models/reporting;
- current Robitzsch source artifact;
- current source PDF directly through PyMuPDF.

Determine what source evidence is already captured and what is currently lost.

Produce an evidence matrix such as:

| Property | Current model evidence | Recoverable? | Confidence basis | Notes |
| --- | --- | --- | --- | --- |
| font size | `TextSpan.font_size` | yes | high | dominant/median span |
| font family | investigate | investigate | investigate | source PDF font name |
| bold | investigate | investigate | flags/name | do not infer from size |
| italic | investigate | investigate | flags/name | source-backed only |
| color | `TextSpan.text_color` | yes | high | packed RGB |
| alignment | geometry | inferred | medium | line edges |
| line height | line geometry | inferred | medium | baseline spacing |
| first-line indent | line geometry | inferred | medium | first vs following lines |
| paragraph spacing | neighboring geometry | inferred | medium/low | context-dependent |

Do not invent support that the source data does not provide.

If PyMuPDF exposes useful raw font/span flags that are currently discarded, document the smallest safe model change required to retain them.

---

# Source authority

Canonical source evidence remains authoritative.

Use, in order:

```text
source PDF
PyMuPDF raw extraction
current extracted schema models
reconstruction artifacts
```

Do not infer a property merely because it is typical for books.

Unknown must remain unknown.

---

# Typography evidence model

Introduce a typed production model.

A suggested shape:

```text
TypographyEvidence
    role
    font_family
    font_size
    bold
    italic
    color
    alignment
    line_height
    first_line_indent
    left_indent
    right_indent
    space_before
    space_after
```

Each field should use an evidence wrapper or equivalent:

```text
TypographyProperty[T]
    value: T | None
    confidence: high | medium | low | unknown
    source: ...
    fallback: ...
```

Exact names may follow project conventions.

Do not use ad-hoc dictionaries as the authoritative model.

---

# Confidence model

Define a small deterministic confidence vocabulary.

Recommended:

```text
HIGH
MEDIUM
LOW
UNKNOWN
```

Avoid fake numeric confidence unless there is a real calibrated basis.

Examples:

```text
font size from dominant source spans
→ HIGH

alignment inferred from stable left/right edges across multiple lines
→ MEDIUM

paragraph spacing inferred from one neighboring paragraph
→ LOW

font family unavailable
→ UNKNOWN
```

The implementation must document the confidence rules.

---

# Evidence provenance

Every inferred property must say where it came from.

Possible provenance:

```text
SOURCE_SPAN
SOURCE_FONT
SPAN_FLAGS
LINE_GEOMETRY
PARAGRAPH_GEOMETRY
NEIGHBOR_GEOMETRY
PARAGRAPH_KIND
FALLBACK
```

Use enums/typed constants rather than free-form strings where practical.

---

# Font family / font identity

Investigate what PyMuPDF exposes for:

```text
font name
font family
subset prefixes
embedded font names
font flags
```

Normalize only obvious PDF subset prefixes if safe, for example:

```text
ABCDEE+MinionPro-Regular
→ MinionPro-Regular
```

Do not pretend this means the same font is locally installed.

Store source font identity separately from future render font resolution.

Recommended distinction:

```text
source_font_name
render_font_family   # future ticket
```

PDFTR-27 should primarily establish `source_font_name`.

---

# Bold / italic evidence

Determine bold/italic from explicit source evidence where possible.

Potential evidence may include:

```text
font name
font flags
span flags
font metadata
```

Do not infer bold only from larger font size.

Do not infer italic solely from paragraph role.

If evidence conflicts, record ambiguity rather than forcing a value.

---

# Font size baseline

Determine a representative paragraph font size.

Prefer a deterministic policy such as:

```text
weighted dominant span size
or
median over meaningful text spans
```

Avoid tiny punctuation/superscript spans skewing the value.

Footnote markers and superscript citations must not incorrectly define paragraph font size.

Document the chosen algorithm.

---

# Color

Preserve source text color as normalized RGB.

If spans contain multiple colors:

- record dominant color;
- record mixed-color evidence;
- do not silently treat mixed paragraphs as uniformly black.

A later renderer ticket may decide how to reproduce mixed inline colors.

---

# Alignment inference

Infer at minimum:

```text
LEFT
CENTER
RIGHT
JUSTIFIED
UNKNOWN
```

Use line/fragment geometry, not text content.

Possible evidence:

```text
stable left edge
stable right edge
short final line
centered line centers
page/body-region width
```

Be conservative.

For one-line headings, centered vs left may be inferred when geometry is clear.

For ambiguous paragraphs return `UNKNOWN`.

---

# Line height / line spacing

Estimate line height from source line/baseline geometry where sufficient evidence exists.

Do not confuse:

```text
font size
line box height
baseline distance
```

Store a clear unit.

Recommended output where safely derivable:

```text
line_height_points
line_height_ratio
```

For one-line paragraphs, use `UNKNOWN` unless another same-style source provides reliable evidence.

---

# Indentation

Infer:

```text
first_line_indent
left_indent
right_indent
```

relative to the reconstructed paragraph/body region where possible.

Required distinction:

```text
first line starts further right
≠
whole paragraph left indent
```

Use geometry from paragraph lines/fragments.

Do not infer first-line indent from a single-line paragraph.

---

# Paragraph spacing

Estimate paragraph spacing from neighboring paragraph geometry only when ordering is reliable.

Avoid double-counting the same vertical gap as both:

```text
space_after(previous)
and
space_before(current)
```

Choose and document one canonical representation.

For PDFTR-27 a simple baseline is acceptable, for example:

```text
observed_gap_before
```

and defer normalized before/after style resolution to PDFTR-28.

---

# Paragraph role

Use existing semantic evidence from `ParagraphKind`.

Map at minimum:

```text
BODY
HEADING
FOOTNOTE
OTHER/UNKNOWN
```

Do not invent heading levels in PDFTR-27 unless reliable source evidence already exists.

If heading-level evidence is discovered, document it but keep implementation conservative.

---

# Mixed inline styles

Investigate paragraphs containing mixed source spans:

```text
roman + italic
roman + bold
different font names
different sizes
different colors
superscript markers
```

PDFTR-27 must at least detect and report them.

Suggested evidence:

```text
mixed_font_family: bool
mixed_weight: bool
mixed_italic: bool
mixed_font_size: bool
mixed_color: bool
```

Do not flatten away evidence even if the first paragraph baseline uses a dominant style.

Inline run reproduction belongs to a later ticket.

---

# Typography baseline output

Produce a paragraph-level baseline suitable for PDFTR-28.

Conceptual example:

```json
{
  "occurrence_index": 38,
  "paragraph_id": "p0003-b0002",
  "role": "body",
  "source_page": 3,
  "font": {
    "value": "MinionPro-Regular",
    "confidence": "high",
    "source": "source_span"
  },
  "font_size": {
    "value": 10.5,
    "confidence": "high",
    "source": "source_span"
  },
  "alignment": {
    "value": "justified",
    "confidence": "medium",
    "source": "line_geometry"
  },
  "first_line_indent": {
    "value": 14.2,
    "confidence": "medium",
    "source": "paragraph_geometry"
  }
}
```

Exact serialization may differ.

---

# Storage / schema decision

Investigate whether typography evidence belongs:

### Option A
Directly inside schema 1.3 paragraph models.

### Option B
In a new optional schema-compatible document section.

### Option C
Derived at rendering time and retained only in diagnostics/cache.

### Option D
Another source-verified design.

Prefer not to bump schema unless persistence provides clear value.

The implementation report must explain the decision.

If schema changes:

- preserve backward compatibility;
- update serialization tests;
- update cache/resume compatibility deliberately;
- do not silently invalidate prior artifacts.

---

# Production API

Expose a deterministic service/function, conceptually:

```text
extract_typography_evidence(document, source_pdf)
```

or equivalent.

It should operate independently of Typer.

Rendering must not be required just to inspect typography.

---

# Diagnostics

Extend diagnostics so typography evidence can be inspected.

At minimum per logical occurrence expose:

```text
role
source font
font size
bold
italic
color
alignment
line height
indent evidence
spacing evidence
confidence/provenance
mixed-style flags
```

Avoid dumping excessively verbose raw span data into normal reports.

Detailed evidence may live in debug/diagnostic mode if appropriate.

---

# Developer inspection command

A small developer-facing command/script is allowed and preferred.

For example:

```powershell
uv run python -m scripts.typography_inspect ...
```

It should allow inspection of:

```text
occurrence index
page
paragraph ID
source text preview
typography baseline
confidence
```

Do not add a public end-user CLI option unless clearly necessary.

---

# Robitzsch baseline

Run the extractor against the real Robitzsch artifact.

Produce compact evidence for representative occurrences from:

```text
page 1
page 3
page 4
```

Include at least:

```text
2 body paragraphs
1 heading if available
2 footnotes
1 mixed-style paragraph if available
```

Record actual evidence rather than manually entering expected values.

---

# Source-vs-baseline verification

For selected representative paragraphs:

1. inspect raw PyMuPDF source spans/lines;
2. inspect reconstructed `LogicalParagraph`;
3. inspect generated typography evidence;
4. verify the baseline matches the source evidence;
5. render source page to PNG for human comparison where useful.

The report must distinguish properties that are:

```text
direct
inferred
unavailable
ambiguous
```

---

# Deterministic tests

Add tests for at least:

### 1. Dominant font size
Paragraph with several same-size spans and one small superscript. Main font size must win.

### 2. Font name normalization
Subset prefix handling.

### 3. Bold
Explicit bold evidence produces bold=true.

### 4. Italic
Explicit italic evidence produces italic=true.

### 5. Conflicting weight/style
Mixed evidence remains visible.

### 6. Color
Packed source color becomes normalized RGB.

### 7. Left alignment

### 8. Center alignment

### 9. Justified alignment

### 10. Ambiguous alignment
Return unknown rather than guess.

### 11. Line-height inference

### 12. Single-line paragraph
Reduced/unknown line-height confidence.

### 13. First-line indent

### 14. Whole-paragraph indent

### 15. Footnote style
Smaller footnote source size retained.

### 16. Heading style
Heading evidence remains distinct from body.

### 17. Mixed inline style detection

### 18. Duplicate paragraph IDs
Occurrence index remains authoritative.

### 19. Serialization/diagnostics
If evidence is persisted.

### 20. Existing rendering regression
PDFTR-24 rendering remains unchanged.

---

# No rendering regression

PDFTR-27 must not materially alter production PDF layout.

Run existing body/footnote rendering tests.

The real Robitzsch output should remain publishable.

Compare key completeness metrics before/after:

```text
required occurrences
overflow
unplaced text
final page count
```

They should remain unchanged unless a separate bug is explicitly discovered.

---

# Performance

Typography extraction must be cheap relative to translation/rendering.

Avoid:

- reopening the PDF once per paragraph;
- raster analysis for every typography property;
- OCR;
- model inference;
- web font lookup;
- external font downloads.

Prefer one source-PDF pass with cached page/span evidence.

---

# ProjectWiki

Before implementation read/search affected typography/rendering knowledge.

After implementation document:

```text
typography evidence architecture
confidence/provenance model
source font identity
alignment inference
line-height inference
indentation evidence
mixed-style limitations
```

Update only affected pages and Wiki log.

Run:

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

---

# Required artifacts

Create:

```text
.implementation-plans/investigation-PDFTR-27.md
.implementation-plans/implementation-plan-PDFTR-27.md
.implementation-reports/implementation-report-PDFTR-27.md
reviews/review-PDFTR-27.md
```

Add/update appropriate architecture documentation, for example:

```text
docs/typography-evidence.md
```

Update:

```text
CHANGELOG.md
affected ProjectWiki pages
```

README only if a developer-facing command is worth documenting.

---

# Quality gates

Run focused tests first, then:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src
.\scripts\check.ps1
```

Run Wiki lint.

Update CRG.

Refresh Graphify if model/module boundaries change materially.

---

# Acceptance criteria

PDFTR-27 is complete when:

- production has a typed typography-evidence model;
- occurrence index remains authoritative;
- body, heading, and footnote typography can be inspected;
- source font identity is captured where available;
- font size baseline is deterministic and resistant to superscript noise;
- bold/italic evidence is captured where supported;
- source color is normalized;
- alignment can be conservatively inferred;
- line-height evidence is available where geometrically supported;
- first-line/left/right indentation evidence is available where supported;
- paragraph spacing evidence is represented without double-counting;
- mixed inline styles are detected and preserved as evidence;
- every property has confidence/provenance or equivalent explicit uncertainty;
- unknown properties remain unknown instead of guessed;
- no production rendering regression is introduced;
- real Robitzsch typography evidence is collected and reviewed;
- representative raw-source vs baseline comparisons are documented;
- full repository quality gate passes;
- docs and ProjectWiki describe the typography baseline and limitations;
- the resulting model is suitable as the input contract for PDFTR-28 style reconstruction.
