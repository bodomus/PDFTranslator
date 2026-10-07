# PDFTR-50 — GitHub-triggered independent review dispatch

## Status

Planned

## Summary

Integrate the PDFTR-49 independent-review contract with GitHub PR/CI events and a trusted external review dispatcher.

The integration must:

```text
GitHub event
    ↓
untrusted wake-up signal
    ↓
authoritative GitHub refresh
    ↓
normalized exact PR/head/base/CI facts
    ↓
PDFTR-49 IndependentReviewPolicy
    ↓
durably persisted REQUESTED generation
    ↓
trusted independent-review dispatch
```

The dispatched review must be pinned to the exact immutable review context:

```text
repository
pull_request
generation
head_sha
base_sha
```

This ticket does **not** publish PASS/CHANGES_REQUIRED back to GitHub and does not automate merge.

---

## Motivation

PDFTR-49 established a fail-closed independent-review policy with:

- exact PR head SHA binding;
- exact PR base SHA binding;
- required CI gating;
- duplicate suppression;
- immutable review generations;
- stale-result handling;
- crash-safe request intent persistence;
- dispatch uncertainty representation;
- read-only agent-facing diagnostics;
- human-owned merge.

The remaining manual operation is initiating the independent review after GitHub state becomes eligible.

Currently the operator must observe:

```text
Pi cycle PASS
+
PR ready
+
CI success
```

and manually request an independent ChatGPT review.

PDFTR-50 should automate that handoff without moving trust into webhook payloads or agent-controlled files.

---

## Goals

Implement a trusted GitHub-triggered dispatch layer that:

1. accepts GitHub events only as wake-up signals;
2. refreshes authoritative GitHub state before every policy decision;
3. constructs the normalized PDFTR-49 facts contract;
4. verifies exact repository, PR, head SHA and base SHA identity;
5. verifies required CI for the exact head SHA;
6. invokes the existing PDFTR-49 policy/store rather than reimplementing eligibility;
7. persists review request intent before external dispatch;
8. dispatches at most once for one review generation;
9. records dispatch success or uncertainty;
10. survives duplicate GitHub events;
11. survives process restart without duplicate dispatch;
12. prepares a stable transport contract for ChatGPT Work or another independent reviewer.

---

## Non-goals

PDFTR-50 does not:

- publish review results back to GitHub;
- post PR comments;
- create GitHub checks/statuses for independent review;
- automatically apply fixes;
- invoke the Pi implementer after CHANGES_REQUIRED;
- automatically merge;
- change PDFTR-49 eligibility semantics;
- change Pi implementer/reviewer behavior;
- make YouTrack required;
- create a YouTrack issue implicitly;
- treat webhook payloads as trusted authorization facts;
- expose harness mutation APIs to implementer/reviewer agents.

Result publication and automated continuation belong to PDFTR-51+.

---

## Core invariant

A GitHub event may cause evaluation.

It must never directly cause authorization.

```text
event received
    !=
review authorized
```

Only freshly fetched authoritative state evaluated through PDFTR-49 may create a review request.

---

# Architecture

Preferred structure:

```text
GitHub
  │
  │ event
  ▼
GitHubEventAdapter
  │
  │ wake-up identity only
  ▼
GitHubFactsProvider
  │
  ├─ fetch PR
  ├─ fetch HEAD/base
  ├─ fetch required CI/checks
  └─ verify repository/PR identity
  │
  ▼
Normalized IndependentReviewFacts
  │
  ▼
IndependentReviewStore.request(...)
  │
  ├─ refresh_state
  ├─ evaluate_independent_review
  └─ persist REQUESTED
  │
  ▼
IndependentReviewDispatcher
  │
  ▼
ChatGPT Work / trusted review transport
```

Do not duplicate PDFTR-49 policy inside the integration layer.

---

# Trust boundaries

## GitHub event

Treat incoming event data as untrusted notification data.

Allowed use:

```text
repository hint
PR number hint
event type for diagnostics
delivery/event identifier
```

Forbidden use as authorization:

```text
payload head SHA is trusted
payload CI conclusion is trusted
payload draft state is trusted
payload base SHA is trusted
```

Those facts must be re-fetched from GitHub.

---

## Authoritative GitHub adapter

The trusted adapter must independently fetch:

```text
repository identity
PR existence
PR state
draft state
PR head SHA
PR base SHA
required CI/check state
```

The adapter must verify that the fetched repository and PR correspond to the configured ticket/review target.

---

## Policy

PDFTR-49 remains the only independent-review authorization policy.

PDFTR-50 may normalize data, but must not create alternate eligibility semantics.

---

## Dispatcher

The dispatcher receives an already-persisted review generation.

It must not decide whether that generation was eligible.

---

# GitHub events

The integration should support at least signals equivalent to:

```text
pull request opened
pull request reopened
pull request ready-for-review
pull request synchronize / new commit
pull request edited / retargeted
CI/check completion
manual reevaluation
```

Different event types must converge on the same operation:

```text
refresh authoritative facts
→ evaluate
```

Do not implement event-specific authorization rules.

---

# Event deduplication

GitHub may redeliver events.

A repeated delivery must be safe.

Store a bounded diagnostic delivery record or equivalent idempotency information if needed, but correctness must not rely solely on GitHub delivery IDs.

Primary idempotency remains the PDFTR-49 review identity:

```text
(repository, PR, head_sha, base_sha)
```

Repeated events for the same authoritative pair must produce:

```text
ALREADY_REQUESTED
```

or:

```text
ALREADY_REVIEWED
```

rather than another dispatch.

---

# Authoritative facts adapter

Introduce a small adapter, for example:

```text
scripts/github_independent_review.py
```

or equivalent.

Preferred responsibilities:

```python
fetch_pr(...)
fetch_required_checks(...)
build_independent_review_facts(...)
```

The resulting facts must match the PDFTR-49 schema exactly.

Do not add GitHub-specific fields to the pure policy contract unless strictly necessary.

---

# Repository binding

The integration must have trusted configuration containing the expected repository.

Example:

```json
{
  "repository": "bodomus/PDFTranslator",
  "ticket": "PDFTR-50",
  "pull_request": 123,
  "required_checks": [
    "windows",
    "ubuntu"
  ]
}
```

Repository identity mismatch must fail closed.

Do not accept repository identity solely from event data.

---

# PR binding

The PR number must resolve to the configured repository.

Fetched PR data must prove:

```text
PR exists
repository matches
PR number matches
```

Cross-repository/fork cases must not silently weaken repository identity checks.

If fork PR support is intentionally implemented, source and target identities must be explicit and tested.

Otherwise fail closed.

---

# Exact HEAD binding

The authoritative PR HEAD must become:

```text
facts.head_sha
```

The implementation cycle SHA must independently become:

```text
facts.implementation_sha
```

PDFTR-49 must continue enforcing:

```text
head_sha == implementation_sha
```

PDFTR-50 must not rewrite cycle state to make these match.

Mismatch:

```text
=> NOT_ELIGIBLE
```

---

# Exact BASE binding

The authoritative PR base commit SHA must become:

```text
facts.base_sha
```

A base-only movement must therefore naturally invoke the PDFTR-49 behavior:

```text
old generation → STALE
new (head, base) pair → new generation
```

No special bypass is allowed.

---

# CI normalization

GitHub CI/check observations must be normalized into:

```text
SUCCESS
PENDING
FAILURE
UNKNOWN
```

Only configured required checks count toward authorization.

Suggested mappings:

```text
queued / waiting / in_progress
→ PENDING

success
→ SUCCESS

failure / cancelled / timed_out / action_required
→ FAILURE

missing / conflicting / unverifiable
→ UNKNOWN
```

The adapter must not infer success from absence.

---

# Exact CI SHA

All required CI evidence must belong to:

```text
facts.head_sha
```

A successful workflow/check for an older SHA must never authorize the current HEAD.

Conflicting evidence for the same required check must fail closed unless the adapter can deterministically identify the authoritative latest run.

---

# Required-check configuration

Required checks must come from trusted configuration.

Do not accept the required-check list from:

- webhook payload;
- implementer output;
- reviewer output;
- PR comment;
- agent-created temporary file.

Missing trusted configuration must fail closed.

---

# Cycle integration

PDFTR-50 must read the existing harness cycle state.

It must not trust:

```text
READY FOR HUMAN REVIEW
```

console prose.

Required authoritative cycle facts include at minimum:

```text
cycle state
implementation SHA
ticket identity
repository/branch binding where applicable
```

Only:

```text
cycle_state == PASSED
```

may satisfy the PDFTR-49 readiness contract.

---

# Request persistence before dispatch

Mandatory ordering:

```text
1. receive signal
2. acquire trusted ownership
3. refresh GitHub facts
4. evaluate PDFTR-49 policy
5. persist REQUESTED generation
6. release/commit durable state as required
7. dispatch external independent reviewer
8. persist dispatch status
```

External dispatch must never occur before step 5 succeeds.

---

# Dispatch contract

Define a transport-neutral immutable dispatch request.

Recommended schema:

```json
{
  "schema_version": "1.0",
  "repository": "bodomus/PDFTranslator",
  "ticket": "PDFTR-50",
  "pull_request": 123,
  "generation": 1,
  "head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "base_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "review_profile": "strict-independent-review"
}
```

The dispatcher must receive exact SHAs, never:

```text
review branch X
review latest PR state
```

---

# Independent review instructions

The generated reviewer request must explicitly require:

```text
Review repository <repo>
PR <number>
generation <N>

Review exact HEAD SHA <head_sha>
against exact BASE SHA <base_sha>.

Do not substitute current branch HEAD.
Do not review a newer SHA.
Do not mutate repository state.
Do not merge.

Return structured PASS or CHANGES_REQUIRED
bound to generation and reviewed_sha.
```

The result schema remains owned by PDFTR-49.

---

# ChatGPT Work adapter

If ChatGPT Work is the selected dispatcher, isolate it behind an interface such as:

```python
class IndependentReviewDispatcher:
    def dispatch(request: DispatchRequest) -> DispatchReceipt:
        ...
```

The PDFTR-49 policy/store must not import ChatGPT/OpenAI-specific APIs.

This keeps future replacement possible:

```text
ChatGPT Work
Codex review service
local review worker
other trusted reviewer
```

without changing review authorization.

---

# Dispatch receipt

A definite successful dispatch should produce stable receipt metadata.

Example:

```json
{
  "generation": 1,
  "status": "RUNNING",
  "provider": "chatgpt-work",
  "external_request_id": "...",
  "requested_head_sha": "...",
  "requested_base_sha": "..."
}
```

Do not store secrets or credentials.

---

# Dispatch failures

Classify dispatch outcomes as either:

```text
DEFINITE_NOT_DISPATCHED
DISPATCH_UNCERTAIN
DISPATCHED
```

Examples:

## Definite failure before request transmission

May remain REQUESTED but must require explicit safe handling according to a deterministic retry policy.

PDFTR-50 should prefer fail-closed over inventing automatic delivery.

## Timeout/connection loss after request transmission

```text
=> DISPATCH_UNCERTAIN
```

Never automatically dispatch another reviewer.

Human reconciliation remains required unless a trusted provider query can prove the original request did not exist.

---

# Crash safety

## Crash before REQUESTED persistence

No dispatch may have occurred.

A later event may evaluate normally.

## Crash after REQUESTED persistence, before dispatch

Do not automatically manufacture generation 2.

Existing generation remains authoritative.

The integration may require human reconciliation or a future explicit safe dispatch-recovery mechanism.

## Crash after dispatch with unknown receipt

Mark/recover as:

```text
DISPATCH_UNCERTAIN
```

Never automatically issue another independent review.

---

# Concurrency

Two simultaneous GitHub events for the same ticket/PR must not produce two requests.

Reuse existing OS-held ticket ownership / serialization where compatible.

Required property:

```text
event A ─┐
         ├─ exactly one REQUESTED generation
event B ─┘
```

Do not introduce an independent weaker lock implementation.

---

# Webhook/event receiver security

If a real webhook receiver is implemented in this ticket:

- validate GitHub webhook signatures;
- reject missing/invalid signatures;
- use constant-time signature comparison;
- enforce payload size limits;
- accept only expected content type;
- reject unsupported repositories;
- never log webhook secrets;
- preserve delivery ID only for diagnostics/idempotency;
- expose no arbitrary command execution;
- expose no generic filesystem paths;
- expose no arbitrary repository selector.

However, if ChatGPT Work provides the event trigger directly, a custom public HTTP receiver is not required.

Prefer the smallest integration compatible with actual Work trigger capabilities.

---

# Secrets

Credentials must:

- never be written to `.agent-cycle`;
- never appear in agent prompts;
- never be included in review artifacts;
- never be committed;
- never be echoed in diagnostics.

Use environment/connector/provider-managed authentication.

---

# YouTrack

YouTrack remains non-authoritative for this flow.

If `PDFTR-50` does not exist remotely:

```text
Issue not found
```

must not block GitHub independent-review automation.

Do not automatically create the issue merely because an event arrived.

Remote issue creation remains governed by the existing explicit operator-action boundary.

---

# Reviewer permissions

The independent reviewer remains read-only.

It must not receive:

```text
push
merge
GitHub mutation
YouTrack mutation
harness mutation
```

capabilities merely because dispatch is automated.

---

# Local/manual trigger

Provide a trusted manual reevaluation path useful for testing and fallback.

Suggested command:

```text
uv run python scripts/github_independent_review.py evaluate PDFTR-50
```

or equivalent.

This command may perform authoritative GitHub reads.

It must not bypass PDFTR-49.

A separate explicit dispatch command is acceptable if useful:

```text
uv run python scripts/github_independent_review.py dispatch PDFTR-50
```

but dispatch must still use persisted PDFTR-49 REQUESTED state and all normal safety checks.

Avoid generic:

```text
--force
```

---

# Observability

Record concise operational diagnostics without chain-of-thought.

Useful fields:

```text
event type
event delivery id
PR
observed head SHA
observed base SHA
cycle SHA
CI normalized state
policy decision
generation
dispatch state
external receipt id
timestamp
```

Do not treat logs as authorization state.

---

# Tests

Add focused tests for at least the following.

## Event does not authorize

Construct an event payload claiming:

```text
ready
CI success
HEAD A
```

while authoritative refresh says CI pending.

Result:

```text
NOT_ELIGIBLE
```

---

## Spoofed event SHA

Event says:

```text
HEAD A
```

authoritative PR says:

```text
HEAD B
```

Only B may enter normalized facts.

---

## Duplicate events

Multiple event types/deliveries for the same `(head, base)`:

```text
=> exactly one generation
=> exactly one dispatch attempt
```

---

## Concurrent events

Two concurrent handlers cannot create duplicate request/dispatch.

---

## Old CI success

PR HEAD:

```text
B
```

CI success:

```text
A
```

must not authorize review.

---

## Missing required check

Must normalize to UNKNOWN and remain not eligible.

---

## Failed check

Must remain not eligible.

---

## PR draft

Must remain not eligible.

---

## PR closed

Must remain not eligible.

---

## Cycle not PASSED

Must remain not eligible.

---

## Cycle SHA mismatch

Must remain not eligible.

---

## Base-only movement

Start:

```text
HEAD H
BASE B1
review generation 1
```

Authoritative GitHub refresh changes only:

```text
BASE B2
```

Expected:

```text
generation 1 STALE
generation 2 eligible/requested once normal readiness holds
dispatch pinned to H/B2
```

---

## Event race during refresh

PR changes from SHA A to SHA B while facts are being fetched.

Adapter must either:

- obtain a coherent authoritative snapshot, or
- reject/retry the read without creating a request.

Never synthesize mixed facts such as:

```text
HEAD B
CI from A
base from unrelated observation
```

---

## Persist failure

Failure writing REQUESTED:

```text
=> no dispatch call
```

---

## Dispatch definite failure

Verify state follows the defined fail-closed semantics and does not create another generation.

---

## Dispatch timeout after send

```text
=> DISPATCH_UNCERTAIN
```

Repeated events:

```text
=> no redispatch
```

---

## Restart after REQUESTED

Restart and event redelivery:

```text
=> same generation
=> no duplicate external request
```

---

## Restart after RUNNING

No redispatch.

---

## Invalid/corrupt independent-review state

Fail closed.

No GitHub dispatch.

---

## Repository mismatch

Fail closed.

---

## PR mismatch

Fail closed.

---

## Event type independence

Different supported events that refresh to identical authoritative facts produce identical policy behavior.

---

## Secrets

Ensure diagnostics, state and generated reviewer request contain no credentials.

---

# Integration tests

Add deterministic adapter tests using mocked GitHub responses.

Do not require live GitHub credentials for the normal test suite.

If an opt-in live smoke test is added:

```text
read-only only
no mutations
explicit operator opt-in
```

---

# Acceptance criteria

PDFTR-50 is complete when:

1. GitHub events function only as wake-up signals.
2. Authoritative GitHub state is refreshed before policy evaluation.
3. PDFTR-49 remains the sole eligibility policy.
4. PR head SHA is fetched and exact-bound.
5. PR base SHA is fetched and exact-bound.
6. Required CI is verified for the exact head SHA.
7. Event payload claims cannot authorize review.
8. Request intent is durably persisted before dispatch.
9. Duplicate events cannot create duplicate generations.
10. Duplicate events cannot create duplicate dispatch.
11. Concurrent handlers cannot create duplicate dispatch.
12. Dispatch request contains exact head/base SHA.
13. Reviewer is never instructed to review a moving branch.
14. Base-only movement creates a new review context.
15. Crash/restart cannot silently redispatch.
16. Uncertain dispatch cannot automatically retry.
17. Existing PDFTR-49 stale/PASS semantics remain unchanged.
18. Reviewer remains read-only.
19. YouTrack remains outside authorization.
20. Missing YouTrack issue does not block the flow.
21. No automatic merge is introduced.
22. Secrets are absent from persisted artifacts and prompts.
23. Focused tests pass.
24. Full `scripts/check.ps1` passes.
25. Windows and Ubuntu CI pass for the exact implementation SHA.

---

# Reviewer focus

Treat these as P1/HIGH or higher when they can authorize or duplicate an independent review incorrectly:

1. trusting webhook payload HEAD/base/CI without authoritative refresh;
2. dispatch before REQUESTED persistence;
3. duplicate dispatch from repeated events;
4. duplicate dispatch after restart;
5. redispatch after `DISPATCH_UNCERTAIN`;
6. review request using branch name instead of exact SHA;
7. head/base observations from different inconsistent snapshots;
8. CI success from another SHA;
9. bypassing PDFTR-49 policy;
10. reviewer gaining mutation capability;
11. agent-writable files controlling dispatch;
12. credentials leaking into prompts/state/logs.

---

# Implementation guidance

Prefer small modules with explicit boundaries, for example:

```text
scripts/independent_review_policy.py
    existing PDFTR-49 pure policy

scripts/independent_review.py
    existing PDFTR-49 state/store

scripts/github_review_facts.py
    authoritative GitHub read/normalization

scripts/independent_review_dispatch.py
    transport-neutral dispatch interface

scripts/github_independent_review.py
    orchestration / event handling
```

Exact names are not mandatory.

Do not place GitHub API calls inside the pure policy.

Do not place ChatGPT Work-specific logic inside the PDFTR-49 store.

---

# Follow-up

## PDFTR-51 — Independent review result publication and closed-loop continuation

After PDFTR-50:

```text
trusted reviewer result
    ↓
validate generation/head/base
    ↓
PASS / CHANGES_REQUIRED
    ↓
publish GitHub review/check
```

Potential later extension:

```text
CHANGES_REQUIRED
    ↓
human policy / trusted continuation gate
    ↓
Pi implementer fix cycle
    ↓
new CI
    ↓
new independent review
```

Automatic merge remains explicitly out of scope until separately designed and approved.
