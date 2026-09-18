---
title: ProjectWiki Phase 1 pilot evaluation
type: testing
status: active
created: 2026-09-17
updated: 2026-09-18
tags:
- project-wiki
- pilot
- evaluation
sources:
- ../../../Tickets/PDFTR-19.md
- ../../../Tickets/PDFTR-20-strict-render-completeness.md
- ../../../Tickets/PDFTR-21-preserve-foreign-language-text.md
- ../../../Tickets/PDFTR-22-reflow-architecture-poc.md
related:
- ../overview.md
- ../decisions/wiki-as-markdown.md
- ../architecture/reflow-layout.md
- ../workflows/wiki-maintenance.md
---

# ProjectWiki Phase 1 pilot evaluation

Evaluate ProjectWiki over the next 2–3 non-trivial PDFTranslator tickets before proposing Phase 2.
Each ticket's implementation report should record:

- ticket ID;
- Wiki pages consulted before implementation;
- whether raw or canonical sources still had to be opened;
- missing or stale Wiki knowledge discovered;
- Wiki pages updated after implementation;
- whether the Wiki prevented an obvious rediscovery of already-known facts;
- whether review exposed a Wiki gap.

Use concrete observations. Do not claim time, token, or percentage improvements unless they were
actually measured.

## Trial results

### PDFTR-22

- Consulted `index.md`, `architecture/system-overview.md`,
  `failure-modes/render-completeness.md`, `components/foreign-language-preservation.md`, and this
  pilot page; searches covered rendering completeness, foreign-language preservation, paragraph
  reconstruction, layout/overflow, and atomic publication.
- The Wiki preserved the occurrence-based completeness, source immutability, publication, and
  foreign-language exactness constraints before the new planner boundary was designed.
- Canonical reconstruction/repeated/rendering/diagnostic/pipeline source, tests, prior reports,
  Graphify/CRG output, the source PDF, and persisted schema 1.3 artifact were still required for
  exact geometry and planner behavior.
- The review exposed a material evidence gap: the Wiki repeated the 40-rendered/21-overflow count
  but did not say that all 21 current overflows are footnotes. Added
  `architecture/reflow-layout.md` and corrected the completeness boundary.
- Visual PDF review found a continuation/baseline collision that extraction checks passed. The
  PoC and architecture now require visual inspection and one-line baseline safety.
- Updated navigation, system overview, completeness, this evaluation, and the Wiki log. No measured
  time or token saving is claimed.

### PDFTR-21

- Consulted `index.md`, `architecture/system-overview.md`,
  `failure-modes/render-completeness.md`, and `testing/pilot-evaluation.md`; lexical searches also
  covered translation, protected tokens, glossary, paragraph reconstruction, rendering
  completeness, and foreign language.
- The Wiki preserved the pipeline/publication boundary and the PDFTR-20 fail-closed rendering
  constraint, so the translation fix did not weaken rendering to obtain a pilot PDF.
- Canonical translation, glossary, cache, reconstruction, diagnostics, tests, CRG/Graphify output,
  and the persisted Robitzsch workspace still had to be inspected for exact behavior.
- The searches exposed a concrete gap: there was no durable page describing foreign-language
  classification, protected-span composition, glossary precedence, or cache compatibility.
- Added `components/foreign-language-preservation.md` and updated navigation, architecture, and
  this pilot record. No measured time or token saving is claimed.
- Review should verify the Wiki against deterministic and real Robitzsch evidence before the
  ticket is closed.

### PDFTR-20

- Consulted `index.md`, `architecture/system-overview.md`, `workflows/development-workflow.md`,
  and `testing/wiki-validation.md` before implementation.
- The Wiki avoided rediscovery of the high-level pipeline/publication boundary and the required
  validation workflow.
- Canonical renderer, pipeline, model, diagnostics, test, and prior PDFTR-17/PDFTR-18 report
  sources still had to be opened to verify paragraph-level behavior.
- The search exposed a concrete gap: no page documented overflow as a content-completeness failure
  mode or defined a document-level render invariant.
- Added `failure-modes/render-completeness.md` and updated navigation and this pilot record.
- Review must verify that the new page stays aligned with the final implementation and real-PDF
  result; no measured time or token saving is claimed.

## Phase 2 decision

Decision: **keep as-is**.

Across PDFTR-20, PDFTR-21, and PDFTR-22, curated source-backed Markdown plus deterministic lexical
search consistently preserved high-level safety boundaries and exposed missing durable knowledge.
Exact implementation and runtime claims still required canonical source and artifact validation,
which is the intended authority model rather than a failure of the Wiki. The pilot does not provide
measured evidence that embeddings, semantic search, MCP, QMD, automated ingestion, or graph
generation would improve this workflow. Continue the current maintenance process and reassess only
when a concrete retrieval failure justifies expansion.
