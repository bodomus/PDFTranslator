# PDFTR-35 — Pi sequential two-agent runner MVP

## Goal

Automate the proven PDFTR-33/PDFTR-34 two-agent workflow with Pi while keeping
`scripts/agent_cycle.py` as the deterministic authority for state, exact SHA binding,
review rounds, ownership, and fail-closed safety.

Runtime assignment:

```text
implementer → Pi / deepseek / deepseek-v4-pro
reviewer    → Pi / openai-codex / gpt-6.1-sol
```

Workflow roles remain product-neutral: `system`, `implementer`, `reviewer`.

## Proven prerequisite

Both Pi subprocess smoke tests already pass locally:

```powershell
pi --provider deepseek --model deepseek-v4-pro -p "Reply exactly: IMPLEMENTER_OK"
pi --provider openai-codex --model gpt-6.1-sol --tools read,grep,find,ls -p "Reply exactly: REVIEWER_OK"
```

Do not re-solve provider authentication in this ticket.

## Target flow

```text
one command
→ agent_cycle preflight/init
→ Pi implementer
→ wait for process exit
→ deterministic Git + handoff validation
→ exact SHA
→ agent_cycle begin-review
→ Pi reviewer (read-only)
→ validate structured JSON review
→ agent_cycle record-review
   ├─ PASS → STOP / HUMAN
   ├─ BLOCKED → STOP
   └─ CHANGES_REQUIRED
        → Pi implementer again
        → require new SHA
        → Pi reviewer round 2
        → PASS/BLOCKED/STOPPED
```

No third automated review round. No automatic merge.

## Proposed entry point

Prefer:

```text
scripts/pi_ticket_cycle.py
```

Expected usage:

```powershell
uv run python scripts/pi_ticket_cycle.py PDFTR-36
```

Optional explicit runtime overrides are acceptable, but defaults should be:

```text
implementer provider = deepseek
implementer model    = deepseek-v4-pro

reviewer provider    = openai-codex
reviewer model       = gpt-6.1-sol
reviewer tools       = read,grep,find,ls
```

Concrete provider/model names must remain configuration, not state-machine concepts.

## Authority boundary

The runner must not duplicate the workflow state machine.

Authoritative facts come only from Git plus `scripts/agent_cycle.py`:

```text
ticket
branch
HEAD SHA
base SHA
working-tree cleanliness
active role
review round
reviewed SHA
workflow state
review verdict
```

LLM prose is never authoritative.

If an agent prints “tests passed”, “pushed SHA X”, or “PASS”, the runner must verify the corresponding
machine state instead of trusting the sentence.

## Implementer

Launch Pi non-interactively with:

```text
--provider deepseek
--model deepseek-v4-pro
```

The implementer may use normal coding tools and is the only project-file writer.

It must receive the ticket, repository instructions, implementer contract, and current cycle context.

It must investigate, implement, test, commit, push, and prepare its role-specific handoff input.

The runner must wait for the Pi child process to exit before any reviewer starts.

After implementer exit, require:

```text
normal process exit
clean working tree
expected branch
new HEAD when required
valid implementer handoff input
successful agent_cycle handoff
cycle current_head_sha == Git HEAD
```

If any check fails: stop. Do not start reviewer.

## Reviewer

Launch Pi with:

```text
--provider openai-codex
--model gpt-6.1-sol
--tools read,grep,find,ls
```

Do not grant reviewer `write`, `edit`, or `bash` in this MVP.

Before reviewer launch, the runner must call the existing begin-review transition for the exact
current 40-character SHA.

The reviewer prompt must include:

```text
ticket ID
acceptance criteria
exact reviewed SHA
reviewer contract
explicit read-only rule
required JSON output schema
```

## Structured reviewer result

Because the reviewer is technically read-only, the runner — not the reviewer — persists the review.

Require one unambiguous machine-readable result:

```json
{
  "schema_version": "1.0",
  "ticket": "PDFTR-36",
  "review_round": 1,
  "reviewed_sha": "0123456789abcdef0123456789abcdef01234567",
  "verdict": "PASS",
  "findings": [],
  "blocked_reason": null
}
```

Allowed verdicts:

```text
PASS
CHANGES_REQUIRED
BLOCKED
```

Reject malformed JSON, wrong ticket, wrong round, wrong SHA, invalid verdict, invalid findings,
PASS with findings, CHANGES_REQUIRED without findings, or BLOCKED without a reason.

After parsing, pass the result through the existing `agent_cycle.py record-review` logic.
Do not reimplement its business rules.

## Round behavior

Round 1 `PASS` → `PASSED` → stop for human review.

Round 1 `BLOCKED` → stop.

Round 1 `CHANGES_REQUIRED` → begin implementation again, provide reviewer findings to the
implementer, require a new commit/SHA, hand off again, then run reviewer round 2.

Round 2 `PASS` → `PASSED` → stop for human review.

Round 2 `BLOCKED` → stop.

Round 2 `CHANGES_REQUIRED` → existing cycle terminal stop. Never launch round 3.

## Process handling

Use Python standard-library process control unless investigation proves otherwise.

Requirements:

```text
wait for every child
capture exit code
capture stdout/stderr
no parallel agents
no shell=True unless justified
Ctrl+C stops orchestration cleanly
abnormal child exit stops the cycle
no automatic retry loop
```

Do not invent aggressive default timeouts.

## Pi logs

Diagnostic logs may live under ignored state, for example:

```text
.agent-cycle/PDFTR-36/
  pi-implementer-round-1.log
  pi-reviewer-round-1.log
```

Logs are not authoritative and must not contain credentials or be committed.

## Security

Do not read/copy Pi auth files unnecessarily.
Do not serialize OpenAI/DeepSeek credentials.
Do not log secrets.
Do not auto-install or auto-update Pi.

Resolve `pi` through normal `PATH` and fail clearly if unavailable.

## Git safety

Do not auto-stash, reset, clean, checkout, fetch, merge, or delete unexpected files as recovery.

Unexpected Git state means stop and report.

## Human-facing terminal result

On success:

```text
AGENT CYCLE PASSED

Ticket: PDFTR-36
State: PASSED
Implementation SHA: <sha>
Review rounds: <n>
Implementer: deepseek / deepseek-v4-pro
Reviewer: openai-codex / gpt-6.1-sol

READY FOR HUMAN REVIEW
```

Never print `READY TO MERGE`; merge remains human-owned.

## Investigation

Before implementation create:

```text
.implementation-plans/investigation-PDFTR-35.md
```

Answer:

1. Which `agent_cycle.py` functions should be reused directly?
2. Import Python functions or spawn its CLI — which is simpler and safer here?
3. What is the thinnest runner boundary that avoids duplicating state logic?
4. What exact Pi CLI arguments are required for each role?
5. How should stdout/stderr and logs be captured?
6. How will reviewer JSON be extracted unambiguously?
7. How will Windows/Linux cancellation be handled?
8. How will tests replace the real Pi executable?
9. How are round-1 findings supplied to the second implementer run?
10. Can the implementation remain standard-library only?
11. What is the exact expected blast radius?
12. What existing subprocess/test helpers can be reused?

Do not implement before this investigation is complete.

## Tests

Tests must never call real LLM providers.

Use fake Pi process adapters/executables plus isolated real Git fixtures.

Required cases:

1. One-round PASS: implementer exits → handoff → reviewer exact SHA → PASS → PASSED.
2. CHANGES_REQUIRED then new implementation SHA then round-2 PASS.
3. Round-2 CHANGES_REQUIRED stops; no third review.
4. Reviewer invocation contains `openai-codex`, `gpt-6.1-sol`, and exactly read-only tools.
5. Implementer invocation contains `deepseek` and `deepseek-v4-pro`.
6. Malformed reviewer JSON fails closed.
7. Wrong SHA/ticket/round fails closed.
8. Implementer abnormal exit never starts reviewer.
9. Reviewer abnormal exit never starts another role.
10. Dirty tree after implementer never starts reviewer.
11. No new SHA after CHANGES_REQUIRED prevents review round 2.
12. Pi missing from PATH gives actionable failure.
13. Cancellation never launches the next agent.
14. Existing `agent_cycle.py` remains the real transition authority in integration tests.

## Expected files

Likely:

```text
scripts/pi_ticket_cycle.py
tests/test_pi_ticket_cycle.py
README.md
CHANGELOG.md
knowledge/wiki/workflows/development-workflow.md
knowledge/wiki/log.md
.implementation-plans/investigation-PDFTR-35.md
.implementation-plans/implementation-plan-PDFTR-35.md
.implementation-reports/implementation-report-PDFTR-35.md
reviews/review-PDFTR-35.md
Tickets/PDFTR-35-pi-sequential-two-agent-runner-mvp.md
```

Modify `scripts/agent_cycle.py` only if a small missing integration seam is proven necessary.

## Quality gate

```powershell
uv run pytest tests/test_pi_ticket_cycle.py
uv run pytest
uv run python scripts/project_wiki/wiki_lint.py
.\scripts\check.ps1
```

Windows and Ubuntu CI must be green.

CI/tests must not require Pi, provider authentication, network, model downloads, CUDA, or OCR.

## Acceptance criteria

PDFTR-35 is complete when:

- one command starts the sequential two-agent cycle;
- Pi runs both roles;
- implementer uses `deepseek / deepseek-v4-pro`;
- reviewer uses `openai-codex / gpt-6.1-sol`;
- reviewer is technically read-only;
- roles never run concurrently;
- each child fully exits before the next starts;
- `agent_cycle.py` remains the workflow authority;
- exact-SHA review is enforced;
- stale review protection remains intact;
- one fix/review retry is supported;
- round 2 requires a new SHA;
- no third review can start;
- malformed/wrong-SHA reviewer output fails closed;
- abnormal Pi exit or dirty Git state stops the cycle;
- no automatic PR or merge occurs;
- no auth secrets are copied or logged;
- deterministic tests pass without real providers;
- full local gate and both CI jobs pass;
- terminal output returns control to the human.

## Non-goals

Do not implement:

```text
Pi-Harness
EV/JEV routing
dynamic model/provider selection
parallel agents
multiple implementers/reviewers
worktrees
automatic PR
automatic merge
semantic finding similarity
retry policy engine
daemon/service
scheduler
database
Web UI
Docker
remote orchestration
automatic model fallback
automatic YouTrack mutation
agent-to-agent free-form chat
```

## Final boundary

PDFTR-35 automates exactly the successful PDFTR-34 manual sequence and nothing more:

```text
one command
→ DeepSeek implementer
→ deterministic handoff gate
→ Codex reviewer on exact SHA
→ optional one fix/review round
→ STOP
→ HUMAN
```

The next real PDF feature ticket will be the first practical test of the completed Pi runner.
