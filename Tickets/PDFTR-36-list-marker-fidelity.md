# PDFTR-36 — List marker fidelity in translated reflow

## Summary

Preserve source list markers and list indentation when translated paragraphs are rendered back into the PDF.

This is a real PDFTranslator product task, not orchestration work.

The objective is to prevent translated bulleted and numbered list items from losing, duplicating, translating, or visually detaching their structural marker.

## Problem

PDFTranslator already reconstructs and reflows translated BODY / HEADING / FOOTNOTE text with source-aware typography.

List items are still vulnerable because the marker can be treated as ordinary paragraph text.

Typical source examples:

```text
• Install the package.
• Restart the application.

1. Open Settings.
2. Select Export.

a) First option
b) Second option

– Important note
```

A translation model may:

```text
translate the marker
delete the marker
duplicate the marker
replace it with a different marker
move it away from the first rendered line
change numbering punctuation
```

Long translated text can also wrap so that continuation lines no longer respect the list item's source indentation.

The renderer must preserve list structure independently of translation-model behavior.

## Goal

For safe, supported list items:

```text
source structural marker
+
translated semantic content
+
source-derived list indentation
```

must render as one coherent list item.

The structural marker is source-owned and must not depend on the translated text returned by the model.

## Scope

Implement safe list-marker fidelity for translated reflow.

Initial supported marker families:

```text
• text
● text
○ text
▪ text
- text
– text
— text
* text

1. text
1) text
(1) text

a. text
a) text
(a) text

A. text
A) text
(A) text
```

Roman numerals are out of scope for this ticket unless the existing parser already exposes them with no additional heuristic complexity.

Support applies only when the marker can be identified confidently at the beginning of one logical paragraph.

## Required behavior

### 1. Detect source list marker

Detect the structural marker from the source paragraph before translation/reflow.

Store enough information to reproduce it without relying on translated text.

At minimum preserve:

```text
marker text
marker family
source paragraph identity / occurrence
marker-to-content separation
list indentation geometry when available
```

Do not infer a list marker from translated text alone.

### 2. Separate marker from translatable content

For a supported list item:

```text
SOURCE:
"2. Install the package."

TRANSLATABLE CONTENT:
"Install the package."

STRUCTURAL MARKER:
"2."
```

The marker itself must not be semantically translated.

If the current translation pipeline cannot safely remove the marker before provider invocation without broad changes, an acceptable alternative is:

```text
translate using current flow
discard any translated marker representation
reconstruct the final visible marker from source-owned structure
```

Whichever approach is used must be deterministic and covered by tests.

Do not duplicate the marker.

### 3. Preserve exact source marker form

Examples:

```text
1.  → 1.
1)  → 1)
(1) → (1)

a.  → a.
A)  → A)

•   → •
–   → –
```

Do not normalize all bullets to one glyph.

Do not renumber items.

Do not change punctuation style.

### 4. Preserve list indentation

The first rendered line must preserve the relationship between:

```text
left list edge
marker position
content start
```

Continuation lines should align with the source list content start where source geometry provides enough evidence.

Conceptually:

```text
• First translated line starts here and may be long
  continuation line aligns with content, not with bullet
```

not:

```text
• First translated line starts here and may be long
continuation line jumps back to the bullet edge
```

Reuse existing paragraph typography / indent geometry where possible.

Do not invent a second independent layout system.

### 5. Fail closed on ambiguity

If the prefix cannot be classified confidently as a supported list marker, preserve existing behavior.

Examples that must not be aggressively reinterpreted:

```text
2026. Annual report
3.14 is pi
A. Smith
-5 °C
12.5 mm
```

Avoid broad regexes that classify ordinary prose/numeric prefixes as lists.

Prefer false negatives over destructive false positives.

### 6. Pagination and continuation

A list item may span multiple rendered lines or pages.

The marker appears only once, on the first rendered line of that logical list item.

Do not repeat the marker on continuation pages unless the existing renderer already has an explicit source-backed semantic reason to do so.

Existing overflow, continuation, clipping, completeness, and saved-PDF validation rules remain authoritative.

### 7. Typography

Marker typography should reuse source-backed paragraph typography where safe.

Do not synthesize a new font family.

Do not redesign inline-style handling.

If the source marker is part of an inline-style run, prefer the smallest safe integration with existing style-run logic.

If exact marker styling cannot be preserved safely, preserve the marker text and geometry first; document the limitation.

## Architecture constraints

Reuse existing concepts where possible:

```text
paragraph occurrence identity
role-aware BODY / HEADING / FOOTNOTE mapping
source-backed typography
measurement
reflow planning
continuation handling
saved-PDF validation
diagnostics
```

Do not create a separate list renderer unless investigation proves it is necessary.

Do not duplicate measurement or insertion logic already present in production reflow.

## Diagnostics

Expose enough structured diagnostics to understand whether list-marker handling was applied.

Add minimal counters, for example:

```text
list_marker_candidates
list_markers_applied
list_markers_deferred
```

If the project already has a more appropriate diagnostics naming pattern, follow it.

Diagnostics must not contain sensitive translated content.

Human-readable reporting is optional unless the existing reporting path makes the addition trivial.

Do not introduce a diagnostics schema break unless unavoidable.

## Investigation

Before implementation, create:

```text
.implementation-plans/investigation-PDFTR-36.md
```

Answer briefly:

1. Where are logical paragraphs finalized before translation?
2. Where is paragraph occurrence identity assigned?
3. Where are BODY / HEADING / FOOTNOTE indentation values reconstructed?
4. Where does translated paragraph text enter production reflow?
5. Can source marker metadata be attached without changing public schemas?
6. Can the marker be removed before translation safely?
7. If not, where can translated markers be discarded deterministically?
8. How are hanging indents currently represented?
9. Which measurement/insertion path should own marker width?
10. How do inline style runs interact with the first characters of a paragraph?
11. Which existing saved-PDF validation can verify marker presence?
12. What is the minimum coherent file set for this change?

Do not implement before investigation is complete.

## Acceptance criteria

### Basic bullet preservation

Given:

```text
• Install the package.
```

and a translated semantic result equivalent to:

```text
Установите пакет.
```

the rendered item contains exactly one source bullet:

```text
• Установите пакет.
```

### Exact numbering preservation

Given:

```text
2) Restart the application.
```

the output preserves exactly:

```text
2)
```

as the marker.

The translation provider must not be able to change it to:

```text
2.
(2)
3)
```

### Translation attempts to duplicate marker

If translated text comes back as:

```text
2) 2) Перезапустите приложение.
```

the final rendered structure still contains only one structural source marker.

### Translation attempts to remove marker

If translated text comes back without a marker, the final rendered item still contains the source marker.

### Wrapped item indentation

For a long translated list item, continuation lines align to the source-derived content indentation rather than the marker edge.

### Multiple marker families

Regression tests must cover at least:

```text
•
-
–
1.
1)
(1)
a.
A)
```

### Non-list false positives

Tests must prove these are not treated as list markers solely because of their prefix:

```text
2026. Annual report
3.14 is pi
-5 °C
12.5 mm
```

Add any additional ambiguity cases discovered during investigation.

### Existing behavior preserved

Non-list paragraphs render identically to the previous behavior.

No regression to:

```text
BODY typography
HEADING typography
FOOTNOTE typography
inline styles
overflow/completeness
saved-PDF validation
diagnostics privacy
```

## Tests

Add focused unit/integration tests for:

```text
marker detection
marker family preservation
marker/content separation
provider-deleted marker
provider-duplicated marker
wrapped hanging indentation
multi-page continuation if relevant to current architecture
ambiguous-prefix fail-closed behavior
BODY path
at least one non-BODY role if list items are supported there
diagnostic counters
saved output contains exactly one marker
```

Prefer source-backed fixtures already used by reflow tests.

Do not call a real translation provider.

## Quality gate

Run the repository-standard focused tests plus:

```powershell
uv run pytest
uv run python scripts/project_wiki/wiki_lint.py
.\scripts\check.ps1
```

Windows and Ubuntu CI must pass.

## Non-goals

Do not add:

```text
automatic list renumbering
nested-list semantic reconstruction
Roman-numeral heuristics
Markdown conversion
OCR-specific list detection
new translation provider behavior
new orchestration behavior
Pi changes
agent-cycle changes
GUI changes
automatic table/list reconstruction
```

Do not refactor unrelated reflow code.

## Implementation principle

Prefer:

```text
source structure → deterministic marker metadata → existing reflow
```

over:

```text
guess structure from translated text
```

The translated model output owns semantic text.

The source PDF owns the list marker and source-backed geometry.

## Completion

PDFTR-36 is complete when supported source list items:

```text
retain exactly one original marker
retain source marker form
retain safe list indentation
survive translation-model marker changes
fail closed on ambiguous prefixes
pass full regression and CI gates
```

No merge is automated. Final merge remains a human decision.
