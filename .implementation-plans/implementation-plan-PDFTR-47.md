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

## Impact
Only harness tracking, its configuration, tests and documentation. No PDF, model, OCR, dependency,
agent-cycle schema, exact-SHA or reviewer-tool changes. No live API calls during implementation.
