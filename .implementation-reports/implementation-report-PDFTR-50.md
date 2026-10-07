# Implementation Report

## Ticket
PDFTR-50 — GitHub-triggered independent review dispatch (attempt 1).

## Workflow
- Level: 2; starting working tree clean on the supplied task branch.
- Graphify: queried IndependentReviewStore, refreshed with `graphify update .`, queried new entrypoint.
- CRG: `code-review-graph update --brief`; initial cp1251 console error resolved with
  `PYTHONIOENCODING=utf-8`. Post-change update completed.
- Plan/investigation: `.implementation-plans/implementation-plan-PDFTR-50.md`.
- Existing ticket Markdown remains under Tickets; remote attachment/tracking is runner-owned.

## Scope
- Modules: GitHub facts adapter, immutable review transport, trusted-parent orchestration,
  one store dispatch operation, focused integration tests and operational documentation.
- Pipeline stages: external independent review only. No PDF/translation/model/device/OCR changes.
- Dependencies: none added. Python 3.12/uv, Windows/PowerShell compatibility retained.
- Public contract: trusted service manual reevaluation and bounded stdin GitHub signal input;
  pure policy and existing read-only inspection/result/history schemas unchanged.

## Investigation
PDFTR-49 already authorizes exact head/base generations and durably stores REQUESTED under shared
OS ticket ownership. Missing capability was authoritative GitHub refresh and immutable external
dispatch. Source-verified request_review, mark_dispatch, ticket_ownership, _load_cycle and store APIs.
Required configuration remains the existing PDFTR-49 schema; credentials/endpoint are trusted
service environment, never event/agent facts. Blast radius is limited to the independent-review layer.

## Changes
- Fixed-host bounded GET adapter verifies configured repository and PR, rejects forks, reads
  exact-head check runs between matching PR snapshots, and builds the existing facts schema.
- Unique configured check observations must match exact HEAD. Missing/ambiguous/old-SHA checks
  normalize UNKNOWN; pending and failure mappings fail closed. Truncated collections reject.
- Existing harness loader validates cycle Git/repository/branch/handoff facts; cycle SHA is
  independent of PR SHA and is never rewritten. Every signal invokes the same PDFTR-49 policy.
- Added one shared ticket-ownership scope across refresh, durable intent, dispatch and status.
  A newly persisted generation dispatches once. Restart/redelivery conservatively recovers
  REQUESTED as uncertain. Definite failure has no automatic retry; timeout/receipt uncertainty
  never redispatches. Corrupt history and failed intent persistence prohibit dispatch.
- Frozen dispatch request pins repository, PR, generation, head/base and review profile.
  Instructions prohibit mutation/merge and require exact-generation PDFTR-49 results.
- HTTPS connector uses one POST, rejects redirects, verifies echoed identity and bounded opaque ID,
  never persists credentials, arbitrary provider prose or exception strings. Diagnostic receipt
  sidecars are atomically persisted and never influence authorization.
- GitHub PR/CI event adapter and trusted signal/manual CLI share the same operation. Payload
  authorization claims are unused. No public HTTP receiver, result publisher or merge introduced.
- YouTrack is not imported or called, and missing issues cannot block this flow.

## Graph and source validation
Graphify confirms the independent policy/store/ownership neighborhood; new entrypoint imports the
existing harness loader without invoking transitions. Source verification confirms no policy network
imports, no runner changes and no GitHub/YouTrack mutation API. Graph traversal includes neighboring
runner transition symbols via imports, not evidence they execute. CRG reports static test gaps for
store/request_and_dispatch; focused integration tests exercise those symbols through handle_signal,
including concurrent ownership and persistence-before-send assertions. Dynamic closures/Protocol
transport calls are a graph limitation, not untested runtime paths. No unexpected PDF dependants.
Context7 was not exposed in this session; documented REST shapes are strictly validated with mocked
responses. No native ChatGPT Work API is invented.

## Validation
- Focused: `uv run pytest tests/test_github_independent_review.py tests/test_independent_review.py
  --no-cov -q` — PASS, 154 tests.
- Full quality gate: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` — PASS.
- Full pytest: 1299 passed, 3 skipped; coverage 89.54% (80% required).
- Ruff format/lint, mypy src and ProjectWiki lint — PASS.
- `git diff --check` — PASS.
- No live dispatch, live credentials, large-model downloads, CUDA/OCR or PDF manual validation;
  not relevant to this integration. Network tests use deterministic GitHub/connector doubles.
- Remote Windows/Ubuntu CI for the final implementation SHA is pending push/remote observation;
  local check.ps1 success is not GitHub CI authorization evidence.

## Documentation
README, CHANGELOG, docs/independent-review.md, affected development-workflow Wiki page and Wiki log
updated. Trusted deployment, configuration, manual/event commands, connector response, supported CI
check-run subset, restart uncertainty and read-only reviewer capability requirements are documented.

## Remaining risks / deployment boundaries
- Operator must provision a trusted GitHub/Work event connector and HTTPS review transport;
  this ticket defines the connector contract, not a native Work API or public receiver.
- Service code/configuration/cycle history and credentials must be isolated from agent writes.
  A shared writable checkout is not a security boundary; trusted connector must enforce read-only
  worker tools. Never expose the dispatch entrypoint to implementer/reviewer agents.
- At-most-once dispatch favors safety over automatic delivery. REQUESTED crash recovery, uncertain
  receipt, definite non-delivery and ambiguous reruns require human reconciliation.
- Check-run names only; legacy commit statuses and collections exceeding 100 runs fail closed.
- PR read sandwich rejects observed changes but cannot lock remote GitHub; dispatched context is
  always immutable exact SHAs, never current branch HEAD.
- Filesystem persistence retains PDFTR-49 atomic replace/fsync guarantees, not universal power-loss
  durability. State/temp must share a filesystem.
- Integration warnings requested by runner: ["YouTrack identity mismatch; remote mutation refused",
  "YouTrack authentication failed"]. No direct YouTrack mutation was attempted by this role.

## Human exact-SHA review correction — 2026-10-07

The human review of `81ab41bf5ea6d3b038e1368f4a0970a323cb14a7` returned CHANGES_REQUIRED
for the missing production first-initialization entrypoint (P2 / MEDIUM). This correction is
implemented in the same branch/workspace on the user's explicit instruction. It does not
record an automated review verdict or change the actual ticket cycle's manifest/handoff.

### Investigation and scope

The production CLI exposed evaluate/signal, both reaching `request_and_dispatch` and requiring
existing history. PDFTR-49 already provides exclusive `initialize()` and `empty_state(config)`;
there was no production path to invoke them. Only `scripts/github_independent_review.py` changes
in production. Policy, store, schemas, GitHub facts/transport, runner and ticket ownership remain
unchanged; no dependencies, PDF/model/device/OCR behavior or external-library usage changes.

### Implementation

- Added trusted-parent/operator `init <ticket>` using the existing protected
  `PDFTR_REVIEW_CONFIG` source and store configuration validation/ticket binding.
- Reused `load_cycle` and its trusted harness loader before `store.initialize()`: existing cycle,
  repository fingerprint, branch, handoff and clean unchanged HEAD must validate.
- Store initialization uses its existing shared OS ticket ownership and atomic/fsynced persistence
  of `empty_state(config)`. No second state constructor or weaker lock was added.
- Init returns INITIALIZED with generation zero and no reviews. It executes before GitHub/provider
  review transport construction and requires no dispatch credentials.
- Existing/corrupt state rejects without replacement; a second init returns INVALID with the
  bounded `state_already_exists` reason. Other errors retain sanitized diagnostics.
- Normal evaluate/signal never initialize missing/deleted/corrupt history. Init performs no
  review dispatch, result ingestion, GitHub/YouTrack mutation, merge or automatic cycle transition.
  No force/reset/generic recovery or implicit reinitialization was introduced.

### Regression evidence

Twenty CLI cases in `tests/test_github_independent_review_init.py` use real temporary Git
repositories and harness-created cycles; the eligible path also uses validated harness handoff
and exact-SHA review to establish PASSED. External GitHub/connector operations are deterministic
doubles. Fresh init's transport constructors are forbidden; eligible init asserts zero reads/calls.

| Scenario | Observed behavior |
| --- | --- |
| Fresh explicit init | State exists; generation 0; reviews empty; no dispatch/receipt; Git/cycle unchanged |
| Second init | state_already_exists; existing bytes unchanged |
| Fresh event without init | evaluate and signal fail closed; no file or dispatch |
| Initialized eligible flow | One generation and one exact head/base dispatch; duplicate suppressed |
| Deleted used history | evaluate and signal fail closed; no recreation or extra dispatch |
| Malformed/invalid existing state | Init rejects; original bytes unchanged |
| Concurrent init | One success; competing owner rejects; complete valid state; no leftover temp file |
| Invalid trusted config/context | Rejects absent/malformed/mismatched config and invalid cycle/Git context |

### Graph/source verification

Graphify preflight query found store/policy/ownership/harness relationships; `graphify update .`
refreshed the code graph successfully and a post-change query includes the new test module.
CRG incremental refresh succeeded before and after implementation (including the staged new test).
Direct callees verify production `main -> load_cycle / IndependentReviewStore.initialize`.
The scoped radius reaches the two independent-review test modules, with no PDF dependants.
Source inspection confirms init is separate from handle_signal/dispatch and there is no policy,
store, schema, ownership or runner diff. Static graph edges do not prove branch exclusion;
the runtime no-transport and unchanged-cycle assertions establish it.

### Validation

- RED: fresh-init CLI regression failed because argparse did not accept init on the reviewed code.
- Focused command: `uv run pytest tests/test_github_independent_review_init.py
  tests/test_github_independent_review.py tests/test_independent_review.py --no-cov
  -o "addopts=--strict-config --strict-markers" --basetemp=temp/PDFTR-50-init-focused-final -q`.
  Result: 🟢 PASS — 173 passed in 11.37 seconds.
- Full gate: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` with
  `PYTEST_ADDOPTS=--basetemp=temp/PDFTR-50-init-full` and repository-local uv/coverage/temp output.
  Result: 🟢 PASS — exit 0; Wiki lint, Ruff format/lint, mypy (98 source files),
  1319 passed and 3 skipped in 524.37 seconds. Package/branch coverage: 89.54% (80% required).
- CLI `--help` lists init/evaluate/signal. Wiki lint: 15 pages, 159 links, zero errors/warnings.
- Windows sandbox ACLs blocked pytest temporary-directory access and Git/Graphify cache writes;
  validation/graph refresh run outside that sandbox. All test/temp/coverage/uv-cache output stays
  under repository-local temp/ or the existing ignored graph directories.

### Documentation and handoff boundary

README, CHANGELOG, independent-review contract, affected development-workflow Wiki and log,
ticket Markdown, this report, implementation plan and `reviews/review-PDFTR-50.md` are updated.
The YouTrack connector reports Issue not found: PDFTR-50; remote fields/attachments cannot be
updated and no issue is created. Local ticket/review Markdown remains available.
Trusted deployment isolation still enforces operator-only access; init is for legitimate first
use, never recovery after lost history. No live review dispatch or production init was invoked.
The new implementation SHA requires a fresh human exact-SHA review; earlier reviews cannot
authorize it. Commit/push are the requested final handoff; merge remains human-owned.
