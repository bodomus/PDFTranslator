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
