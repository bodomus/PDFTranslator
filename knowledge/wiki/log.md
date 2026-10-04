---
title: ProjectWiki knowledge change log
type: log
status: active
created: 2026-09-17
updated: 2026-10-04
tags:
- project-wiki
- log
sources:
- ../../Tickets/PDFTR-41.md
- ../../Tickets/PDFTR-40.md
- ../../Tickets/PDFTR-39.md
- ../../Tickets/PDFTR-37.md
- ../../Tickets/PDFTR-35B-windows-process-safety-final-fix.md
- ../../Tickets/PDFTR-35A-orchestrator-safety-follow-up.md
- ../../Tickets/PDFTR-35-pi-sequential-two-agent-runner-mvp.md
- ../../Tickets/PDFTR-34-human-readable-inline-style-diagnostics-summary.md
- ../../Tickets/PDFTR-33-two-agent-ticket-handoff-contract-validator.md
- ../../Tickets/PDFTR-32-safe-inline-style-runs.md
- ../../Tickets/PDFTR-19.md
- ../../Tickets/PDFTR-20-strict-render-completeness.md
related:
- index.md
---

# ProjectWiki knowledge change log

## 2026-10-04

- Preserved lowercase apostrophe name components and mixed prose/name neighbors as complete
  semantic text; separated geometry-backed letter-prefix joining from structural list ownership.

- Expanded source initial/name ambiguity handling for surname qualifiers, lowercase particles and
  compound names; preserved genuine prose letter lists and full semantic provider input.

- Connected conservative source list evidence to semantic-only translation and the shared reflow
  contract; documented source marker restoration, independent inline offsets, unchanged artifact
  versions/cache revision and local missing/duplicate/continuation-marker validation.
- Applied PDFTR-41 review corrections for adjacent semantic initials, owned source continuation
  lines and unresolved-tail fallback, explicit contract markers, and duplicate checks in semantic
  placement rectangles while retaining planned marker-like content.

## 2026-10-03

- Documented pre-subprocess rejection of `.git/commondir` entries after the PDFTR-40 P1 review,
  preserving the fixed Git-directory boundary and explicit unsupported linked-worktree policy.

- Documented constrained reviewer-only Git observability, fixed repository root and helper/filter
  hardening for every Pi preset, without changing state/round/merge ownership.

- Documented optional source-backed structural list metadata in the shared reflow model: independent
  marker/content measurement, first-occurrence ownership, shared insertion/saved-validation identity
  and fail-closed evidence. Detection, translation behavior and artifact schemas remain unchanged.

- Documented test-local isolation of process-tree service children from inherited coverage
  startup, avoiding statement-only parallel data without changing parent branch policy or
  production process semantics; added a real child/grandchild diagnostic.
- Documented Pi lifecycle output, timed communication heartbeat, explicit runtime role/model
  presets, independent same-model contexts, and expected dirty status during active implementation.
  Validator ownership, two-round semantics, reviewer restrictions, and process cleanup remain
  unchanged.

## 2026-10-01

- Finished the Windows process-safety guarantees: a `KeyboardInterrupt` at any point after `Popen`,
  including during Job Object creation/assignment/resume, terminates and reaps the direct child and
  all descendants, and the Job Object is closed on interrupted setup. The `ResumeThread` result is
  checked so a suspended process is never treated as started; failure fails closed by terminating
  the tree.
- Closed the PDFTR-35A round-1 findings: the Windows child is now created suspended and joined to
  its Job Object before it can run (race-free containment), POSIX termination reaps the direct child
  while polling so zombie processes do not mask cleanup, the reviewer parser rejects duplicate JSON
  keys, tree-guard acquisition failures clean up the spawned process, runner-side persistence and
  active-phase I/O failures stop through the validator, and ticket files are matched on the exact ID
  boundary so `PDFTR-35` never selects `PDFTR-35A`.
- Hardened the Pi two-agent runner after the PDFTR-35A safety findings: role ownership is
  consistent (implementer writes only its handoff input, read-only reviewer returns JSON on stdout,
  runner persists validated output), cancellation and post-spawn failures terminate the whole owned
  process tree through a Windows Job Object or a saved POSIX process group, and the reviewer parser
  requires exactly one supported envelope and fails closed on malformed or contradictory output.
- Documented `scripts/pi_ticket_cycle.py`, the sequential Pi two-agent runner. The runner imports
  `scripts/agent_cycle.py` as the unchanged workflow authority, sequences the Pi implementer and a
  technically read-only Pi reviewer over an exact SHA, records reviewer JSON through the validator,
  allows one fix/review retry with a required new SHA, and stops for human review. Provider, model,
  and tool names remain configuration; the change does not touch the package, schemas, rendering,
  translation, OCR, model, or cache boundaries.

## 2026-09-28

- Exposed the four document-level inline-style totals (candidates, applied, deferred, and
  applied-character counts) in the human-readable HTML diagnostic summary. The rows read directly
  from `ReportSummary`, render explicit zeros, and change neither the embedded machine-readable
  JSON, rendering/translation behavior, nor the diagnostics schema.

## 2026-09-27

- Added the durable, product-neutral sequential agent-cycle workflow: one implementation writer,
  one read-only exact-SHA reviewer, validator-owned system state, two bounded review rounds,
  stale-review and repeated-finding stops, human final merge ownership, and the explicit PDFTR-33
  bootstrap exception.

## 2026-09-26

- Tightened PDFTR-32 repeated-token mapping so equal source/target counts do not imply identity,
  and documented production PyMuPDF physical-line counting for inline-aware heading orphan checks.

## 2026-09-25

- Added the PDFTR-32 safe inline-run boundary for BODY, HEADING, and FOOTNOTE reflow: exact
  preserved-text mapping, size/color-only application, run-aware prefix/continuation measurement,
  shared insertion representation, saved-style validation, and privacy-safe applied/deferred
  diagnostics. Corrected stale pages that still described production typography as inactive.

This records meaningful knowledge-base changes, not every Git commit or formatting edit.

## 2026-09-24

- Activated authoritative occurrence-indexed reconstructed typography for production FOOTNOTE,
  including resolved measurement/insertion, continuation spacing, geometry failure, diagnostics,
  and the 35-occurrence Robitzsch validation while preserving separator ownership and BODY/HEADING
  behavior.
- Activated authoritative occurrence-indexed reconstructed typography for production HEADING,
  documented shared BODY/HEADING mapping, removed the obsolete uniform-heading gate, and preserved
  fail-closed identity/geometry checks, style-aware orphan handling, and unchanged FOOTNOTE scope.

## 2026-09-23

- Made heading-orphan protection style-aware and documented fail-closed hanging-indent geometry
  while preserving safe negative first-line indents.
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
