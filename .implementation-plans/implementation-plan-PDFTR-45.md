# PDFTR-45 investigation and implementation plan

## Investigation (Level 2)
Baseline: clean, ticket branch `pdftr45-operational-stopped-retry.md`, Python 3.12 via uv.
Validator `stop_cycle` records only text; `reopen_cycle` supports exhausted reviews only.
Runner derives attempt from review round, truncates implementer logs and removes stale input.
Progress journals already append execution boundaries and must remain append-only.
Graphify query `reopen_cycle run_cycle stop_cycle` identifies validator, runner, resume tests and tracking callers; verified in source. CRG update parsed successfully but console encoding failed; retry with UTF-8. No Context7 tools available; no new external APIs or dependencies needed.
No PDF, translation, OCR, model or package boundary impact.

## Attempt 2 / R1 investigation and plan
The runner records active IMPLEMENTING before tracking hooks and child launch. A crash there
currently cannot resume. Add an OS-held per-ticket runner lock (released on process death), and
an atomic attempt-bound prepared/launching marker for operational approvals. Only a strictly
validated prepared marker plus exclusive ownership and unchanged clean Git facts may resume
IMPLEMENTING without repeating begin/approval/accounting. Persist launching before executor entry;
uncertain launch ownership, legacy active phases, corrupt markers and concurrent runners reject.
Regression tests inject crashes after begin and tracking, check preserved diagnostics/accounting,
and prove launch-side uncertainty and competing owners fail closed. No external library API or
PDF/model boundary changes; source-verified Graphify and CRG preflight performed.

## Plan
1. Add optional strict structured stop fields and operational approval history, separate retry policy/state, cumulative attempt accounting and read-only eligibility.
2. Integrate separate runner/validator CLI, classified process failures, approval resume, preserved attempt artifacts and observable attempt diagnostics.
3. Add deterministic policy/runner tests, preserve existing review recovery and containment contracts.
4. Update README, changelog, contract and affected Wiki; run focused tests, Wiki lint and PowerShell quality gate.
5. Commit/push and prepare only the designated handoff input. External tracking owned by runner; integration warning: YouTrack credentials unavailable.

Legacy text-only failures remain unknown and cannot be automatically migrated from provider strings. The PDFTR-44 operational shape is covered with structured process-exit classification; pre-existing unclassified manifests require manual intervention.
