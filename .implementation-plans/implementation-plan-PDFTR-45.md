# PDFTR-45 investigation and implementation plan

## Investigation (Level 2)
Baseline: clean, ticket branch `pdftr45-operational-stopped-retry.md`, Python 3.12 via uv.
Validator `stop_cycle` records only text; `reopen_cycle` supports exhausted reviews only.
Runner derives attempt from review round, truncates implementer logs and removes stale input.
Progress journals already append execution boundaries and must remain append-only.
Graphify query `reopen_cycle run_cycle stop_cycle` identifies validator, runner, resume tests and tracking callers; verified in source. CRG update parsed successfully but console encoding failed; retry with UTF-8. No Context7 tools available; no new external APIs or dependencies needed.
No PDF, translation, OCR, model or package boundary impact.

## Plan
1. Add optional strict structured stop fields and operational approval history, separate retry policy/state, cumulative attempt accounting and read-only eligibility.
2. Integrate separate runner/validator CLI, classified process failures, approval resume, preserved attempt artifacts and observable attempt diagnostics.
3. Add deterministic policy/runner tests, preserve existing review recovery and containment contracts.
4. Update README, changelog, contract and affected Wiki; run focused tests, Wiki lint and PowerShell quality gate.
5. Commit/push and prepare only the designated handoff input. External tracking owned by runner; integration warning: YouTrack credentials unavailable.

Legacy text-only failures remain unknown and cannot be automatically migrated from provider strings. The PDFTR-44 operational shape is covered with structured process-exit classification; pre-existing unclassified manifests require manual intervention.
