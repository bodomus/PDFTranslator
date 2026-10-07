# PDFTR-52 — Safe automatic fix continuation

## Status

Planned

## Summary

Implement the trusted continuation layer that consumes a current independent-review `CHANGES_REQUIRED` result from PDFTR-51 and safely starts a new Pi implementation cycle.

Target flow:

```text
implementation
    ↓
Pi reviewer
    ↓
CI
    ↓
independent review
    ↓
CHANGES_REQUIRED
    ↓
trusted continuation policy
    ↓
new implementation attempt
    ↓
tests / Pi review / CI
    ↓
new independent review
```

The continuation must remain exact-context bound, budgeted, crash-safe, non-duplicating, and incapable of reviving stale findings.

Automatic merge remains out of scope.

---

# Motivation

PDFTR-49 introduced exact head/base independent-review generations.

PDFTR-50 added trusted GitHub-triggered dispatch.

PDFTR-51 added trusted result ingestion, GitHub publication, and a separate continuation intent for current `CHANGES_REQUIRED`.

The remaining manual step is:

```text
current independent CHANGES_REQUIRED
→ operator manually starts another implementation cycle
```

PDFTR-52 should automate that step without allowing:

- stale findings to trigger work;
- duplicate implementers;
- infinite review/fix loops;
- continuation after uncertainty;
- reviewer output to directly execute agents;
- bypass of existing retry/recovery budgets;
- branch/HEAD drift between approval and launch.

---

# Goals

Implement a deterministic trusted continuation policy that:

1. consumes only a PDFTR-51 continuation intent;
2. verifies that the intent is still current;
3. verifies exact independent-review generation/head/base binding;
4. verifies current PR/head/base state authoritatively;
5. verifies the existing local cycle state;
6. carries structured findings into the new implementation attempt;
7. creates at most one continuation attempt per independent-review generation;
8. persists continuation authorization before agent launch;
9. survives restart without launching a duplicate implementer;
10. applies an explicit automatic continuation budget;
11. never treats stale `CHANGES_REQUIRED` as actionable;
12. never bypasses operational/review/pre-handoff recovery policies;
13. preserves human intervention for uncertainty, safety stops and exhausted budgets.

---

# Non-goals

PDFTR-52 does not:

- automatically merge;
- let the independent reviewer launch Codex directly;
- grant reviewer mutation capabilities;
- change PDFTR-49 review semantics;
- change PDFTR-50 dispatch semantics;
- change PDFTR-51 publication semantics;
- retry uncertain GitHub publication;
- retry uncertain agent launch blindly;
- auto-resolve safety stops;
- auto-resolve operational retry exhaustion;
- auto-create YouTrack issues;
- use free-form GitHub comments as implementation instructions.

---

# Core invariant

Automatic continuation is authorized only by a **current, published, exact-context independent `CHANGES_REQUIRED` result**.

Conceptually:

```text
continuation allowed
iff

independent result == CHANGES_REQUIRED
AND
publication == PUBLISHED
AND
continuation intent == current
AND
reviewed head == current PR head
AND
reviewed base == current PR base
AND
local cycle implementation SHA == reviewed head
AND
no newer independent-review generation supersedes it
AND
continuation budget remains
AND
no active agent exists
AND
repository state is safe
```

Fail closed if any predicate cannot be proven.

---

# Trust boundary

The flow must be:

```text
independent reviewer
    ↓ evidence only

PDFTR-51
    ↓ trusted continuation intent

PDFTR-52 continuation policy
    ↓ trusted launch authorization

Pi harness
    ↓
implementer
```

Forbidden:

```text
reviewer
→ directly launch implementer
```

and:

```text
GitHub comment
→ launch implementer
```

---

# Continuation intent source

Reuse the PDFTR-51 continuation object.

Example:

```json
{
  "schema_version": "1.0",
  "ticket": "PDFTR-52",
  "source": "independent_review",
  "generation": 2,
  "reviewed_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "verdict": "CHANGES_REQUIRED",
  "status": "PENDING_HUMAN_OR_POLICY"
}
```

PDFTR-52 must not construct its own continuation evidence from raw reviewer findings.

The intent must resolve back to:

```text
PDFTR-51 publication ledger
→ PDFTR-49 review generation
→ immutable result
```

---

# Continuation policy

Prefer a pure policy module such as:

```text
scripts/independent_review_continuation_policy.py
```

Conceptual interface:

```python
evaluate_continuation(
    cycle_state,
    independent_review_state,
    publication_state,
    continuation_history,
    authoritative_facts,
) -> Decision
```

No network calls.

No subprocesses.

No filesystem writes.

No agent execution.

---

# Eligibility requirements

Automatic continuation may proceed only when all required predicates hold.

At minimum:

```text
independent result verdict == CHANGES_REQUIRED

review status == CHANGES_REQUIRED

publication state == PUBLISHED

continuation intent exists

continuation intent status == PENDING_HUMAN_OR_POLICY

continuation intent generation == independent review generation

continuation intent reviewed_sha == generation requested_sha

generation == current independent-review generation

authoritative PR head == generation requested_sha

authoritative PR base == generation requested_base_sha

PR open

PR not draft

cycle implementation SHA == generation requested_sha

cycle state is compatible with continuation

required CI/reference facts remain coherent

no active Pi agent

repository identity matches

expected branch matches

working tree clean

no merge/rebase/cherry-pick conflict state

no unresolved GitHub publication uncertainty

no unresolved independent dispatch uncertainty

continuation budget remains
```

---

# Cycle state

Do not reuse a state transition implicitly.

Define explicitly which existing local cycle state is eligible after independent review.

Preferred:

```text
PASSED
```

with the exact implementation SHA that received independent `CHANGES_REQUIRED`.

Do not permit continuation from:

```text
IMPLEMENTING
REVIEWING
READY_FOR_REVIEW
STOPPED
FAILED
```

unless an existing explicit recovery path already authorizes it.

Do not reinterpret STOPPED as continuation eligibility.

---

# Findings handoff

The new implementer must receive the structured independent-review findings.

Do not pass only prose such as:

```text
fix review comments
```

Preferred trusted handoff artifact:

```json
{
  "schema_version": "1.0",
  "source": "independent_review",
  "generation": 2,
  "reviewed_sha": "...",
  "requested_base_sha": "...",
  "findings": [
    {
      "id": "IR-1",
      "severity": "HIGH",
      "file": "scripts/foo.py",
      "symbol": "Foo.bar",
      "problem": "...",
      "required_fix": "...",
      "regression_test": "..."
    }
  ]
}
```

This artifact is harness-generated from the already accepted PDFTR-49 result.

Agents do not author or modify continuation authority.

---

# Findings integrity

Before launch verify:

```text
continuation generation
→ exact persisted review
→ exact immutable result
→ exact findings
```

Do not accept findings from:

- GitHub comments;
- PR review text;
- local arbitrary JSON;
- implementer notes;
- manually edited continuation files.

---

# Continuation identity

Define a stable automatic continuation identity.

Recommended:

```text
(repository, PR, independent_generation)
```

or stronger:

```text
(repository, PR, generation, reviewed_head, reviewed_base)
```

One independent-review generation may authorize at most one automatic continuation attempt.

Repeated events must not launch another implementer.

---

# Automatic continuation budget

Introduce an explicit budget independent from:

- PDFTR-45 operational retry budget;
- PDFTR-48 pre-handoff retry;
- PDFTR-42 human review-exhaustion recovery.

Recommended initial limit:

```text
MAX_INDEPENDENT_CONTINUATIONS = 2
```

Interpretation:

```text
initial implementation
→ independent CR
→ auto fix #1
→ independent CR
→ auto fix #2
→ independent CR
→ STOP / human intervention
```

Do not allow an unbounded loop.

The exact default may be 1 or 2 if existing project policy suggests a safer value, but it must be explicit, deterministic and tested.

---

# Budget accounting

Budget must count successful launch authorizations, not free-form review rounds.

Persist history such as:

```json
{
  "continuations": [
    {
      "continuation_id": 1,
      "source_generation": 2,
      "source_head_sha": "...",
      "source_base_sha": "...",
      "approved_by": "policy",
      "state": "LAUNCHING"
    }
  ]
}
```

Do not reuse:

```text
operational_retries
pre_handoff_retries
review_round
```

as hidden continuation budget.

Keep policies distinct.

---

# Required state transitions

Recommended continuation lifecycle:

```text
PENDING
    ↓
AUTHORIZED
    ↓
PREPARED
    ↓
LAUNCHING
    ↓
RUNNING
    ↓
COMPLETED
```

Possible terminal/fenced states:

```text
LAUNCH_UNCERTAIN
REJECTED
STALE
```

Do not jump directly:

```text
PENDING → implementer process
```

without persisted authorization/attempt identity.

---

# Persist-before-launch

Mandatory:

```text
1. refresh authoritative facts
2. evaluate continuation policy
3. allocate continuation ID
4. persist AUTHORIZED
5. create immutable implementation handoff
6. persist PREPARED
7. record launch ownership
8. launch implementer
```

No agent process before durable continuation identity exists.

---

# Process safety

Reuse existing PDFTR-35A/PDFTR-45 process lifecycle and ownership mechanisms.

Do not add a second weaker subprocess implementation.

On Windows retain the hardened process containment/Job Object behavior.

On POSIX retain existing child reaping/termination behavior.

---

# Launch uncertainty

A process launch may become uncertain.

For example:

```text
process creation initiated
parent crashes
```

or equivalent OS ambiguity.

Required:

```text
→ LAUNCH_UNCERTAIN
```

Do not launch another implementer automatically.

Use existing process ownership/probe evidence where possible.

---

# Restart semantics

On restart the system must distinguish at least:

```text
AUTHORIZED but not prepared
PREPARED but not launched
LAUNCHING
RUNNING
process exited
handoff present
handoff absent
```

Never infer:

```text
no handoff
→ safe to launch again
```

without positive launch-state evidence.

---

# Integration with existing Pi cycle

Prefer reusing existing Pi implementer execution rather than creating a separate agent runner.

Possible design:

```text
PDFTR-52 policy
    ↓
trusted continuation artifact
    ↓
existing pi_ticket_cycle / runner
```

The new attempt must remain inside the same ticket/cycle lineage.

Do not create a disconnected second orchestration state machine.

---

# Implementation attempt identity

Existing implementation attempt numbering must remain monotonic.

Example:

```text
initial implementation attempt = 1
independent continuation = attempt 2
second continuation = attempt 3
```

Do not reset attempts to 1 after independent review.

---

# Independent review history

Previous independent-review generation remains immutable.

Example:

```text
generation 1
SHA A
CHANGES_REQUIRED
```

After continuation:

```text
implementation attempt 2
→ SHA B
```

Then PDFTR-49/PDFTR-50 should eventually produce:

```text
generation 2
SHA B
```

Do not rewrite generation 1 into PASS.

---

# Stale continuation

Assume continuation intent exists for:

```text
HEAD A
BASE B1
```

Before implementer launch:

```text
PR HEAD becomes C
```

or:

```text
BASE becomes B2
```

Required:

```text
continuation → STALE / reject
no implementer launch
```

A new independent review is required for the new context.

---

# Publication uncertainty fence

If PDFTR-51 state is:

```text
PUBLICATION_UNCERTAIN
```

automatic continuation must reject.

Even if local result is CHANGES_REQUIRED.

Reason:

The externally visible result may be ambiguous and repeated automated activity could create conflicting workflow state.

Human reconciliation first.

---

# Dispatch uncertainty fence

If the independent-review generation still has unresolved PDFTR-50:

```text
DISPATCH_UNCERTAIN
```

and no authenticated accepted result resolves it cleanly, do not continue.

Accepted result plus exact receipt correlation may resolve the practical dispatch identity according to existing PDFTR-51 semantics.

Do not weaken those semantics in this ticket.

---

# Repository safety

Before authorization and again before launch verify:

```text
expected repository fingerprint
expected branch
clean working tree
exact HEAD == source reviewed SHA
no merge in progress
no rebase in progress
no cherry-pick in progress
no unresolved conflicts
```

Reuse existing repo safety code.

Do not parse human-oriented `git status` output.

---

# Branch behavior

The continuation should remain on the existing task branch.

Do not automatically create a new branch for every independent review finding unless existing harness policy already requires it.

Expected:

```text
same ticket
same task branch
new commit(s)
new exact SHA
```

---

# Implementer prompt/input

The automatic implementer prompt should clearly state:

```text
This is an independent-review correction cycle.

Source independent generation: N
Reviewed HEAD: <sha>
Reviewed BASE: <sha>

Fix only the actionable findings below.

Do not change unrelated architecture.
Do not rewrite independent review evidence.
Do not modify continuation authorization.
Do not merge.

Run focused tests and full gate.
Commit and push.
```

Then include the trusted structured findings.

---

# Reviewer step after fix

Automatic continuation must not skip the existing internal Pi reviewer.

Flow remains:

```text
implementer
↓
Pi reviewer
↓
PASS
↓
CI
↓
independent review
```

Never:

```text
implementer
↓
independent review
```

unless the normal local reviewer was explicitly removed by a separately approved architecture change.

---

# Internal reviewer findings

Existing internal reviewer policy remains unchanged.

If the Pi reviewer returns CHANGES_REQUIRED, existing review-round behavior applies.

Do not count those rounds as independent continuation budget unless explicitly designed.

---

# GitHub / CI interaction

After implementer produces a new SHA:

- normal CI must run;
- PDFTR-49 eligibility must see the new implementation SHA;
- PDFTR-50 dispatches the next independent review only after required CI success.

PDFTR-52 does not bypass CI to accelerate the loop.

---

# Human intervention conditions

Automatic continuation stops when any of these occur:

```text
continuation budget exhausted
publication uncertain
dispatch uncertain
launch uncertain
repository mismatch
branch mismatch
dirty tree
active agent
corrupt state
stale independent result
review generation mismatch
unexpected cycle state
safety-class stop
operational retry exhaustion
review recovery required
```

The stop should include stable machine-readable reason codes.

---

# Suggested rejection/stop codes

Examples:

```text
continuation_not_changes_required
continuation_not_published
continuation_stale
continuation_generation_mismatch
continuation_head_mismatch
continuation_base_mismatch
continuation_cycle_state_invalid
continuation_cycle_sha_mismatch
continuation_branch_mismatch
continuation_repository_mismatch
continuation_dirty_tree
continuation_agent_active
continuation_budget_exhausted
continuation_publication_uncertain
continuation_dispatch_uncertain
continuation_launch_uncertain
continuation_state_corrupt
continuation_already_used
```

Do not use free-form prose as policy authority.

---

# Idempotency

Repeated triggers for the same continuation intent must produce:

```text
already authorized
already running
already consumed
```

not another implementer.

Test:

```text
event A
event B
restart
manual reevaluate
```

for the same generation:

```text
=> one continuation ID
=> one implementation launch
```

---

# Continuation completion

When implementation/review cycle completes successfully and produces new SHA:

mark source continuation:

```text
COMPLETED
```

with:

```text
resulting_implementation_sha
```

Do not modify original independent review result.

---

# Failure semantics

If the continuation implementation ends in a normal actionable internal review failure, use existing cycle semantics.

If the process itself fails operationally, use PDFTR-45 semantics.

If implementation stops pre-handoff for a safe clarification/unknown case, use PDFTR-48.

PDFTR-52 must not create alternate retry routes around those policies.

---

# YouTrack

YouTrack remains outside authorization.

Missing remote ticket:

```text
Issue not found
```

must not block continuation.

Optional status updates may remain best-effort through existing project tracking.

Do not auto-create PDFTR-52 in YouTrack because continuation happened.

---

# Security invariants

Must remain true:

1. independent reviewer cannot launch implementer;
2. GitHub comment cannot launch implementer;
3. agent cannot mark its own continuation authorized;
4. stale findings cannot launch work;
5. one independent generation cannot launch multiple automatic continuations;
6. continuation cannot bypass operational retry limits;
7. continuation cannot bypass review-round limits;
8. continuation cannot bypass pre-handoff safety;
9. uncertain launch cannot auto-retry;
10. merge remains human-owned.

---

# Tests

Add focused tests covering at least:

## Happy path

Given:

```text
current independent generation
CHANGES_REQUIRED
publication PUBLISHED
continuation intent current
cycle PASSED
repo clean
exact head/base match
budget available
```

Expected:

```text
continuation authorized
one new implementation attempt
findings handed to implementer
```

---

## PASS result

Independent PASS:

```text
→ continuation rejected
```

---

## Unpublished result

CHANGES_REQUIRED but publication not PUBLISHED:

```text
→ reject
```

---

## PUBLICATION_UNCERTAIN

```text
→ reject
```

---

## Stale head

Intent for A, current head B:

```text
→ reject
→ no launch
```

---

## Stale base

Same head, changed base:

```text
→ reject
```

---

## Older generation

Generation 1 CR but current generation 2 exists:

```text
→ generation 1 cannot launch continuation
```

---

## Duplicate trigger

Repeated trigger:

```text
→ one continuation
→ one launch
```

---

## Concurrent trigger

Two concurrent continuation attempts:

```text
→ one wins ownership
→ exactly one launch
```

---

## Restart before launch

Persist AUTHORIZED/PREPARED, simulate crash.

Restart:

```text
→ same continuation identity
→ no duplicate allocation
```

---

## Crash during launch

Simulate uncertain launch.

Expected:

```text
LAUNCH_UNCERTAIN
→ no automatic second process
```

---

## Active agent

Reject.

---

## Dirty working tree

Reject.

---

## HEAD mismatch

Reject.

---

## Branch mismatch

Reject.

---

## Repository identity mismatch

Reject.

---

## Merge/rebase/cherry-pick state

Reject.

---

## Budget

Run independent CR → continuation repeatedly.

At budget:

```text
MAX_INDEPENDENT_CONTINUATIONS reached
→ reject
→ human intervention
```

---

## Alternating retry paths

Prove that alternating:

```text
independent continuation
operational retry
pre-handoff retry
```

cannot exceed any individual policy's limit or convert one budget into another.

---

## Findings integrity

Tamper with continuation findings after authorization.

Expected:

```text
reject / hash mismatch
```

or equivalent immutable binding.

---

## Findings from GitHub comment

Must not authorize continuation.

---

## Continuation after stale CHANGES_REQUIRED publication

Reject.

---

## Internal reviewer still runs

Regression proving continuation does not skip Pi review.

---

## New SHA requires new independent review

After successful continuation implementation:

```text
old independent generation cannot authorize new SHA
```

---

## Missing YouTrack issue

Does not block.

---

# Acceptance criteria

PDFTR-52 is complete when:

1. automatic continuation uses only trusted PDFTR-51 intent;
2. only current published CHANGES_REQUIRED is eligible;
3. exact head/base/generation binding is enforced;
4. stale findings cannot launch work;
5. continuation history is persisted separately and immutably;
6. one generation creates at most one automatic continuation;
7. authorization persists before process launch;
8. restart cannot duplicate implementer launch;
9. launch uncertainty blocks automatic retry;
10. explicit continuation budget exists;
11. continuation budget cannot be bypassed via other recovery commands;
12. existing PDFTR-45/PDFTR-48/review-recovery policies remain distinct;
13. structured findings are handed to the implementer;
14. findings integrity is preserved;
15. normal Pi reviewer still runs after implementation;
16. CI remains required before next independent review;
17. YouTrack remains non-authoritative;
18. no automatic merge exists;
19. focused tests pass;
20. full `scripts/check.ps1` passes;
21. Windows and Ubuntu CI pass for the exact implementation SHA.

---

# Reviewer focus

Treat these as P1/HIGH or higher if they can cause unauthorized/duplicate work:

1. reviewer directly launching implementer;
2. stale `CHANGES_REQUIRED` launching fixes;
3. same generation launching twice;
4. continuation before persisted authorization;
5. automatic relaunch after uncertain process start;
6. continuation bypassing operational retry budget;
7. continuation bypassing internal review budget;
8. findings accepted from mutable/untrusted files;
9. HEAD/base mismatch ignored;
10. branch/repository/dirty-state checks weakened;
11. Pi reviewer skipped after fix;
12. infinite independent review/fix loop;
13. merge introduced anywhere in this flow.

---

# Recommended implementation boundaries

Prefer small modules:

```text
scripts/independent_review_continuation_policy.py
    pure eligibility/budget policy

scripts/independent_review_continuation.py
    trusted persisted continuation state

scripts/pi_ticket_cycle.py
    minimal hook into existing implementation launch path
```

Reuse:

```text
cycle_ownership.py
agent_cycle.py
existing process launch safety
existing repo identity validation
PDFTR-49 state
PDFTR-51 publication ledger
```

Do not duplicate these mechanisms.

---

# Initial automation level

For this ticket, automatic continuation may be enabled only when all deterministic safety predicates pass.

Otherwise:

```text
STOPPED / human intervention
```

This is preferable to a permissive fallback.

---

# Follow-up

After PDFTR-52 is stable, the normal loop should be:

```text
human starts ticket once
        ↓
implement
        ↓
internal review
        ↓
CI
        ↓
independent review
        ↓
CR → automatic fix continuation
        ↓
repeat within budget
        ↓
PASS
        ↓
human merge
```

At that point, routine implementation/review corrections should require very little manual orchestration.

Automatic merge remains a separate future decision.
