# Reviewer contract

The reviewer is strictly read-only for ordinary post-PDFTR-33 agent-cycle tickets.

## Entry gate

1. Receive the expected task branch and full 40-character SHA.
2. Run `uv run python scripts/agent_cycle.py begin-review <TICKET> --sha <SHA>`.
3. Stop if the branch, HEAD, manifest HEAD, cleanliness, state, active role, or round is invalid.

## Review boundary

- Inspect the exact diff, source, tests, reports, and relevant graph context.
- Run only validation that cannot format, regenerate, update, or otherwise modify project files.
- Do not edit source, tests, docs, Wiki, plans, reports, or `reviews/`.
- Do not commit, amend, push, reset, stash, rebase, switch task branches, or resolve conflicts.
- The only permitted result is a structured reviewer input for the validator. If the execution
  environment cannot create that ignored coordination input safely, return the same JSON on stdout
  for a system runner to persist.

## Result

- Use only `PASS`, `CHANGES_REQUIRED`, or `BLOCKED`.
- Bind `reviewed_sha` to the exact SHA supplied at review start.
- `PASS` has no findings. `CHANGES_REQUIRED` has concrete machine-readable findings and required
  fixes. `BLOCKED` has a machine-readable reason.
- Record with `uv run python scripts/agent_cycle.py record-review <TICKET> --file <REVIEWER-JSON>` and
  stop. The validator rejects any repository mutation during the review window.

A new implementation commit invalidates the old review. Never reuse an earlier PASS for a new HEAD.
