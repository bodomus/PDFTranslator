# Implementation plan — PDFTR-37

1. Complete the required investigation and retain ticket text under `Tickets/PDFTR-37.md`.
2. Add four immutable role presets with explicit CLI field precedence and existing reviewer
   allowlist enforcement before cycle initialization.
3. Add a minimal lifecycle reporter and bounded communicate retries for five-minute heartbeat;
   retain all existing process ownership, cleanup, transition, and two-round behavior.
4. Treat only IMPLEMENTING + active implementer + live dirty tree as expected status information.
5. Add deterministic regression tests for preset swapping, same-model independent invocations,
   lifecycle/heartbeat, error/cancellation cleanup, and strict cleanliness outside active editing.
6. Update README/CHANGELOG and only the affected Wiki page/log; refresh CRG and inspect scope.
7. Run focused tests, full pytest, Wiki lint, and complete `scripts/check.ps1` gate.
8. Write implementation report and completion summary under `reviews/`; attach required artifacts,
   commit/push, verify remote and CI results, record implementer handoff, and stop.

No reviewer, PR, merge, new state transition, retry engine, worktree, or PDF behavior change.

## CI coverage follow-up (2026-10-03)

1. Inspect Windows CI failure at implementation SHA `468db7977ecb2c15aea1fc45a254abc8589040b3`.
2. Preserve PID/argv/config and parallel coverage data from heartbeat/process-tree fixtures;
   prove which files carry statement-only metadata and reproduce the exact combine error.
3. Disable inherited automatic coverage startup only in `test_pi_ticket_cycle.py`; preserve
   running parent measurement, project branch policy, and production subprocess semantics.
4. Add a real executor child/grandchild diagnostic, and confirm it fails without isolation.
5. Run focused tests, `uv run pytest`, `scripts/check.ps1`, update affected documentation,
   commit/push the fix, and stop without launching a reviewer.
