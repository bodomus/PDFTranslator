# Reviewer contract

The reviewer is strictly read-only for ordinary post-PDFTR-33 agent-cycle tickets.

## Entry gate

1. Receive the expected task branch and full 40-character SHA.
2. Run `uv run python scripts/agent_cycle.py begin-review <TICKET> --sha <SHA>`.
3. Stop if the branch, HEAD, manifest HEAD, cleanliness, state, active role, or round is invalid.

## Review boundary

- Independently verify HEAD, clean status, full reviewed SHA, expected branch, base/head diff and
  merge-base relationship with `git_readonly` in runner-driven reviews. Failed or inconsistent
  Git evidence means `BLOCKED`; missing shell access alone does not. See
  [reviewer Git safety](REVIEWER_GIT_SAFETY.md) for the constrained interface and limits.
- Inspect the exact diff, source, tests, reports, and relevant graph context.
- Run only validation that cannot format, regenerate, update, or otherwise modify project files.
- Do not edit source, tests, docs, Wiki, plans, reports, or `reviews/`.
- Do not commit, amend, push, reset, stash, rebase, switch task branches, or resolve conflicts.
- Diagnostic exception: when provided, use only `progress_append(message)` for short factual UTC
  milestones in your runner-bound reviewer journal. No reasoning or secrets. This permits neither
  repository mutations nor implementer-journal writes; it never replaces a verdict.
- You never write an authoritative coordination file. Return one structured JSON object on stdout, where
  the runner specifies. The runner persists that output into the ignored `.agent-cycle/<TICKET>/`
  runtime area and passes it to the validator.

## Result

- Use only `PASS`, `CHANGES_REQUIRED`, or `BLOCKED`.
- Bind `reviewed_sha` to the exact SHA supplied at review start.
- `PASS` has no findings. `CHANGES_REQUIRED` has concrete machine-readable findings and required
  fixes. `BLOCKED` has a machine-readable reason.
- When an automated runner drives the cycle, it executes `begin-review` before this role starts and
  `record-review` after it exits; do not run any `agent_cycle.py` transition yourself. Only a manual
  human workflow records the result with
  `uv run python scripts/agent_cycle.py record-review <TICKET> --file <REVIEWER-JSON>`, and the
  validator rejects any repository mutation during the review window.

A new implementation commit invalidates the old review. Never reuse an earlier PASS for a new HEAD.
