# PDFTR-41 — List-marker fidelity on shared layout contract

## Summary

Implement end-user list-marker fidelity on top of the shared list layout infrastructure introduced by PDFTR-39.

PDFTR-39 established the architecture-level contract for:

```text
marker_text
marker_x
content_x
semantic_text
```

through the shared reflow pipeline.

PDFTR-41 now connects real source list evidence to that contract and delivers the original product behavior:

```text
source marker preserved
semantic text translated independently
source-backed marker/content geometry preserved
continuation lines aligned correctly
pagination safe
saved PDF validated
```

This ticket must use the existing shared reflow infrastructure. Do not reintroduce workaround layers from earlier stopped list-marker attempts.

## Goal

For confidently recognized list items in the source PDF, preserve marker identity, marker position, semantic content origin, and continuation indentation during EN→RU translation and reflow.

Examples:

```text
• Install the package
1. Configure the project
2) Run the command
a) Optional step
A. Notes
```

Translated output must preserve the source structural marker while translating semantic content only.

## Architecture baseline

PDFTR-41 must consume the existing shared list-layout contract from PDFTR-39.

```text
source PDF
    owns marker identity and source geometry

translation provider
    owns semantic translation only

shared reflow pipeline
    owns measurement, pagination, insertion and validation
```

Do not create a second list renderer, planner, paginator, validator, or post-processing path.

## Required behavior

### 1. Detect supported source list markers

Recognize only confidently supported structural markers.

At minimum consider:

```text
•
-
–
*
1.
1)
a)
A.
```

Detection must be source-evidence-based, not provider-output-based.

### 2. Separate structural marker before translation

Once a list item is confidently recognized, `marker_text` remains structural metadata and the provider receives semantic content only.

Example:

```text
source:
1. Configure the project

provider input:
Configure the project

structural metadata:
marker_text = "1."
```

The provider must not be responsible for reproducing numbering/bullets.

### 3. Preserve semantic lookalikes

Ordinary semantic text that resembles a list marker must remain intact.

Examples:

```text
A. Smith
1.5 mm
3.14
```

Do not strip these unless source evidence independently proves a structural list marker.

No broad regex-only destructive prefix removal.

### Clarification: provider marker replacement for source-confirmed list items

For source-confirmed list items, it is explicitly allowed to replace
a provider-added or provider-changed list marker with the marker derived
from the source/shared layout contract.

Example:

```text
source: 1. Configure project
provider output: 2. Настройте проект
final: 1. Настройте проект
```

This is not considered forbidden translated-prefix stripping when the
block is already confirmed by the source/shared layout contract to be a
list item.

Do NOT apply this rule to ordinary text or semantic prefixes such as:

- A. Smith
- 1.5 mm
- 3.14

### 4. Build ListLayoutContract from source evidence

For each confidently recognized list item, construct the shared contract using actual source geometry:

```text
marker_text
marker_source_rect
content_source_rect
```

Derived `marker_x` and `content_x` must come from source evidence, not guessed widths.

If evidence is missing, contradictory, non-finite, overlapping, or otherwise unsupported, fail closed or retain existing fallback behavior.

### 5. Geometry

Semantic content must begin at source-backed `content_x`.

Structural marker must remain at source-backed `marker_x`.

Wrapped semantic lines must align to `content_x`, not `marker_x`.

Marker placement must not move because semantic alignment is LEFT/CENTER/RIGHT/JUSTIFIED.

Do not emulate hanging indentation with spaces or tabs.

### 6. Pagination

If a list item spans pages:

```text
marker appears once
marker belongs only to first logical occurrence
continuation pages contain semantic continuation only
```

Use the existing PDFTR-39 structural-fragment ownership.

### 7. Marker fit

Marker fit must be measured using the shared measurer and actual structural region.

Do not guess glyph widths, measure with mismatched font assumptions, add fake separation spaces, or use hard-coded padding as marker width.

If the marker cannot safely fit its source-backed region, fail closed/fallback.

Measurement and insertion must agree.

### 8. Translation and inline styles

Semantic inline styles must continue to work.

Structural marker identity must not be mixed into semantic inline-run offsets.

Do not regress PDFTR-32 inline-style behavior.

### 9. Saved-PDF validation

Use the typed output occurrence model introduced by PDFTR-39.

Validation must detect at least:

```text
missing structural marker
duplicate structural marker
marker on continuation page
missing semantic content
```

Validation must use local target rectangles and deterministic occurrence identity.

Do not accept a marker found elsewhere on the page as proof that the correct marker was rendered.

## Ambiguity policy

List reconstruction must remain fail-closed.

If source evidence cannot clearly distinguish structural marker from semantic prefix, do not silently alter semantic text.

Prefer existing fallback behavior over incorrect structural reconstruction.

## Detection constraints

Detection may use source text spans/lines/rectangles already available in extraction/reconstruction.

It should consider combinations of:

```text
token form
line structure
spatial separation
source span rectangles
paragraph geometry
neighboring list evidence where available
```

A regex may be one signal, but structural classification must remain evidence-backed.

## Forbidden approaches

Do not introduce:

```text
HTML tables
inline-block layout hacks
manual spaces/tabs
post-render x patches
hard-coded glyph-width guesses
provider-specific marker reconstruction
translated-prefix stripping
second renderer
second planner
second pagination path
page-global marker validation
silent clipping
```

## Investigation

Before implementation, create:

```text
.implementation-plans/investigation-PDFTR-41.md
```

Answer at least:

1. Where is the earliest reliable source representation that still has marker/content spatial evidence?
2. Which existing extraction/reconstruction objects expose marker and semantic rectangles?
3. What exact evidence will classify a prefix as structural rather than semantic?
4. Which marker forms will be supported?
5. Which ambiguous forms will deliberately fall back?
6. Where should marker removal from provider input occur?
7. How will semantic inline-style offsets be adjusted after structural marker separation?
8. How will `ListLayoutContract` be populated without guessed widths?
9. How will source marker/content evidence survive to `FlowParagraph`?
10. How will measurement and insertion share identical geometry/font assumptions?
11. How will duplicate/missing/continuation marker validation work using `OutputOccurrence` identity?
12. Which existing tests protect BODY/HEADING/FOOTNOTE typography?
13. Which existing tests protect inline styles and semantic prefixes?
14. What production files need to change?
15. What is the smallest implementation that enables real list fidelity without expanding shared architecture again?

Do not implement before investigation is complete.

## Required tests

Add deterministic tests for at least:

```text
bullet marker detection and preservation
numbered marker detection and preservation
letter marker detection and preservation
marker separated before provider call
provider input contains semantic text only
provider-restyled marker cannot duplicate source marker
marker not lost
marker not duplicated
marker absent from continuation pages
semantic "A. Smith" preserved
semantic "1.5 mm" preserved
semantic "3.14" preserved
styled semantic prefix preserved
first-line content begins at content_x
continuation lines begin at content_x
marker remains at marker_x for LEFT
marker remains at marker_x for CENTER
marker remains at marker_x for RIGHT
wide marker/content gap
narrow but valid gap
marker-too-wide fail-closed behavior
invalid geometry fail-closed behavior
ambiguous prefix fallback
multi-page list item
saved PDF missing marker rejection
saved PDF duplicate marker rejection
saved PDF continuation-marker rejection
ordinary non-list paragraph regression
BODY typography regression
HEADING regression
FOOTNOTE regression
inline-style regression
```

Use real PyMuPDF saved-PDF probes for geometry-sensitive behavior.

No real translation provider calls.

## Provider boundary tests

Use a fake provider that deliberately returns misleading list-like prefixes.

Example:

```text
source marker: 1.
semantic source: Configure the project

fake provider returns:
2. Настройте проект
```

Expected output:

```text
1. Настройте проект
```

without duplicate/provider-owned structure.

Also verify that semantic content such as `A. Smith` and `1.5 mm` is not stripped or reclassified incorrectly.

## Compatibility

Existing documents without recognized list evidence must behave exactly as before.

Existing serialized artifacts must remain compatible unless investigation proves a revision bump is unavoidable.

Do not invalidate caches/artifacts merely because list detection was added.

## Workflow

For this ticket:

```text
implementer = Codex
reviewer    = Codex
```

Separate processes/contexts.

Use the merged PDFTR-40 reviewer Git-read capability.

Recommended:

```powershell
uv run python scripts/pi_ticket_cycle.py PDFTR-41 --preset codex-codex
```

The reviewer must independently verify:

```text
HEAD
clean status
exact implementation SHA
expected base SHA
diff
merge-base
```

through the constrained Git-read tool.

Maximum automatic review rounds: 2.

No auto-merge.

## Reviewer focus

The reviewer must explicitly verify:

```text
1. Marker detection is source-evidence-based.
2. Structural marker is removed from provider input before translation.
3. Semantic lookalikes remain intact.
4. Real source geometry populates ListLayoutContract.
5. No guessed marker width/spacing exists.
6. First-line and continuation geometry use content_x.
7. Marker placement stays source-owned across alignments.
8. Marker ownership is first-occurrence-only across pagination.
9. Saved validation catches missing/duplicate/continuation markers.
10. Inline-style offsets remain correct after marker separation.
11. Existing non-list/typography behavior remains unchanged.
12. No second renderer/planner/pagination/validation path exists.
13. No workaround from earlier stopped list-marker attempts reappears.
```

## Quality gate

Run:

```powershell
uv run pytest
uv run python scripts/project_wiki/wiki_lint.py
.\scripts\check.ps1
```

Required:

```text
ruff format/check: PASS
mypy: PASS
full pytest: PASS
coverage threshold: PASS
Windows CI: PASS
Ubuntu CI: PASS
working tree: clean
```

## Completion criteria

PDFTR-41 is complete when:

```text
real source list evidence is recognized conservatively
marker identity is source-owned
provider receives semantic text only
provider cannot redefine marker structure
semantic lookalikes are preserved
ListLayoutContract uses real source geometry
first-line content begins at content_x
continuation lines align at content_x
marker remains at marker_x
marker fit is measured consistently
marker appears once across pagination
missing/duplicate/continuation markers are rejected in saved validation
inline styles remain correct
ambiguous cases fail closed
ordinary paragraphs remain unchanged
no workaround layout path is introduced
full local gate passes
Windows CI passes
Ubuntu CI passes
exact-SHA read-only review returns PASS
```

Final merge remains a human decision.

## After PDFTR-41

After PDFTR-41 is merged, move the handoff boundary from local `.agent-cycle` coordination to GitHub Pull Requests:

```text
Codex implementer
→ branch + commit + push
→ GitHub PR
→ CI
→ ChatGPT Work independent review
→ human merge
```

That workflow is intentionally out of scope for PDFTR-41 and should be designed as the next infrastructure step.
