# Investigation — PDFTR-37

Scope: console lifecycle/heartbeat, runtime role/model presets, active implementation status
presentation. Base: master at 390467263a4be4961225b7d0b85752b4fd51e02c. Initial tree was clean.
No PDF/translation changes, new transitions, retries, worktrees, or reviewer execution.

## Required investigation answers

1. `SubprocessExecutor.run()` blocks in `process.communicate(input=stdin_text)` after the
   Windows Job Object or POSIX process-group owner has been acquired.
2. Retry `communicate(timeout=300)` after `TimeoutExpired`, supplying stdin only on the first
   call. Report elapsed monotonic time through a callback; never expose captured output.
   This avoids threads, additional process owners, and live transcript streaming.
3. Keep the timeout loop inside the existing guarded try/except/finally. Job creation,
   suspended Windows launch/resume, group capture, termination, waiting, and close stay intact.
   Cancellation, pipe errors, and heartbeat callback failures still take existing cleanup paths.
4. Runner reports phase boundaries and validated results; executor reports only elapsed time
   while the owned child is running. A small reporter formats plain flushed console lines.
5. Ticket, role, provider/model, attempt, validated SHA, review round/verdict, and authoritative
   terminal state belong to the runner. The executor receives an elapsed-time callback only.
6. Existing CLI flags are `--implementer-provider`, `--implementer-model`,
   `--reviewer-provider`, `--reviewer-model`, and `--reviewer-tools`.
7. Use an immutable pair of existing `RoleConfig` values, stored in a four-entry preset mapping.
   No configuration file or dependency is necessary.
8. Explicit CLI fields override the selected preset field independently. Unspecified fields
   use the preset or existing defaults. Argparse choices reject unknown presets before state
   initialization. Default reviewer tools remain `read,grep,find,ls` for all providers.
9. `validate_reviewer_config()` runs before executable checks or cycle initialization.
   `_pi_arguments()` passes the allowlist to each independent reviewer child invocation.
10. `cycle_status()` compares live Git cleanliness with the manifest's phase-entry snapshot.
    This snapshot stays clean while the implementer is legitimately editing.
11. Suppress only that cleanliness mismatch when state is IMPLEMENTING, active role is
    implementer, and the live tree is dirty; label this expected condition in text and JSON.
    HEAD/branch binding and every transition's clean-tree requirements remain unchanged.
    REVIEWING, NEW, READY_FOR_REVIEW, PASSED, and STOPPED keep existing status validation.
12. Production edits: `scripts/pi_ticket_cycle.py`, `scripts/agent_cycle.py` only. Regression
    tests: `tests/test_pi_ticket_cycle.py`, `tests/test_agent_cycle.py`. Documentation:
    README, CHANGELOG, affected development-workflow Wiki/log, and ticket-specific artifacts.

## Repository intelligence and risk

ProjectWiki search: `agent cycle process runner status`; source-verified development workflow.
CRG incremental preflight updated the Pi runner/tests from the previous graph SHA; queries cover
`run_cycle` and `cycle_status`. Graphify's older snapshot is orientation only; it lacks the newer
Pi runner, so current source/tests are authoritative. No graph conclusion determines behavior.

Process safety is the primary regression risk: retrying communication must not resend stdin,
reset the process group, release the Job Object early, or bypass cleanup on callback exceptions.
Console output must exclude prompts, credentials, child stdout/stderr, and model reasoning.
Preset independence must be tested by role/prompt rather than provider identity.

## Validation

Deterministic fake timing/process tests; role/preset/override and allowlist tests; lifecycle,
second-round and stop tests; dirty-state/gate tests; existing real local process-tree safety
tests. Focused runner/validator suite, full pytest and `scripts/check.ps1`, Wiki lint. No Pi or
LLM provider is run. Push the implementation branch to trigger Windows/Ubuntu CI, record its
actual results separately, hand off implementation only, and stop without launching a reviewer.
