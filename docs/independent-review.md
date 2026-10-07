# Independent exact-SHA review contract (PDFTR-49)

This is a separate independent-review layer, not a change to the Pi cycle or its review budget.
It implements no receiver, GitHub API adapter, Work dispatch, publication, automatic retry or merge.
YouTrack is not an authorization input. Merge and contradictory-state recovery remain human-owned.

## Trust boundary

Every future signal (`opened`, `ready_for_review`, `synchronize`, check/status completion or manual
reevaluation) must do the same thing: refresh authoritative GitHub PR/check and harness cycle facts,
normalize them, then call the policy. Event names and payloads are **not** authorization facts.
A trusted adapter must verify repository/PR identity and exact commit ownership of every check,
reject conflicting check observations, and normalize queued/in-progress to PENDING;
failed/cancelled/timed-out to FAILURE; missing/unverifiable to UNKNOWN. Only SUCCESS qualifies.
A stable trusted required-check configuration is independent of the event/facts source. Empty or
duplicate required-check sets reject. Extra unrelated checks do not substitute for required checks.
Local check.ps1 results, old human-review.json readiness, and YouTrack status are not CI evidence.

The policy has no network, subprocess or filesystem operations. Configuration, facts, history and
results use exact versioned JSON keys, lowercase full 40-character SHA strings and strict types.
Unknown/missing fields and duplicate JSON keys reject. Existing automated review findings retain
CRITICAL/HIGH/MEDIUM/LOW severity meanings; PASS requires no findings, CHANGES_REQUIRED requires
findings. Independent results intentionally support only these two verdicts; operational uncertainty
is represented separately rather than fabricated reviewer evidence.

**Agent-editable files are diagnostic only.** The read-only CLI never writes state, ingests results,
or grants dispatch/merge permission. `IndependentReviewStore` is a trusted-parent library API, not
an agent tool. Future deployments must keep its write-capable code and state outside agent-writable
mounts/permissions and accept results only from the trusted independent reviewer transport. A shared
writable checkout is not a security boundary; JSON and OS locking do not authenticate a reviewer or
protect against a malicious filesystem owner. This ticket does not wire that deployment or identity
service. Do not promote agent-provided JSON, local inspection output or an edited PASS to approval.

## Configuration and normalized facts

Trusted configuration (save diagnostic examples under `temp/`, not runtime coordination):

```json
{
  "schema_version": "1.0",
  "repository": "bodomus/PDFTranslator",
  "ticket": "PDFTR-49",
  "pull_request": 123,
  "required_checks": ["windows", "ubuntu"]
}
```

Facts (`head_sha`, `implementation_sha`, `ci_sha` must agree):

```json
{
  "schema_version": "1.0",
  "repository": "bodomus/PDFTranslator",
  "ticket": "PDFTR-49",
  "pull_request": 123,
  "pr_exists": true,
  "pr_state": "OPEN",
  "pr_draft": false,
  "head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "base_sha": "cccccccccccccccccccccccccccccccccccccccc",
  "cycle_state": "PASSED",
  "implementation_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "ci_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "checks": {"windows": "SUCCESS", "ubuntu": "SUCCESS"}
}
```

Base SHA is validated context, not an additional review identity. PR must exist, be open and not
 draft. Required checks must all succeed for candidate SHA. Unknown PR state fails closed.

## Pure API

`scripts/independent_review_policy.py` exposes:

- `evaluate_independent_review(facts, state, config)`: decision/reason/generation, no mutation.
- `request_review(...)`: copied refreshed history plus a decision. ELIGIBLE appends REQUESTED.
- `refresh_state(...)`: marks old SHA records STALE, retaining evidence.
- `mark_dispatch(state, config, generation, status)`: RUNNING or DISPATCH_UNCERTAIN.
- `record_result(facts, state, config, result)`: accepts exact bound results, once.
- `pass_is_valid(...)`: current exact PASS **and** all readiness facts still hold; not a merge grant.

Decisions: ELIGIBLE, NOT_ELIGIBLE, ALREADY_REQUESTED, ALREADY_REVIEWED, STALE, INVALID.
Stable readiness reasons include pr_missing, pr_closed, pr_draft, cycle_not_passed, sha_mismatch,
ci_sha_mismatch, ci_pending, ci_failed, ci_unknown. Schema/binding contradictions produce INVALID;
mutation APIs raise IndependentReviewError without changing their inputs.

History contains the configuration plus `current_generation` and `reviews`. Each record has exactly
`generation`, `requested_sha`, `status`, `result`. Generations are contiguous positive integers;
SHA identity is unique for the repository/PR. No generation is allocated until ready. Repeated
requests for the same SHA do not append; every previously superseded record is STALE. Returning
to a previously stale SHA does not revive approval or allocate another request: human reconciliation
is required. Observing HEAD movement revokes earlier status even while the new SHA is not eligible.
The immutable request identity and original result/findings remain; STALE is a derived historical
status, not an alteration of the review verdict. Duplicate identical result delivery is idempotent;
a different replacement result rejects. PASS cannot survive changed HEAD, draft/closed PR, cycle
mismatch or failing/incomplete CI. Late results may be recorded despite non-ready current CI, but
never authorize that current HEAD.

Result shape:

```json
{
  "schema_version": "1.0",
  "repository": "bodomus/PDFTranslator",
  "ticket": "PDFTR-49",
  "pull_request": 123,
  "generation": 1,
  "reviewed_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "verdict": "PASS",
  "findings": []
}
```

Each finding has exactly id, severity, file, symbol, problem, required_fix, regression_test.
IDs are unique, id/problem/required_fix nonempty, remaining location/test fields strings.

## Persistence and future dispatch

`IndependentReviewStore(repository_root, directory, config)` stores `independent-review.json`.
Preferred directory: `.agent-cycle/<ticket>/`, independently of manifest/handoff.
No current runner integration changes its authoritative files.

A trusted operator explicitly initializes a new store once; existing/corrupt state never resets.
Missing state on request/result ingestion rejects. Do not initialize after lost history without
human investigation. Configuration is bound in history; changing it requires human reconciliation.
The API uses the existing cross-platform OS ticket lock (nonblocking competing ownership rejects).
It owns that lock itself; do not call it inside an already-held ticket lock. A future dispatcher must
arrange one trusted ownership scope rather than nested lock acquisition.

`store.request(refresh_facts)` loads validated history and refreshes facts **under ownership**,
computes intent, flushes/fsyncs a repository-local `temp/independent-review/` file and atomically
replaces state, then returns the decision. Store and temp must be on the same filesystem; failed
replacement propagates and returns no dispatch grant. This protects process interruption, not a
claim of full power-loss durability on every filesystem. Symlink/junction paths reject.

Only a newly returned ELIGIBLE intent may dispatch the pinned requested SHA. The dispatcher must
refresh/revalidate before launch if facts may have changed and must not use a moving branch.
A crash after persistence leaves REQUESTED; restart returns ALREADY_REQUESTED, not another grant.
This deliberately chooses at-most-once intent over automatic delivery. RUNNING and
DISPATCH_UNCERTAIN also suppress further requests. Uncertainty cannot transition back to RUNNING
or automatically redispatch; human reconciliation is required. No external dispatch is implemented.

`store.accept_result(refresh_facts, result)` validates bindings and freshly observed HEAD before
recording evidence. Newer HEAD makes a late result STALE. No external publisher consumes it yet.

## Read-only local inspection

```powershell
uv run python scripts/independent_review.py status PDFTR-49 --config temp/policy.json
uv run python scripts/independent_review.py evaluate PDFTR-49 --config temp/policy.json --facts temp/facts.json
```

`--state <file>` selects explicit historical input; missing explicit input rejects. Missing default
state displays an empty NOT_REQUESTED history without creating files. Output always contains
`inspection_only: true`. Evaluation does not allocate generations or dispatch; eligibility of
unchanged empty history will remain ELIGIBLE. A trusted persisted request makes it ALREADY_REQUESTED.
INVALID exits 1; valid diagnostic decisions exit 0. No credentials are required.
