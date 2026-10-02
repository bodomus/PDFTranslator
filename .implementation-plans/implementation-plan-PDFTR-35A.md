# Implementation Plan — PDFTR-35A Orchestrator safety follow-up

## Objective

Close the four PDFTR-35 round-2 findings with regression coverage, keeping `agent_cycle.py` as the
only state authority and remaining dependency-free.

## Changes

### `scripts/pi_ticket_cycle.py`

**R2 — consistent ownership instructions.**
- Implementer prompt: explicitly permit creating/replacing *only* the designated
  `.agent-cycle/<TICKET>/implementer.json` handoff input; explicitly prohibit modifying
  `manifest.json`, `handoff.json`, `review-*.json`, `reviewer-input-*.json`, and any other
  coordination file, and prohibit running transitions.
- Reviewer prompt: state the reviewer is read-only, produces its verdict on stdout, and that the
  runner persists it into ignored `.agent-cycle` state; never instruct the reviewer to write.

**R4 — process-tree ownership independent of parent lifetime.**
- Introduce a `_ProcessTree` abstraction:
  - Windows: create a Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` via `ctypes`, assign
    the spawned process immediately, terminate with `TerminateJobObject`, and close the handle
    (which also kills survivors). Fall back to `taskkill /F /T` only if job setup fails.
  - POSIX: capture `os.getpgid(pid)` at spawn and signal that saved group (`SIGTERM`, bounded wait,
    `SIGKILL`, poll `killpg(pgid, 0)`), never re-resolving a reaped PID.
  - `terminate()` returns whether the tree is confirmed empty; `close()` always releases the handle.

**R6 — exception-safe cleanup.**
- Wrap every post-spawn path in `try/except BaseException/else/finally`: on cancellation, failure,
  or completion, terminate the owned tree (including descendants) before the failure propagates,
  reap the direct child, and close the job handle. Surface cleanup failure as an actionable
  `RunnerError`. `run_cycle` therefore records a stop only after executor cleanup completes.

**R5 — strict single-envelope extraction.**
- Replace scavenging with `_single_envelope`: exactly one ordered sentinel pair, else exactly one
  JSON fence, else the whole trimmed stdout. Parse the complete envelope body with `json.loads` as
  exactly one object; reject arrays, malformed/truncated JSON, trailing body content,
  duplicate/unmatched/reversed delimiters, and any JSON object outside the envelope. Keep
  `record_review` as the schema/verdict authority.

### Contracts — `.agents/skills/two-agent-ticket-workflow/`

- `IMPLEMENTER_CONTRACT.md`: the automated runner owns transitions; the implementer writes only its
  own handoff input.
- `REVIEWER_CONTRACT.md`: the reviewer is read-only and returns JSON on stdout; the runner persists
  it. Remove the instruction that the reviewer writes the coordination input.
- `SKILL.md`: note the runner persists reviewer output.

### `scripts/agent_cycle.py`

- Allow the optional uppercase suffix in `TICKET_PATTERN` (already applied) so canonical follow-up
  IDs initialize; test updated in `tests/test_agent_cycle.py`.

### Tests — `tests/test_pi_ticket_cycle.py`

- R2: prompts permit the handoff path, protect coordination files, and remain read-only.
- R4: real parent that exits while a descendant survives, plus Ctrl+C cancellation; assert all
  descendants gone via the same group/job primitives.
- R5: truncated JSON, array-wrapped payload, extra/contradictory object, reversed/unmatched
  delimiters rejected with no PASS artifact and no next role; a single valid object accepted.
- R6: inject an I/O failure after a real child + descendant spawn; assert both terminate, state is
  `STOPPED`, and no further role runs.

### Docs

- `README.md`, `CHANGELOG.md`, `knowledge/wiki/workflows/development-workflow.md`,
  `knowledge/wiki/log.md`.

## Validation

```powershell
uv run pytest tests/test_pi_ticket_cycle.py --no-cov -q
uv run pytest tests/test_agent_cycle.py --no-cov -q
uv run python scripts/project_wiki/wiki_lint.py
.\scripts\check.ps1
```

## Non-goals

No new dependencies, parallel agents, worktrees, PR/merge automation, retry engine, provider/model
routing, daemon, database, Docker, or YouTrack automation. No unrelated production refactors.
