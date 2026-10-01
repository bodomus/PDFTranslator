# PDFTR-35A — Orchestrator safety follow-up

## Goal

Fix the four unresolved safety findings remaining after PDFTR-35 review round 2.

This is a stabilization follow-up only. Do not expand scope beyond the defects listed here.

## Roles

Use the normal two-agent contract:

```text
implementer → DeepSeek
reviewer    → Codex
```

Codex remains read-only.

PDFTR-35A is a new ticket/cycle. Do not reopen or mutate the completed PDFTR-35 round history.

## Source findings

PDFTR-35 stopped after review round 2 on SHA:

```text
1e3a3a78712ebb4f1e91f8090377759930e1546c
```

The unresolved findings are:

```text
R2 — contradictory handoff write permissions
R4 — cancellation can leave a descendant process alive after the direct child exits
R5 — malformed/corrupted JSON can be accepted as a successful reviewer verdict
R6 — I/O failure can leave a spawned process running
```

These four findings define the full scope of PDFTR-35A.

## R2 — Resolve contradictory handoff write permissions

### Problem

The current contracts/instructions contain contradictory ownership rules around agent-cycle handoff artifacts.

The runtime design must remain:

```text
implementer → may write project files and its role-owned handoff input
reviewer    → read-only project access
runner      → may persist validated reviewer result into local .agent-cycle state
agent_cycle → authoritative validator/state transition layer
```

There must be no instruction that simultaneously requires the reviewer to write a file while also denying all write tools.

### Required fix

Make ownership explicit and internally consistent across:

```text
Pi runner prompts
two-agent workflow skill/contracts
runner implementation
tests
relevant docs
```

Reviewer stdout must be structured machine-readable output.

The runner may persist that output into the ignored `.agent-cycle/<TICKET>/` runtime area and pass it to existing `agent_cycle` validation.

The reviewer itself must not require write/edit/bash access.

### Acceptance

- no contradictory reviewer write requirement remains;
- reviewer still runs with `read,grep,find,ls`;
- reviewer cannot modify tracked project files;
- runner persists only validated reviewer output;
- existing agent-cycle ownership rules remain intact.

## R4 — Kill the complete Pi process tree on cancellation

### Problem

Stopping/cancelling the orchestrator may terminate the direct Pi process while leaving a descendant process alive.

That is unsafe because a supposedly stopped role can continue modifying state after orchestration has returned control to the user.

### Required fix

Implement deterministic process-tree termination for cancellation and abnormal stop.

Requirements:

```text
Windows supported
Linux supported
no orphan descendant Pi/agent process
bounded graceful termination attempt
forced termination fallback when required
wait/reap before returning
no next role starts during cleanup
```

Use standard-library/process primitives where practical.

Do not add a large process-management dependency unless independently justified.

### Acceptance

A test must prove that a spawned child with its own descendant is fully terminated after orchestrator cancellation.

Testing only the immediate child PID is insufficient.

## R5 — Strict reviewer JSON extraction

### Problem

The current reviewer-output parser can accept malformed/corrupted or contradictory output as a successful verdict.

The reviewer result is a safety boundary and must fail closed.

### Required fix

Require exactly one valid structured review result.

Reject at minimum:

```text
truncated JSON
invalid JSON
multiple competing JSON result objects
contradictory verdict objects
text that contains one valid object plus another conflicting object
wrong ticket
wrong review round
wrong reviewed SHA
invalid verdict
invalid finding schema
PASS with findings
CHANGES_REQUIRED without findings
BLOCKED without blocked_reason
unexpected fields if the existing contract rejects them
```

Do not select "the last valid object" or otherwise guess intent.

If output is ambiguous:

```text
STOP
```

Do not record a review.

### Acceptance

Add deterministic regression tests for malformed and contradictory reviewer stdout.

No malformed/ambiguous review output may advance the agent cycle.

## R6 — Clean up spawned process on I/O failure

### Problem

If stdout/stderr/log capture or another runner-side I/O operation fails after Pi has been spawned, the Pi process can remain alive.

The orchestrator must own the lifetime of every child process it creates.

### Required fix

Ensure all exceptional paths after spawn perform process cleanup before propagating the failure.

This includes failures while:

```text
reading stdout/stderr
writing diagnostic logs
parsing/capturing process output
persisting runner-side runtime artifacts
```

Use `try/finally` or an equivalent deterministic ownership structure.

Cleanup must include descendants as required by R4.

### Acceptance

Inject an I/O failure after process spawn and prove:

```text
runner fails closed
child process terminates
descendant process terminates
active role is released/left in the valid stopped state
no next agent launches
```

## State-machine boundary

Do not redesign `scripts/agent_cycle.py`.

Reuse its existing transitions and validation.

Modify it only if investigation proves a small concrete integration defect.

The Pi runner must still treat these as authoritative:

```text
branch
HEAD
clean tree
active role
review round
reviewed SHA
verdict
terminal state
```

Do not trust agent prose for any of them.

## Process-safety invariant

After PDFTR-35A, the following must always hold:

```text
runner returns
    ⇒
no Pi process started by that runner is still alive
    ⇒
no descendant process from that role is still alive
```

This must hold for:

```text
success
CHANGES_REQUIRED
BLOCKED
malformed reviewer output
I/O failure
Ctrl+C
child abnormal exit
runner exception
```

## Investigation

Before implementation create:

```text
.implementation-plans/investigation-PDFTR-35A.md
```

Answer briefly:

1. Where exactly are the contradictory reviewer/handoff write instructions?
2. Which component currently writes reviewer JSON?
3. How is Pi spawned on Windows and Linux?
4. Can the current process API terminate descendants reliably?
5. What process-group/job-object strategy is appropriate per platform?
6. Which exception paths currently bypass cleanup?
7. How does the reviewer parser currently locate JSON?
8. Why can contradictory/malformed output pass?
9. What is the minimum parser change that fails closed?
10. What is the minimum test fixture for a child + descendant process?
11. Can this remain dependency-free?
12. What exact files must change?

Do not implement before investigation is complete.

## Tests

Add focused deterministic tests for all four findings.

Required:

```text
R2 reviewer invocation remains read-only and no prompt requires reviewer file writes
R4 Ctrl+C/cancellation kills child and descendant
R5 truncated JSON rejected
R5 multiple review objects rejected
R5 contradictory PASS/CHANGES_REQUIRED rejected
R5 valid single object accepted
R6 injected log/stdout I/O failure kills child and descendant
R6 no next role starts after I/O failure
R6 active role/state remains recoverable and valid
```

Do not call real LLM providers in tests.

## Quality gate

Run:

```powershell
uv run pytest tests/test_pi_ticket_cycle.py
uv run pytest
uv run python scripts/project_wiki/wiki_lint.py
.\scripts\check.ps1
```

Windows and Ubuntu CI must pass.

## Non-goals

Do not add:

```text
Pi-Harness
parallel agents
worktrees
automatic PR
automatic merge
retry engine
new provider selection
new model routing
semantic finding matching
daemon/service
Web UI
database
Docker
YouTrack automation
```

Do not refactor unrelated PDFTranslator production code.

## Completion

PDFTR-35A is complete when all four findings are fixed with regression coverage and the runner fails closed on every tested error path.

After implementation:

```text
commit
push
new PDFTR-35A agent-cycle handoff
STOP
Codex read-only review
```

Final merge remains a human decision.
