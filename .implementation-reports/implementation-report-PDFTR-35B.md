# Implementation Report

## Ticket

PDFTR-35B — Windows process-safety final fix. Two defects from the PDFTR-35A round-2 review:
R6-SPAWN (interrupt after `Popen` must always clean up the whole tree) and R4-RESUME (`ResumeThread`
result must be checked and a suspended process must never count as started).

## Workflow

- Level: 1 (narrow bugfix in one known module plus its tests).
- Branch: `pdftr-35b-windows-process-safety`, created from the PDFTR-35A head `10d8ae5`.
- CRG: reused; `scripts` is an isolated community. Source and tests are authoritative.
- Working tree before changes: clean.

## Scope

- Modules: `scripts/pi_ticket_cycle.py`, `tests/test_pi_ticket_cycle.py`, docs.
- `scripts/agent_cycle.py` unchanged. No workflow/state-machine redesign. No new dependencies.
- No `src/pdftranslate`, provider, model, rendering, OCR, or PDF impact.

## Changes

- **R6-SPAWN:** `_create_job_object` now closes the Job Object in a `except BaseException` guard so an
  interrupt during creation/configuration/assignment cannot leak the job or its members.
  `_WindowsProcessTree.__init__` is exception-safe: on any failure it closes the job (which, via
  `KILL_ON_JOB_CLOSE`, terminates a suspended or partially resumed tree) and re-raises. In
  `SubprocessExecutor.run` the ownership guard immediately follows `Popen` with no intervening
  statement, and `_terminate_without_tree` now also issues `taskkill /F /T` on Windows before
  killing/reaping the direct child. Any `KeyboardInterrupt` in that region therefore terminates and
  reaps the child and descendants before control returns.
- **R4-RESUME:** `ResumeThread` is declared `restype=DWORD` and wrapped by `_resume_thread`.
  `_resume_suspended_process` returns `(threads_resumed, failed)`, treating a
  `0xFFFFFFFF` result as failure. `_WindowsProcessTree.__init__` fails closed when resume failed or
  no thread was resumed: it closes the Job Object (terminating the child tree) and raises
  `RunnerError`, so a suspended process is never treated as a running child.

## Tests

- `test_windows_resume_thread_failure_is_detected` — `_resume_suspended_process` reports failure
  when `ResumeThread` fails.
- `test_windows_resume_failure_fails_closed` — a resume failure aborts `executor.run` with a
  `RunnerError` and the never-resumed child leaves no artifacts.
- `test_interrupt_during_tree_acquisition_terminates_child` — a `KeyboardInterrupt` raised at guard
  acquisition kills and reaps the direct child (cross-platform).
- `test_windows_interrupt_during_job_assignment_closes_job` — a `KeyboardInterrupt` injected inside
  `AssignProcessToJobObject` (after the real assignment) closes the Job Object, terminates the
  suspended child, and leaves no artifacts.

## Validation

- Focused: `uv run pytest tests/test_pi_ticket_cycle.py tests/test_agent_cycle.py --no-cov -q` —
  all passed.
- Full gate: `.\scripts\check.ps1` — Wiki lint OK, Ruff format/check OK, mypy OK,
  `459 passed, 3 skipped`, coverage 89.10%.
- Real providers/CUDA/OCR/PDF: not applicable.

## Remaining risks

- Windows Job Object containment still requires `AssignProcessToJobObject` to succeed; failure now
  fails closed rather than running an uncontrolled child.
- POSIX-specific tests run only on Ubuntu CI.
