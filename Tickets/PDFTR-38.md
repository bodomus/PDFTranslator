# PDFTR-38 — List marker fidelity

## Summary

Preserve source PDF list markers, numbering, and list indentation during translated reflow.

This is a clean product-task implementation from the current `master`.

The implementer must solve the task from the requirements and current repository architecture.
Do not use or rely on implementation details, review findings, or follow-up approaches from prior stopped list-marker experiments.

## Goal

Translated list items should retain the source document's structural list presentation where it can be reconstructed safely.

Examples:

```text
• Install the package
1. Configure the project
2) Run the command
a) Optional step
A. Notes
```

After translation:

- the marker identity remains source-owned;
- the translated semantic content follows the marker;
- list indentation and hanging indentation remain visually faithful;
- continuation lines align with the source list content edge;
- unsupported or ambiguous cases fail safely instead of being guessed.

## Required behavior

### 1. Preserve source marker identity

For a confidently recognized list item, preserve the source structural marker.

Common examples include:

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

The translation provider must not become the authority for structural marker identity.

Avoid marker duplication and marker loss.

### 2. Preserve semantic text correctly

Content after the structural marker remains semantic text.

Do not accidentally strip ordinary semantic prefixes that resemble list markers.

Examples that must remain safe where semantic:

```text
A. Smith
1.5 mm
3.14
```

Avoid broad destructive prefix heuristics.

### 3. Preserve list indentation

Where source evidence is sufficient, preserve the relationship between:

```text
marker position
first semantic-content position
continuation-line position
```

Continuation lines should align with the source content edge rather than the marker edge.

Do not manufacture indentation with repeated spaces or tabs.

### 4. Reflow and pagination

List items must remain compatible with the existing shared reflow pipeline:

```text
measurement
fit / overflow decisions
pagination
insertion
saved-PDF validation
```

Do not create a second list-only renderer or planner.

If the source geometry cannot be represented safely, fail closed or retain the existing fixed-layout fallback rather than clipping text.

### 5. Ambiguity must remain fail-closed

Only apply list-specific reconstruction when source evidence is sufficiently confident.

Ambiguous isolated prefixes or text that merely resembles a list item must not silently change semantic content or bypass existing ambiguity protections.

## Architecture requirements

Use the existing PDFTranslator typography/reflow architecture.

Prefer source-backed structural evidence already available from extraction and paragraph reconstruction.

Keep responsibilities clear:

```text
source PDF
    owns marker identity and geometry

translation provider
    owns semantic translation

reflow
    owns measurement, pagination and placement
```

Do not let the translation provider become the authority for source list structure.

## Forbidden approaches

Do not solve the task with:

```text
HTML tables
inline-block layout hacks
manual spaces/tabs for geometry
post-render x-position patches
hard-coded glyph-width guesses
a second list-specific renderer
a second list-specific planner
silent clipping
broad translated-prefix stripping heuristics
provider-specific list hacks
```

If the current architecture cannot support the required behavior safely, document the blocker rather than stacking workaround layers.

## Investigation

Before implementation, create:

```text
.implementation-plans/investigation-PDFTR-38.md
```

Answer at least:

1. Where in extraction/region reconstruction can a structural list marker be identified?
2. What source evidence exists for marker position and semantic-content position?
3. How does the current paragraph/reflow model represent first-line and continuation indentation?
4. Where should structural marker identity live so translation and rendering can share it without circular dependencies?
5. Should the provider receive the marker, semantic content only, or another representation? Why?
6. How will ordinary semantic prefixes such as `A. Smith` and `1.5 mm` remain safe?
7. How will list items participate in the same measurement/overflow logic as ordinary paragraphs?
8. How will first-line and continuation geometry be preserved?
9. How will multi-page continuation behave?
10. How will saved-PDF validation detect missing, duplicated, or clipped list structure?
11. Which ambiguous cases should deliberately fall back to existing behavior?
12. Which existing typography, inline-style, and reflow tests are most likely to regress?
13. Which production files need to change?
14. What is the smallest architecture-consistent implementation?

Do not implement before the investigation is complete.

## Test requirements

Add focused deterministic tests for at least:

```text
bullet marker preservation
numbered marker preservation
letter marker preservation
marker not duplicated
marker not lost
semantic prefix A. preserved when semantic
semantic decimal prefix 1.5 preserved when semantic
first-line list content geometry
continuation-line geometry
wide marker/content indentation
narrow but valid indentation
overflow / pagination
multi-page continuation
saved-PDF validation
ambiguous prefix fail-closed behavior
non-list paragraph regression
BODY typography regression
inline-style regression
```

Use representative real reflow fixtures where geometry matters.

Tests must validate actual saved-PDF behavior where feasible, not only intermediate model values.

Do not call a real translation provider.

## Quality gate

Run focused tests first, then:

```powershell
uv run pytest
uv run python scripts/project_wiki/wiki_lint.py
.\scripts\check.ps1
```

Required before handoff:

```text
ruff format/check: PASS
mypy: PASS
full pytest: PASS
coverage threshold: PASS
Windows CI: PASS
Ubuntu CI: PASS
working tree: clean
```

## Workflow

For this experiment:

```text
implementer = Codex
reviewer    = Codex
```

The two roles must run in separate contexts/processes.

Recommended command after the ticket branch is prepared:

```powershell
uv run python scripts/pi_ticket_cycle.py PDFTR-38 --preset codex-codex
```

The reviewer remains read-only under the existing tool allowlist.

Maximum automatic review rounds remain:

```text
2
```

No auto-merge.

## Experiment integrity

This ticket is intentionally a clean comparison run.

The implementer should work only from:

```text
this ticket
current master
current repository architecture
current tests/documentation
```

Do not feed the implementer prior stopped implementation reports or reviewer findings from earlier list-marker attempts.

The purpose is to measure whether Codex can solve the original product problem more effectively as implementer.

## Completion criteria

PDFTR-38 is complete only when:

```text
supported list markers are preserved
provider cannot redefine structural marker identity
semantic lookalike prefixes are not destroyed
source-backed list indentation is preserved where supported
continuation lines align correctly
measurement and insertion agree
overflow/pagination remain safe
saved PDF is structurally complete
ambiguous cases remain fail-closed
no list-specific side renderer/planner is introduced
existing typography and inline-style behavior remains intact
full local gate passes
Windows CI passes
Ubuntu CI passes
exact-SHA read-only review returns PASS
```

Final merge remains a human decision.
