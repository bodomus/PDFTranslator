# Implementer contract

The implementer owns all repository mutation for tickets using the agent cycle.

> Automated runners. When an orchestrator (for example `scripts/pi_ticket_cycle.py`) drives the
> cycle, the runner executes `begin-implementation` before launching this role and `handoff` after
> it exits. In that mode the implementer must not run any `agent_cycle.py` transition. The
> implementer's only coordination write is its designated handoff input file, whose exact path the
> runner supplies; it must never modify `manifest.json`, `handoff.json`, review artifacts, or any
> other coordination file under `.agent-cycle/`.

## Before work

1. Read repository instructions, the ticket, and the normal pre-ticket workflow.
2. Confirm the expected ticket branch and one working directory.
3. Run `uv run python scripts/agent_cycle.py begin-implementation <TICKET>` only from `NEW` or the
   first `CHANGES_REQUIRED` state.
4. Preserve unrelated user changes. Do not clean, reset, stash, rebase, or overwrite them.

## Implementation and handoff

- Implement the smallest coherent change and update tests, docs, Wiki, plan, and report as required.
- Run focused validation and the repository quality gate.
- Commit and push the task branch. A second attempt must produce a new SHA.
- Prepare only the implementer section input documented in `HANDOFF_CONTRACT.md`, then run:

  `uv run python scripts/agent_cycle.py handoff <TICKET> --file <IMPLEMENTER-JSON>`

- If remote verification is required, validate the already-present remote-tracking ref with
  `status --verify-remote <REMOTE>`. The validator never fetches.
- Stop and yield control after handoff. Do not continue editing until a reviewer result is returned.

The implementer must not claim authoritative current HEAD, branch, clean-tree state, review round, reviewed
SHA, or verdict. The validator derives or owns those facts.
