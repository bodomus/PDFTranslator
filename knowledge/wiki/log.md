---
title: ProjectWiki knowledge change log
type: log
status: active
created: 2026-09-17
updated: 2026-09-23
tags:
- project-wiki
- log
sources:
- ../../Tickets/PDFTR-19.md
- ../../Tickets/PDFTR-20-strict-render-completeness.md
related:
- index.md
---

# ProjectWiki knowledge change log

This records meaningful knowledge-base changes, not every Git commit or formatting edit.

## 2026-09-23

- Activated reconstructed typography for production BODY reflow by occurrence index, including
  shared CSS measurement/insertion, physical alignment, indents, one-time spacing, applied-style
  diagnostics, and explicit deferred bold/italic variants without changing heading or footnote
  style selection.
- Added the paragraph style reconstruction boundary: robust role baselines, direct/role/document/
  default precedence, traceable fallbacks, conservative font grouping, one-gap spacing, retained
  mixed-style evidence, Robitzsch stability findings, and the inactive PDFTR-29 renderer boundary.
- Documented the derived paragraph-occurrence typography baseline: direct span/font evidence,
  categorical confidence and provenance, conservative alignment/line-height/indent/spacing
  inference, mixed-style flags, Robitzsch findings, and the explicit no-renderer-change boundary.

## 2026-09-22

- Extended the production reflow architecture with ordered footnote groups, source-region-first
  placement, bounded dedicated continuation pages, one body/footnote page map, pre-mutation
  collision checks, separator/anchor preservation, and footnote-specific diagnostics.
- Recorded the controlled Robitzsch result: all 61 required occurrences are terminally placed,
  the prior 21 footnote overflows are zero, and one body plus four footnote continuation pages
  produce a nine-page output with zero unplaced text.

## 2026-09-18

- Promoted single-column body/heading reflow into production with conservative eligibility,
  Strategy A inserted continuation pages, baseline-safe exact segments, anchor protection,
  segment-local validation, and explicit footnote/unsupported-layout limits.
- Hardened PDFTR-22 post-save validation from region-wide substring checks to padded
  segment-target clips, preventing duplicate text elsewhere in a region from masking a missing
  placement.
- Added the PDFTR-22 body-text reflow architecture, typed region/continuation model, hybrid page
  strategy, Robitzsch PoC evidence, explicit footnote boundary, and unsupported-layout policy.
- Completed the three-ticket Phase 1 pilot and selected `keep as-is`: curated source-backed Markdown
  plus lexical search remains useful without semantic-search or automated-ingestion expansion.
- Documented conservative whole-unit and inline foreign-language preservation, glossary and
  protected-token precedence, privacy-safe diagnostics, and translation revision invalidation
  after the PDFTR-21 pilot.

## 2026-09-17

- Created the PDFTranslator Phase 1 ProjectWiki structure and curated navigation.
- Documented maintenance, provenance, Markdown, validation, and pilot-evaluation rules.
- Added dependency-free lint and lexical-search tooling to the repository quality workflow.
- Documented schema 1.3 rendering completeness, explicit per-unit terminal states, and fail-closed
  overflow publication after the PDFTR-20 pilot.
