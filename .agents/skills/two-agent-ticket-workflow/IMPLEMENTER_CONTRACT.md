# DeepSeek implementer contract

DeepSeek owns all repository mutation for ordinary tickets using the agent cycle.

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
- Prepare only the DeepSeek section input documented in `HANDOFF_CONTRACT.md`, then run:

  `uv run python scripts/agent_cycle.py handoff <TICKET> --file <DEEPSEEK-JSON>`

- If remote verification is required, validate the already-present remote-tracking ref with
  `status --verify-remote <REMOTE>`. The validator never fetches.
- Stop and yield control after handoff. Do not continue editing until a Codex result is returned.

DeepSeek must not claim authoritative current HEAD, branch, clean-tree state, review round, reviewed
SHA, or verdict. The validator derives or owns those facts.
