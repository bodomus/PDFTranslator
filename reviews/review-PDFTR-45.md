# PDFTR-45 implementation completion summary

Implemented separate human-approved pre-handoff operational retry with structured stop policy,
strict identity/clean-tree/exact-HEAD gates, independent attempt accounting, a three-retry bound,
audited approval resume and retained failed-attempt diagnostics. Reviewer permissions and exhausted
review recovery remain unchanged.

Attempt 2 resolves R1: exclusive OS runner ownership and atomic prepared/launching attempt markers
resume a proven pre-launch crash after begin/tracking without duplicate approval/accounting.
Unknown launch ownership and unsafe/corrupt evidence remain fail-closed.

Attempt 3 closes R1's remaining gap between begin's manifest and handoff replacements. Under
exclusive prepared ownership, normal resume atomically completes only the exact blank previous
approved projection after full identity/clean-tree/exact-HEAD validation. Nonblank/contradictory
handoffs and uncertain markers reject without mutation or repeated approval/accounting.

Validation: 352 focused tests passed (2 skipped); final Windows PowerShell quality gate passed,
923 tests passed (3 skipped), 89.54% coverage. README, CHANGELOG, contract and affected Wiki updated.
See `.implementation-reports/implementation-report-PDFTR-45.md` for scope and compatibility limits.
Legacy text-only operational stops remain unknown; Ubuntu CI is pending remote execution.
Integration warnings: ["YouTrack credentials unavailable", "YouTrack credentials unavailable", "YouTrack credentials unavailable"].

This is an implementer completion summary, not the independent exact-SHA reviewer verdict.

## Post-cycle human-approved corrective patch

R1 rejects unauthorized numbered implementation/review snapshots while loading an approved
pre-first-handoff operational attempt, before normalization, preservation, journal append or
transition. Valid later review/rework history and failed-attempt diagnostics remain accepted.
R2 compares the exact blank approval-crash projection through canonical JSON, rejecting nested
Boolean/float substitutions for integer zero before normalization.

Focused validator/retry/runner/resume/progress/reviewer-Git/tracking suite: 471 passed, 2 skipped.
Windows PowerShell `scripts/check.ps1`: PASS, 933 passed, 3 skipped, 89.54% coverage; Wiki lint,
Ruff format/lint and mypy passed. An initial sandbox Node-to-Git `spawn EPERM` was resolved by
running the authorized Windows checks outside the sandbox; no production permissions changed.
All 20 historical cycle files other than the append-only implementer journal retain their hashes.
The completed cycle verdict is retained as historical evidence, not approval of the new patch SHA.

YouTrack MCP returned `Issue not found: PDFTR-45`; fields and attachments could not be updated.
Ubuntu CI was not run locally. This remains an implementation summary, not a new review verdict.
