# Implementation Report

## Ticket
PDFTR-47 — YouTrack Live Synchronization Validation and Hardening (attempts 1–5).

## Attempt 5 — R3 ambiguous HTTP mutation outcomes
- Level 1 scoped fix, clean baseline. `_request` previously classified every HTTP error as a
  definite failure. A gateway 504 or other server error can arrive while an upstream POST still
  executes, allowing newer repeatable writes to bypass the durable uncertainty fence.
  Mutation HTTP 408 and all 5xx responses now raise sanitized UncertainTransport. Existing
  operation persistence retains `uncertain`/`conflicting_write`, fencing subsequent writes
  across restart, even after the delayed write completes. No automatic retry or fence reset.
  GET failures remain ordinary API errors (never exact absence except 404); definite 4xx
  rejections retain APIError handling. GitHub readiness remains independent and unchanged.
- Extended real request/_request fake-opener delayed-state regressions to HTTP 408/500/502/503/504.
  They verify no newer state write or success claim, persisted uncertainty, lifecycle/operator
  fences before and after delayed completion across restart, and sanitized diagnostics/evidence.
  Additional read regressions cover 408/500/502/503/504/599; definite mutation rejection tests
  cover 400/401/403/404/409/422/429. Existing independent GitHub readiness tests remain green.
- Focused tracking/validator/uncertainty suite: **182 passed**, no coverage, repository-local temp.
  Full Windows `scripts/check.ps1`: **PASS**; Wiki lint 0 errors/warnings, Ruff format/lint,
  mypy 98 source files, **1035 passed, 3 skipped**, 89.54% coverage, 340.68 seconds.
  Temporary files/logs stayed under repository-local `temp/`. No models were downloaded.
- Graphify scoped query and UTF-8 CRG pre/post incremental updates succeeded. Source verifies
  TrackingHooks/runner/operator reachability and the unchanged operation fence/GitHub boundary.
  Graph test-gap heuristics are superseded by executable coverage. No architecture refresh needed;
  no dependency, schema, module-boundary, reviewer-capability, cycle transition or PDF/model/OCR
  impact. Context7 unavailable; no external-library API usage changed.
- README, CHANGELOG, affected workflow Wiki/log, plan and completion summary updated.
  **No live YouTrack operation performed in attempt 5.** Credentials/account acceptance, project,
  assignee, mappings, fields, lifecycle, attachments and cross-links remain fake-tested and unverified
  live. Missing access does not block handoff; remote Windows/Ubuntu CI is not claimed passed.
  Integration warning categories: ["YouTrack credentials unavailable", "YouTrack identity mismatch;
  remote mutation refused", "YouTrack authentication failed"]. Identity/authentication categories
  represent deterministic coverage, not observed live failures. Operator reconciliation remains
  required for uncertain writes; an HTTP error or client termination does not prove remote completion.

## Attempt 4 — R2 independent GitHub synchronization
- Level 1 scoped fix; clean baseline. `passed` formerly entered the YouTrack write fence before
  `_passed`, blocking independent PR processing and stale human-review evidence revocation.
  It now retains the same OS lock and fresh artifact reload without requiring YouTrack write
  eligibility. PR processing checks that eligibility separately and persists a specific cross-link
  skip warning. All YouTrack operations remain fenced; no uncertain operation is reset or replaced.
  GitHub creation/reverification, exact-SHA checks and stale readiness revocation are unchanged.
- Eight deterministic regressions cover persisted pending/uncertain field/definition writes with
  stable/moved GitHub heads. They verify no YouTrack calls, fence preservation, visible warnings,
  PR creation and second-run idempotency, success/failure events and local readiness refresh/removal.
- Focused tracking/validator/uncertainty suite: **167 passed**, no coverage, repository-local temp.
  An initial command named a nonexistent uncertainty test file and collected no tests; corrected
  to `tests/test_youtrack_uncertainty.py` before the passing run.
- Full Windows `scripts/check.ps1`: **PASS**, Wiki lint 0 errors/warnings, Ruff format/lint,
  mypy 98 source files, **1020 passed, 3 skipped**, 89.54% coverage, 336.80 seconds.
  Logs and test temporary directories stayed under repository-local `temp/`.
- Graphify scoped query and UTF-8 CRG pre/post incremental updates succeeded. Source verification
  confirms TrackingHooks/runner/operator reachability; no PDF/translation/model/OCR impact,
  dependency change, schema change, reviewer capability change or cycle transition change.
  CRG summary retains heuristic test gaps despite executable regression coverage; source/tests win.
  No architecture refresh needed. Context7 unavailable; no external-library API change needed.
- Updated README, CHANGELOG, affected workflow Wiki/log, plan and implementer completion summary.
  No live operation performed in attempt 4. Credentials/account, fields/login, lifecycle, attachments
  and cross-links remain deterministically fake-validated and **unverified live**. Missing access
  remains non-blocking. Remote Windows/Ubuntu CI is not claimed passed by the local Windows gate.
  Integration warning categories: ["YouTrack credentials unavailable", "YouTrack identity mismatch;
  remote mutation refused", "YouTrack authentication failed"]. Identity/authentication failures
  describe deterministic diagnostic coverage, not observed live failures.

## Attempt 3 — R1 socket/connection-loss remediation
- Level 1 scoped fix from a clean baseline. `_request` previously turned socket timeouts and
  connection loss into ordinary TrackingError, permitting later repeatable writes despite a
  dispatched POST still executing remotely. Non-HTTP exceptions after entering the mutation
  transport now become sanitized UncertainTransport, including unreadable/truncated responses and
  response bounds. Definite HTTP rejection and pre-dispatch identity validation remain distinct;
  failed GET responses remain ordinary read failures, not exact issue absence.
- Existing operation write-ahead evidence now retains `uncertain` plus `conflicting_write` for
  these failures, fencing all later synchronization across action/SHA changes and restarts.
  No retry, automatic fence reset, new dependency, schema or module-boundary change. Local cycles
  continue safely; operator reconciliation must establish remote write completion and reconcile
  state before repairing evidence. A terminated socket alone does not prove remote failure.
- Deterministic tests exercise the real YouTrack request/_request wrapper through a fake opener:
  delayed server-side In Progress POST dispatch followed by socket TimeoutError, connection reset,
  or URLError before the overall deadline. Subsequent handoff/operator synchronization and restart
  fail closed, even after releasing the delayed write; no successful newer state is claimed.
  Additional tests cover malformed mutation responses, non-uncertain failed reads, definite
  400/401/403 rejections, pre-dispatch identity checks and safe diagnostic/artifact redaction.
- Focused tracking/validator/uncertainty suite: **159 passed** (`--no-cov`, repository-local basetemp).
  Initial focused run exposed a test-fixture expectation (existing issue had no State); corrected
  by explicitly initializing Open. Its default package coverage gate was inapplicable to script-only
  tests; full package coverage was validated by the complete gate below.
- Full Windows `scripts/check.ps1`: **PASS**, Wiki lint 0 errors/warnings, Ruff format/lint,
  mypy 98 source files, **1012 passed, 3 skipped**, 89.54% coverage, 403.04 seconds.
  Temporary files/logs were repository local. No model, CUDA, OCR or PDF manual validation needed.
- Graphify scoped query reused existing orientation. CRG UTF-8 pre/post incremental updates
  succeeded; source inspection verifies callers are TrackingHooks/operator validation and tests,
  not translation code (graph adjacency is not a source dependency). No external API changes;
  Context7 capability unavailable. Blast radius remains harness tracking and its diagnostics/tests.
- README, CHANGELOG, affected development-workflow Wiki/log, plan and completion summary updated.
  Wiki lint passed. No runner-owned authoritative coordination files were modified.
- Live limitations: **no live YouTrack operation performed in attempt 3**; credentials/account,
  fields/login, lifecycle, attachments and read-back remain fake-validated, not live verified.
  Windows/Ubuntu remote CI is not claimed passed; local Windows gate is confirmed.
  Required integration warning categories: ["YouTrack credentials unavailable", "YouTrack identity
  mismatch; remote mutation refused", "YouTrack authentication failed"]. The latter two are
  deterministic diagnostic coverage, not observed live failures. Live access is non-blocking.

## Attempt 2 — review remediation
- R1: repeatable definition/field operations now persist a conflicting-write marker before execution.
  An overall transport timeout records an uncertain outcome; pending crash evidence and uncertain
  outcomes fence all later synchronization, across instances/restarts and action/SHA differences.
  The lock cannot outlive a detached transport, so release/GET alone never reset the fence. Failure
  remains visible; no later lifecycle update is falsely verified while the stale write can complete.
  There is intentionally no automatic fence reset: operator repair must establish old transport
  termination and reconcile remote state first. This conservative fence can require human repair
  even if a pending operation crashed before sending its request.
- R2: every exception from ensure marks aggregate bootstrap failure. Configured field types and
  estimation/date syntax are validated before bootstrap mutation. Independent valid intent fields
  still proceed when another intent field is malformed. Numeric estimation produces the specific
  `unsupported estimation; expected string` warning. The live validator returns nonzero and omits
  its completion claim for first/second synchronization or field-validation failures.
- Level 1 scoped remediation; clean baseline inspected. Graphify query reused existing orientation;
  CRG UTF-8 pre/post incremental updates completed. Source-verified blast radius remains tracking
  hooks/operator/tests; no dependency, module-boundary, PDF, model, OCR or cycle-authority changes.
  No Context7 capability is available; no external-library API changes were needed.
- Focused deterministic suite: **151 passed** (tracking, live-validator and attempt-two regressions).
  Regressions include delayed state and definition transports released after a subsequent attempted
  synchronization, restart/pending-crash fences, malformed numeric/string defaults, bootstrap errors
  after issue resolution and second-pass failure claim suppression.
- Full Windows `scripts/check.ps1`: **PASS**; Wiki lint 0 errors/warnings, Ruff format/lint,
  mypy 98 source files, **1004 passed, 3 skipped**, 89.54% coverage, 326.82 seconds.
  Tests/logs used repository-local temp paths. Operator CLI --help passed without network access.
- README, CHANGELOG, plan, affected Wiki/log and implementer completion summary updated.
  Graph outputs/caches/logs remain ignored; no authoritative runner files were modified.
- Integration warnings: ["YouTrack credentials unavailable"]. **No live YouTrack operation was
  performed in attempt 2**; all remote behavior remains deterministically fake-validated, not live
  verified. Missing credentials do not block implementation or handoff. Remote CI is separate from
  the local quality gate and is not claimed passed before exact pushed-SHA confirmation.

## Attempt 1 evidence (retained)


## Workflow
- Level 2; clean initial tree on the expected task branch.
- Graphify: queried, source-verified and refreshed without an LLM.
- CRG: incremental updates completed with UTF-8; initial cp1251 summary printing failed after parsing.
- Context7 is unavailable in this harness. No new SDK or dependency was introduced.
- Ticket Markdown already exists under Tickets/; remote attachment is delegated to the harness,
  not attempted by this implementer without credentials.

## Investigation / scope
ProjectTracking is reached through TrackingHooks in the startup-loaded runner. Existing exact
identity checks/write-ahead operation journals were preserved, while implicit creation, inferred
field values, generic preflight and missing semantic write verification were hardened. See the
scoped investigation and implementation plan under .implementation-plans/.

Only harness tracking/configuration, its deterministic tests and documentation changed. No PDF,
translation, OCR, model/device/cache, dependency, cycle schema, exact-SHA or reviewer capability
changes. Graphify's translation-to-tracking association was rejected after source inspection;
actual dependants remain the hooks, operator entry point and tracking/runner tests.

## Changes
- Canonical project-tracking.toml HTTPS base_url; environment token only. Legacy URL must match
  exactly. Transport refuses redirects/arbitrary targets, sanitizes errors and bounds socket/overall
  execution. No automatic mutation retry loop; timed-out work remains explicitly uncertain.
- Credential/account, project and endpoint preflight with specific statuses. Missing credentials
  and unknown mappings never block local implementation/review.
- Exact find/reuse or explicitly allowed create, exact re-read by ID/key, conflict/lost-response
  discovery and durable identity/operation evidence. A different allocated issue number stops
  subsequent mutations and is recorded for operator reconciliation.
- Locally OS-held, non-waiting synchronization lock shared by bootstrap/lifecycle/operator updates,
  role metadata and PR synchronization. Contention returns safely without replacing another owner's
  pending write-ahead fence. Contention/acquisition diagnostics are console/in-memory only (captured
  by runner logs); they must not save a stale snapshot outside lock ownership. Owned synchronization
  reloads current operation evidence and never blindly duplicates local creation.
- Field/state introspection, exact API login resolution checked against allowed project users,
  strict semantic field types, no invented estimation/date/type/priority. Period units are preserved;
  ISO dates are encoded as UTC midnight milliseconds.
- Read-before-write and semantic read-back for definitions/important fields. Repeated identical
  synchronization makes no extra write. Aggregate partial failures are not hidden by successful
  comments. Uncertain prior non-repeatable operations explicitly require reconciliation.
- NEW/Open, implementation, review and human-review mapping; Done only on an explicit merged or
  finalization signal, including configured close-state names.
- Concise confirmed lifecycle evidence, not unverified agent prose/log dumps. PR cross-link uses
  verified GitHub SHA/CI evidence. Reviewer remains read-only and supplies only constrained intent.
- Explicit validate-live command: read-only default, dry-run, explicit creation/field/state opt-ins,
  finalization guard and a second idempotent synchronization. It does not change local cycle state
  or fabricate a review/SHA/CI event.

## Deterministic validation
- Focused tracking/validator tests cover credentials, exact existence/absence, ambiguous failures,
  explicit creation, conflict/lost responses and post-create mismatch, current PDFTR-47 identity,
  missing mappings/login, semantic field verification, UTC dates, lifecycle/finalization, idempotency,
  contention, secret redaction, host/target security, hung transport, dry-run/operator CLI and journals.
- Broader focused runner regressions passed: operational retry, startup module coherence, exact-SHA
  review, reviewer isolation, containment, resume and progress journals (platform skips retained).
- Final narrow tracking/validator suite: 140 tests passed, including five contended-writer fence
  preservation regressions added during the final concurrency audit.
- Full scripts/check.ps1: PASS on Windows/Python 3.12, including Wiki lint (0 errors/warnings),
  Ruff format/lint, mypy (98 source files) and pytest: **993 passed, 3 skipped**, 90% coverage.
  The final gate completed in 328.73 seconds. Temporary test/log paths were repository local.
- Operator CLI --help smoke test passed without contacting YouTrack.
- No real model, GPU, OCR or manual PDF validation is applicable to this harness-only change.

## Live evidence and limitations
Integration warnings: ["YouTrack credentials unavailable"]. A presence-only environment check
confirmed that the token is unavailable; no secrets were printed or persisted.

**No live YouTrack operation was performed.** Authentication acceptance, project visibility,
assignee bodomus resolution, field/state names, REST formats/timezone, issue creation/number
allocation, attachments, lifecycle writes/read-back and cross-links are tested with fakes only.
An operator must run the documented read-only/dry-run commands, then explicitly opt into mutation
if appropriate. Deterministic tests do not establish live API compatibility.

YouTrack allocates numbers; --allow-create does not force or guess the requested number. A
mismatched allocation is a remote limitation requiring human reconciliation, not fake success.
Period verification deliberately does not assume workday/week duration; different server-normalized
presentations generate a visible mismatch rather than guessed equivalence. Pending/failed
attachments/comments require reconciliation; creation is never blindly retried. Locks serialize
invocations sharing this repository, not arbitrary independent remote clients. An overall timeout
may leave a daemon transport call in flight, fenced as uncertain, with no duplicate mutation retry.
Historical backfill and broad remote concurrency queues remain out of scope.

GitHub Windows/Ubuntu CI is independent of local checks; no CI success is claimed before verified
remote results. GitHub CLI authentication is unavailable; public read-only Actions API access is
available. Final pushed-SHA CI evidence is recorded in the implementer handoff notes after push. Live limitations do not block implementation, push or runner handoff.

## Documentation / post-change impact
README, CHANGELOG, canonical config, affected development-workflow Wiki and Wiki log updated.
.graphifyignore now excludes runtime .agent-cycle evidence. Graph outputs and temporary artifacts
are not committed. Plan/investigation, report and implementer completion summary are ticket scoped.
Startup snapshots mean this tracking generation activates on the next runner invocation, not by
hot-reloading the already active cycle. No reviewer tools, state transitions or authority changed.

## Post-cycle human-approved corrective patch — R4

Baseline: clean `pdftr-47-youtrack-live-sync` at
`9839b05942c864ab12a13090f1a20c8a14ee5d42`. Level 1 correction confined to tracking transport,
field/definition preparation, deterministic regressions and their documentation. No dependencies,
PDF/model/OCR behavior, reviewer capabilities, PDFTR-45/PDFTR-46 safety or cycle schema changed.

Read-only overall timeouts now raise ordinary `ReadTimeout`. Field/definition preparation reads,
identity checks, mapping and comparisons run before pending mutation journaling. A failed pre-write
GET is recorded as a failed operation with `conflicting_write=false`, without pending/uncertain
mutation evidence. Healthy synchronization can resume after restart. Actual writes retain pending
write-ahead evidence, transport/response uncertainty and restart fences. A verification GET timeout
after a dispatched write retains the operation's uncertainty fence; existing fences are never cleared.
Mutation HTTP 408/5xx and definite 4xx rejection classification remains unchanged.

ProjectWiki search, scoped Graphify query and successful incremental CRG updates/caller/impact
queries were source-verified in tracking, hooks, runner and tests. CRG reports truncated/unresolved
edges, so source and executable regressions establish the boundary. No structural Graphify rebuild
was needed. README, CHANGELOG, affected workflow Wiki and its log were updated.

Validation:
- Final focused transport/fencing/tracking suite: **193 passed in 2.18s**.
- Broader tracking/validator/runner/resume/reviewer suite: **523 passed, 2 skipped in 377.60s**.
- Full `scripts/check.ps1`: **PASS** on Windows/Python 3.12.10; Wiki lint 0 errors/0 warnings,
  Ruff format/lint, mypy (98 source files), **1046 passed, 3 skipped in 537.43s**, 89.54% coverage.
- Regressions cover delayed real-wrapper pre-write GETs at definition, field identity and field
  value stages: zero POSTs, no pending/fence during the read or after failure, ordinary read failure
  diagnostics and healthy synchronization after state reload. Mutation overall timeout still
  persists pending before POST and uncertain fences after timeout. Post-write verification timeout,
  socket/reset/connection loss, HTTP 408/500/502/503/504, definite 400/401/403 and independent GitHub
  readiness regressions remain covered.

No `.agent-cycle` artifacts or historical verdicts were modified, and no new automated review was
recorded. The existing implementer completion record is extended only with this corrective work.
Read-only connector lookup returned `Issue not found: PDFTR-47`; ticket fields and ticket/report
attachments could not be updated. No live mutation, guessed issue creation or reconciliation occurred.
Concise factual progress and test logs are under `temp/PDFTR-47-R4-*` and are not committed.

## Post-cycle human-approved corrective patch — R5

Baseline: clean `pdftr-47-youtrack-live-sync` at
`fd1ca03b45fa6f0bfea39ff04fca85016301b0e7`. Correction confined to the remaining independent
preparation finding, its regression tests and affected ticket/operational documentation.

Every operation now requires an explicit preparation callback. Issue-creation rechecks,
lifecycle identity/comment discovery, attachment identity checks and PR cross-link discovery run
before pending mutation intent. Payloads are prepared before execution. Preparation failures
record diagnostic events without creating or replacing mutation/idempotency evidence, so the
same non-repeatable action can retry after state reload. Existing pending/uncertain guards remain
unchanged; execution persists pending intent before a possible POST. Creation reconciliation that
cannot prove the dispatched write's outcome retains uncertainty. Exact identity and post-write
verification remain in place; GitHub readiness stays independent of YouTrack write fences.

Validation:
- Focused preparation/mutation-boundary regressions: **10 passed in 1.39s**.
- Broader tracking/validator suite: **203 passed in 3.38s**.
- Full `scripts/check.ps1`: **PASS**, Windows/Python 3.12.10; Wiki lint 0 errors/0 warnings,
  Ruff format/lint (333 files), mypy (98 source files), **1056 passed, 3 skipped in 458.13s**,
  coverage 89.54%.
- Wiki lint: 0 errors/0 warnings; targeted Ruff format/lint passed.
- Parameterized pre-write identity/duplicate GET timeouts cover all four paths, no mutation
  dispatch or transient/durable mutation evidence, restart retry and subsequent idempotency.
  Actual POST timeouts retain pending-before-dispatch evidence and non-repeatable uncertainty
  guards across restart. Existing transport/HTTP/definite-rejection/GitHub regressions passed.

ProjectWiki search, scoped existing Graphify evidence and incremental CRG caller/impact queries
were source-verified. CRG output is truncated and has unresolved edges; source checks confirm all
six production operation sites supply preparation and execution starts with POST, before any
verification/reconciliation GET. No dependencies, module boundaries or cycle schema changed.
Protected PDFTR-45/46 runner/reviewer/progress files and historical `.agent-cycle` artifacts remain
unchanged. No new automated review was recorded. YouTrack connector lookup returned
`Issue not found: PDFTR-47`; no ticket mutation or guessed creation occurred, and ticket/report
attachments remain unavailable. Factual progress/test logs: `temp/PDFTR-47-R5-*` (uncommitted).

## Post-cycle human-approved corrective patch — R6

Baseline: clean `pdftr-47-youtrack-live-sync` at
`c8ff18631b6c8d17b3bd8d4311cedfae2befcef7`. Only the remaining P2 independent-review finding
was addressed. A real REST-wrapper regression first reproduced POST 504 followed by discovery
GET 401 persisting `failed` instead of `uncertain`.

Creation now rethrows the original UncertainTransport when reconciliation discovery/verification
fails. Sanitized secondary read diagnostics are retained without replacing the mutation outcome;
identity mismatches also preserve uncertainty and set the existing identity-safety fence. Restart
lookup or a healthy absent lookup retains the non-repeatable creation guard. A later verified exact
ticket/project lookup resolves only that matching uncertain creation and reuses its canonical issue,
with no second POST. Unrelated field/definition fences and the original append-only mutation event
are preserved. Definite mutation rejections and all mandatory pre-write preparation remain unchanged.

Validation:
- Focused uncertain-create/reconciliation tests: **47 passed**.
- Broader tracking/validator suite: **250 passed in 3.95s**. Includes existing preparation,
  timeout/HTTP uncertainty, definite rejection, restart and independent GitHub readiness regressions.
- Full Windows `scripts/check.ps1`: **PASS**, Python 3.12.10; Wiki lint 0 errors/0 warnings,
  Ruff format/lint (334 files), mypy (98 source files), **1103 passed, 3 skipped in 453.14s**,
  coverage **89.54%**.
- The real-wrapper matrix covers POST 502/503/504/socket timeout/connection loss followed by
  GET 401/403/408/502/503/504/socket timeout/connection loss. It verifies original mutation
  diagnostics, durable uncertainty, restart/re-entry without duplication, exact reconciliation,
  unchanged unrelated fences, mismatch refusal and credential redaction.
- Initial sandboxed pytest setup failed with WinError 5 before assertions; the same uv workflow
  passed outside that ACL restriction. Temporary files, test logs and caches stayed under `temp/`.

ProjectWiki search and scoped existing Graphify orientation were source-verified. CRG incremental
update/caller analysis succeeded; graph output is bounded and source confirms the hooks/operator
boundary. All six production operation sites still require preparation and execute starts at POST.
No dependencies, module boundaries, schemas, runner/reviewer permissions, PDFTR-45/46 behavior or
historical `.agent-cycle` artifacts changed. No new automated review or live mutation was performed.
Read-only YouTrack lookup returned `Issue not found: PDFTR-47`; ticket fields and ticket/report
attachments remain unavailable. Concise factual progress: `temp/PDFTR-47-R6-progress.log`;
validation logs: `temp/PDFTR-47-R6-focused.txt`, `temp/PDFTR-47-R6-broader.txt`,
`temp/PDFTR-47-R6-check.txt` (uncommitted).

## Post-cycle human-approved corrective patch — R7

Baseline: clean `pdftr-47-youtrack-live-sync` at
`b196eaa691c3ec16b916a0a0eea203822ff3dcb4`; scope is only the remaining P2 diagnostic-sink finding.
Secondary create-reconciliation reporting now runs best-effort, while the original
UncertainTransport is re-raised outside that protection. A warning/reporting failure cannot replace
its operation classification or original mutation evidence. No transport classification, mutation
fence, identity check, reviewer permission, runner or PDFTR-45/46 behavior changed.

Four new regression cases reproduce POST 504 / reconciliation GET 503 with BrokenPipeError and
OSError from a transient or persistently unavailable diagnostic sink. They verify that the same
original mutation exception reaches outcome classification, the operation remains uncertain,
the HTTP 504 diagnostic and UncertainTransport journal event survive restart, re-entry sends no
second POST, and later exact-identity discovery resolves only the matching creation. Existing
HTTP/auth/socket reconciliation, preparation, rejection, identity and GitHub regressions remain.

Before the fix all four new cases failed; after the fix the focused suite passed 51 tests and
the broader tracking/validator suite passed 254 tests. ProjectWiki search, existing Graphify
orientation and CRG incremental update/caller analysis were source-verified; CRG reported no errors.

The first full-gate run was interrupted after detecting Windows backslashes stripped by pytest
option parsing; its generated test directory and output were preserved under `temp/`. The rerun
validated forward-slash options before execution. All validation caches, coverage and logs remain
under repository-local `temp/` and are uncommitted.

Read-only YouTrack lookup returned `Issue not found: PDFTR-47`; remote field updates and ticket/report
attachments remain unavailable. No live mutation, new automated review or historical `.agent-cycle`
artifact rewrite was performed. Concise progress: `temp/PDFTR-47-R7-progress.log`; validation logs:
`temp/PDFTR-47-R7-focused.txt`, `temp/PDFTR-47-R7-broader.txt`, `temp/PDFTR-47-R7-check.txt`.

Full Windows `scripts/check.ps1`: **1107 passed, 3 skipped in 649.43s**, coverage **89.54%**;
Wiki lint **0 errors/0 warnings**, Ruff format/lint and mypy **98 source files** passed.
This is an implementer completion record, not a new independent-review verdict.
