# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Human-approved pre-review operational retry (PDFTR-45) with `--recover-operational`, structured
  stop codes, clean-tree/exact-HEAD/branch/repository gates, separate approval state and strict audit
  history. Up to three retries increment implementation attempts without spending review budget;
  previous logs, journals, partial handoffs and reports survive. Status reports retry eligibility;
  approval resumes without duplicate counting. Locked, attempt-bound pre-launch ownership also
  resumes a crash after the implementation transition but before the launch fence; uncertain launch
  ownership fails closed. Legacy text-only operational stops remain unknown.

- Role-bound append-only operational progress journals for Pi cycles (PDFTR-44), UTC milestones,
  safe last-activity heartbeat display, configurable diagnostic stale warnings, and preserved
  resume/recovery boundaries and failure/cancellation evidence. Reviewer access is limited to its
  own journal through `progress_append`; cycle authority and process cleanup remain unchanged.
  No hard execution timeout or automatic stale-run recovery is introduced. Enabled runner prompt
  overrides explicitly authorize the bound diagnostic tool without relaxing other write restrictions;
  disabled prompts retain their original restrictions.

- Harness-owned YouTrack bootstrap, schema-checked agent update intents, lifecycle synchronization,
  idempotency journals and credential-free audit artifacts (PDFTR-43). After `PASSED`, configured
  GitHub PR creation/reuse verifies the exact reviewed head SHA, records real check status, and
  emits a deterministic human/ChatGPT Work handoff. External failures warn without changing local
  verdicts; historical placeholders are excluded and merge remains human-owned.

- Resumable Pi ticket cycles (PDFTR-42): idle review and rework states dispatch directly to the
  required role; passed cycles report completion without rerunning agents. Explicit human recovery
  authorizes one further SHA-bound implementation/review pair after exhausted reviews, retaining
  immutable numbered artifacts and audited approval/stop history. Automatic review limit stays two.

- Source-confirmed list marker fidelity through the existing shared reflow path (PDFTR-41):
  independent source-span rectangles, semantic-only provider input, per-occurrence canonical marker
  restoration, source content/marker origins and first-occurrence pagination. Ambiguous prefixes
  retain fallback behavior; ordinary text, semantic initials/decimals and artifact/cache versions
  remain compatible. Saved validation rejects local duplicate and continuation markers in addition
  to missing marker/content, and semantic inline offsets exclude structural spans.
  Review corrections reject adjacent name-like initials as list evidence, associate proven source
  continuation lines with their items, and retain fallback for unresolved tails. Saved validation
  accepts explicit contract tokens beyond automatic detection and rejects extra markers in semantic
  rectangles while allowing marker-like text already present in the planned content.
  Human-approved R1 recovery also preserves complete initials/names with surname qualifiers,
  lowercase particles and compound surnames instead of treating them as structural letter lists.
  The R1 follow-up recognizes lowercase straight/curly-apostrophe name components without a
  surname allowlist; mixed prose/name neighbors retain complete initials and fallback behavior.

- Reviewer-only constrained `git_readonly` capability for all Pi role presets (PDFTR-40):
  independent exact-SHA/status/branch/diff/show/merge-base/history evidence without shell,
  arbitrary Git argv or repository writes. Fixed root, helper/filter/pager/network hardening,
  bounded output and fail-closed errors preserve validator ownership and two-round semantics.
  CI installs Node 22 for deterministic provider-free inspector regressions.

- Optional source-backed internal list-layout metadata with separate structural marker/content
  origins, shared measurement/insertion, first-occurrence-only pagination ownership and typed
  saved-output occurrence identity. Invalid evidence fails closed. Automatic list reconstruction,
  translation providers and existing artifact schemas remain unchanged (PDFTR-39).

### Fixed

- PDFTR-44 human-approved repair: encode every runner console diagnostic safely on CP1251/ASCII
  streams without interrupting child execution or masking original failures. Reject dangling
  symbolic journal links before opening, preserving the reviewer's fixed journal boundary.

- PDFTR-43 recovery: protect the selected review envelope from metadata removal and reject
  nested/overlapping intent delimiters. Stage GitHub PR publication through neutral metadata,
  exact-head verification and SHA-bound readiness/CI evidence; revoke claims on detected races.

- Reviewer Git inspection rejects `.git/commondir` entries before any Git subprocess, preventing
  foreign common-directory redirects (PDFTR-40 P1). Linked-worktree/common-directory layouts
  remain unsupported; normal repositories and existing safety guards are unchanged.

- `agent_cycle.py status` treats a dirty working tree during active implementation as expected
  information, while retaining HEAD binding and all workflow cleanliness gates.
- Added Pi runner lifecycle messages and a five-minute child heartbeat without streaming prompts,
  reasoning, or child output. Communication retries retain existing process-tree cleanup.
- Added `--preset` choices `deepseek-codex`, `codex-deepseek`, `codex-codex`, and
  `deepseek-deepseek`, with explicit role CLI overrides taking precedence. Reviewer tools remain
  read-only for every preset, including independent same-model child invocations.

- Completed the Windows process-safety guarantees in `scripts/pi_ticket_cycle.py`. A
  `KeyboardInterrupt` after `Popen` — including during Windows Job Object creation, assignment, or
  the resume step — now always terminates and reaps the direct child and every descendant before
  control returns, and the Job Object is closed on setup interruption so no member is leaked. The
  `ResumeThread` return value is now checked: a failure fails closed by terminating the suspended
  child tree and raising a startup error instead of treating an uncontained child as started.
- Hardened `scripts/pi_ticket_cycle.py` against the PDFTR-35A safety findings. Implementer prompts
  now permit exactly the role-owned handoff input while protecting validator-owned coordination
  files and the contracts no longer tell a read-only reviewer to write one; cancellation and any
  post-spawn failure terminate and verify the whole owned process tree via a Windows Job Object or a
  saved POSIX process group; the reviewer parser requires exactly one supported JSON envelope and
  rejects malformed, truncated, array-wrapped, extra, reversed-delimiter, or duplicate-key results;
  and operational failures reap children before the cycle records a stop. The Windows child is
  created suspended and joined to the Job Object before it can run, POSIX termination reaps the
  direct child while polling, tree-guard acquisition failures clean up the spawned process,
  reviewer-result persistence and active-phase I/O failures stop through the validator, and ticket
  files are matched on the exact ID boundary (`PDFTR-35` never selects `PDFTR-35A`).
  `scripts/agent_cycle.py` also accepts suffixed follow-up ticket IDs such as `PDFTR-35A`.
- Deferred repeated inline-style tokens unless both source and translated text contain exactly one
  occurrence, and made PyMuPDF heading-orphan checks count physical rendered lines instead of
  deriving logical lines from inline-inflated height.
- Made the heading orphan guard use the same style-aware BODY measurement path as normal reflow,
  and rejected hanging indents whose physical first-line start escapes the safe flow region.
- Prevented the typography inspection JSON output from aliasing and overwriting its source PDF.
- Kept typography role-region and paragraph-gap geometry isolated by source column, and stopped
  missing line baselines from joining non-adjacent lines into a false doubled line height.
- Made the PDFTR-22 reflow PoC post-save validation segment-local, so identical text in another
  placement cannot falsely prove that a missing segment was saved; region extraction is now
  diagnostic-only evidence.
- Enforced strict schema 1.3 paragraph render completeness: every logical paragraph now has an
  explicit terminal state, required overflow aborts before publication with occurrence-level
  diagnostics, policy-excluded units are accounted for, and failed debug layouts remain separate
  from the requested output.
- Made post-save Cyrillic PDF validation render-unit aware, with PDF extraction punctuation
  normalization and debug-only preservation of failed temporary render PDFs for diagnostics.
- Prevented PDF private-use marker-only paragraphs from being sent to translation models as prose,
  preserving them as non-empty pass-through text so schema 1.3 rendering no longer reports false
  missing translations for split source blocks.

### Added

- Added `scripts/pi_ticket_cycle.py`, a sequential Pi two-agent runner. One command imports
  `scripts/agent_cycle.py` (the unchanged workflow authority), runs a Pi implementer, validates the
  handoff and exact SHA deterministically, runs a technically read-only Pi reviewer, records the
  reviewer JSON through the validator, supports one fix/review retry with a required new SHA, and
  stops for human review after `PASS`, `BLOCKED`, or the two-round limit. Prompts are delivered on
  stdin so large multilingual prompts are not subject to Windows command-line limits; reviewer tool
  configuration is validated against a fixed read-only allowlist before any state change; the
  reviewer result must be a single unambiguous JSON object; cancellation terminates the whole
  owned process tree; and ordinary process failures stop the active phase cleanly. Provider, model,
  and tool names are configuration, and deterministic tests never invoke real providers.
- Added an inline-style summary to the human-readable HTML diagnostic report. The report table now
  exposes inline-style candidate, applied, deferred, and applied-character counts directly from
  `ReportSummary`, with explicit zero rows and no change to the embedded JSON, rendering behavior,
  translation behavior, or the diagnostics schema.
- Added the repository-local `.agent-cycle` contract and fail-closed validator for sequential
  implementation and exact-SHA, read-only review. The versioned, product-neutral three-section
  handoff (`system`, `implementer`, `reviewer`) enforces ownership, clean-tree and branch/HEAD binding,
  active-role exclusion, immutable review artifacts, stale-review invalidation, exact repeated
  findings, external stops, and the two-round limit without launching agents or automating merge.
- Safe source-backed inline style runs for production BODY, HEADING, and FOOTNOTE reflow. Exact,
  order-preserving translated substrings can retain local font size and RGB color through shared
  measurement/insertion, continuation clipping, and saved-PDF validation; ambiguous or unsupported
  candidates fail closed into privacy-safe applied/deferred diagnostics. Bold, italic, and source
  font identity remain requested evidence and are not synthesized.
- Production FOOTNOTE reflow now consumes reconstructed typography by authoritative occurrence
  index through the same common role-aware mapping as BODY and HEADING. Resolved size, line height,
  RGB color, physical alignment, indents, one-time spacing, mixed-style/fallback state, and
  requested-versus-applied bold/italic values drive measurement, pagination, continuation,
  insertion, saved validation, and diagnostics. Invalid identity, role, alignment, or geometry
  fails closed without falling back to synthetic footnote spacing.
- Production HEADING reflow now consumes reconstructed typography by authoritative occurrence
  index through the same role-aware mapping as BODY. Resolved size, line height, RGB color,
  physical alignment, indents, one-time spacing, mixed-style/fallback state, and requested versus
  applied bold/italic values participate in planning, diagnostics, and insertion. Safe
  heterogeneous headings are supported per occurrence; invalid identity, role, or geometry fails
  closed before PDF mutation.
- Production BODY reflow now consumes reconstructed paragraph typography by authoritative
  occurrence index, applying resolved size, line height, RGB color, physical alignment, indents,
  and one-time paragraph spacing through a shared PyMuPDF HTML/CSS measurement and insertion path.
  Diagnostics retain mixed-style/fallback evidence and explicitly report requested-but-unapplied
  bold/italic variants.
- Added a versioned renderer-facing paragraph style reconstruction contract with role-aware robust
  baselines, per-property source/fallback decisions, conservative font family/role inference,
  mixed-style preservation, JSON round-tripping, and opt-in `typography_inspect --resolved`
  diagnostics. Production rendering remains unchanged until PDFTR-29.
- Typed source-backed typography evidence for every logical paragraph occurrence, including
  dominant source font/size/color, flag-derived bold/italic, conservative alignment, baseline
  spacing, indents, canonical gap-before evidence, categorical confidence/provenance/fallback,
  mixed inline-style flags, and a standalone inspection command without renderer changes.
- Production footnote-group reflow with structured lower-page region discovery, source-derived
  minimal styling, bounded dedicated continuation pages, unified body/footnote page mapping,
  collision checks, segment-local validation, footnote-specific diagnostics, and fail-closed
  handling of unsafe anchored objects.
- Production single-column body reflow with conservative structured eligibility, one basic heading
  style, exact occurrence-backed continuation segments, bounded pages inserted after their source
  page, protected anchors, zero-unplaced planning, segment-local saved-PDF validation, strategy
  diagnostics, and fail-closed fallback for footnotes and unsafe layouts.

- Isolated PDFTR-22 body-text reflow proof of concept with typed flow regions, occurrence-preserving
  continuation segments, exact character accounting, bounded hybrid page creation, selectable PDF
  output, machine-readable plans, debug visualization, and deterministic tests.
- Durable reflow architecture and Robitzsch evidence for pages 1, 3, and 4, including the corrected
  finding that all 21 current fixed-layout overflows are footnotes and remain outside PDFTR-23 body
  reflow scope.
- Conservative, explicit foreign-language classification now preserves confidently Latin/Greek
  quotation paragraphs without model inference and protects Greek spans plus selected academic
  foreign terms inside translated prose, with serialized per-unit evidence and report totals.
- Foreign-language preservation keeps inline spans outside model inference, composes with glossary
  and protected-token placeholders, honors explicit glossary translation, fails closed on
  inconsistent span assembly, and invalidates pre-PDFTR-21 translation cache/resume/workspace
  artifacts through behavior revision 5.
- Phase 1 ProjectWiki with Git-tracked source-backed Markdown, curated navigation, agent maintenance
  rules, dependency-free frontmatter/link/source linting, deterministic lexical search, focused
  tests, and local/CI quality-gate integration.
- Versioned JSON and Markdown performance reports for deterministic and real NLLB runs, including
  cold/warm timing, translation-cache reuse, batch-size distributions, RSS, CUDA memory, shared
  model reuse, and output-integrity evidence.
- Reproducible official CUDA 13.0 PyTorch resolution on Windows through uv project metadata,
  while Linux CI and explicit CPU inference remain GPU-independent.

- PDFTR-13A end-to-end glossary benchmark with 64 logical paragraphs, repeated-element policies,
  protected-token segmentation/restoration, deterministic fake translation, isolated SQLite
  caches, warm-cache reuse, and changed-glossary invalidation evidence.
- PDFTR-13 strict versioned EN-to-RU JSON glossaries with deterministic paragraph-bounded
  matching, translate/preserve modes, fixed/allow-model behavior, overlap priorities, and explicit
  conflict rejection.
- Glossary-aware protected-token restoration, validated final output, cache/resume/workspace
  identity, once-per-batch loading, per-file batch statistics, and privacy-safe diagnostic evidence
  with stable glossary codes.
- `--glossary PATH` for normal PDF, batch, and direct JSON translation workflows plus schema docs,
- Conservative document-level detection for sequential page numbers, uniform/alternating running
  headers and footers, repeated legal boilerplate, watermark candidates, and ambiguous repeated
  content, with retained source blocks and auditable confidence/group/policy evidence.
- Typed `--repeated-elements auto|off` controls for root, batch, and extract workflows; confirmed
  non-body elements are isolated from paragraph merging, repeated translations are reused, page
  numbers are preserved, and uncertain content is never automatically removed.
- PDFTR-10 diagnostics now include repeated-element counts, confidence, group IDs, policies,
  ambiguity flags, and a stable `REPEATED_ELEMENT_AMBIGUOUS` finding.
- Typed schema 1.2/1.3 paragraph reconstruction with preserved raw lines/blocks, reversible source
  mappings, conservative reading order, two-column/list/heading/caption/footnote boundaries,
  protected hyphenation, strong cross-page continuation, ambiguity decisions, and metrics.
- `--paragraph-reconstruction conservative|off` for root, extract, and batch workflows plus typed
  `PDFTRANSLATE_PARAGRAPH_*` tolerance settings.
- Paragraph-aware translation, cache/resume identity, diagnostics, and rendering that redacts every
  mapped source fragment while inserting each logical translation exactly once.

- Opt-in per-translation diagnostics with versioned privacy-safe JSON and self-contained offline
  HTML reports, stable warning codes, page/block geometry, cache/OCR/fitting/overflow/validation
  evidence, durations, file sizes, and measurable Python peak memory.
- `--debug-layout` publication with source/final rectangles plus selectable block IDs and final
  states, kept separate from the validated normal output PDF.
- `--report`, `--report-format`, `--report-dir`, `--debug-layout`, and
  `--include-report-text` end-to-end CLI options; source/translated text remains excluded by default.
- Versioned 61-sample synthetic English-to-Russian benchmark dataset with explicit PDFTR-8
  regressions for protected token `1900-1` and page-7 numeric/date corruption with `F￾`.
- `pdftranslate benchmark-translation` with atomic JSON/Markdown reports, backend/model/tokenizer/
  device/settings/commit/timing/cache metadata, fake-testable execution, human 1–5 review fields,
  and baseline comparison.
- Deterministic, stage-attributed benchmark findings for extraction, segmentation, protected-token,
  model, terminology, and rendering evidence, including numbers, units, URLs, paths, options,
  missing segments, untranslated output, length ratios, and suspicious characters.
- Opt-in `scripts/validate-real-pdfs.ps1` corpus harness with dry-run, manifest/category/path
  subset selection, continue-on-error/fail-fast policies, one shared model/cache runtime, and
  explicit real-model, device, OCR, offline, resume, and overwrite controls.
- Versioned real-PDF evidence: atomic JSON and Markdown summaries, per-document results, copied
  logs, anonymized relative paths, stage timing, page classifications, source checksums, OCR and
  cache/resume metrics, manual PDF-XChange observations, and mapped deterministic defects.
- Generated-PDF/fake-backed validation tests covering text/image success, scanned OCR dependency,
  translation/render/output-validation failures, continuation, Unicode paths, source preservation,
  report generation, cache reuse, resume, and manual compatibility failures without model downloads.
- Recursive and non-recursive `pdftranslate batch INPUT_DIR` processing with deterministic
  case-insensitive PDF discovery, glob/exclude filters, `.ru.pdf` and output-tree protection,
  preserved relative output structure, and Unicode/spaced-path support.
- Lazy single-model and shared SQLite translation-cache lifetime across sequential batch files,
  while retaining source-specific workspaces, OCR settings, atomic output publication, and resume.
- Atomic versioned JSON batch reports, human-readable summaries, fail-fast and
  `--continue-on-error` policies, explicit skipped-file reasons, and exit code 10 for partial or
  complete batch failure.

- OCRmyPDF/Tesseract preprocessing stage with `auto`, `on`, and `off` modes, English language
  selection, deskew/clean/rotation controls, explicit force mode, bounded subprocess execution,
  retained logs/sidecars, actionable dependency failures, and a dedicated OCR failure exit code.
- Conservative mixed-PDF handling via OCRmyPDF skip mode, immutable source files, post-OCR
  page-count/geometry/classification validation, low-text warnings, and resumable `ocr.pdf`
  workspace artifacts invalidated by source or OCR-setting changes.
- `pdftranslate doctor` OCRmyPDF, Tesseract, Ghostscript, executable-path, version, and English
  language-data diagnostics without automatic system installation.
- Mocked OCR unit and pipeline tests plus an explicitly enabled optional real-OCR integration test.
- Root `pdftranslate INPUT.pdf` workflow for inspection, extraction, local translation, rendering,
  final validation, and atomic publication with `<stem>.ru.pdf` default naming.
- Deterministic application-cache workspaces containing inspection/extraction/translation
  artifacts, render candidates, versioned stage manifests, detailed logs, and failure state.
- Stage-aware `--resume` with strict source/options/artifact compatibility, completed-stage reuse,
  translation checkpoint continuation, and visible reused-stage reporting.
- Model-free `--dry-run` planning with page classifications, block estimates, OCR requirement,
  selected backend/device, output path, and expected stages.
- Centralized stable exit-code categories for arguments, PDF input, OCR, model loading,
  translation, rendering, output validation, and interruption.
- Generated-PDF/fake-backend end-to-end tests including option/source invalidation, publication
  safety, Ctrl+C, spaces, and Cyrillic paths.
- `pdftranslate render` for validated Russian text reconstruction in a new PDF.
- Cyrillic system-font discovery and glyph validation, embedded custom fonts, deterministic
  wrapping/font reduction, bounded block expansion, and explicit overflow warnings.
- Text-only redaction that retains image/vector objects, sampled non-white backgrounds, atomic PDF
  publication, reopening validation, and separate debug-layout output.
- Runtime-generated rendering tests for geometry, images/vectors, fitting, overflow, mismatch,
  Unicode paths, font validation, and CLI behavior.
- Local `pdftranslate translate` English-to-Russian pipeline using the
  `facebook/nllb-200-distilled-600M` backend.
- Backend-independent translator protocol, CPU/CUDA/auto selection, offline model loading, bounded
  OOM recovery, token-aware batching, protected tokens, and deterministic segmentation.
- Schema 1.1 translated JSON with original/translated text, settings identity, timestamps,
  warnings, progress statistics, atomic checkpoints, and validated resume.
- SQLite translation memory under the configured application cache root.
- Fake-backed translation/NLLB/CLI tests that never download model weights.
- PyMuPDF-backed PDF validation, inspection, and structured text-block extraction.
- `pdftranslate inspect` with readable table and clean `--json` output.
- `pdftranslate extract` with one-based page ranges, pretty/compact version 1.0 UTF-8 JSON,
  overwrite protection, and atomic writes.
- Strict domain models for source fingerprints, metadata, page geometry and classification,
  image placement counts, text-block order, bounding boxes, and span typography.
- Configurable deterministic `text`, `scanned`, `mixed`, and `empty` page heuristics.
- Runtime-generated PDF tests including encrypted and Unicode-path scenarios.
- Initial Python 3.12 project foundation.
- `pdftranslate --version` and `pdftranslate doctor` commands.
- Typed environment-based settings and centralized Rich logging.
- Tests, Ruff, mypy, pre-commit, PowerShell helpers, and cross-platform CI.

### Changed

- Translation diagnostics now publish into a unique per-execution directory and reject existing
  JSON, HTML, or debug-PDF targets instead of silently replacing them.
- A success-report/debug publication failure now returns dedicated exit code 11 while preserving and
  naming the already validated translated PDF.

### Fixed

- Protected-token detection no longer treats ordinary slash-separated prose as file paths, and
  translation text preparation now normalizes common PDF ligatures before matching protected tokens.
- Translation cache and pipeline workspace identity now include the protected-token preprocessing
  revision, preventing stale pre-PDFTR-16 cache/resume artifacts from being reused.
- Benchmark exact-source cache hits now reuse only inference artifacts and independently recompute
  protected-token, human-review, historical-trace findings, and status for every sample.
- NLLB `--offline` now resolves a local model/cache snapshot before Transformers import, loads
  configuration/tokenizer/model with local-only settings under a restored scoped offline
  environment, and fails before any online fallback when files are missing.
- NLLB protected-token restoration now uses collision-safe ASCII placeholders that the real model
  preserves, instead of Unicode sentinels that were stripped during inference.

### Security

- The one-command workflow renders only to its cache workspace, validates a temporary destination
  sibling, and publishes the final name atomically; failed runs retain diagnostics without leaving
  a partial final PDF.
- Rendering validates source identity and block/page layout, refuses source/output aliases, and
  publishes only a reopened valid PDF; mismatch override never skips structural validation.
- Translation preserves original source text and fails rather than silently dropping protected
  URLs, email addresses, paths, measurements, or identifiers.
- Offline mode prevents remote model acquisition; default cache paths remain outside the repository.
- Source PDFs are never rewritten; extraction rejects source/output aliases and protects existing
  JSON unless `--overwrite` is explicit.
- Password-required PDFs are reported by inspection and rejected by extraction with a useful error.

## [0.1.0] - 2026-07-31

- Bootstrap release foundation; PDF translation is not implemented yet.
