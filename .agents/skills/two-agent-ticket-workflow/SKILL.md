---
name: two-agent-ticket-workflow
description: Run PDFTranslate tickets with one implementation writer and one sequential, read-only reviewer bound to an exact Git SHA through repository-local .agent-cycle state.
---

# Two-agent ticket workflow

Use this skill only when a ticket explicitly uses the repository agent cycle. It adds coordination
rules to the normal repository investigation and validation workflow; it does not replace
`.codex/PRE_TICKET_WORKFLOW.md`.

## Invariants

- The implementer is the only role permitted to modify project files, commit, or push.
- The reviewer checks exactly one explicit immutable SHA and does not modify project files.
- The roles run sequentially in one ticket branch and one working directory.
- A new implementation SHA invalidates every earlier review result.
- At most two automated review rounds are allowed.
- Final review and merge decisions remain human-owned.
- `scripts/agent_cycle.py` derives Git facts and validates transitions; neither agent's prose is
  authoritative for branch, HEAD, cleanliness, state, round, or verdict.

PDFTR-33 itself is the one bootstrap exception: the user explicitly authorized Codex to implement
the infrastructure before these controls existed. Do not generalize that exception to later tickets.
The current DeepSeek/Codex assignment is orchestration metadata; the contract itself uses only the
`implementer` and `reviewer` roles.

## Role routing

- Before implementing or handing off, read [IMPLEMENTER_CONTRACT.md](IMPLEMENTER_CONTRACT.md).
- Before reviewing, read [REVIEWER_CONTRACT.md](REVIEWER_CONTRACT.md).
- Before producing or consuming JSON, read [HANDOFF_CONTRACT.md](HANDOFF_CONTRACT.md).

## Normal sequence

1. Initialize a clean task-branch cycle and begin implementation.
2. The implementer implements, validates, commits, and pushes one SHA, then records its handoff and stops.
3. The reviewer begins a review for that exact SHA, remains read-only, records `PASS`,
   `CHANGES_REQUIRED`, or `BLOCKED`, and stops.
4. If changes are required after round one, the implementer produces and pushes a new SHA before a second
   review. Round-two changes required or a repeated exact finding stops the cycle.
5. A human performs the final review and decides whether to merge.

The validator records state only. It does not launch agents, fetch remotes, retry, merge, create a
pull request, or resolve conflicts.
