---
title: Rendering completeness
type: failure-mode
status: active
created: 2026-09-17
updated: 2026-09-17
tags:
- rendering
- paragraphs
- overflow
- output-validation
- content-completeness
sources:
- ../../../Tickets/PDFTR-20-strict-render-completeness.md
- ../../../src/pdftranslate/rendering/models.py
- ../../../src/pdftranslate/rendering/renderer.py
- ../../../tests/test_rendering.py
related:
- ../architecture/system-overview.md
- ../architecture/reflow-layout.md
- ../testing/pilot-evaluation.md
---

# Rendering completeness

Schema 1.3 rendering is fail-closed at the logical-paragraph boundary. Planning must account for
every paragraph occurrence in document order; paragraph IDs alone are not unique because split
source blocks and marker/pass-through paragraphs may share an ID.

## Invariant

Every logical paragraph reaches one explicit terminal state:

- `rendered` for a required `TRANSLATE` unit that fits and is inserted;
- `preserved` for `PRESERVE` content retained from the source;
- `excluded_by_policy` for `SKIP` or `REMOVE` content intentionally omitted from translation;
- `overflow` or `failed` for a required unit that cannot reach a valid rendered state.

A render may be published only when every `TRANSLATE` occurrence is `rendered`. Policy-excluded
states are complete by policy and do not create false failures. An unresolved required overflow
raises a rendering error before redaction, insertion, saving, or pipeline publication.

## Diagnostics

Completeness errors identify the paragraph ID and occurrence index, page, terminal state,
source/final bounding boxes, selected and minimum font sizes, fitting attempts, expansion flag,
and translated character count. Normal messages do not include full document text. Debug mode may
write a separate failed-layout PDF; it never writes a partial translation to the requested output.

## Relationship to saved-PDF validation

Completeness planning answers whether every required logical paragraph reached a valid render
state. The PDFTR-18 saved-PDF check remains a separate later invariant: it reopens the candidate
and verifies that planned Cyrillic render units survived PDF serialization in their local regions.
Neither check substitutes for the other.

## Evidence and boundary

The Robitzsch regression contained 61 logical paragraphs under the current schema 1.3 artifact.
Replaying the production fixed-layout planner produced 40 rendered and 21 overflow occurrences;
the overflow units matched the missing regions observed on pages 1, 3, and 4. PDFTR-22 later
source-verified that all 21 current overflow occurrences are classified as footnotes; all 26 body
occurrences render under the shrink-to-fit policy. PDFTR-20 correctly rejects the incomplete result.
The production [Body-text reflow architecture](../architecture/reflow-layout.md) adds exact
cross-page segments for confidently classified body/heading occurrences. Its zero-unplaced plan and
segment-local saved checks compose with this gate; footnote pagination deliberately remains
fail-closed.
