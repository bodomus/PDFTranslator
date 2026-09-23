---
title: PDFTranslator Knowledge Base
type: index
status: active
created: 2026-09-17
updated: 2026-09-23
tags:
- project-wiki
- navigation
sources:
- ../../Tickets/PDFTR-19.md
related:
- overview.md
- architecture/system-overview.md
- workflows/development-workflow.md
---

# PDFTranslator Knowledge Base

This is the curated entry point for durable project knowledge. Current source, tests, configuration,
canonical reports, and runtime evidence remain authoritative.

## Start here

- [Overview](overview.md) — purpose, boundaries, and how agents use ProjectWiki.
- [System architecture](architecture/system-overview.md) — verified high-level PDFTranslate flow.
- [Development workflow](workflows/development-workflow.md) — ticket and quality-gate sequence.
- [Wiki maintenance](workflows/wiki-maintenance.md) — when and how to update knowledge.

## Architecture

- [System overview](architecture/system-overview.md)
- [Body-text reflow architecture](architecture/reflow-layout.md) — typed regions, paragraph
  continuations, hybrid page creation, preserved anchors, and explicit unsupported layouts.
- [Typography evidence architecture](architecture/typography-evidence.md) — source-backed paragraph
  style evidence, confidence/provenance, geometry inference, and mixed-style limits.

## Components

- [Foreign-language preservation](components/foreign-language-preservation.md) — conservative
  whole-unit and inline-span preservation across translation, glossary, cache, and diagnostics.
- [Rendering completeness](failure-modes/render-completeness.md) — strict schema 1.3 paragraph
  accounting and fail-closed overflow behavior.

## Workflows

- [Development workflow](workflows/development-workflow.md)
- [Wiki maintenance](workflows/wiki-maintenance.md)

## Decisions and constraints

- [Wiki as Markdown](decisions/wiki-as-markdown.md)
- [Raw sources are immutable](constraints/raw-sources-immutable.md)

## Known issues

- Fixed-layout rendering can be unable to fit required translated paragraphs. See
  [Rendering completeness](failure-modes/render-completeness.md) for the enforced fail-closed
  behavior and [Body-text reflow architecture](architecture/reflow-layout.md) for the proven
  single-column body-flow direction and its footnote boundary.

## Testing

- [Wiki validation](testing/wiki-validation.md)
- [Phase 1 pilot evaluation](testing/pilot-evaluation.md)

## Integrations

The Wiki integrates with the existing local and CI quality gates through its lint command; details
are kept in [Wiki validation](testing/wiki-validation.md).

## History

- [Knowledge change log](log.md)
