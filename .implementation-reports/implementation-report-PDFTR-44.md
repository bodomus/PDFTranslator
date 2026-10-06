# Implementation Report — PDFTR-44

## Workflow and scope
- Level 2; initial working tree clean on `pdftr-44-agent-progress-journal`.
- Graphify used for scoped orientation/impact, refreshed with `graphify update . --no-cluster`.
- CRG updated before/after implementation; first console output failed under cp1251, successful
  retry used `PYTHONIOENCODING=utf-8 code-review-graph update --brief`.
- No dependencies added; Python 3.12 / uv and Windows PowerShell retained.
- No PDF/output integrity, translation, model/device, OCR, domain or application-cache changes.
- Investigation/plan: `.implementation-plans/investigation-PDFTR-44.md` and
  `.implementation-plans/implementation-plan-PDFTR-44.md`.

## Investigation and changes
Existing heartbeat showed only elapsed duration. Reviewer had no write capability, so prompt-only
logging would either fail or weaken the read-only boundary. Added a narrow harness-bound capability:

- `scripts/agent_progress.py`: centralized factual-only prompt policy, UTC execution boundaries,
  safe bounded last-valid-line parser, configuration and per-execution stale observation.
- `scripts/agent_progress/extension.ts` / `journal.mjs`: `progress_append(message)` accepts only
  one short milestone, never a path. Runner CLI binds ticket/role/cwd. Writes are append-only;
  redirects/hard links, controls, HTTP URLs and common credential patterns are rejected.
- `scripts/pi_ticket_cycle.py`: role-specific paths/policy/tool binding, preserved resume/round
  history, activity in heartbeat, configurable stale warnings, exit/failure/cancellation diagnostics.
  Defaults: enabled, 30 minutes, 180 console characters. CLI flags configure/disable progress.
- Reviewer guard permits only the bound diagnostic tool in addition to its existing read tools.
  No shell, tracked-file writes, implementer-journal writes or verdict artifact writes are granted.
- Journals remain diagnostic evidence, never authoritative state or review verdicts. No changes to
  validator schemas/transitions, exact-SHA gates, subprocess communication/cleanup, Windows Job
  Objects or POSIX process groups. No hard timeout, stale kill or automated recovery was introduced.

## Graph and source validation
Graphify identified runner/FakePi/test adjacency, verified in source. CRG refreshed changed symbols;
its inferred test gaps do not account for all indirect deterministic tests. New functionality is
reachable through both role child launches, local heartbeat callbacks and common exit diagnostics.
Installed Pi docs/examples and API declarations verified extension registration/flags; the real
installed extension loader loaded `progress_append` and both binding flags with zero errors.
Context7 is unavailable in this tool environment; no external library/dependency was introduced.
Graphify refresh warned only about four pre-existing zero-node JSON sources.

## Validation
- Focused final suite (progress, redirects, Pi cycle, resume, reviewer Git, validator):
  **265 passed, 2 skipped** (Windows skips POSIX-only process tests).
- Full `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`: **PASS**.
- Full pytest: **814 passed, 3 skipped**, coverage **89.54%** (required 80%).
- Ruff format: **313 files formatted**, lint **PASS**; mypy **PASS**, 98 source files.
- Wiki lint: **PASS**, 15 pages / 137 links / zero errors or warnings.
- Deterministic coverage: missing/empty/malformed/partial/long/control journal lines; bounded tail;
  no-progress/updated/stale heartbeat; duplicate/truncated activity identity; role path binding;
  reviewer isolation and runtime guard; hard-link rejection; resume/recovery preserved boundaries;
  non-zero exit/cancel journals retained after STOPPED; disabled/invalid configuration.
- Real Pi extension-loader smoke: **PASS**, no providers, model calls or coordination writes.
- Existing cleanup, Windows Job Object, POSIX group, role permissions, exact-SHA and recovery tests
  remain green on this Windows run. Ubuntu CI was not executed locally; CI result remains remote.
- No real model, CUDA, OCR or PDF manual validation needed for this harness-only change.

## Documentation
Updated README, CHANGELOG, role/handoff/Git-safety contracts and skill, affected development Wiki
page and Wiki log. Ticket Markdown was already present; ticket attachment and external workflow
updates remain runner-owned. Completion summary is `reviews/review-PDFTR-44.md`, not a reviewer verdict.

## Limitations and safety
- Staleness is based on newly observed complete valid entries at five-minute heartbeat polling,
  not HH:MM wall-clock inference, and resets per execution. It is diagnostic only.
- Parser inspects the last 64 KiB; if no complete valid line fits, reports no activity. Tool entries
  are capped at 240 characters, console rendering independently capped. Controls are sanitized.
- Factual-only content and all secret exclusions are centralized policy. Common-pattern rejection
  is defense in depth, not a universal secret detector or OS sandbox; trusted Pi/Node and no hostile
  concurrent filesystem writers are the existing capability-boundary assumptions.
- Token overhead is limited to one short policy/tool and meaningful one-line milestones; no model
  heartbeat requests or reasoning summaries. A numerical token benchmark was not performed.
- This bootstrap execution's runner override prohibited its own progress journal writes; only the
  designated implementer input will be written under the real `.agent-cycle/PDFTR-44/` directory.
- Integration warnings: ["YouTrack credentials unavailable"]. No direct YouTrack API was called.

## Attempt 2 — reviewer finding R1
- Workflow Level 1; clean baseline, no unrelated changes. Both generated runner overrides
  previously conflicted with the appended progress policy. Corrected `_implementer_prompt` and
  `_reviewer_prompt` to explicitly authorize `progress_append(message)` only for their bound
  diagnostic journal when enabled, superseding blanket restrictions. Direct journal writes and
  all other coordination/repository restrictions remain intact; disabled overrides retain their
  original restrictions. No tool, schema, process, role capability or state transition changes.
- Added enabled/disabled prompt regressions checking both highest-precedence role overrides,
  bound paths, prohibition precedence, direct-write restrictions and disabled-mode restrictions.
- Graphify scoped query confirmed prompt/run-cycle adjacency, source verified; CRG refreshed
  before/after edits with UTF-8 output. No architecture refresh required for this local correction.
  No external-library API changes or additional dependencies.
- Focused final suite: **267 passed, 2 skipped** (`--no-cov`, harness-only tests). First focused run
  exposed the existing explicit artifact-ban assertion and package coverage scope; retained an
  explicit authoritative-artifact ban and reran successfully without package-only coverage.
- Full `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`: **PASS**;
  **816 passed, 3 skipped**, **89.54%** coverage; Ruff format/lint, mypy and Wiki lint all pass.
  First gate found line-length errors; corrected literal formatting and reran the entire gate.
- Updated README, CHANGELOG, affected Wiki/log, ticket plan and implementer completion summary.
  Windows validated locally; Ubuntu CI is not run locally. No model/provider calls required.
- Integration warnings: ["YouTrack credentials unavailable"]. No direct tracking API calls or
  cycle transitions. This execution still obeys its supplied override: only the designated
  handoff input is written under the real `.agent-cycle/` directory.

## Delivery
Commit/push and the designated implementer handoff follow validation. The runner derives the final
Git SHA, clean-tree state and review ownership; no manual cycle transitions are performed.

## Human-approved independent-review repair — R1/R2 (2026-10-06)

- Continued from `1e31fb77183bcfb7d6c81cc8733e83c827888ac1` on the same clean ticket branch,
  under the human's explicit authorization to implement, validate, commit and push these two fixes.
  No automatic recovery/validator transitions or historical review artifact writes are performed.
  Any previous PASS belongs only to its original SHA; the repaired SHA requires a new review.
- R1: every runner diagnostic uses `_console_message`, including argparse errors, lifecycle and
  heartbeat output, stderr failures and final reports. Representable text is preserved; unsupported
  stream characters become `?`, keeping console character bounds. Closed/broken output is best
  effort and cannot interrupt the child or replace the original process failure. Existing bounded
  parser, invalid UTF-8 replacement, control sanitization and truncation remain intact.
- R2: `appendProgress` always inspects the journal entry with `lstatSync`. Only ENOENT permits
  creation. Symbolic links, including dangling Windows links, non-files and hard links are
  rejected before open; other inspection failures propagate without any fallback write path.
  Existing root/directory checks and descriptor checks remain unchanged.
- Added deterministic strict CP1251/ASCII heartbeat, invalid-byte, normal child completion,
  original exit/exception, CLI/final report, unavailable-console and length-bound regressions.
  Real Windows symlink tests cover both absent and existing referents, no outside writes, and
  normal absent/regular journal creation and append behavior.
- Workflow Level 1: ProjectWiki search, existing Graphify neighborhood and CRG pre/post queries
  are source-verified. No architectural refresh, dependency changes, role capabilities, hard
  timeouts, automatic recovery, process ownership or PDFTR-35A/40/42/43 contract changes.
- Initial regressions reproduced both defects. A sandboxed run hit Node-to-Git `spawn EPERM`;
  the focused safety suite is rerun outside that sandbox. One test's Windows newline assertion
  was corrected to strip CRLF. All test/cache/log artifacts stay under repository `temp/`.
- Documentation: README, CHANGELOG, affected Wiki/log, existing plan and completion summary.
  Operational milestones are appended only to `.agent-cycle/PDFTR-44/implementer-progress.log`.
- YouTrack lookup returned `Issue not found: PDFTR-44`; external ticket fields/attachments could
  not be updated through the available connector. No issue was created or historical state edited.
- Focused progress/runner/security suite: **PASS**, **291 passed, 2 skipped**; process exit 0.
  Evidence: `temp/pdftr44-recovery/focused.log`. Windows dangling/existing symlink and normal
  journal-path cases executed successfully; the focused skips are existing POSIX-only checks.
- Full `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`: **PASS**,
  **840 passed, 3 skipped**, **89.54%** coverage; 317 files formatted, Ruff lint, mypy (98 source
  files) and Wiki lint (15 pages / 137 links / no errors or warnings) all pass.
  Evidence: `temp/pdftr44-recovery/full-check.log`. No models/providers or network are used by tests.
- Post-change CRG updated and qualified caller query verified `_print_message`, `_report` and
  `main` routing through the safe output helper. Its test-gap heuristic misses indirect mocked
  runner/Node tests; all relevant calls and the registered progress default are source-verified.
  Graphify reuse is sufficient for these local fixes. Ubuntu execution remains remote/unverified.
- Historical `review-1.json` and `review-2.json` hashes remain unchanged. Commit/push on the
  existing branch follows this validation; the final SHA and clean status are verified separately
  and recorded in the operational progress journal, without rewriting old cycle authority.
