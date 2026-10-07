# Implementation Report

## Ticket
PDFTR-51 — Independent review result ingestion, GitHub publication, and closed-loop continuation

## Workflow
- Level: 2; initial working tree clean, expected ticket branch.
- Plan/investigation: `.implementation-plans/implementation-plan-PDFTR-51.md`.
- Graphify: queried before implementation, refreshed with `graphify update . --no-cluster`, queried new service boundaries afterward.
- CRG: `code-review-graph update --brief` initially encountered a cp1251 console encoding error after successful parsing; UTF-8 retry succeeded. Staging new files enabled post-change indexing: 90 nodes / 682 edges; final detect-changes completed.
- Context7 tools unavailable; source conventions and deterministic urllib tests substituted. No dependencies added.

## Scope and investigation
PDFTR-49 already owned strict immutable results, head/base staleness and current PASS policy. PDFTR-50 already owned authoritative facts, successful dispatch receipts and OS ticket ownership. Missing capability was a trusted return path plus an independently fenced GitHub side effect. New modules are `scripts/independent_review_result.py` and `scripts/github_review_publication.py`; focused tests are `tests/test_independent_review_result.py`.

No PDF, translation, model/device, OCR, package CLI, dependency, Pi transition or review-budget changes. Existing result schema is unchanged. Publication uses a separate strict ledger; receipt correlation now consumes protected PDFTR-50 sidecars, never substitutes for policy history.

## Changes
- Trusted transport-neutral receiver and authenticated bounded HTTPS connector polling; no CLI, local result-file/stdin/comment ingestion or public callback.
- Mandatory successful dispatch receipt identity/profile/head/base/generation and returned request ID correlation; strict PDFTR-49 result validation/record_result.
- One OS ticket ownership scope across refresh/persistence/write. Accepted evidence persists before publication intent, which persists before mutation.
- Explicit first-use ledger initialization; missing/corrupt/existing history never resets. Duplicate identical results suppress independently duplicate publication; replacement evidence rejects.
- Deterministic exact-head GitHub App `Independent Review` check, stable external identity, persisted positive external ID, complete bounded inert JSON findings and full local evidence retention.
- Recovered PENDING and uncertain mutation outcomes never resend. HTTP definite rejection is separate; ambiguous writes/read failures preserve uncertainty. Exact unique app/head/identity/output read reconciliation can confirm publication without mutation.
- Fresh authoritative refresh before publication, after write and on status; PASS validity delegates to PDFTR-49. Stale evidence persists but receives no new current publication or continuation.
- Current published CHANGES_REQUIRED creates one separate pending human/policy continuation object. Historical intents lose eligibility; no agent launch, cycle/budget transition, YouTrack mutation or merge API.
- Known transport/reader/publisher tokens and additional parent-supplied secrets reject before evidence persistence; internal transport exceptions are never stored/rendered.

## Graph/source validation and impact
Source-verified Graphify candidates: policy, store, dispatch, facts, ownership and their tests. Refreshed graph exposes new result service and publisher with those same boundaries. CRG reported 47 heuristic test gaps, including protocol methods/dynamically injected adapters; 55 new deterministic test cases exercise their real behavior, so graph gaps are not treated as proof of absent tests. Existing operational modules are imported but not changed. No unexpected PDF pipeline dependants. Service reachability is an explicit trusted parent API, not automatic runner wiring.

## Validation
- Focused: `uv run pytest tests/test_independent_review_result.py tests/test_independent_review.py tests/test_github_independent_review.py tests/test_github_independent_review_init.py --no-cov -q` — 226 passed.
- Final full gate: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` — PASS.
- Full pytest: 1372 passed, 3 skipped; package coverage 89.54%.
- Wiki lint: 15 pages, 162 links, zero errors/warnings.
- Ruff format/lint and mypy (98 package source files): PASS.
- `git diff --cached --check`: PASS.
- Real GitHub App/connector, real-model/CUDA/OCR/PDF integration: not run (operational change; no credentials/model downloads).
- Remote Windows/Ubuntu CI must be checked against the pushed implementation SHA; local Windows validation does not establish remote CI success. GitHub CLI authentication was unavailable during pre-push inspection. Handoff notes record any subsequent public CI verification.

## Documentation
README, CHANGELOG, `docs/independent-review.md`, affected development Wiki and knowledge log updated. Existing ticket Markdown is preserved under Tickets; attaching ticket/report/review and tracking updates remains runner-owned.

## Remaining risks / deployment limitations
- Operator must deploy pinned trusted parent code/config/history/receipt/ledger and credentials outside agent authority, provision an independently read-only connector and GitHub App. Python protocols/filesystem locking are not authentication or a sandbox. Current Pi runner does not automatically connect this service.
- SHA-bound checks cannot atomically bind GitHub's moving PR base. A during-write race leaves exact-head historical evidence; local readiness/continuation is freshly revoked. Future protection integration must respect the base limitation. No branch protection changes made.
- Reconciliation deliberately fails closed for incomplete (>100 runs), absent or ambiguous evidence; no automatic/operator retry API is supplied. Lost history requires human investigation, never initialization as recovery.
- Whole findings rendering is bounded; full result remains protected locally. Known secrets are rejected, not a universal secret scanner; parent must supply additional credentials and never include secrets in review inputs.
- Continuation is an advisory pending intent only; operator follows existing safe human recovery procedures. No automatic launch or merge.
- Integration warnings supplied by runner context: ["YouTrack identity mismatch; remote mutation refused", "YouTrack authentication failed"]. No YouTrack API was called by this implementation; YouTrack remains non-authoritative and omitted.
