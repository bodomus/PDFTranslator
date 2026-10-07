# PDFTR-49 investigation and implementation plan

## Investigation (Level 2)
Baseline: clean tree, expected task branch; Python 3.12.10 and uv 0.5.26.
The ticket is already saved under Tickets/PDFTR-49-Independent-Review-Trigger-Contract.md.
ProjectWiki search `agent cycle` identifies development-workflow.md. Source verification:
agent_cycle.py owns automated reviews and strict finding/verdict meanings; project_tracking.py
owns existing GitHub readiness, not independent-review authorization. Neither is changed.
Graphify `query 'agent_cycle review' --budget 800` locates these boundaries; source wins.
CRG `update --brief` updated its index but failed rendering under cp1251; retry with UTF-8.
Context7 is unavailable in this session; implementation uses only standard-library APIs and no
new dependencies or external integration semantics.

Missing capability: separate deterministic eligibility/generation/result contract. Smallest change:
a pure dictionary/JSON boundary, separate harness persistence adapter, read-only CLI, focused tests.
No PDF, translation, models, CUDA, OCR, dependencies or existing retry behavior is affected.

## Plan
1. Strictly validate trusted configuration, normalized authoritative facts, history and results.
2. Evaluate repository/PR/cycle/exact SHA/required check facts, suppress existing generations.
3. Pure request/result/status transitions retain historical evidence, reject contradictions and
   block redispatch in REQUESTED/RUNNING/DISPATCH_UNCERTAIN states.
4. Harness-only persistence API: explicit initialization, OS serialization, atomic replacement,
   persist request intent before returning any dispatchable generation; no external dispatch.
5. Read-only status/evaluate CLI: facts files are diagnostics, never authorization state writes.
6. Test eligibility, duplicates, stale/late results, contradictory state, restart, uncertain dispatch,
   concurrency, CLI read-only boundaries and corruption. Update README/CHANGELOG/Wiki/report.
7. Run focused tests then scripts/check.ps1, refresh graphs, commit and push. Runner owns transitions.

## Trust boundary
Policy requires refreshed authoritative facts supplied by a trusted harness, not webhook data.
Persistence APIs are for trusted harness/operator use only. Result ingestion is not wired to an agent
or CLI. A future dispatcher must keep its store outside agent-writable mounts/permissions and use
trusted reviewer output; local JSON itself is not an authenticated reviewer identity service.
No merge authority is introduced. YouTrack is absent from policy and persistence.

## Human review correction: exact head/base binding (2026-10-07)

Reviewed SHA: `768575baa3fdbf14423f13900a784d237b17fad9`; finding P1/HIGH.
Level 1 scoped policy fix, explicitly requested by the human with commit/push authorization.
The cycle manifest is already PASSED; this manual correction does not rewrite harness-owned
cycle state or manufacture a new independent approval.

Root cause: facts validate base_sha, but history identity, refresh and PASS validation only
compare head SHA. A base-only move can preserve approval of an obsolete review context.
Source-verified scope: independent_review_policy.py, its store/inspection callers and focused
tests. Graphify scoped query and CRG incremental update/caller queries confirm these boundaries;
CRG has duplicate slash/backslash nodes, so qualified names and source searches are used.
No PDF/model/OCR/dependency or module-boundary changes. YouTrack get_issue reports not found.

- [x] Add regressions for PASS/base movement, active and late reviews, readiness gating,
  identical-pair duplicates, historical pair returns and malformed/missing persisted base SHA.
- [x] Run the new tests against the reviewed implementation and observe the defect.
- [x] Require requested_base_sha in every generation; validate uniqueness by (head, base) within
  the existing repository/PR binding. Compare both SHAs in eligibility, refresh and PASS validity.
  Keep reviewer result schema and immutable evidence, persistence, uncertainty and read-only APIs.
- [x] Update contract/README/CHANGELOG and affected Wiki; document fail-closed legacy history.
- [x] Update CRG and verify scope; run focused tests and full scripts/check.ps1 with all temporary
  output under temp/. Update this ticket's report/review.

Delivery: commit this validated correction, inspect its exact SHA read-only, push the ticket branch,
and report that SHA. Final human review and merge remain separate human decisions.
