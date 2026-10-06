# Implementation Report — PDFTR-45

## Workflow and investigation
- Level 2; initial tree clean. Python 3.12 / existing uv workflow; no dependencies added.
- Source-verified Graphify query identified `agent_cycle`, `pi_ticket_cycle`, resume/progress tests and tracking callers. Updated AST graph; reverse callers of `retry_operational_cycle` are validator `main` and runner `run_cycle`.
- CRG updated successfully with UTF-8 console configuration after an initial CP1251 output failure. Reported graph test gaps were checked against deterministic tests; runtime/dynamic test relationships are not graph authority.
- Design: separate policy functions/state and an optional typed adapter failure code; no new service hierarchy or package boundary.
- Current gap was free-text-only stops, review-derived attempts, overwritten logs/stale inputs, and review-only recovery. No PDF, translation, model, CUDA, OCR or package behavior changes.

## Changes
- Added structured stop class/code, separate human-approved operational retry state and strict optional audit/attempt fields; legacy manifests remain readable.
- Retry gates require round zero, no accepted handoff/review or contradictory immutable artifacts, no active agent, clean tree, unchanged exact HEAD, recorded branch/repository/ticket and valid strict JSON. Symlink/junction boundaries reject. Rejected approval never mutates artifacts.
- Three operational retries maximum. Persisted attempt accounting does not grant reviews. Existing exhausted-review recovery and new-SHA requirements remain intact, including after operational retry; legacy review classification uses immutable review evidence instead of stop text.
- Runner/validator expose distinct approval CLI; status includes class/code, attempt/count and eligibility reason. Duplicate approval rejects; normal invocation resumes the existing approval. Atomic manifest approval can recover its blank handoff projection after interruption between writes.
- Nonzero exits, termination and OS process launch/runtime failures receive stable codes. Trusted adapters can supply explicit quota/provider/network/auth codes; uncertain adapter/runtime failures stay unknown. No provider-message substring policy.
- Unique cumulative implementer logs and append-only journals survive. Partial input and prior report receive attempt-numbered snapshots. Heartbeat/final diagnostics include implementation attempt/retry count. Reviewer capabilities and process-tree containment are unchanged.

## Validation
- Focused validator/retry/resume/runner/progress/tracking tests: **314 passed, 2 skipped** (`--no-cov`, isolated repository-local fixtures).
- Final `scripts/check.ps1` via Windows PowerShell: **PASS**, **885 passed, 3 skipped**, **89.54%** package coverage. Includes Wiki lint, Ruff format/lint and mypy (98 source files).
- An earlier combined focused-plus-gate command exceeded the tool duration; the standalone final gate completed successfully in 243 seconds.
- Wiki lint: 15 pages, 139 links, zero errors/warnings. Diff whitespace check passed.
- No provider/network/model downloads during tests. Windows containment tests passed; POSIX-specific cases remain platform-skipped locally. Ubuntu/GitHub CI is not claimed executed here.

## Documentation and impact
Updated README, CHANGELOG, handoff contract, affected development Wiki/log and ticket-scoped plan. New deterministic tests cover approval/handoff, safety bindings, strict/corrupt JSON, artifact/history preservation, counting/bounds, crash/resume, status, trusted/unknown classification and review-recovery compatibility.
Blast radius is local cycle validation/orchestration and diagnostic output. Tracking and progress regression suites pass; no unexpected PDF subsystem dependants.

## Compatibility and remaining risks
- Legacy text-only operational stops, including an already-created PDFTR-44 manifest without classification, remain unknown and require manual intervention. This is the ticket's fail-closed backward-compatibility rule: no unsafe inference from `implementer exited with code 1` or quota text. Newly recorded identical round-zero process failures support the new approval command without directory renaming.
- Approval persisted before implementation transition resumes the same attempt. Once an active phase is recorded, process ownership is not guessed; active phases retain the existing human-inspection gate.
- Real provider classifications require a trusted adapter; current subprocess adapter does not parse provider message text.
- Final merge and remote CI approval remain human/CI decisions.
- Integration warnings: ["YouTrack credentials unavailable"]. Ticket attachments/tracking are runner-owned; no direct YouTrack API calls were made.
