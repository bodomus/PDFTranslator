# Implementation Plan — PDFTR-35 Pi sequential two-agent runner MVP

## Objective

Add one deterministic orchestration entry point, `scripts/pi_ticket_cycle.py`, that drives the
existing `scripts/agent_cycle.py` state machine through a sequential Pi implementer → Pi read-only
reviewer flow with at most one fix/review retry, and stops for human review.

## Non-negotiable design boundaries

- `scripts/agent_cycle.py` remains the only workflow authority. The runner imports and calls it;
  it never reimplements state, SHA, round, ownership, verdict, or cleanliness rules.
- Provider/model/tools are configuration values (`RoleConfig`), never state-machine concepts.
- Standard library only; no new dependency.
- No real provider, network, model, CUDA, or OCR use in tests or CI.
- No automatic fetch, stash, reset, clean, checkout, merge, PR, or retry loop.

## Files

### New: `scripts/pi_ticket_cycle.py`

Components:

1. Import bootstrap so `uv run python scripts/pi_ticket_cycle.py <TICKET>` works when executed as
   a file, while `from scripts.agent_cycle import ...` stays authoritative.
2. Configuration dataclasses:
   - `RoleConfig(provider, model, tools)`; defaults `deepseek/deepseek-v4-pro` and
     `openai-codex/gpt-6.1-sol/(read,grep,find,ls)`.
   - `RunnerConfig(implementer, reviewer, base_branch, executable)`.
3. Errors: `RunnerError`, `RunnerCancelled`.
4. Process adapter:
   - `CommandResult(returncode, stdout, stderr)`.
   - `PiExecutor` protocol with `run(command, *, cwd, log_path) -> CommandResult`.
   - `resolve_executable(name)` raising an actionable `RunnerError` when `pi` is absent.
   - `SubprocessExecutor` using `Popen`/`communicate`, no `shell=True`, KeyboardInterrupt ->
     terminate/kill -> `RunnerCancelled`, writes combined diagnostic log.
5. Command construction `_pi_command(config, prompt, executable)` (testable provider/model/tools).
6. Reviewer JSON extraction `extract_review_json(stdout)` with sentinel, then single fence, then
   whole-object fallback; zero/multiple/invalid -> fail closed.
7. Ticket/contract prompt loading:
   - `_load_ticket_text` discovers `Tickets/<TICKET>*.md` (or explicit path) and fails clearly if
     absent/ambiguous.
   - contract text is embedded from the two-agent skill with a concise built-in fallback.
   - `_implementer_prompt` and `_reviewer_prompt` include ticket, contracts, cycle context, exact
     SHA, read-only rule, JSON schema, and (round 2) reviewer findings.
8. `run_cycle(repo_root, ticket, *, executor, config)`:
   - preflight/init if absent; require `NEW`; `begin_implementation`.
   - loop: build/execute implementer, require exit 0 + clean tree, `record_handoff`, verify
     `cycle_status` HEAD; `begin_review` on exact SHA; build/execute reviewer; require exit 0;
     `extract_review_json`; persist role input; `record_review`.
   - `PASSED`/`BLOCKED`/`STOPPED` -> return outcome; `CHANGES_REQUIRED` -> next round only.
   - any failure -> best-effort `stop_cycle`, then raise `RunnerError`/`RunnerCancelled`.
9. `RunOutcome` and human-facing terminal report (`AGENT CYCLE PASSED` / stopped; never
   `READY TO MERGE`).
10. `argparse` CLI with ticket and optional overrides; exit code 0 only for `PASSED`.

### New: `tests/test_pi_ticket_cycle.py`

Deterministic, offline, isolated real Git fixtures under `temp/`. A scripted fake `PiExecutor`
records commands and simulates implementer commits/handoff and reviewer JSON/exit codes.

Required coverage:

1. One-round PASS.
2. CHANGES_REQUIRED → new SHA → round-2 PASS (and round-1 findings reach the second prompt).
3. Round-2 CHANGES_REQUIRED stops; no third reviewer run.
4. Reviewer command contains `openai-codex`, `gpt-6.1-sol`, and exactly `read,grep,find,ls`.
5. Implementer command contains `deepseek` and `deepseek-v4-pro`.
6. Malformed reviewer JSON fails closed and stops.
7. Wrong SHA / ticket / round fails closed.
8. Implementer abnormal exit never starts reviewer.
9. Reviewer abnormal exit never starts another role.
10. Dirty tree after implementer never starts reviewer.
11. No new SHA after CHANGES_REQUIRED prevents round-2 review.
12. Missing `pi` on PATH gives an actionable failure.
13. Cancellation never launches the next agent.
14. `agent_cycle.py` remains the real transition authority (manifest/review artifacts/state).

Plus focused unit tests for `extract_review_json` and `_pi_command`.

### Modified documentation

- `README.md`: one-command runner usage and stop/read-only semantics.
- `CHANGELOG.md`: `Added` entry.
- `knowledge/wiki/workflows/development-workflow.md`: automated runner boundary.
- `knowledge/wiki/log.md`: dated entry.

### Ticket artifacts

- `.implementation-plans/investigation-PDFTR-35.md` (done).
- `.implementation-plans/implementation-plan-PDFTR-35.md` (this file).
- `.implementation-reports/implementation-report-PDFTR-35.md`.
- `reviews/review-PDFTR-35.md`.

## Sequencing

1. Write investigation and plan (done).
2. Implement `scripts/pi_ticket_cycle.py`.
3. Write `tests/test_pi_ticket_cycle.py` and iterate on focused tests.
4. Update README, CHANGELOG, Wiki pages and log.
5. Run `uv run pytest tests/test_pi_ticket_cycle.py`,
   `uv run python scripts/project_wiki/wiki_lint.py`, `.\scripts\check.ps1`.
6. Post-change CRG update and blast-radius inspection.
7. Write the implementation report; commit; push; record handoff; stop.

## Validation commands

```powershell
uv run pytest tests/test_pi_ticket_cycle.py -q
uv run python scripts/project_wiki/wiki_lint.py
.\scripts\check.ps1
```

## Explicit non-goals

No Pi-Harness, EV/JEV routing, dynamic model/provider selection, parallel agents, multiple
implementers/reviewers, worktrees, automatic PR/merge, semantic finding similarity, retry policy
engine, daemon, scheduler, database, Web UI, Docker, remote orchestration, automatic fallback,
YouTrack mutation, or agent-to-agent chat.
