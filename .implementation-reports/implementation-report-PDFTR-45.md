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

## Attempt 1 validation
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
- Approval persisted before implementation transition resumes the same attempt. Attempt 2 additionally resumes proven pre-launch active implementation under exclusive runner ownership; once the launch fence is crossed, process ownership remains uncertain and requires human inspection.
- Real provider classifications require a trusted adapter; current subprocess adapter does not parse provider message text.
- Final merge and remote CI approval remain human/CI decisions.
- Integration warnings: ["YouTrack credentials unavailable", "YouTrack credentials unavailable"]. Ticket attachments/tracking are runner-owned; no direct YouTrack API calls were made.

## Attempt 2 — reviewer R1
### Investigation and changes
- Clean baseline at attempt 1's SHA. Source confirmed the gap between `begin_implementation`
  persisting active IMPLEMENTING and the executor call. The previous before-launch test stopped
  before this transition and did not exercise the gap.
- Added a per-ticket OS lock held across the runner invocation (Windows byte-range locking /
  POSIX flock). Competing runners reject; process death releases ownership without stale PID guesses.
- Before beginning an approved operational attempt, persist an atomic attempt-specific `prepared`
  launch record bound to the approval, ticket, repository fingerprint, branch and exact HEAD.
  A matching strict record permits normal invocation to continue that active pre-launch attempt,
  without repeating begin, approval, attempt increment or review accounting. Clean unchanged Git
  facts and absence of accepted/contradictory handoff/review artifacts remain mandatory.
- Persist `launching` before entering the executor: any crash from that fence onward fails closed
  rather than guessing whether a child exists. Missing/corrupt/mismatched markers, legacy active
  phases and unsafe Git bindings reject without mutation. Historical markers/logs/journals/partial
  inputs remain preserved. No reviewer capabilities or review-recovery semantics changed.
- Regression tests crash immediately after begin and inside pre-launch tracking, then complete the
  same approved attempt. They verify accounting and diagnostics, duplicate approval rejection,
  dirty/changed HEAD/branch rejection, strict markers, contradictory artifacts, uncertain launch
  rejection, competing owners, cross-process lock enforcement and release after `os._exit`.

### Source/graph/design validation
- Graphify query `run_cycle begin_implementation operational retry` identified runner, validator,
  FakePi, retry/resume/tracking tests; source verified the relevant orchestration edges.
- CRG updated before and after changes using `PYTHONIOENCODING=utf-8 code-review-graph update --brief`.
  Scoped source inspection confirms CLI main -> run_cycle ownership wrapper -> _run_cycle;
  new marker paths are operational-only. No new package/module boundaries or PDF dependants.
- Kept ownership and marker checks as small synchronous functions/context manager, not a new
  service hierarchy. Standard library only; no dependencies or external APIs. Context7 unavailable.
  Graphify rebuild not required for this local fix; graph findings remain subordinate to tests/source.

### Final validation
- Focused cycle/retry/resume/progress/tracking suite: **329 passed, 2 skipped** (207.93 seconds).
- `scripts/check.ps1` via Windows PowerShell: **PASS**, **900 passed, 3 skipped** (256.48 seconds),
  **89.54%** package coverage. Wiki lint: 15 pages/139 links, no errors/warnings; Ruff format/lint
  and mypy (98 source files) passed. `git diff --check` passed.
- Initial broad focused run exposed early lock-file creation for invalid reviewer tools/unavailable
  initial executors; preflight ordering was corrected and all existing regressions now pass.
- Updated README, CHANGELOG, handoff contract, ticket plan, completion summary and affected Wiki/log.
- Windows locking and process containment exercised locally. Ubuntu CI is not claimed run; POSIX
  lock coverage executes through the same deterministic tests on Ubuntu. No provider/model downloads.

### Remaining boundary
A crash after the durable launch fence (even just before spawn), or contradictory/corrupt authoritative
artifacts, requires manual inspection. This deliberate conservative boundary avoids reopening a phase
whose child ownership is uncertain. The R1 begin-to-tracking-to-pre-launch gap is now resumable.
