# PDFTR-48 — Human-approved retry for clean pre-handoff STOPPED states

## Human exact-SHA review correction

Reviewed SHA: `e54c6ed2ec336f96f104efd48cc27d7827003280`. P1/HIGH: pre-handoff retry
must reject every structured operational stop, including implementer_process_failed. Operational
failures use only the PDFTR-45 path and its MAX_OPERATIONAL_RETRIES budget. Stop prose never grants
eligibility. Keep clean pre-handoff rules, review-exhaustion recovery, remote uncertainty fences and
reviewer permissions intact. Add same-state rejection/acceptance and alternating-command budget
regressions, run focused tests and full scripts/check.ps1, then commit and push the minimal fix.

## Status

Planned

## Summary

Add a safe, explicit, human-approved recovery path for cycles that stop cleanly before implementer handoff is produced.

The target case is a cycle in `STOPPED` state where the implementer process has exited without producing a valid `implementer.json`, no review has started, repository state is unchanged and clean, and there is no unresolved remote mutation uncertainty.

The operator must be able to retry the implementer phase without manually renaming or deleting `.agent-cycle/<ticket>`.

This recovery path must preserve all existing safety guarantees from PDFTR-35A, PDFTR-40, PDFTR-42, PDFTR-45, PDFTR-46, and PDFTR-47.

---

## Motivation

During PDFTR-47, the first implementer invocation stopped cleanly before producing a handoff:

```text
STOPPED
review_round=0
stop_reason=implementer did not produce implementer.json
stop_class=unknown
working tree clean
HEAD unchanged
```

The operational retry mechanism introduced by PDFTR-45 correctly rejected this case because the stop was not classified as operational.

Recovery therefore required a manual workaround:

```text
rename .agent-cycle/PDFTR-47
```

followed by starting a fresh cycle.

This is undesirable because manual manipulation of `.agent-cycle`:

- bypasses normal state-machine controls;
- weakens provenance;
- risks accidental loss of diagnostic artifacts;
- makes repeated attempts harder to audit;
- creates an unnecessary operator procedure outside the harness.

The harness should support this case directly while remaining fail-closed.

---

## Goals

Implement an explicit human-approved retry mechanism for safe pre-handoff STOPPED states.

The mechanism must:

1. allow retry only before a valid implementer handoff exists;
2. require explicit operator action;
3. prove repository safety before retry;
4. preserve all artifacts from the failed attempt;
5. record retry provenance;
6. prevent accidental transition into review;
7. remain safe across process restart;
8. remain safe under malformed, incomplete, or contradictory persisted state;
9. remain independent of free-form `stop_reason` text;
10. remain compatible with existing operational retry semantics from PDFTR-45.

---

## Non-goals

PDFTR-48 does not:

- add automatic retries for clarification or unknown stops;
- broaden PDFTR-45 operational retry eligibility;
- permit retry after review has started;
- permit retry after source changes have been made;
- permit retry when repository identity cannot be proven;
- permit retry while remote mutation outcome is uncertain;
- discard or overwrite prior attempt artifacts;
- automatically reinterpret arbitrary `stop_class=unknown` as safe;
- allow agents themselves to authorize retry;
- allow reviewer mutation;
- change merge ownership;
- weaken Git safety checks from PDFTR-40;
- change the coherent startup snapshot guarantees from PDFTR-46;
- weaken YouTrack uncertainty handling from PDFTR-47.

---

## Terminology

### Attempt

One implementer execution within a ticket cycle.

A retry creates a new attempt.

Attempts must have stable monotonic identity, for example:

```text
attempt=1
attempt=2
attempt=3
```

or an equivalent persisted representation.

### Pre-handoff STOPPED

A cycle state where:

- the cycle is `STOPPED`;
- no valid accepted `implementer.json` exists;
- review has not started;
- `review_round == 0`;
- the repository remains at the expected source state.

### Human-approved retry

A recovery action initiated explicitly by the operator after the harness verifies eligibility.

The harness must never enter this recovery path automatically.

---

## Core safety invariant

A pre-handoff retry may occur only when the harness can prove that repeating the implementer phase is equivalent to starting another implementation attempt from the same trusted repository state.

If this cannot be proven, retry must fail closed.

---

## Eligibility

The harness may offer or accept pre-handoff retry only when all required predicates pass.

At minimum:

```text
cycle_state == STOPPED
review_round == 0
no accepted implementer handoff exists
review has never started
working tree is clean
HEAD == expected pre-implementation HEAD
current branch == expected branch
repository identity == expected repository
no conflicting Git state exists
no active agent process exists
no unresolved operational mutation exists
no unresolved project-tracking mutation uncertainty exists
persisted retry metadata is internally consistent
```

Existing hardened repository validation must be reused rather than reimplemented.

---

## Stop classification

Retry eligibility must not depend on matching text in:

```text
stop_reason
```

The following is forbidden:

```python
if "did not produce implementer.json" in stop_reason:
    allow_retry()
```

Eligibility must be derived from structured cycle state and independently verified runtime facts.

A new structured stop classification may be introduced if useful, for example:

```text
stop_class=pre_handoff
stop_code=implementer_no_handoff
```

or:

```text
stop_class=clarification
stop_code=implementer_requested_clarification
```

However:

- legacy `stop_class=unknown` must not automatically become retryable;
- classification must remain fail-closed;
- eligibility must still be validated independently at retry time.

---

## CLI

Provide an explicit operator command for this recovery path.

Preferred shape:

```text
uv run python scripts/agent_cycle.py retry-pre-handoff PDFTR-48
```

or an equivalent dedicated subcommand.

The command must not overload the existing operational retry command if doing so would make the safety model ambiguous.

The command must clearly report:

- current cycle state;
- current attempt;
- expected HEAD;
- actual HEAD;
- branch;
- working-tree state;
- retry eligibility;
- reason for rejection if ineligible.

The action itself must require explicit operator invocation.

No implicit retry on normal `run`, `resume`, or status commands.

---

## Artifact preservation

Previous attempt artifacts must remain immutable.

A retry must not overwrite prior:

```text
progress.log
implementer progress data
stdout/stderr captures
diagnostics
stop metadata
process metadata
handoff validation errors
```

Preferred layout:

```text
.agent-cycle/PDFTR-48/
    state.json
    attempts/
        1/
            implementer/
                ...
        2/
            implementer/
                ...
```

If changing the existing on-disk layout is unnecessarily invasive, an equivalent append-only representation is acceptable.

The important invariant is:

> Historical evidence from attempt N must remain available after attempt N+1 starts.

No destructive rename/delete workflow should be required.

---

## Retry provenance

Each retry must persist enough metadata to audit why it occurred.

At minimum:

```text
attempt_id
previous_attempt_id
retry_kind=pre_handoff
approved_by=human
approved_at
source_head
branch
repository_identity
previous_stop_class
previous_stop_code
previous_stop_reason
```

Do not store secrets.

Do not store chain-of-thought.

Human approval should be represented as an operational fact, not as free-form model output.

---

## State transitions

Allowed transition:

```text
STOPPED
  |
  | human-approved pre-handoff retry
  v
IMPLEMENTING
```

The transition is permitted only after retry validation succeeds.

The retry must create a new attempt identity before starting the implementer.

The previous STOPPED attempt remains historical and immutable.

---

## Forbidden transitions

The following must be rejected:

```text
READY_FOR_REVIEW -> retry-pre-handoff
REVIEWING -> retry-pre-handoff
READY_FOR_REVIEW_2 -> retry-pre-handoff
PASS -> retry-pre-handoff
FAILED -> retry-pre-handoff
```

Also reject when:

```text
review_round > 0
```

or when any accepted reviewer artifact proves that review already started.

Persisted state contradictions must fail closed.

---

## Handoff rules

A retry is only a pre-handoff recovery.

If a valid accepted `implementer.json` already exists, this command must refuse.

Malformed or rejected handoff files require careful distinction:

- an invalid, never-accepted candidate handoff may remain diagnostic evidence;
- an accepted handoff permanently closes the pre-handoff retry path;
- the validator must not silently treat malformed handoff artifacts as accepted;
- retry must not delete malformed handoff evidence.

---

## Repository safety

Before starting the new attempt, the harness must re-run the same hardened repository checks required by existing recovery mechanisms.

At minimum:

### HEAD binding

```text
actual HEAD == persisted expected HEAD
```

### Branch binding

```text
actual branch == persisted expected branch
```

### Clean tree

No tracked or untracked implementation changes may be present unless current existing policy explicitly permits them.

### Repository identity

The repository must be the exact expected repository.

Reuse PDFTR-40 protections for:

- gitfiles;
- symlinks;
- `.git/commondir`;
- alternates;
- repository redirects;
- unsafe Git configuration;
- helper/filter/pager execution surfaces.

Do not introduce a weaker retry-specific Git inspection implementation.

---

## Process safety

Retry must not start if an earlier agent process may still be active.

Reuse existing process ownership and child-process safety mechanisms.

The harness must avoid:

- overlapping implementers;
- retry while an old implementer is still alive;
- stale PID trust without identity validation;
- orphaned child processes.

On Windows, existing Job Object protections must remain effective.

On POSIX, existing process reap/ownership behavior must remain effective.

---

## Remote mutation safety

Retry must not bypass mutation fences.

If any remote mutation is in an unresolved uncertain state, retry must fail closed where that mutation could make repeating the phase unsafe.

In particular, preserve PDFTR-47 guarantees around YouTrack mutations:

```text
post-dispatch timeout
connection loss
HTTP 408
HTTP 5xx
```

may leave a mutation uncertain.

A pre-handoff retry must not cause duplicate remote mutation merely because the implementation attempt is being repeated.

Existing exact-identity reconciliation and duplicate-create prevention remain mandatory.

---

## Project tracking behavior

Starting a new local implementation attempt must not imply creation of a new YouTrack issue.

Project tracking must continue using the exact existing issue identity.

If the prior attempt already performed a definite successful project-tracking mutation, retry must not repeat it unless the mutation protocol independently determines that another mutation is required.

If project-tracking state is uncertain, preserve the uncertainty fence.

GitHub readiness must remain independent of YouTrack uncertainty where PDFTR-47 already guarantees that behavior.

---

## Crash safety

The retry action itself must be crash-safe.

A crash between approval and process launch must not leave the cycle in an ambiguous state that allows duplicate concurrent attempts.

The harness should persist retry intent / new attempt state before process dispatch, using the existing crash-safe persistence model.

After restart, the runner must be able to determine whether:

- retry had not started;
- retry was committed but implementer was not dispatched;
- implementer was dispatched;
- implementer exited;
- handoff exists or does not exist.

The system must not silently launch an additional attempt merely because startup occurred after a crash.

---

## Idempotency

Repeated execution of the retry command must be safe.

Examples:

### First invocation succeeds

```text
attempt 1 STOPPED
retry command
attempt 2 starts
```

A second immediate retry command must not create attempt 3 while attempt 2 is active.

### Crash after retry state persistence

Restart must recover attempt 2 rather than manufacture attempt 3.

### Retry command after handoff

If attempt 2 already produced an accepted handoff, retry-pre-handoff must reject.

---

## Clarification-needed cases

The design should support clean clarification-related stops where the implementer intentionally declines to proceed before mutation/handoff.

However, PDFTR-48 must not assume that every clarification request is safe to retry.

The same repository and state invariants apply.

Preferred future-compatible structured representation:

```text
stop_class=clarification
stop_code=<stable code>
```

The human operator may resolve the clarification externally and then explicitly authorize a retry.

The harness does not need to understand the semantic content of the clarification.

---

## Compatibility with PDFTR-45

Operational retry and pre-handoff retry must remain separate safety concepts.

### Operational retry

Used when execution failed for a recognized operational reason under PDFTR-45 policy.

### Pre-handoff retry

Used when implementation did not reach a valid handoff but the repository and cycle remain provably unchanged and safe.

Do not make:

```text
stop_class=unknown
```

globally operational-retryable.

Do not weaken existing PDFTR-45 predicates.

A shared lower-level restart primitive is acceptable if both public recovery paths enforce their own independent eligibility policies before calling it.

---

## Compatibility with PDFTR-42

PDFTR-42 handles recovery after review exhaustion.

PDFTR-48 handles recovery before the first implementer handoff.

These must remain distinct.

Conceptually:

```text
pre-handoff failure
    -> PDFTR-48

operational execution failure
    -> PDFTR-45

review exhaustion
    -> PDFTR-42
```

Avoid a single generic `force-retry` path.

---

## Security / trust boundary

Only the human operator may authorize this retry.

Agents may:

- report that they stopped;
- report clarification requirements;
- write structured artifacts allowed by their role.

Agents must not:

- mark their own attempt retry-approved;
- modify persisted approval state directly;
- bypass the harness state machine;
- invoke privileged mutation through crafted handoff content.

Reviewer remains strictly read-only.

---

## Validation failures

Retry must reject with a specific structured reason.

Recommended examples:

```text
retry_not_stopped
retry_review_already_started
retry_handoff_already_accepted
retry_head_mismatch
retry_branch_mismatch
retry_dirty_tree
retry_repository_identity_mismatch
retry_agent_still_active
retry_remote_mutation_uncertain
retry_state_corrupt
retry_attempt_metadata_inconsistent
```

Do not collapse all failures to:

```text
retry not allowed
```

The structured reason should be persisted where appropriate for diagnostics.

---

## Tests

Add focused tests covering at least the following.

### Happy path

Given:

```text
STOPPED
review_round=0
no accepted implementer.json
HEAD unchanged
branch unchanged
tree clean
repository identity valid
no running agent
no unresolved mutation uncertainty
```

Then explicit human-approved retry:

- succeeds;
- creates a new attempt;
- preserves previous attempt artifacts;
- starts only one implementer;
- leaves reviewer untouched.

---

### Dirty working tree

Any implementation-related working-tree change causes retry rejection.

No new attempt is created.

---

### HEAD changed

If HEAD differs from the persisted expected source SHA:

- reject;
- preserve state;
- do not spawn implementer.

---

### Branch changed

Reject if current branch differs from expected branch.

---

### Repository identity mismatch

Reject foreign or redirected repositories using the hardened Git inspection layer.

---

### Accepted handoff exists

If an accepted `implementer.json` exists:

- reject pre-handoff retry;
- do not alter artifacts.

---

### Review already started

Reject if:

```text
review_round > 0
```

or persisted accepted review artifacts prove review started.

---

### Active process

Retry while the previous implementer is still active must reject.

---

### Repeated command

Two retry invocations must not create two new attempts.

---

### Crash before dispatch

Simulate crash after retry intent/state persistence but before implementer launch.

On restart:

- state remains coherent;
- at most one attempt exists;
- no duplicate attempt is created.

---

### Crash after dispatch

Simulate process launch followed by runner crash.

On restart:

- active/finished process state is reconciled;
- no duplicate implementer is launched.

---

### Malformed state

Contradictory persisted state must fail closed.

Examples:

```text
STOPPED + review_round=1
STOPPED + accepted implementer handoff + pre-handoff retry marker
attempt=2 but attempt 1 missing without valid migration explanation
```

---

### Legacy unknown stop

A generic:

```text
stop_class=unknown
```

must not become retryable merely because it is unknown.

Retry succeeds only if the explicit pre-handoff recovery policy independently validates all required facts.

---

### Free-form stop_reason attack

Changing `stop_reason` to text resembling a retryable condition must not affect eligibility.

---

### Artifact preservation

Attempt 1 logs and diagnostics must remain byte-for-byte preserved after attempt 2 starts.

---

### Reviewer isolation

Pre-handoff retry must not:

- spawn reviewer;
- modify reviewer artifacts;
- increment review round.

---

### YouTrack definite success

If a prior tracking mutation definitely succeeded, retry must not duplicate it.

---

### YouTrack uncertain mutation

If mutation uncertainty exists, behavior must follow the existing PDFTR-47 fence and must never produce duplicate create/update actions.

---

### Restart persistence

A retryable STOPPED state remains correctly represented across process restart.

Approval itself must not accidentally turn into automatic infinite retry behavior.

---

## Acceptance criteria

PDFTR-48 is complete when:

1. a clean pre-handoff STOPPED cycle can be retried without renaming `.agent-cycle/<ticket>`;
2. retry requires explicit human action;
3. retry eligibility is based on structured state plus independently verified invariants;
4. `stop_reason` text does not control eligibility;
5. previous attempt artifacts are preserved;
6. each retry has explicit attempt identity and provenance;
7. retry is rejected after accepted implementer handoff;
8. retry is rejected after review begins;
9. HEAD, branch, clean tree, and repository identity are revalidated;
10. concurrent or duplicate attempts cannot be created;
11. crash/restart cannot silently create another attempt;
12. remote mutation uncertainty remains fenced;
13. project-tracking mutations are not duplicated;
14. PDFTR-45 operational retry behavior is unchanged;
15. PDFTR-42 review-exhaustion recovery is unchanged;
16. reviewer remains strictly read-only;
17. existing PDFTR-35A / 40 / 42 / 45 / 46 / 47 safety tests remain green;
18. focused adversarial tests are added for the new recovery path;
19. full `scripts/check.ps1` passes;
20. CI passes on Windows and Ubuntu.

---

## Reviewer focus

Reviewer should treat the following as high-risk areas:

1. Any path allowing retry based only on `stop_reason`.
2. Any generic `force` or `reset` command that bypasses state validation.
3. Any deletion or overwrite of previous attempt artifacts.
4. Any possibility of duplicate implementer execution.
5. Any retry after accepted handoff or review start.
6. Any weaker Git validation than existing hardened repository inspection.
7. Any agent-controlled approval field.
8. Any retry path that bypasses remote mutation uncertainty fences.
9. Any crash window capable of manufacturing an extra attempt.
10. Any backward-compatibility change that silently makes historical `unknown` stops retryable.

A failure in these areas should normally be considered at least P1/HIGH if it can bypass an existing safety boundary.

---

## Implementation guidance

Prefer a small policy layer over broad runner restructuring.

Suggested separation:

```text
pre_handoff_retry_policy.py
    evaluate_pre_handoff_retry(...)

agent_cycle.py
    CLI / operator command

pi_ticket_cycle.py
    execution of already-authorized attempt
```

Exact module names are not mandatory.

The important architectural property is that retry eligibility remains a deterministic harness policy rather than an agent decision.

Where possible, reuse existing primitives for:

- repository snapshot verification;
- process-state validation;
- artifact persistence;
- mutation uncertainty handling;
- atomic state writes.

Do not create a second implementation of those safety mechanisms.

---

## Follow-up opportunities

Not part of PDFTR-48, but the attempt model introduced here should make future work easier:

- unified attempt history/status display;
- richer operator inspection of failed attempts;
- explicit clarification artifacts;
- generic recovery audit trail;
- ChatGPT Work visibility into attempt history;
- automated archival of completed attempt diagnostics.

These should remain follow-up work unless required to implement PDFTR-48 safely.
