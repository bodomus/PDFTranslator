# Implementation Report

## Ticket

PDFTR-35A — Orchestrator safety follow-up. Fixes the four unresolved safety findings from the
PDFTR-35 round-2 review for SHA `1e3a3a78712ebb4f1e91f8090377759930e1546c`.

## Workflow

- Level: 2 (orchestration safety, process lifecycle, reviewer trust boundary).
- Graphify/CRG: reused the isolated `scripts` community; source and tests are authoritative.
- Working tree before changes: clean. Branch created from the PDFTR-35 implementation SHA
  `1e3a3a7`; PDFTR-35 history untouched.

## Scope

- Modules: `scripts/pi_ticket_cycle.py`, `scripts/agent_cycle.py` (small suffixed-ID integration
  fix), `tests/test_pi_ticket_cycle.py`, `tests/test_agent_cycle.py`, the two-agent skill
  contracts, README/CHANGELOG/Wiki.
- Pipeline stages: none; no `src/pdftranslate` change.
- Dependency impact: none (standard library only, including `ctypes` for the Windows Job Object).
- Model/device/OCR/PDF impact: none.

## Investigation

- Current behavior: prompts contradicted themselves on `.agent-cycle` writes; cancellation and
  post-spawn failures could leave a descendant Pi process alive; the reviewer parser scavenged any
  decodable object.
- Expected behavior: consistent ownership, deterministic process-tree termination, and a
  fail-closed single-envelope reviewer result.
- Root cause: see `.implementation-plans/investigation-PDFTR-35A.md`.

## Changes

- **R2 — ownership.** `_implementer_prompt` now permits creating/replacing only the designated
  handoff input and prohibits modifying any other coordination file; `_reviewer_prompt` states the
  reviewer returns JSON on stdout and never writes. `IMPLEMENTER_CONTRACT.md`, `REVIEWER_CONTRACT.md`
  and `SKILL.md` were aligned: the runner owns transitions, the runner persists the reviewer result.
- **R4 — process tree.** New `_ProcessTree` abstraction. Windows uses a Job Object with
  `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (assigned immediately at spawn; `TerminateJobObject` plus
  handle close), independent of the direct parent lifetime. POSIX captures the child's process
  group at spawn and signals the saved group (`SIGTERM` then `SIGKILL`), polling until it is gone.
- **R6 — exception-safe cleanup.** `SubprocessExecutor.run` wraps the post-spawn path in
  `try/except BaseException/else/finally`; every exit path terminates and verifies the owned tree of
  the direct child and descendants, reaps the direct child, closes the job handle, and surfaces a
  cleanup failure as an actionable `RunnerError`. `run_cycle` therefore stops only after cleanup.
- **R5 — strict extraction.** `extract_review_json` selects exactly one supported envelope (single
  ordered sentinel pair, else a single JSON fence, else whole stdout), parses the complete body as
  one object, and rejects arrays, malformed/truncated JSON, duplicate/unmatched/reversed delimiters,
  trailing body content, and any JSON outside the envelope. `agent_cycle` still validates the
  parsed object.
- **Integration defect.** `agent_cycle.TICKET_PATTERN` now accepts an optional uppercase suffix so
  canonical follow-up IDs such as `PDFTR-35A` (and existing `PDFTR-9A`/`10A`/`14A`/`16A`) can
  initialize; `tests/test_agent_cycle.py` updated.

## Validation

- Focused tests: `uv run pytest tests/test_pi_ticket_cycle.py tests/test_agent_cycle.py --no-cov -q`
  — all passed. Coverage includes real child+descendant termination (parent-exit and injected
  cancellation/I/O failure), read-only reviewer prompts, and malformed/contradictory reviewer output.
- Full gate: `.\scripts\check.ps1` — Wiki lint OK, Ruff format/check OK, mypy OK,
  `438 passed, 1 skipped`, coverage 89.10%.
- Real Pi/CUDA/OCR/PDF validation: not applicable; tests never contact providers.

## Remaining risks

- The Windows Job Object assignment races the shim launching Node; assignment happens immediately
  after `Popen`, before the batch/Node work begins, and the local probe plus tests confirm
  descendants are captured. If `AssignProcessToJobObject` ever fails (unusual nesting), the runner
  falls back to `taskkill /F /T`, which cannot traverse an already-exited parent.
- Real Pi end-to-end remains the next practical validation, as in PDFTR-35.
