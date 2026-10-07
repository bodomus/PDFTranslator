# Independent exact-SHA review contract (PDFTR-49)

This is a separate independent-review layer, not a change to the Pi cycle or its review budget.
PDFTR-50 adds trusted GitHub facts/connector dispatch; PDFTR-51 adds authenticated result polling
and GitHub App check publication below. No public callback, automatic retry or merge is implemented.
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

Both `head_sha` and `base_sha` bind the review generation. PR must exist, be open and not
draft. Required checks must all succeed for candidate head SHA. Unknown PR state fails closed.

## Pure API

`scripts/independent_review_policy.py` exposes:

- `evaluate_independent_review(facts, state, config)`: decision/reason/generation, no mutation.
- `request_review(...)`: copied refreshed history plus a decision. ELIGIBLE appends REQUESTED.
- `refresh_state(...)`: marks records with a different head or base SHA STALE, retaining evidence.
- `mark_dispatch(state, config, generation, status)`: RUNNING or DISPATCH_UNCERTAIN.
- `record_result(facts, state, config, result)`: accepts exact bound results, once.
- `pass_is_valid(...)`: current exact PASS **and** all readiness facts still hold; not a merge grant.

Decisions: ELIGIBLE, NOT_ELIGIBLE, ALREADY_REQUESTED, ALREADY_REVIEWED, STALE, INVALID.
Stable readiness reasons include pr_missing, pr_closed, pr_draft, cycle_not_passed, sha_mismatch,
ci_sha_mismatch, ci_pending, ci_failed, ci_unknown. Schema/binding contradictions produce INVALID;
mutation APIs raise IndependentReviewError without changing their inputs.

History contains the configuration plus `current_generation` and `reviews`. Each record has exactly
`generation`, `requested_sha`, `requested_base_sha`, `status`, `result`. Generations are contiguous
positive integers; `(repository, pull_request, requested_sha, requested_base_sha)` is unique.
Both persisted SHAs must be lowercase full 40-character commit SHAs. Missing or malformed base
binding rejects the entire history, including legacy records; no inferred migration is permitted.
No generation is allocated until ready. Repeated requests for the same `(head, base)` do not append;
every previously superseded record is STALE. Returning to a previously stale pair does not revive
approval or allocate another request: human reconciliation is required. Observing head or base
movement revokes earlier status even while the new pair is not eligible.
The immutable request identity and original result/findings remain; STALE is a derived historical
status, not an alteration of the review verdict. Duplicate identical result delivery is idempotent;
a different replacement result rejects. PASS requires requested/reviewed head SHA to equal current
head SHA and requested base SHA to equal current base SHA. It cannot survive either SHA changing,
draft/closed PR, cycle mismatch or failing/incomplete CI. Late results may be recorded despite
non-ready current CI, but never authorize a different `(head, base)` pair.

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
The result's generation identifies its immutable requested head/base pair; `reviewed_sha` must
match that generation's requested head. Result schema and accepted evidence remain unchanged.

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

Only a newly returned ELIGIBLE intent may dispatch the pinned requested head/base pair.
The dispatcher must refresh/revalidate before launch if facts may have changed and must not use
a moving branch.
A crash after persistence leaves REQUESTED; restart returns ALREADY_REQUESTED, not another grant.
This deliberately chooses at-most-once intent over automatic delivery. RUNNING and
DISPATCH_UNCERTAIN also suppress further requests. Uncertainty cannot transition back to RUNNING
or automatically redispatch; human reconciliation is required. The PDFTR-50 integration below is the only dispatch entrypoint added here.

`store.accept_result(refresh_facts, result)` validates bindings and freshly observed head/base SHAs
before recording evidence. Either SHA changing makes a late result STALE, even with unchanged head.
PDFTR-51 uses the same pure policy under a single ownership scope and adds receipt correlation
and separate publication persistence; the lower-level API alone does not publish.

## GitHub-triggered dispatch (PDFTR-50)

`scripts/github_independent_review.py` runs only in a **trusted parent/service**, never inside an
agent tool or an untrusted PR job. Keep its code, trusted configuration, Git checkout and harness
history outside agent-writable mounts/permissions. Shared local files cannot authenticate an agent;
this is not a sandbox or filesystem identity service. Do not copy credentials into prompts or artifacts.
The trusted parent supplies these environment variables:

- `PDFTR_REVIEW_CONFIG`: protected operator-owned PDFTR-49 configuration file (schema above).
- `GITHUB_TOKEN`: read-only repository/PR/check access.
- `PDFTR_REVIEW_ENDPOINT`: operator-owned HTTPS review connector URL (no redirects/userinfo).
- `PDFTR_REVIEW_TOKEN`: connector authentication, not given to the reviewer.

The existing cycle must be validated in its bound repository/task branch; the parent/operator must
explicitly initialize `IndependentReviewStore` once for legitimate first use with the command below.
`init` loads only protected `PDFTR_REVIEW_CONFIG`, validates its ticket/config binding, and reuses
the dispatch path's `load_cycle` harness validation (repository fingerprint, task branch, handoff,
clean unchanged HEAD). It then calls the existing store's exclusive `initialize()`; the store owns
shared ticket serialization and persists PDFTR-49 `empty_state(config)` with
`current_generation == 0` and `reviews == []`. Concurrent owners reject; a second init returns
`INVALID` / `state_already_exists` with existing bytes unchanged. Any existing file, including
malformed/corrupt state, rejects rather than being replaced.

Init does not construct GitHub/provider review transports and requires none of their credentials.
It performs no dispatch, result ingestion, GitHub/YouTrack mutation, merge or automatic cycle
transition. Only the trusted parent/operator may invoke it; deployment isolation described above
enforces that boundary. It is a first-use operation, never a recovery/reset procedure: investigate
lost history rather than invoking init again. Evaluate/signal still require existing valid history
and fail closed when it is missing, deleted or corrupt; events never implicitly initialize it.
Do not initialize or invoke dispatch inside an already-owned runner lock. The current Pi runner is
unchanged; invoke this service after the runner releases ownership.

```powershell
uv run python scripts/github_independent_review.py init PDFTR-50
uv run python scripts/github_independent_review.py evaluate PDFTR-50
```

Manual reevaluation performs real authoritative reads and **may dispatch**, unlike the diagnostic
`independent_review.py evaluate`. There is no force flag or retry command.

A trusted GitHub/Work event connector can invoke `handle_signal` or the `signal PDFTR-50` CLI,
passing the GitHub JSON body on stdin and `GITHUB_EVENT_NAME` in its environment. Input is bounded
at 1 MiB. PR actions opened/reopened/ready_for_review/synchronize/edited and check_run/check_suite/
status/workflow_run signals all converge on the same evaluation. Incoming payload fields, including
repository, PR number, CI, draft and SHAs, do not select the configured target or authorize dispatch.
Notifications for other targets may cause an extra authoritative refresh, never authorization.
Delivery identifiers are unnecessary for correctness; persisted head/base identities deduplicate.
No HTTP receiver is provided: the upstream connector owns event authentication and routing. Do not
expose the CLI as a public unauthenticated execution endpoint or run PR-provided code with secrets.

GitHub reads use the fixed `api.github.com` host and GET only. Repository full name, PR number,
base repository and head repository must match trusted configuration; forks are intentionally rejected.
A second PR read must match the first head/base/branch/draft/state snapshot after fetching checks.
Changed snapshots reject, without automatic retry. Cycle validation reuses the harness loader,
including repository fingerprint/branch/handoff validation and clean unchanged Git HEAD. Cycle SHA
is never rewritten to match PR HEAD. Base-only movement passes directly through PDFTR-49.

Configured names refer to GitHub **check runs** (e.g. windows/ubuntu jobs), not legacy commit statuses.
Each required name must have exactly one check observation, with exact head SHA and SUCCESS.
Missing/ambiguous/wrong-SHA/neutral/skipped observations are UNKNOWN; failed/cancelled/timed_out/
action_required are FAILURE. Queued/waiting/in-progress are PENDING. More than 100 check runs or
incomplete collections reject, rather than silently trusting an unpaginated subset. This deliberately
fails closed on reruns; operators must reconcile ambiguous CI rather than bypass eligibility.

The store holds the existing OS ticket ownership from refresh through dispatch/status persistence.
Concurrent owners reject nonblocking; a later notification may reevaluate. Only freshly persisted
ELIGIBLE intent dispatches. Definite non-delivery leaves REQUESTED with no retry grant; timeout or
unknown receipt becomes DISPATCH_UNCERTAIN. Restart/redelivery conservatively marks recovered
REQUESTED uncertain (even if the crash was before send); RUNNING/uncertainty never redispatch.
A crash after send/status-write failure therefore cannot silently duplicate delivery. Human
reconciliation remains required. Exact-SHA history/result schemas and stale/PASS semantics are unchanged.

### Trusted connector transport

`IndependentReviewDispatcher` accepts a frozen `DispatchRequest`; the HTTPS implementation sends
one POST with these fields plus `instructions`:

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

Instructions demand review of those exact SHAs, no moving branch/newer SHA, no repository mutation
or merge, and PDFTR-49 structured PASS/CHANGES_REQUIRED bound to generation/reviewed_sha.
The trusted connector must enforce a read-only worker capability profile: no push/merge, GitHub,
YouTrack or harness mutation tools. The request does not grant capabilities. This is a transport
contract for an operator-managed connector, **not a claimed native ChatGPT Work API**; provisioning
Work triggers, authentication and read-only worker credentials is a deployment responsibility.

For definite acceptance the connector responds HTTP 200/201/202 with every request identity/profile
field echoed exactly (without `instructions`), plus `external_request_id` (1–128 ASCII letters,
digits, `_` or `-`). Any other response, redirect, network failure or binding mismatch is uncertain;
there are no automatic retries. The bounded opaque ID must not contain credentials. The transport
rejects echoes of its authentication token. Local pre-transmission missing authentication is definite
non-delivery. No server-provided free text or exception strings are logged/persisted.

`independent-dispatch-<generation>.json` contains immutable request fields, outcome and opaque
receipt ID. PDFTR-51 uses this protected trusted-parent receipt for transport correlation only;
it cannot substitute for policy history, generation binding or refreshed GitHub readiness.
A missing/mismatched/uncertain receipt fails closed on ingestion. Policy history remains
`independent-review.json`; only it controls dispatch duplicate suppression. Dispatch sends no
results, PR comments/checks/statuses, YouTrack creation or merge operations.
All normal tests use mocked GitHub and connector responses, without live credentials.

## Trusted result ingestion and publication (PDFTR-51)

`scripts/independent_review_result.py` exposes a trusted service API, deliberately **no CLI**.
The parent constructs `IndependentReviewResultService(store, provider, receiver, publisher)`
with the existing configured `IndependentReviewStore` / `GitHubFactsProvider`, an authenticated
`HTTPSReviewResultReceiver(endpoint, token)` and `GitHubCheckPublisher(installation_token, app_id)`.
App ID is independently protected configuration, not a result field. Provision a GitHub App
installation token with Checks write plus required repository/PR/check read access. Reader credentials
may remain separately read-only. Connector credentials, App token and service code/configuration/state
must be inaccessible to agents. Do not execute PR-provided or agent-edited code in the trusted process.
The current Pi runner does not wire this optional deployment; operator-managed connector provisioning
is required, not a claimed native Work integration. Context7/live integration was unavailable during
implementation; mocked tests do not establish live connector/App compatibility.

After legitimate first use of the PDFTR-49 store, call `service.initialize()` exactly once to create
`independent-publications.json` under shared ticket ownership. Existing/malformed bytes reject.
Normal operations with missing/corrupt history fail closed. Never reinitialize lost history to retry
publication. Release runner ownership before invoking this service; do not nest ticket locks.

Call `service.receive_and_publish(generation)` for a previously dispatched generation. The trusted
receiver performs authenticated HTTPS GET `<endpoint>/<external_request_id>` (no redirects,
userinfo/query/fragment, 1 MiB response bound). Connector returns exactly:

```json
{"external_request_id": "opaque-123", "result": {"schema_version": "1.0", "repository": "bodomus/PDFTranslator", "ticket": "PDFTR-51", "pull_request": 123, "generation": 2, "reviewed_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "verdict": "PASS", "findings": []}}
```

The envelope ID must equal the persisted successful dispatch receipt. Receipt fields must equal
policy history's immutable repository/PR/ticket/generation/head/base/profile. The result reuses
PDFTR-49 strict keys and cannot supply a substitute base or mutation fields. Transport must attest
that evidence came from the independently dispatched read-only worker. A Python Protocol or OS lock
is **not** authentication: arbitrary in-process callers and agent-writable mounts are outside the
supported deployment boundary. Files/comments/stdin are not ingestion sources. Receipt and ledger
must be protected alongside policy history, not copied back from agent artifacts.

Under one OS ticket lock: validate history/receipt/result, refresh authoritative facts, call
`record_result`, durably persist evidence, refresh again, persist publication intent, then send
at most one SHA-bound GitHub check. PASS authorization delegates to `pass_is_valid`; current
CHANGES_REQUIRED also requires exact generation and current readiness. Late head/base results are
retained STALE, without publication or continuation. A second refresh before mutation prevents
publishing an already obsolete context. A race during sending leaves only an exact-head historical
check; post-write refresh revokes local readiness/continuation. Same-head base changes also revoke
local readiness: GitHub's check SHA alone does not prove a still-current reviewed base. Future branch
protection integration must respect that limitation; this ticket changes no protection rules.

Publication identity hashes repository/PR/generation/head/base/verdict. The separate ledger persists
identity, deterministic payload, generation, `publication_state`, `github_check_id` and optional
continuation. States are PENDING, PUBLISHED, PUBLICATION_UNCERTAIN, FAILED_DEFINITE, STALE; absent
entry means NOT_REQUESTED. Recovered PENDING becomes uncertain even if a crash preceded dispatch.
Timeouts, connection failures, HTTP 408/5xx, redirects and invalid responses remain uncertain.
400/401/403/404/422 rejection is definite. Neither classification grants automatic retry.
Accepted evidence or intent persistence failure prevents sending; post-send persistence failure
leaves its durable PENDING fence. Duplicate evidence is immutable/idempotent, publication is
independently at-most-once. The original outcome is saved before secondary refresh diagnostics.

`service.status(generation, reconcile=True)` reads GitHub only. It accepts exactly one complete,
matching app-owned check with the exact identity/head/name/conclusion/output and positive ID.
Incomplete (>100 runs), ambiguous, absent or failed reads remain uncertain, never permission to
send again. Definite absence requires separate operator investigation; there is no retry command.
`status(generation)` refreshes policy/readiness and returns advisory `ready_for_human_merge` and
`continuation_eligible`; these are snapshots, not durable merge/launch grants. Checks are never
accepted as independent-review evidence. No merge endpoint is implemented.

CHANGES_REQUIRED check output contains full JSON findings as inert code blocks, up to 20 complete
findings / roughly 40,000 rendering characters. If a complete finding cannot fit, the rest are
explicitly omitted with a reference to protected `independent-review.json` and generation; full
structured evidence remains local. No finding is partially truncated. Transport exceptions, raw
reviewer logs and chain-of-thought are not rendered or persisted. Known receiver/publisher/reader
tokens are rejected in evidence before persistence; supply other protected credentials via the
service's `secrets` tuple. Do not put secrets in review inputs; this is not a universal secret detector.

Only a PUBLISHED, freshly current CHANGES_REQUIRED creates one separate continuation object:
`schema_version`, `ticket`, `source=independent_review`, `generation`, `reviewed_sha`,
`verdict=CHANGES_REQUIRED`, `status=PENDING_HUMAN_OR_POLICY`. Historical intent is retained but
`continuation_eligible` becomes false after context/readiness changes. An operator may inspect this
intent and follow existing human recovery procedures; this service does not transition Pi states,
launch agents, consume/reset review budgets or automatically fix code. PASS creates no continuation.
YouTrack is omitted entirely and missing issues cannot block evidence/publication.

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
