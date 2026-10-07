# PDFTR-49 — Independent Review Trigger Contract

## Status

Planned

## Summary

Define and implement a deterministic harness contract that decides when an independent exact-SHA human/ChatGPT review is eligible to start for a GitHub pull request.

This ticket does **not** implement GitHub webhooks or ChatGPT Work automation yet.

It establishes the safety and state-machine layer that future GitHub event triggers must call.

The contract must guarantee that independent review is always bound to an immutable commit SHA, cannot be duplicated for the same review generation, cannot authorize a newer PR HEAD based on a stale result, and cannot be triggered while required CI for that exact SHA is incomplete or failing.

---

## Motivation

The current PDFTranslator workflow already provides:

- deterministic implementation/reviewer cycles;
- exact-SHA automated review;
- strict reviewer read-only behavior;
- crash-safe operational retry;
- human-approved review recovery;
- human-approved clean pre-handoff retry;
- GitHub PR integration;
- YouTrack mutation safety;
- immutable attempt/review evidence.

After PDFTR-48, the remaining manual step before final merge is the independent exact-SHA human review.

Today the operator manually copies:

```text
Ticket: PDFTR-XX
State: PASSED
Implementation SHA: <SHA>
READY FOR HUMAN REVIEW
```

into ChatGPT and requests review.

The next automation stage should replace that manual handoff with an event-driven independent-review pipeline.

Before connecting GitHub webhooks or ChatGPT Work, the harness needs a deterministic contract that answers:

```text
Should this exact PR HEAD SHA receive an independent review now?
```

The event source must never decide that directly.

---

## Goals

Implement a pure/deterministic independent-review eligibility layer.

The contract must:

1. bind every independent review request to an exact commit SHA;
2. bind the SHA to a specific repository and pull request;
3. require the PR to be in an eligible state;
4. require required CI to be successful for that exact SHA;
5. reject duplicate independent reviews for the same review generation;
6. detect stale results when PR HEAD changes;
7. ensure PASS applies only to the exact reviewed SHA;
8. preserve previous independent review history;
9. fail closed on contradictory or incomplete state;
10. provide a stable interface for future GitHub webhook / ChatGPT Work integration.

---

## Non-goals

PDFTR-49 does not:

- implement a public webhook endpoint;
- create a GitHub App;
- configure ChatGPT Work triggers;
- automatically start ChatGPT Work;
- automatically merge pull requests;
- grant agents merge authority;
- change existing Pi implementer/reviewer behavior;
- replace GitHub CI;
- make YouTrack part of review authorization;
- automatically retry failed independent reviews;
- create an authenticated reviewer identity service;
- permit review of a moving branch name instead of an exact SHA.

---

## Core invariant

An independent review result authorizes only the exact commit SHA that was reviewed.

Formally:

```text
independent PASS is valid
iff
reviewed_sha == current_authorized_sha
```

A PASS for SHA A must never authorize SHA B.

---

## Architecture boundary

Future automation should conceptually be:

```text
GitHub event
    ↓
untrusted event notification
    ↓
refresh authoritative GitHub state
    ↓
IndependentReviewPolicy
    ↓
eligible exact SHA
    ↓
independent reviewer
```

The webhook/event payload is not authoritative.

The policy must operate on normalized, verified facts.

---

## Terminology

### Candidate SHA

The current exact PR head SHA proposed for independent review.

### Review generation

One logical independent review request for one exact SHA.

A new PR HEAD creates a new generation.

Example:

```text
generation 1 -> SHA A
generation 2 -> SHA B
generation 3 -> SHA C
```

### Stale review

A review whose `reviewed_sha` no longer equals the current PR HEAD.

Its evidence may be retained, but its result cannot authorize the current PR.

### Independent review

The external review performed after the normal Pi implementer/reviewer cycle and required CI succeed.

---

## Proposed persisted state

Add an independent review state record under the existing cycle coordination directory.

Preferred shape:

```text
.agent-cycle/PDFTR-49/
    independent-review.json
```

or an equivalent deterministic persisted structure.

Example:

```json
{
  "schema_version": "1.0",
  "repository": "bodomus/PDFTranslator",
  "ticket": "PDFTR-49",
  "pull_request": 123,
  "current_generation": 2,
  "reviews": [
    {
      "generation": 1,
      "requested_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "status": "STALE",
      "reviewed_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "verdict": "PASS"
    },
    {
      "generation": 2,
      "requested_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "status": "PENDING",
      "reviewed_sha": null,
      "verdict": null
    }
  ]
}
```

Exact file layout may differ if a cleaner existing harness representation fits better.

---

## Independent review states

Recommended states:

```text
NOT_REQUESTED
ELIGIBLE
REQUESTED
RUNNING
PASS
CHANGES_REQUIRED
STALE
BLOCKED
```

Do not overload the main implementation cycle state with these values.

Independent-review state is a separate concern.

---

## Authoritative eligibility facts

Eligibility must be derived from normalized facts such as:

```text
repository_identity
pull_request_number
pull_request_state
pull_request_draft
pull_request_head_sha
pull_request_base_sha
cycle_state
cycle_implementation_sha
ci_sha
ci_required_checks_complete
ci_required_checks_success
existing_review_generation
existing_review_status
```

Do not derive authorization from event names alone.

---

## Eligibility policy

An independent review may become eligible only when all required conditions pass.

At minimum:

```text
cycle_state == PASSED

PR exists

PR is open

PR is not draft

PR HEAD SHA == cycle implementation SHA

required CI belongs to PR HEAD SHA

all required CI checks are complete

all required CI checks succeeded

no active independent review already exists for this SHA

no PASS or CHANGES_REQUIRED result already exists for this generation

repository identity matches expected repository
```

If any required fact cannot be proven, eligibility must fail closed.

---

## PR ready state

Preferred initial policy:

```text
PR open
AND
draft == false
```

Do not require a specific webhook such as `ready_for_review`.

A PR already in ready state may become review-eligible after CI finishes.

This allows multiple event sources to converge on the same deterministic policy.

---

## CI contract

Independent review must require CI success for the exact candidate SHA.

Forbidden:

```text
latest CI succeeded
```

Required:

```text
CI success for SHA == candidate SHA
```

The implementation should normalize CI state into a simple deterministic representation.

Recommended:

```text
ci_status =
    PENDING
    SUCCESS
    FAILURE
    UNKNOWN
```

Only:

```text
SUCCESS
```

authorizes independent review.

---

## Required checks

The policy should support a deterministic required-check set.

Do not hard-code provider-specific webhook semantics into the policy.

Preferred representation:

```text
required_checks = [
    "windows",
    "ubuntu"
]
```

or existing project-equivalent workflow/check identifiers.

All configured required checks must report success for the exact candidate SHA.

Missing check:

```text
=> not eligible
```

Queued/in-progress check:

```text
=> not eligible
```

Failed/cancelled/timed-out check:

```text
=> not eligible
```

---

## Review generation identity

Each new candidate SHA creates at most one new independent review generation.

Example:

```text
SHA A
-> generation 1

additional webhook for SHA A
-> still generation 1

CI completion event for SHA A
-> still generation 1

PR synchronize event with SHA B
-> generation 2
```

Duplicate events must never create duplicate generations.

---

## Duplicate suppression

The following sequence:

```text
pull_request event
check_run event
workflow_run event
status event
```

for the same SHA must result in at most one independent review request.

Eligibility evaluation must therefore be idempotent.

Recommended identity:

```text
(repository identity, PR number, candidate SHA)
```

or a stable hash derived from those fields.

---

## Stale result handling

Assume:

```text
review generation 1 -> SHA A
```

While review is running:

```text
PR HEAD changes to SHA B
```

The review of SHA A may finish.

Its result must be recorded as historical evidence but must not authorize SHA B.

Example:

```text
reviewed_sha = SHA A
current PR HEAD = SHA B

=> result status = STALE
```

Even:

```text
verdict = PASS
```

does not make SHA B eligible for merge.

---

## PASS validity

A PASS is valid only while:

```text
reviewed_sha == PR HEAD SHA
```

and all other required authorization facts still hold.

If HEAD changes after PASS:

```text
previous PASS -> STALE
new generation -> candidate
```

A new independent review is required.

---

## CHANGES_REQUIRED validity

`CHANGES_REQUIRED` also belongs to the exact reviewed SHA.

After a fix produces a new SHA:

```text
old CHANGES_REQUIRED remains historical
new SHA receives new generation
```

Do not mutate the previous review record into the new review.

---

## Review result contract

Define a normalized independent review result.

Recommended shape:

```json
{
  "schema_version": "1.0",
  "repository": "bodomus/PDFTranslator",
  "pull_request": 123,
  "generation": 2,
  "reviewed_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "verdict": "PASS",
  "findings": []
}
```

or:

```json
{
  "verdict": "CHANGES_REQUIRED",
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

Reuse existing review-schema primitives where safe.

Do not create conflicting meanings for severity or verdict.

---

## Result validation

Before accepting a result:

```text
repository matches
PR matches
generation exists
generation requested_sha matches reviewed_sha
reviewed_sha is valid SHA
verdict schema valid
findings schema valid
```

Then refresh authoritative current PR state.

If:

```text
current PR HEAD != reviewed_sha
```

record result as stale.

---

## Event model

PDFTR-49 should define the future event contract without implementing the receiver.

Possible event signals include:

```text
pull_request opened
pull_request ready_for_review
pull_request synchronize
check_suite completed
check_run completed
workflow_run completed
manual reevaluate
```

All events perform the same operation:

```text
refresh facts
evaluate policy
```

There must not be separate safety semantics per webhook event.

---

## Re-evaluation

Policy evaluation must be safe to run repeatedly.

Example:

```text
evaluate()
evaluate()
evaluate()
```

with unchanged external state must produce no additional review request.

This is essential for webhook delivery retries.

---

## Crash safety

Persist generation/request intent before an external reviewer is dispatched.

Conceptual order:

```text
1. refresh authoritative facts
2. evaluate eligibility
3. allocate generation
4. persist REQUESTED
5. dispatch reviewer
```

A crash after step 4 must not allocate another generation for the same SHA.

A restart must recover the existing `REQUESTED` generation.

---

## Dispatch uncertainty

Future reviewer dispatch may fail with uncertain outcome.

PDFTR-49 should reserve a representation for this case.

Recommended:

```text
REQUESTED
RUNNING
DISPATCH_UNCERTAIN
```

Do not automatically create another reviewer request while dispatch outcome is uncertain.

Exact implementation of external dispatch belongs to PDFTR-50.

---

## Manual reevaluation

Provide a deterministic local inspection/evaluation command.

Suggested shape:

```text
uv run python scripts/independent_review.py status PDFTR-49
```

and:

```text
uv run python scripts/independent_review.py evaluate PDFTR-49 --facts <file>
```

or an equivalent testable interface.

PDFTR-49 must not require live GitHub credentials for unit tests.

---

## Pure policy boundary

Prefer a module such as:

```text
scripts/independent_review_policy.py
```

with a function conceptually like:

```python
evaluate_independent_review(facts, state) -> Decision
```

The function must:

- perform no network calls;
- perform no GitHub mutations;
- perform no filesystem mutations;
- perform no subprocess execution;
- depend only on validated input.

This makes the future webhook boundary small and auditable.

---

## Decision output

Recommended result:

```text
ELIGIBLE
NOT_ELIGIBLE
ALREADY_REQUESTED
ALREADY_REVIEWED
STALE
INVALID
```

plus a stable reason code.

Example:

```text
ci_pending
ci_failed
pr_draft
pr_closed
sha_mismatch
already_requested
already_reviewed
repository_mismatch
cycle_not_passed
state_corrupt
```

Do not use free-form prose as policy input.

---

## YouTrack

YouTrack must remain outside the critical independent-review authorization path.

Failures such as:

```text
credentials unavailable
HTTP failure
mutation uncertainty
field mapping unavailable
```

must not invalidate a GitHub independent review decision unless an existing explicit safety invariant requires otherwise.

Project tracking may observe the result later.

---

## Security / trust boundaries

The following remain human-owned:

```text
merge
force recovery
override of contradictory state
```

Independent-review automation must not grant merge authority.

Agents must not be able to mark their own review generation as PASS by modifying harness state.

Persisted state used for authorization remains harness-owned.

---

## Tests

Add focused tests covering at least:

### Eligible SHA

Given:

```text
cycle PASSED
PR open
PR not draft
PR HEAD == implementation SHA
all required CI success for exact SHA
no previous review
```

Then:

```text
ELIGIBLE
```

---

### CI pending

Required CI still running:

```text
NOT_ELIGIBLE
reason=ci_pending
```

No generation dispatched.

---

### CI failure

```text
NOT_ELIGIBLE
reason=ci_failed
```

---

### CI belongs to old SHA

```text
PR HEAD = B
CI success = A
```

must reject.

---

### Cycle SHA mismatch

```text
cycle implementation SHA = A
PR HEAD = B
```

must reject independent review until authoritative state is reconciled.

---

### Draft PR

Draft PR must not be eligible.

---

### Closed PR

Closed PR must not be eligible.

---

### Duplicate event

Evaluate the same eligible facts repeatedly.

Exactly one generation/request may exist.

---

### HEAD update

```text
generation 1 = SHA A
PR HEAD becomes SHA B
```

Create generation 2 only once.

Generation 1 becomes historical/stale where appropriate.

---

### PASS then HEAD change

PASS for A:

```text
PASS valid
```

Then PR HEAD changes to B:

```text
PASS A no longer authorizes current PR
generation B required
```

---

### Running review becomes stale

Review A is RUNNING.

HEAD changes to B.

Review A returns PASS.

Result must be retained but marked stale.

---

### CHANGES_REQUIRED then new SHA

Old findings remain tied to SHA A.

SHA B receives new generation.

---

### Contradictory generation state

Examples:

```text
two generations for same SHA
duplicate generation numbers
PASS without reviewed_sha
reviewed_sha != requested_sha
```

must fail closed.

---

### Dispatch crash

Persist REQUESTED.

Simulate crash before reviewer invocation.

Restart must not allocate another generation.

---

### Unknown CI state

Fail closed.

---

### Repository mismatch

Reject.

---

### Event name independence

Different event types with identical authoritative facts must produce the same policy decision.

---

## Acceptance criteria

PDFTR-49 is complete when:

1. independent review eligibility is deterministic and exact-SHA bound;
2. GitHub event names are not trusted as authorization;
3. PR HEAD, cycle implementation SHA and CI SHA must agree;
4. required CI must succeed for the exact candidate SHA;
5. duplicate events cannot create duplicate reviews;
6. each new SHA creates at most one generation;
7. stale review results cannot authorize newer HEADs;
8. PASS is valid only for its exact reviewed SHA;
9. previous review evidence remains immutable/history-preserving;
10. crash before reviewer dispatch cannot manufacture duplicate generations;
11. contradictory persisted state fails closed;
12. policy is testable without GitHub credentials;
13. no webhook server is introduced;
14. no ChatGPT Work integration is introduced yet;
15. YouTrack remains outside the critical authorization path;
16. merge remains human-owned;
17. existing PDFTR-35A/40/42/45/46/47/48 safety behavior remains unchanged;
18. focused tests pass;
19. full `scripts/check.ps1` passes;
20. CI passes on Windows and Ubuntu.

---

## Reviewer focus

Treat the following as high-risk:

1. reviewing branch names instead of exact SHA;
2. trusting webhook payloads without authoritative refresh;
3. accepting CI success belonging to another SHA;
4. duplicate generation creation from repeated events;
5. PASS surviving a PR HEAD change;
6. stale review result authorizing current HEAD;
7. external reviewer dispatch before request persistence;
8. automatic re-dispatch after uncertain dispatch;
9. agent-writable authorization state;
10. coupling YouTrack availability to independent review authorization.

Any issue capable of allowing an unreviewed SHA to appear independently approved should normally be P1/HIGH or higher.

---

## Follow-up

After PDFTR-49 passes independent human review:

### PDFTR-50

GitHub event / ChatGPT Work integration:

```text
GitHub PR/CI event
→ authoritative GitHub refresh
→ PDFTR-49 policy
→ exact-SHA ChatGPT Work review
```

### PDFTR-51

Review result publication:

```text
PASS / CHANGES_REQUIRED
→ GitHub PR review/check/comment
→ optional harness continuation
```

Do not implement these integrations inside PDFTR-49.
