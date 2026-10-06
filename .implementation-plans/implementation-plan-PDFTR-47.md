# PDFTR-47 implementation plan

## Investigation (Level 2)
Clean baseline on pdftr-47-youtrack-live-sync. ProjectTracking is reached exclusively through
TrackingHooks in the startup-loaded runner. Existing exact identity checks are sound but bootstrap
creates without explicit permission, invents estimates/dates, omits read-after-write and preflight,
and reports generic exception classes. Normal reviewer capabilities remain read-only.
Graphify query `ProjectTracking TrackingHooks YouTrack` confirms this neighborhood; source verified
in scripts/project_tracking.py, tracking_hooks.py and pi_ticket_cycle.py. CRG update completed parsing
but its summary failed under cp1251; rerun with UTF-8. Context7 capability is unavailable in this session;
no dependency or third-party SDK is introduced. REST behavior remains explicitly unverified live.

## Plan
1. Keep project-tracking.toml canonical; bind HTTPS host to config, token only from environment.
2. Add categorized preflight, exact ensure with opt-in creation and re-read, field discovery diagnostics.
3. Remove invented defaults; resolve users by login, verify semantic writes, concise comments.
4. Add read-only/dry-run operator validator with explicit field/state/finalization opt-ins.
5. Preserve artifact/events and non-blocking hooks; serialize tracking synchronization locally.
6. Expand deterministic fakes/tests, update README/CHANGELOG/Wiki, run focused tests and check.ps1.
7. Record live limitations, commit/push, prepare runner-owned handoff input only.

## Attempt 2 — reviewer findings R1/R2
Level 1 scoped correction; clean baseline. CRG UTF-8 incremental preflight completed, Graphify queried
`ProjectTracking synchronization operation`; source-verified callers remain TrackingHooks and operator
validation, with tracking/validator tests. Graph translation adjacency is not an actual dependency.
R1: daemon transport can outlive lock ownership; repeatable field/definition operations need durable
pending/uncertain evidence that blocks all subsequent synchronization, not just identical action keys.
No automatic reset: operator reconciliation must prove old transport termination and remote state.
R2: ensure exceptions must set aggregate failure; validate configured types/period/date syntax before
bootstrap mutation and suppress completion claims on either synchronization pass failure.
Add delayed fake transport/restart, interrupted pending write, malformed-default and second-pass
failure regressions; preserve independent valid intent fields on partial validation failures.
Update README/CHANGELOG/affected Wiki/report; run focused suite, Wiki lint and full check.ps1;
commit/push a new SHA and prepare only designated handoff JSON. No live mutation or new dependencies.

## Attempt 3 — reviewer R1 transport-failure path
Level 1; clean baseline, existing Graphify query and UTF-8 CRG incremental preflight reused.
Source verifies `_request` converts socket timeout/connection loss to ordinary TrackingError,
bypassing the durable uncertain conflicting-write fence added in attempt 2.
Classify all non-HTTP failures after entering the mutation transport as UncertainTransport;
retain definite HTTP rejection and pre-dispatch identity validation. Include malformed response
and response-bound failures conservatively. No automatic reconciliation/reset or retry.
Exercise real request/_request via fake opener, dispatch delayed server-side state mutation then
raise socket timeout/reset/URLError before overall timeout; verify lifecycle/operator/restart remain
fenced before and after delayed completion. Verify redaction and definite rejection/read semantics.
Update operational docs/Wiki/report; run focused suite and full Windows check.ps1, commit/push,
prepare runner handoff only. No live access or mutation required.

## Attempt 4 — reviewer R2 independent GitHub readiness
Level 1, clean baseline. Graphify query `ProjectTracking passed synchronization` and UTF-8 CRG
incremental preflight succeeded; source verifies TrackingHooks/runner/operator entry points.
Root cause: synchronization applied the YouTrack reconciliation fence before `_passed`, preventing
GitHub PR verification and stale human-review evidence removal. Keep the shared OS lock and fresh
artifact reload, but bypass only its YouTrack-write prerequisite for `passed`. Check the fence within
PR processing, persist a specific cross-link skip warning, and never attempt YouTrack writes while
fenced. Preserve exact-SHA checks, local readiness revocation and all other synchronization fences.
Add pending/uncertain field/definition regressions for stable and moved GitHub heads, persisted
operation preservation and repeat PR idempotency. Update operational docs/Wiki/report, run focused
suite and full quality gate, commit/push and prepare only the designated handoff input.
No live mutations, dependencies, schema changes or reviewer capability changes.

## Attempt 5 — reviewer R3 ambiguous HTTP mutation responses
Level 1, clean baseline. Graphify scoped query and UTF-8 CRG incremental preflight succeeded;
source verifies `_request` treats all HTTP errors as definite failures, bypassing the durable
conflicting-write fence when an upstream write continues after a gateway/server error.
Classify mutation HTTP 5xx and request timeout 408 as UncertainTransport, preserving ordinary
read errors and definite 4xx rejections. Reuse operation's durable uncertainty persistence;
no retry/reset, schema, dependency, module-boundary or GitHub-readiness changes.
Extend real request-wrapper delayed-state regressions to HTTP errors; verify lifecycle/operator
validation stay fenced across restart and after delayed completion, sanitized evidence and no
newer state claim. Retain independent GitHub regressions and definite rejection/read tests.
Update operational docs/Wiki/report; run focused tests and full Windows check.ps1, commit/push,
then write only runner-designated handoff input. No live mutation required or performed.

## Impact
Only harness tracking, its configuration, tests and documentation. No PDF, model, OCR, dependency,
agent-cycle schema, exact-SHA or reviewer-tool changes. No live API calls during implementation.

## Post-cycle human-approved correction — R4
Level 1, clean baseline 9839b05942c864ab12a13090f1a20c8a14ee5d42 on the existing ticket branch.
Graphify scoped query, successful CRG update/caller queries and ProjectWiki search were verified in
current source. Overall request timeout incorrectly classifies GET as mutation uncertainty; operation
also journals pending evidence before its field/definition preparation reads.
Classify read-only timeouts as ordinary ReadTimeout; run field/definition preparation before pending
journaling; preserve write-ahead fencing and post-write verification timeout protection. Retain
mutation socket/connection/HTTP 408/5xx uncertainty and definite rejection behavior.
Verify delayed preparation reads with zero POST dispatch and no transient/persisted fence, restart
recovery, pending evidence before POST, and post-write verification fences. Run focused and broader
tracking/validator regressions, Wiki lint and full check.ps1; append factual completion evidence,
commit/push the existing branch and verify cleanliness. No agent-cycle artifacts or verdicts change.
