# PDFTR-33 — Two-agent ticket handoff contract + validator

## Goal

Introduce a small, explicit, repository-local contract for sequential two-agent ticket execution:

```text
DeepSeek implements and pushes
        ↓
Codex reviews one exact immutable SHA, read-only
        ↓
DeepSeek fixes and pushes a new SHA if required
        ↓
Codex optionally reviews once more
        ↓
final human review
        ↓
human merge decision
```

PDFTR-33 is intentionally a **small tooling/workflow ticket**.

It must establish the contract and validation primitives needed for a future orchestrator, but it
must **not** implement the orchestrator itself.

This ticket is the first pilot of the two-agent workflow.

Current `master` at ticket preparation time:

```text
35c8f698de1370484af8fc73f77518c104efb1e0
```

Do not assume this SHA is still current when work starts. Resolve and record the actual base before
implementation.

---

# Core principles

The workflow must enforce these invariants:

```text
one ticket branch
one working directory
one implementation writer
one read-only reviewer
strictly sequential execution
review bound to an exact Git SHA
maximum two review rounds
human owns final merge decision
```

The implementation agent for the pilot is DeepSeek.

The review agent for the pilot is Codex.

The repository must not assume those product names permanently in low-level validation logic where
generic role names are sufficient.

Preferred role terms:

```text
implementer
reviewer
system
```

---

# 1. Repository-local coordination root

Create a persistent auxiliary runtime area:

```text
.agent-cycle/
```

This directory is intentionally different from `temp/`.

`temp/` is disposable test/runtime scratch data and may be deleted routinely.

`.agent-cycle/` represents local ticket coordination state and should survive ordinary temporary
file cleanup.

Add:

```text
/.agent-cycle/
```

to `.gitignore`.

Do not commit generated ticket-cycle state.

Do not use machine-specific absolute paths.

---

# 2. Per-ticket structure

Each ticket uses:

```text
.agent-cycle/
└── <TICKET-ID>/
    ├── state.json
    ├── handoff.json
    ├── review-1.json
    └── review-2.json
```

Only files that are actually needed must be created.

Example:

```text
.agent-cycle/PDFTR-33/
```

The design should allow:

```text
PDFTR-33
PDFTR-34
...
PDFTR-XX
```

without cross-ticket state leakage.

---

# 3. Three ownership domains

The coordination contract has three logical ownership domains:

```text
system
implementer
reviewer
```

Do not allow one actor to overwrite another actor's authoritative facts.

## System-owned facts

`state.json` is authoritative machine state and is written by the validator/tooling code.

It must contain only facts derived from current repository/runtime state or explicit validated
workflow transitions.

Suggested fields:

```json
{
  "schema_version": "1.0",
  "ticket": "PDFTR-33",
  "branch": "codex/PDFTR-33-two-agent-ticket-handoff-contract",
  "base_sha": "abc123",
  "current_head_sha": "def456",
  "review_round": 1,
  "state": "READY_FOR_REVIEW",
  "active_agent": null,
  "working_tree_clean": true
}
```

The exact schema may evolve during investigation, but ownership must not.

System facts must be derived rather than trusted from agent prose.

At minimum derive with Git:

```powershell
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git merge-base master HEAD
git status --porcelain
```

Where push verification is implemented, use a real remote-ref check rather than trusting the
implementer's statement.

## Implementer-owned handoff

`handoff.json` belongs to the implementation agent.

It communicates implementation claims and artifacts.

Suggested shape:

```json
{
  "schema_version": "1.0",
  "ticket": "PDFTR-33",
  "implementation_attempt": 1,
  "status": "COMPLETE",
  "implementation_report": ".implementation-reports/implementation-report-PDFTR-33.md",
  "focused_tests": "PASS",
  "full_tests": "PASS",
  "check_ps1": "PASS",
  "known_limitations": [],
  "notes": []
}
```

The implementer must not write authoritative values such as:

```text
actual current HEAD
actual branch
actual clean-tree state
review round
review verdict
reviewed SHA
```

Those belong to `system` or `reviewer`.

## Reviewer-owned review

Each review round is a separate immutable artifact:

```text
review-1.json
review-2.json
```

Suggested shape:

```json
{
  "schema_version": "1.0",
  "ticket": "PDFTR-33",
  "reviewed_sha": "def456",
  "verdict": "CHANGES_REQUIRED",
  "findings": [
    {
      "id": "R1",
      "severity": "HIGH",
      "file": "src/...",
      "symbol": "function_name",
      "problem": "Concrete defect description",
      "required_fix": "Concrete required correction",
      "regression_test": "Required regression"
    }
  ]
}
```

Reviewer result values:

```text
PASS
CHANGES_REQUIRED
BLOCKED
```

Do not add scoring, confidence percentages, or subjective ranking.

---

# 4. Single-writer repository rule

The implementation agent is the **only actor allowed to mutate project files**.

The implementer may:

```text
edit source
edit tests
edit docs
edit ticket artifacts
update implementation reports
commit
push
```

The reviewer must be strictly read-only with respect to repository project files.

The reviewer must not:

```text
edit source
edit tests
format files
update docs
update reviews/review-<TICKET>.md
commit
amend
push
reset
stash
rebase
resolve conflicts
switch to another task branch
```

The reviewer may create only its local coordination result:

```text
.agent-cycle/<TICKET>/review-N.json
```

if the environment supports that workflow.

If the selected Codex execution environment cannot safely write only that coordination artifact
without touching the working tree, the review result may instead be returned as structured stdout
for the validator/orchestrator to persist later.

Investigate and choose the smallest safe boundary.

---

# 5. Review is bound to an immutable SHA

Every review must target one explicit commit SHA.

Before review:

```text
state.current_head_sha == expected review SHA
working tree is clean
branch is the expected task branch
```

The reviewer must report:

```text
reviewed_sha
```

A review is valid only when:

```text
reviewed_sha == state.current_head_sha at review start
```

If the implementer pushes a new commit:

```text
old review does not apply to the new HEAD
```

The validator must make this explicit.

Never reuse a PASS from SHA A for SHA B.

---

# 6. Strict sequential execution

The two agents must never run concurrently on the same ticket cycle.

Represent this in system state.

Suggested field:

```json
"active_agent": null
```

Allowed values:

```text
null
implementer
reviewer
```

The validator must reject a transition that would start one role while another role is active.

Do not implement process spawning in PDFTR-33.

Only implement enough state validation to support this future behavior.

---

# 7. State machine

Define a small explicit state machine.

Suggested states:

```text
NEW
IMPLEMENTING
READY_FOR_REVIEW
REVIEWING
CHANGES_REQUIRED
READY_FOR_REVIEW_2
PASSED
BLOCKED
STOPPED
```

Exact names may be adjusted after investigation, but transitions must remain simple and auditable.

Expected nominal flow:

```text
NEW
 ↓
IMPLEMENTING
 ↓
READY_FOR_REVIEW
 ↓
REVIEWING
 ├── PASS ───────────────→ PASSED
 ├── BLOCKED ────────────→ BLOCKED
 └── CHANGES_REQUIRED
          ↓
      IMPLEMENTING
          ↓
      READY_FOR_REVIEW_2
          ↓
       REVIEWING
          ├── PASS ──────→ PASSED
          ├── BLOCKED ───→ BLOCKED
          └── CHANGES_REQUIRED
                  ↓
                STOPPED
```

Human final review and merge occur after:

```text
PASSED
```

and are outside automated state mutation for this ticket.

---

# 8. Maximum review rounds

Hard limit:

```text
MAX_REVIEW_ROUNDS = 2
```

After review round 2:

```text
CHANGES_REQUIRED → STOPPED
```

Do not automatically start a third Codex review.

The future orchestrator may surface the stopped state to the user.

PDFTR-33 validator must encode this rule.

---

# 9. Repeated-finding stop rule

The contract should reserve support for detecting repeated review findings.

Do not overengineer semantic similarity in PDFTR-33.

Use a simple deterministic identifier strategy.

Recommended:

```text
review finding ID + file + symbol
```

or another small stable key.

At minimum define and document:

```text
if the same unresolved finding appears in consecutive review rounds,
the cycle must stop for human inspection
```

The validator may implement only exact deterministic repetition for PDFTR-33.

Do not introduce embeddings, LLM similarity, or fuzzy semantic matching.

---

# 10. Usage/budget stop rule

The workflow must support an external stop condition such as:

```text
Codex usage limit reached
review budget exhausted
external runner says stop
```

PDFTR-33 does not need to integrate with billing/account APIs.

Provide a generic stop transition or command:

```text
STOPPED
reason = "usage_limit"
```

or equivalent.

The validator must not invent account-specific limits.

---

# 11. Validator utility

Add a small repository tooling script.

Preferred path:

```text
scripts/agent_cycle.py
```

Do not create a daemon.

Do not create an autonomous agent launcher.

Do not call DeepSeek or Codex from this ticket.

The script validates and records workflow state only.

Suggested command surface:

```powershell
uv run python scripts/agent_cycle.py init PDFTR-33
uv run python scripts/agent_cycle.py handoff PDFTR-33
uv run python scripts/agent_cycle.py begin-review PDFTR-33
uv run python scripts/agent_cycle.py record-review PDFTR-33 --file .agent-cycle/PDFTR-33/review-1.json
uv run python scripts/agent_cycle.py status PDFTR-33
uv run python scripts/agent_cycle.py stop PDFTR-33 --reason usage_limit
```

These names are illustrative.

Codex must investigate existing CLI/script conventions and choose a small coherent interface.

Do not add a heavy CLI framework dependency.

`argparse` is sufficient unless an existing script convention strongly supports another standard-library
approach.

---

# 12. Validator responsibilities

The validator must be able to detect at least:

```text
wrong repository root
wrong task branch
missing ticket cycle
invalid JSON
schema mismatch
dirty working tree when clean state is required
HEAD mismatch
reviewed SHA mismatch
review round > 2
review artifact for wrong ticket
review artifact for wrong SHA
invalid verdict
invalid state transition
another agent already active
repeated exact unresolved finding across rounds
```

Where remote verification is implemented, also detect:

```text
local HEAD not present at expected remote branch tip
```

Do not require network access for every read-only status command.

Separate local validation from optional remote validation if needed.

---

# 13. JSON contracts

Use typed internal Python models or focused validation functions.

Do not add a new dependency solely for JSON schema validation.

The repository already uses Pydantic broadly, but investigate whether standard-library dataclasses /
TypedDict-style validation or existing project Pydantic usage is the smallest fit.

Whichever is chosen:

```text
unknown fields must not silently alter workflow behavior
required fields must be validated
enum-like fields must reject unknown values
ticket IDs must be validated
SHA fields must have a sane Git hash format
review rounds must be bounded
```

If external JSON Schema files materially improve future orchestrator interoperability, they may be
added, but only with a clear reason.

Avoid duplicating one schema in three different places.

---

# 14. Ticket ID and path safety

Treat ticket ID as untrusted input.

Allow a conservative form such as:

```text
PDFTR-33
ABC-123
```

Reject:

```text
../
absolute paths
slashes
backslashes
empty IDs
dot traversal
control characters
```

All coordination paths must remain below:

```text
<repo>/.agent-cycle/
```

No command may escape that root.

---

# 15. Git safety

The validator is allowed to read Git state.

For PDFTR-33, avoid destructive Git commands.

Forbidden:

```text
git reset
git clean
git stash
git checkout -- .
git restore unrelated files
git rebase
force push
```

The validator must not mutate source-controlled files as part of status verification.

Do not silently clean a dirty tree.

Fail with a clear reason.

---

# 16. Root `AGENTS.md` integration

Update root `AGENTS.md` minimally.

Do not duplicate the full two-agent contract there.

Add a short routing section similar in intent to:

```text
## Two-agent ticket workflow

When a ticket explicitly uses the two-agent workflow:

- one implementation agent owns repository mutation;
- reviewer agents are read-only;
- every review targets an explicit Git SHA;
- reviews are invalidated by a new implementation push;
- implementation and review agents run strictly sequentially;
- at most two automated review rounds are allowed;
- final merge remains a human decision.

Follow:
.agents/skills/two-agent-ticket-workflow/SKILL.md
```

Keep the root file concise.

---

# 17. New skill

Create:

```text
.agents/skills/two-agent-ticket-workflow/SKILL.md
```

Use the repository's existing skill frontmatter convention.

Suggested metadata:

```yaml
---
name: two-agent-ticket-workflow
description: Run PDFTranslate tickets with one implementation writer and one read-only SHA-bound reviewer using repository-local .agent-cycle state, bounded sequential review rounds, and human final merge.
---
```

The skill must define:

```text
role ownership
file ownership
state ownership
sequential execution
SHA binding
handoff requirements
review artifact requirements
review limits
stop conditions
human merge boundary
validator usage
```

Do not copy all of `.codex/PRE_TICKET_WORKFLOW.md`.

Link to it and state precedence.

---

# 18. Role contracts

The skill may be one file, but separate focused contract documents are preferred if they improve
clarity.

Recommended:

```text
.agents/skills/two-agent-ticket-workflow/
├── SKILL.md
├── IMPLEMENTER_CONTRACT.md
├── REVIEWER_CONTRACT.md
└── HANDOFF_CONTRACT.md
```

Do not create files merely for symmetry.

If separate files are created:

## IMPLEMENTER_CONTRACT.md

Must require:

```text
read repository instructions
run normal pre-ticket workflow
work only on the task branch
preserve unrelated user changes
implement smallest coherent change
run required validation
produce implementation report
commit
push
produce handoff.json
stop and yield control
```

After handoff, the implementer must not continue changing files until reviewer result is returned.

## REVIEWER_CONTRACT.md

Must require:

```text
verify expected branch and SHA
verify review target matches state
remain read-only
inspect diff/source/tests/reports
run read-only validation where safe
return PASS / CHANGES_REQUIRED / BLOCKED
identify exact files/symbols/problems/fixes/tests
never push or amend
stop after producing review result
```

## HANDOFF_CONTRACT.md

Must define the three ownership domains:

```text
system
implementer
reviewer
```

and the `.agent-cycle/<TICKET>/` files.

---

# 19. `.codex/PRE_TICKET_WORKFLOW.md` integration

Update the pre-ticket workflow minimally.

Do not rewrite the existing repository intelligence workflow.

Add a small section that says, when the ticket is running under two-agent mode:

```text
normal repository investigation/validation still applies
two-agent skill adds coordination rules on top
implementer is the only repository writer
reviewer verifies exact SHA read-only
```

State the precedence clearly.

Suggested precedence:

```text
explicit user instruction
root AGENTS.md
two-agent skill for coordination
PRE_TICKET_WORKFLOW for repository investigation/validation
nested applicable AGENTS.md
```

Adjust wording if this creates conflict with existing documented precedence.

Do not create contradictory instruction chains.

---

# 20. ProjectWiki

This ticket changes durable development workflow, so ProjectWiki should be updated.

At minimum investigate:

```text
knowledge/wiki/workflows/development-workflow.md
knowledge/wiki/workflows/wiki-maintenance.md
knowledge/wiki/index.md
knowledge/wiki/log.md
```

Create a new durable Wiki page only if the two-agent workflow does not fit naturally in the current
development workflow page.

Do not create ticket-number-specific Wiki documentation.

Document:

```text
single writer
read-only SHA-bound review
.agent-cycle ownership
two-round limit
human final merge
validator vs future orchestrator distinction
```

Run:

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

---

# 21. Tests

Add deterministic tests for `scripts/agent_cycle.py` or its underlying module.

Prefer testing core functions directly instead of shelling out for every case.

Required cases:

## A. Ticket path safety

Accept:

```text
PDFTR-33
ABC-123
```

Reject:

```text
../PDFTR-33
PDFTR/33
PDFTR\33
.
..
empty
absolute path
```

## B. Initialization

Given a clean task branch:

```text
creates .agent-cycle/<TICKET>/
creates valid state.json
records actual branch
records actual HEAD
records actual merge base
review_round starts at 0 or chosen documented initial value
active_agent is null
```

Do not rely on the developer's real repository for unit tests.

Use an isolated temporary Git fixture located under repository-local test temp configuration when
possible.

## C. Dirty-tree handoff rejection

If a tracked file is modified:

```text
handoff validation fails
state does not claim READY_FOR_REVIEW
```

## D. SHA binding

If:

```text
state.current_head_sha = SHA-A
review.reviewed_sha = SHA-B
```

reject the review.

## E. New push invalidates prior review

Simulate:

```text
review-1 PASS for SHA-A
HEAD becomes SHA-B
```

The workflow must not treat the old PASS as valid for SHA-B.

## F. Review round cap

```text
round 1 CHANGES_REQUIRED → fix allowed
round 2 CHANGES_REQUIRED → STOPPED
round 3 → rejected
```

## G. Reviewer read-only contract validation

Where technically practical, ensure validator detects repository mutation during a review window.

A simple snapshot of:

```text
HEAD
git status --porcelain
```

before and after review may be sufficient for PDFTR-33.

Do not attempt filesystem sandboxing in this ticket.

## H. Invalid verdict

Reject anything outside:

```text
PASS
CHANGES_REQUIRED
BLOCKED
```

## I. Repeated finding

Exact same stable finding key in consecutive rounds should stop the cycle for human inspection.

## J. Active-agent exclusivity

Cannot begin reviewer phase while:

```text
active_agent = implementer
```

and vice versa.

## K. Corrupt JSON

Fail clearly.

Do not silently recreate or discard existing coordination state.

---

# 22. Review finding structure

Keep finding format small and machine-readable.

Required fields for `CHANGES_REQUIRED`:

```text
id
severity
problem
required_fix
```

Recommended optional fields:

```text
file
symbol
regression_test
```

Severity may use:

```text
CRITICAL
HIGH
MEDIUM
LOW
```

Do not make severity control merge automatically.

`PASS` must have:

```text
findings = []
```

`BLOCKED` should record a machine-readable reason.

---

# 23. Status output

Human-readable status should be concise.

Example:

```text
Ticket: PDFTR-33
State: READY_FOR_REVIEW
Branch: codex/PDFTR-33-two-agent-ticket-handoff-contract
HEAD: def456...
Review round: 1 / 2
Active agent: none
Working tree: clean
```

Do not expose secrets or environment credentials.

If JSON output mode is easy and useful for the future orchestrator, it may be added, but do not
overbuild the CLI.

---

# 24. Failure behavior

Validator failures must be fail-closed.

Examples:

```text
dirty tree
wrong branch
invalid SHA
corrupt state
unexpected transition
review SHA mismatch
round limit exceeded
```

must not advance workflow state.

Print a clear reason and exit non-zero.

Never repair state by guessing.

Provide an explicit manual recovery path in documentation.

---

# 25. Recovery

Document how to recover from:

```text
agent crash
invalid review file
manual commit between phases
deleted .agent-cycle ticket directory
branch change
stale state after manual intervention
```

Keep recovery conservative.

For PDFTR-33, explicit re-initialization or manual state reset commands may be acceptable if they
validate current Git facts and never delete source work.

Do not implement magical automatic reconciliation.

---

# 26. No orchestrator yet

Explicitly out of scope:

```text
starting DeepSeek
starting Codex
process supervision
background workers
GitHub polling loop
automatic prompts
automatic retries
automatic merge
automatic branch deletion
automatic PR creation
LLM budget API integration
parallel agents
multiple worktrees
conflict resolution
semantic comparison of findings
```

PDFTR-33 creates the contract that a later orchestrator will consume.

---

# 27. Manual pilot

After implementation, exercise PDFTR-33 itself as the first manual pilot where practical.

Record in the implementation report which parts were self-hosted and which could not be because the
new tooling did not exist at ticket start.

Do not fabricate a fully self-hosted run if bootstrap order makes that impossible.

At minimum demonstrate locally:

```text
initialize cycle
produce implementer handoff
validate READY_FOR_REVIEW
record a synthetic PASS review for exact SHA
show PASSED state
```

and separately test:

```text
CHANGES_REQUIRED → second review → STOPPED/PASSED behavior
```

Use deterministic local fixtures for destructive transition testing.

---

# 28. Expected files

Likely additions/changes:

```text
AGENTS.md
.gitignore
.codex/PRE_TICKET_WORKFLOW.md

.agents/skills/two-agent-ticket-workflow/SKILL.md
.agents/skills/two-agent-ticket-workflow/IMPLEMENTER_CONTRACT.md
.agents/skills/two-agent-ticket-workflow/REVIEWER_CONTRACT.md
.agents/skills/two-agent-ticket-workflow/HANDOFF_CONTRACT.md

scripts/agent_cycle.py
tests/test_agent_cycle.py

knowledge/wiki/workflows/development-workflow.md
knowledge/wiki/log.md
possibly knowledge/wiki/index.md
possibly one new workflow page if justified

README.md
CHANGELOG.md

.implementation-plans/investigation-PDFTR-33.md
.implementation-plans/implementation-plan-PDFTR-33.md
.implementation-reports/implementation-report-PDFTR-33.md
reviews/review-PDFTR-33.md
```

Codex must reduce this list if investigation shows fewer files are sufficient.

Do not introduce new dependencies unless strictly required.

---

# 29. Investigation requirements

Before implementation, answer in:

```text
.implementation-plans/investigation-PDFTR-33.md
```

1. What current repository instructions already govern ticket implementation and review?
2. Where should two-agent coordination rules live without duplicating existing workflows?
3. What is the smallest safe `state.json` model?
4. Which fields must be system-derived rather than agent-provided?
5. What exact commands are safe for deriving branch/HEAD/merge-base/clean state?
6. How should remote push verification work, and should it be mandatory or optional in PDFTR-33?
7. What state transitions are required for the first two-round workflow?
8. How should active-agent exclusivity be represented?
9. How should old reviews be invalidated after a new push?
10. How should repeated findings be keyed deterministically?
11. Should coordination model validation use Pydantic or standard-library types, given current project
    conventions?
12. What is the cleanest test strategy for Git behavior without mutating the developer's repository?
13. Which existing ProjectWiki pages should be updated?
14. What bootstrap limitations prevent PDFTR-33 from being completely self-hosted?
15. What future orchestrator interface should the contract preserve without implementing it now?

Do not implement before these are source-verified.

---

# 30. Implementation plan requirements

Create:

```text
.implementation-plans/implementation-plan-PDFTR-33.md
```

The plan must explicitly separate:

```text
contract/docs
state model
Git fact collection
transition validator
review artifact validation
tests
Wiki/docs
manual pilot
```

Avoid mixing future orchestration into the implementation scope.

---

# 31. Quality gate

Run focused tests first.

Then:

```powershell
uv run pytest
uv run python scripts/project_wiki/wiki_lint.py
.\scripts\check.ps1
```

Use repository-local temporary paths per existing project rules.

GitHub CI must pass on:

```text
windows-latest
ubuntu-latest
```

No external LLM/API/model call may be required by unit tests or CI.

---

# 32. Acceptance criteria

PDFTR-33 is complete only when all are true:

- `.agent-cycle/` is the documented coordination root;
- `.agent-cycle/` is ignored by Git;
- per-ticket cycle state is isolated;
- three ownership domains are documented: `system`, `implementer`, `reviewer`;
- system Git facts are derived by tooling, not trusted from agent prose;
- implementer is the only repository writer;
- reviewer is explicitly read-only;
- review is bound to an exact SHA;
- a new implementation push invalidates the previous review;
- agents are strictly sequential;
- active-agent exclusivity is validated;
- maximum automated review rounds is exactly 2;
- second-round `CHANGES_REQUIRED` stops the cycle;
- exact repeated unresolved finding can stop the cycle;
- external/manual stop reason is supported;
- invalid/corrupt state fails closed;
- path traversal through ticket IDs is impossible;
- Git validation uses no destructive commands;
- `AGENTS.md` contains only concise routing/invariants;
- a dedicated two-agent workflow skill exists;
- PRE_TICKET_WORKFLOW integration is minimal and non-duplicative;
- tests cover the required transition and safety cases;
- ProjectWiki documents the durable workflow;
- Wiki lint passes;
- full local quality gate passes;
- Windows and Ubuntu CI are green;
- implementation report records the manual pilot honestly;
- no orchestrator, agent spawning, auto-merge, or parallel execution is introduced.

Final review status:

```text
READY FOR REVIEW
```

only after all acceptance criteria and CI checks pass.

---

# 33. Reviewer handoff for this ticket

After DeepSeek completes PDFTR-33:

1. commit;
2. push;
3. ensure the branch is clean;
4. provide the exact pushed HEAD SHA;
5. produce the normal implementation report;
6. create the PDFTR-33 handoff data using the new contract where bootstrap order permits;
7. stop.

Codex review must then be performed against that exact SHA and remain read-only.

If Codex returns `CHANGES_REQUIRED`:

```text
DeepSeek fixes
→ commit
→ push new SHA
→ prior review is invalid for new HEAD
→ Codex may review once more
```

After the second Codex review, stop automated cycling and return control for final human/ChatGPT
review.

---

# Non-goals

Explicitly out of scope:

- full orchestrator;
- calling DeepSeek from Python;
- calling Codex from Python;
- background automation;
- GitHub Actions-based agent execution;
- auto-merge;
- auto-PR;
- multiple concurrent agents;
- multiple worktrees;
- semantic review finding similarity;
- billing/usage API integrations;
- source-code mutation by reviewer;
- destructive Git recovery;
- replacing normal PRE_TICKET_WORKFLOW checks.
