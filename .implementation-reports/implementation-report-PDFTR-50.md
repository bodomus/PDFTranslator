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
