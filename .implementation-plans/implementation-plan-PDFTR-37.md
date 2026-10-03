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
