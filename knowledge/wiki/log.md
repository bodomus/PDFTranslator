---
title: ProjectWiki knowledge change log
type: log
status: active
created: 2026-09-17
updated: 2026-09-18
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
