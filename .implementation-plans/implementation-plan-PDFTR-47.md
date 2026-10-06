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

## Impact
Only harness tracking, its configuration, tests and documentation. No PDF, model, OCR, dependency,
agent-cycle schema, exact-SHA or reviewer-tool changes. No live API calls during implementation.
