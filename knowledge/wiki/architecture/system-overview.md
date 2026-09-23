---
title: PDFTranslate system overview
type: architecture
status: active
created: 2026-09-17
updated: 2026-09-22
tags:
- architecture
- pipeline
- cli
sources:
- ../../../README.md
- ../../../pyproject.toml
- ../../../.codex/PRE_TICKET_WORKFLOW.md
- ../../../src/pdftranslate/rendering/renderer.py
- ../../../src/pdftranslate/translation/foreign_language.py
related:
- ../overview.md
- ../workflows/development-workflow.md
- ../failure-modes/render-completeness.md
- ../components/foreign-language-preservation.md
- reflow-layout.md
- style-reconstruction.md
---

# PDFTranslate system overview

PDFTranslate uses a `src/pdftranslate` package with a Typer/Rich CLI and domain logic kept outside
the CLI boundary. PyMuPDF owns PDF inspection, extraction, rendering, and validation adapters;
local NLLB translation is isolated behind translation modules; OCRmyPDF/Tesseract are optional
external preprocessing dependencies.

Before NLLB inference, paragraph translation conservatively preserves confidently Latin/Greek
whole units and protects selected foreign-language spans inside English prose. The explicit
classification, evidence, and cache compatibility rules are documented in
[Foreign-language preservation](../components/foreign-language-preservation.md).

## Main processing flow

The root command orchestrates six user-visible stages:

1. inspect the immutable source PDF;
2. decide and optionally run OCR;
3. extract typed layout-aware content;
4. translate logical text through a reusable local backend and cache;
5. render into a workspace candidate;
6. validate and atomically publish the final PDF.

For schema 1.3, stage 5 first plans and accounts for every logical paragraph occurrence. Required
overflow fails before PDF mutation or candidate creation; see
[Rendering completeness](../failure-modes/render-completeness.md).

PDFTR-23 and PDFTR-24 compose production body and footnote reflow with the fixed-layout renderer.
One layout plan maps confidently classified occurrences to exact ordered continuation segments and
one final page map. Each source page is followed by its bounded body continuations and then its
bounded footnote continuations; see [Body and footnote reflow architecture](reflow-layout.md).
Unsafe or unclassified layouts remain fixed only when complete, and required overflow remains
fail-closed.

Typography processing has two derived, cache-independent domain stages: source evidence and
role-aware style reconstruction. The latter records deterministic renderer-facing decisions but is
not yet connected to production rendering; see
[Paragraph style reconstruction](style-reconstruction.md).

Batch processing reuses the translation backend/cache while retaining a separate source-derived
workspace per document. Advanced inspect, extract, translate, render, benchmark, and validation
entry points share the same underlying modules.

## Safety boundaries

- The source PDF is never overwritten.
- Partial or invalid output is not published under the requested final name.
- Unit tests use fakes or mocks and do not download model weights or require CUDA/OCR.
- Cache/resume compatibility is tied to source identity and behavior-affecting settings.
- Windows 11 and PowerShell remain primary development targets; CI also validates Linux.

This page is intentionally high-level. Consult current source, tests, the README, and ticket-specific
reports before changing a pipeline stage.
