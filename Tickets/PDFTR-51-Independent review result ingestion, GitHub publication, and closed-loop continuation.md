# PDFTR-51 — Independent review result ingestion, GitHub publication, and closed-loop continuation

## Status

Planned

## Summary

Implement the trusted result-ingestion and GitHub publication layer for the independent-review pipeline introduced by PDFTR-49 and PDFTR-50.

The flow should become:

```text
GitHub event
    ↓
authoritative refresh
    ↓
PDFTR-49 eligibility
    ↓
PDFTR-50 exact head/base dispatch
    ↓
independent reviewer
    ↓
trusted result ingestion
    ↓
validate generation/head/base/current PR state
    ↓
PASS or CHANGES_REQUIRED
    ↓
publish deterministic GitHub review/check/comment
    ↓
optional controlled continuation
```

This ticket should close the loop enough that the operator no longer has to manually copy independent-review verdicts between ChatGPT and GitHub.

Automatic merge remains out of scope.

---

# Motivation

After PDFTR-50, the system can automatically dispatch an exact immutable review context:

```text
repository
PR
generation
head_sha
base_sha
```

The remaining manual gap is on the return path.

Today an independent reviewer can produce:

```text
PASS
```

or:

```text
CHANGES_REQUIRED
```

but there is no trusted production path that:

1. ingests that result;
2. verifies that it belongs to the dispatched generation;
3. verifies that the PR review context has not changed;
4. stores the result through PDFTR-49;
5. publishes the verdict to GitHub;
6. optionally signals the implementation loop when changes are required.

PDFTR-51 implements that return path.

---

# Goals

Implement a trusted closed-loop result path that:

1. accepts independent-review results only through a trusted transport boundary;
2. validates the PDFTR-49 result schema;
3. binds result to:
   - repository;
   - pull request;
   - generation;
   - reviewed head SHA;
   - requested base SHA through persisted generation state;
4. refreshes authoritative GitHub state before treating a result as current;
5. stores late results as STALE rather than discarding them;
6. publishes current PASS/CHANGES_REQUIRED deterministically to GitHub;
7. never publishes stale PASS as current approval;
8. makes GitHub publication idempotent;
9. prevents duplicate comments/checks/reviews after retries or restart;
10. records publication uncertainty;
11. optionally produces a trusted continuation intent for CHANGES_REQUIRED;
12. never directly lets reviewer output mutate repository state;
13. keeps merge human-owned.

---

# Non-goals

PDFTR-51 does not:

- automatically merge PRs;
- grant merge authority to ChatGPT Work;
- let reviewer agents push commits;
- let reviewer agents mutate YouTrack;
- trust PR comments as review results;
- trust agent-written local JSON as authenticated reviewer output;
- automatically create YouTrack issues;
- bypass PDFTR-49 result validation;
- bypass PDFTR-50 exact-generation dispatch binding;
- reset corrupt review history;
- retry uncertain GitHub mutations blindly;
- automatically accept stale review results as current.

---

# Core trust model

The reviewer is read-only.

The trusted parent/harness performs all authoritative mutations.

```text
reviewer
    ↓ structured evidence only

trusted parent
    ├─ validates
    ├─ refreshes GitHub
    ├─ persists result
    ├─ publishes GitHub status
    └─ optionally creates continuation intent
```

Reviewer-produced text must never directly become a GitHub mutation request.

---

# Result transport

Define a trusted transport-neutral ingestion boundary.

For example:

```python
class IndependentReviewResultReceiver:
    def receive(...) -> IndependentReviewResult:
        ...
```

or equivalent.

The production transport may later be implemented through ChatGPT Work / connector callback / polling.

Do not place provider-specific transport logic inside PDFTR-49 policy.

---

# Result contract

Reuse the PDFTR-49 result schema.

Example PASS:

```json
{
  "schema_version": "1.0",
  "repository": "bodomus/PDFTranslator",
  "ticket": "PDFTR-51",
  "pull_request": 123,
  "generation": 2,
  "reviewed_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "verdict": "PASS",
  "findings": []
}
```

Example CHANGES_REQUIRED:

```json
{
  "schema_version": "1.0",
  "repository": "bodomus/PDFTranslator",
  "ticket": "PDFTR-51",
  "pull_request": 123,
  "generation": 2,
  "reviewed_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
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

Do not invent a second incompatible review schema.

---

# Base SHA binding

The result schema itself does not need to add a separate base SHA if the existing generation identity already persistently binds:

```text
generation
→ requested_head_sha
→ requested_base_sha
```

On ingestion:

```text
result.generation
result.reviewed_sha
```

must resolve to exactly one persisted generation.

The trusted parent must then verify the generation's persisted:

```text
requested_base_sha
```

against refreshed authoritative PR base SHA before considering the result current.

A result cannot substitute a different base SHA.

---

# Result ingestion ordering

Preferred sequence:

```text
1. receive trusted result
2. acquire existing ticket ownership
3. load and validate independent-review state
4. locate exact generation
5. validate result schema and binding
6. refresh authoritative GitHub PR/head/base state
7. call PDFTR-49 record_result(...)
8. durably persist result
9. derive publication intent
10. persist publication intent
11. perform GitHub publication
12. persist publication outcome
13. optionally emit continuation intent
```

Do not perform GitHub mutation before the accepted result is durably stored.

---

# Stale result handling

Example:

```text
generation 1
HEAD H1
BASE B1
```

Reviewer returns PASS, but current PR is now:

```text
HEAD H2
BASE B1
```

or:

```text
HEAD H1
BASE B2
```

Required behavior:

```text
result stored
generation 1 → STALE
PASS does not authorize current PR
no current-PASS GitHub status
```

Historical evidence may be published only if clearly labeled historical/stale.

Preferred initial behavior: do not publish stale results as current PR approval.

---

# Current PASS

PASS may be treated as current only if PDFTR-49 `pass_is_valid()` succeeds against freshly fetched authoritative facts.

That means at minimum:

```text
reviewed head == current head
requested base == current base
PR open
PR not draft
cycle PASSED
implementation SHA == head SHA
required CI still successful for exact head
```

Do not duplicate this logic in PDFTR-51.

Use PDFTR-49.

---

# CHANGES_REQUIRED

A current CHANGES_REQUIRED result must remain bound to its exact generation.

Publishing it must not automatically modify code.

It may produce a continuation intent, but that intent must be separate from the reviewer result.

---

# GitHub publication

Publish independent-review outcome to GitHub using a deterministic machine-readable mechanism.

Preferred model:

```text
GitHub Check Run / Check
```

with optional PR comment for human-readable findings.

If GitHub Check mutation is unavailable through the chosen integration, use a deterministic PR review/comment plus persisted publication record.

Do not rely only on labels.

---

# Publication identity

Every publication must have a stable local identity:

```text
(repository, PR, generation, verdict)
```

or stronger:

```text
(repository, PR, generation, reviewed_sha, publication_kind)
```

Persist the external GitHub publication identifier.

Example:

```json
{
  "generation": 2,
  "reviewed_sha": "...",
  "verdict": "PASS",
  "publication_state": "PUBLISHED",
  "github_check_id": 123456
}
```

---

# Idempotency

Repeated result delivery must not create duplicate GitHub publication.

Example:

```text
same PASS received 3 times
```

must produce:

```text
one persisted result
one GitHub publication
```

Existing PDFTR-49 identical-result ingestion semantics should remain idempotent.

Publication must be independently idempotent as well.

---

# Publication states

Recommended:

```text
NOT_REQUESTED
PENDING
PUBLISHED
PUBLICATION_UNCERTAIN
FAILED_DEFINITE
STALE
```

Do not overload PDFTR-49 review state with these publication states.

Publication is a separate side-effect lifecycle.

---

# Persist-before-publish

Mandatory:

```text
accepted result
    ↓
persist publication intent
    ↓
GitHub mutation
```

Never:

```text
GitHub mutation
    ↓
persist intent
```

Otherwise restart can duplicate publication.

---

# GitHub mutation uncertainty

Treat GitHub writes using the same discipline established in PDFTR-47.

After a mutation may have been dispatched:

```text
timeout
connection reset
HTTP 408
HTTP 5xx
```

must be treated as:

```text
PUBLICATION_UNCERTAIN
```

Do not automatically repeat the mutation.

Reconcile using authoritative GitHub reads.

---

# Definite rejection

Examples:

```text
400
401
403
```

before any plausible successful mutation should be classified as definite rejection according to existing mutation semantics.

Do not overwrite the original uncertainty classification with secondary diagnostic failures.

---

# Publication reconciliation

Provide a deterministic reconciliation path.

For an uncertain publication:

```text
read GitHub
↓
search exact publication identity
```

Outcomes:

```text
exact publication exists
→ mark PUBLISHED

definitively absent
→ safe retry may require explicit operator action

ambiguous/read failure
→ remain PUBLICATION_UNCERTAIN
```

No duplicate publication.

---

# PASS publication

Preferred GitHub visible result:

```text
Independent Review — PASS
```

Include:

```text
reviewed SHA
base SHA
generation
required CI state
```

Do not include secrets or internal exception text.

PASS publication must never imply automatic merge.

Suggested text:

```text
Independent review PASS
Generation: 2
Head: <sha>
Base: <sha>

Merge remains human-owned.
```

---

# CHANGES_REQUIRED publication

Publish concise findings.

Each finding should include:

```text
severity
file
symbol
problem
required fix
regression test
```

Do not publish chain-of-thought.

Do not publish raw internal reviewer logs.

---

# Findings size limits

GitHub comments/check output have practical limits.

Implement deterministic bounded publication.

If findings exceed allowed size:

```text
summary publication
+
reference to persisted local artifact / trusted external artifact
```

Do not silently truncate a finding in a way that changes meaning.

Prefer:

```text
first N findings + "additional findings omitted from GitHub rendering"
```

with the full structured result preserved locally.

---

# Result source authentication

The system must distinguish:

```text
trusted review transport
```

from:

```text
agent-edited JSON file
PR comment
stdin from untrusted hook
repository artifact
```

Do not expose a CLI like:

```text
record-result arbitrary.json
```

that an implementer can invoke to mark itself PASS.

If a manual operator ingestion command exists, it must be clearly trusted/operator-only and isolated from agent permissions.

---

# Reviewer identity

Do not attempt to solve full cryptographic reviewer identity unless required by the chosen transport.

At minimum:

- result transport is trusted-parent controlled;
- transport credentials are outside repository;
- result must match previously dispatched external request/generation;
- optional provider request ID may be cross-checked.

If a provider receipt ID exists from PDFTR-50, prefer binding returned result to that dispatch identity.

---

# Dispatch/result correlation

Where possible:

```text
PDFTR-50 external_request_id
```

should be correlated to the returning result.

Example:

```json
{
  "external_request_id": "opaque-123",
  "result": { ...PDFTR-49 result... }
}
```

Mismatch must fail closed.

Do not make this optional if the actual selected transport can reliably provide it.

---

# GitHub authoritative refresh before publication

Immediately before publication:

```text
fetch PR
fetch head
fetch base
fetch required CI
```

and evaluate current result validity.

A previously current PASS can become stale between result ingestion and publication.

If so:

```text
do not publish current PASS
```

Persist stale state instead.

---

# Race during GitHub publication

Example:

```text
refresh says H1/B1
result PASS H1/B1
publication intent persisted

PR changes to H2 before publication
```

The GitHub publication must itself be bound to H1.

After publication, refresh again or verify target SHA if GitHub API supports exact SHA binding.

A status/check on H1 is acceptable historical evidence.

It must not authorize H2.

---

# Closed-loop continuation

For current `CHANGES_REQUIRED`, create a separate trusted continuation intent.

Recommended persisted object:

```json
{
  "schema_version": "1.0",
  "ticket": "PDFTR-51",
  "source": "independent_review",
  "generation": 2,
  "reviewed_sha": "...",
  "verdict": "CHANGES_REQUIRED",
  "status": "PENDING_HUMAN_OR_POLICY"
}
```

Do not directly launch implementer in the same function that ingests reviewer output.

This separation keeps:

```text
review evidence
```

distinct from:

```text
workflow continuation authority
```

---

# Initial continuation policy

For PDFTR-51, prefer:

```text
CHANGES_REQUIRED
→ publish GitHub result
→ persist continuation intent
```

Then allow a trusted operator/harness command to resume implementation.

Suggested:

```powershell
uv run python scripts/independent_review_result.py continue PDFTR-51
```

or equivalent.

Do not yet automatically launch Codex on every CHANGES_REQUIRED unless the existing harness has a safe exact-SHA continuation boundary that can be reused without weakening review/retry budgets.

If existing runner architecture supports a deterministic safe transition cleanly, implementation may automate continuation, but reviewer result must not directly invoke an agent.

---

# Future full automation target

After this ticket the architecture should be capable of:

```text
implementer
    ↓
Pi reviewer
    ↓
CI
    ↓
GitHub event
    ↓
independent reviewer
    ↓
CHANGES_REQUIRED
    ↓
trusted continuation intent
    ↓
implementer fix
    ↓
CI
    ↓
new independent review
```

with human intervention needed mainly for:

```text
uncertainty
safety stop
retry exhaustion
merge
```

---

# PASS continuation

PASS should not launch any implementation action.

It should produce:

```text
GitHub publication = PASS
independent PASS valid for exact context
ready_for_human_merge = true
```

This is advisory/readiness state only.

Do not call GitHub merge API.

---

# GitHub merge protection compatibility

Where practical, design publication so a future branch protection rule can require:

```text
Independent Review
```

check success.

Do not enable/change branch protection in PDFTR-51.

---

# YouTrack

YouTrack remains optional/non-authoritative.

After publication:

```text
PASS
→ optional Ready to Merge / review status update

CHANGES_REQUIRED
→ optional In Progress update
```

But:

```text
Issue not found
credentials unavailable
mutation uncertain
```

must not invalidate already accepted independent-review evidence or GitHub publication.

Use existing project-tracking mutation safety if YouTrack updates are included.

It is acceptable to omit YouTrack mutation entirely from PDFTR-51.

---

# CLI / trusted service interface

Suggested:

```text
scripts/independent_review_result.py
```

Possible trusted commands:

```powershell
status
reconcile-publication
continue
```

Avoid a generic untrusted result-file ingestion CLI.

If testing requires file-based result ingestion, keep it explicitly diagnostic/test-only or behind trusted-parent code.

---

# Recommended module boundaries

```text
scripts/independent_review_policy.py
    existing pure PDFTR-49 policy

scripts/independent_review.py
    existing store/history

scripts/github_independent_review.py
    existing PDFTR-50 dispatch

scripts/independent_review_result.py
    trusted result orchestration

scripts/github_review_publication.py
    GitHub mutation/reconciliation adapter

scripts/independent_review_continuation.py
    optional continuation intent/policy
```

Do not turn one module into a giant orchestration file.

---

# Security invariants

Must remain true:

1. reviewer cannot push;
2. reviewer cannot merge;
3. reviewer cannot publish its own GitHub approval directly;
4. agent cannot forge PASS by editing repository files;
5. stale PASS cannot authorize current PR;
6. GitHub publication is not authority for local result state;
7. local result state is not merge authority;
8. uncertain mutation cannot be blindly retried;
9. secrets never enter prompts/state/comments;
10. human merge remains final authority.

---

# Tests

Add focused tests covering at least:

## Current PASS happy path

```text
generation exact-match
current head/base unchanged
CI success
PASS received
```

Expected:

```text
result persisted
PASS valid
publication intent persisted
one GitHub PASS publication
ready_for_human_merge = true
```

---

## Current CHANGES_REQUIRED happy path

Expected:

```text
result persisted
one GitHub CHANGES_REQUIRED publication
continuation intent persisted
no direct code mutation
no merge
```

---

## Duplicate PASS delivery

Same result repeatedly:

```text
one result
one publication
```

---

## Duplicate CHANGES_REQUIRED delivery

No duplicate comments/checks.

---

## Late PASS after head move

Result stored STALE.

No current PASS publication.

---

## Late PASS after base move

Same behavior.

---

## Late CHANGES_REQUIRED

Historical result retained.

Must not trigger continuation for current SHA.

---

## Result generation mismatch

Reject.

---

## reviewed_sha mismatch

Reject.

---

## repository/PR/ticket mismatch

Reject.

---

## dispatch receipt mismatch

If correlation is implemented:

```text
external_request_id mismatch
→ reject
```

---

## Result persist failure

No GitHub mutation.

---

## Publication intent persist failure

No GitHub mutation.

---

## GitHub publication success

Persist external publication identity.

---

## GitHub publication timeout

```text
PUBLICATION_UNCERTAIN
```

No automatic duplicate publication.

---

## Publication restart

Existing PENDING/PUBLISHED/UNCERTAIN state must not create duplicate publication.

---

## Publication reconciliation finds exact existing publication

Mark PUBLISHED without another mutation.

---

## Reconciliation ambiguous

Remain uncertain.

---

## GitHub state changes between ingestion and publication

Do not publish a current PASS for obsolete context.

---

## Current PASS then later PR changes

`ready_for_human_merge` becomes false.

Old publication remains historical.

---

## CHANGES_REQUIRED continuation intent

Generated only for current result.

---

## Duplicate continuation event

One continuation intent only.

---

## Reviewer attempts mutation-like fields

Unknown fields reject under strict schema.

---

## Agent-writable result file

Must not become trusted production evidence merely by existing in repository.

---

## Missing YouTrack issue

Does not block ingestion/publication.

---

## Secrets

Ensure:

```text
tokens
Authorization headers
connector secrets
exception strings
```

do not appear in persisted state or GitHub output.

---

# Acceptance criteria

PDFTR-51 is complete when:

1. trusted result ingestion exists;
2. result schema reuses PDFTR-49;
3. generation/head/base binding is enforced;
4. stale results are retained but cannot authorize current PR;
5. PASS validity is delegated to PDFTR-49;
6. accepted result persists before GitHub mutation;
7. publication intent persists before GitHub mutation;
8. publication is idempotent;
9. duplicate result delivery cannot duplicate publication;
10. publication uncertainty cannot blindly retry;
11. reconciliation can detect an already-existing publication;
12. current PASS produces GitHub-visible independent-review success;
13. current CHANGES_REQUIRED publishes findings;
14. stale PASS never publishes as current approval;
15. stale CHANGES_REQUIRED never launches continuation;
16. current CHANGES_REQUIRED produces a separate continuation intent;
17. reviewer itself gains no mutation authority;
18. no automatic merge exists;
19. YouTrack remains non-authoritative;
20. missing YouTrack issue does not block completion;
21. secrets are not persisted or published;
22. focused tests pass;
23. full `scripts/check.ps1` passes;
24. Windows and Ubuntu CI pass for the exact implementation SHA.

---

# Reviewer focus

Treat the following as P1/HIGH or higher if exploitable:

1. agent-forgeable PASS ingestion;
2. stale PASS published as current;
3. GitHub mutation before persisted result/publication intent;
4. duplicate publication after timeout/restart;
5. publication retry while outcome is uncertain;
6. generation/result mismatch accepted;
7. head/base binding lost on result return;
8. CHANGES_REQUIRED for stale SHA launching implementer;
9. reviewer receiving mutation capabilities;
10. PASS causing automatic merge;
11. GitHub comment/check being treated as authoritative review evidence;
12. credentials or internal exceptions leaking into GitHub output.

---

# Preferred delivery sequence

Implement PDFTR-51 in two internal layers:

```text
A. trusted result ingestion + persistence
B. GitHub publication + continuation intent
```

Keep both in this ticket if the implementation stays bounded.

If publication mutation safety becomes significantly larger than expected, stop after layer A and split publication into PDFTR-51A rather than weakening the mutation boundary.

---

# Follow-up

After PDFTR-51 passes:

## PDFTR-52 — Safe automatic fix continuation

Potentially allow:

```text
current CHANGES_REQUIRED
→ trusted continuation policy
→ Pi implementer
→ new SHA
→ CI
→ independent review
```

with strict budgets and safety stops.

## Later

Only after several stable closed-loop cycles should automatic merge even be considered.

Human merge remains the correct boundary for now.
