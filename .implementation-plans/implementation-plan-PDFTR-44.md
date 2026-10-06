# PDFTR-44 investigation and implementation plan

## Preflight (Level 2)
Clean tree on `pdftr-44-agent-progress-journal`, Python 3.12.10 with uv.
Ticket already saved at `Tickets/PDFTR-44-agent-progress-journal.md`; external attachment is runner-owned.
ProjectWiki search: agent cycle. Source verified runner, reviewer extension, FakePi and resume tests.
Graphify query `pi_ticket_cycle ProgressReporter` identifies runner/test neighborhood; source confirms.
CRG `update --brief` updated graph but console encoding failed (cp1251); retry with UTF-8.
Context7 capability unavailable; installed Pi extension docs/examples are the local API reference.

## Investigation
Current timed communicate emits only elapsed duration; reviewer has no mutation capability.
Missing capability: role-bound append-only journal plus safe bounded parser and stale observation.
Authoritative validator artifacts, exact SHA checks and process cleanup must not change.
No PDF, translation, model, OCR, dependencies or cache effects.

## Plan
1. Add focused progress module: centralized prompt policy, bounded parser, per-execution monotonic stale tracking and preserved boundary entries.
2. Add narrow Pi `progress_append` extension bound by runner CLI flags to ticket/role; no path parameter. Reviewer guard permits only this diagnostic exception.
3. Wire prompt, heartbeat and terminal diagnostics; minimal CLI configuration defaults enabled / 30 minutes / 180 chars. Never kill for staleness.
4. Deterministic parser, heartbeat, role capability, failure and resume tests; retain existing cleanup/SHA tests.
5. Update contracts, README, CHANGELOG and affected Wiki; focused tests, Wiki lint and full PowerShell gate.
6. Report, commit, push, designated implementer handoff only. No manual transitions or other coordination writes in this execution.
