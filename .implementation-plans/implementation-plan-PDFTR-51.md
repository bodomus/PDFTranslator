# PDFTR-51 investigation and implementation plan

## Level 2 investigation
Baseline clean, expected ticket branch, Python 3.12.10 / uv 0.5.26. Existing PDFTR-49 policy owns strict result validation, immutable ingestion, stale head/base history and PASS readiness. PDFTR-50 provides authoritative refresh, shared ticket ownership and persisted dispatch receipts, but no return/publication path. Graphify query located these boundaries; source verification confirmed them. CRG update parsed successfully but console rendering failed with cp1251 UnicodeEncodeError; retry with UTF-8 is planned. Context7 is not available in this harness; use the existing urllib REST conventions and bounded deterministic transport tests, with live integration explicitly unverified.

## Smallest coherent change
1. Add trusted transport-neutral receiver and authenticated HTTPS polling implementation. Correlate mandatory external request ID to exact persisted dispatch request. No ingestion from files, comments or stdin; no agent CLI.
2. Add a separate strict publication ledger, explicit initialization, atomic repository-local temporary writes, and one shared ticket lock across validation/persistence/publication. Reuse record_result/refresh_state/pass_is_valid. Persist accepted evidence then side-effect intent before GitHub mutation.
3. Publish SHA-bound GitHub check runs using stable external identity. Persist outcomes, fence recovered PENDING and uncertain writes, reconcile exact app-owned checks through reads only. Never retry writes automatically.
4. Add separate continuation intents only after current CHANGES_REQUIRED publication; expose read-only trusted continuation eligibility, not agent launching. Recompute merge readiness from authoritative facts.
5. Add deterministic tests for bindings, stale contexts, duplicates, crashes, failures, reconciliation, bounded rendering and credential isolation. Update README/CHANGELOG/contract/Wiki. Run focused tests, Wiki lint, full check.ps1, graph updates, commit/push and designated handoff.

## Impact / compatibility
Operational scripts only; PDF, translation, models, OCR, dependency lock and Pi transition/retry budgets unchanged. No merge or YouTrack mutations. Deployment must isolate trusted code, credentials, policy/history and receiver from agent write/execute authority (as required by PDFTR-50); Python protocols are not an authentication sandbox. Existing result schema unchanged; publication ledger is separate and missing/corrupt history fails closed. Live GitHub App/connector and exact-SHA Windows/Ubuntu remote CI must be verified by operator/runner, not inferred from mocked tests.
