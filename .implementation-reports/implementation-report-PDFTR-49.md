# Implementation Report

## Ticket
PDFTR-49 — Independent Review Trigger Contract (attempt 1)

## Workflow and investigation
- Level 2; working tree initially clean on the expected ticket branch.
- Python 3.12.10, uv 0.5.26; no dependencies added.
- Plan/investigation: `.implementation-plans/implementation-plan-PDFTR-49.md`.
- ProjectWiki search: agent cycle. Verified existing automated review grammar in agent_cycle.py,
  persistence ownership in cycle_ownership.py and existing readiness documentation/source.
- Graphify query found agent_cycle/runner/tracking boundaries; source verification confirmed them.
- CRG update initially failed printing under cp1251; UTF-8 invocation succeeded. Post-change
  graph validation: UTF-8 `code-review-graph update --brief` indexed 58 new nodes/750 edges;
  `graphify update . --no-cluster` succeeded and the scoped IndependentReviewStore/request_review/
  pass_is_valid query confirmed policy → store → tests plus OS ownership dependencies.
  Source verification found no existing pipeline/runner/tracking callers of the new APIs.
  CRG's heuristic untested warnings are contradicted by direct focused tests of the store/JSON
  helpers; test results remain authoritative. Graphify warned about four empty non-code JSON
  sources, unrelated to this scope. Context7 tools were unavailable; new code is stdlib-only.

## Scope and changes
- Pure `scripts/independent_review_policy.py`: strict versioned config/facts/state/result validation,
  deterministic eligibility/reasons, SHA uniqueness and generation continuity, copied state
  transitions, stale late-result retention, immutable accepted results and exact current PASS check.
- `scripts/independent_review.py`: harness-only explicit initialization, OS ownership, atomic
  fsync/replace of request intent before returning dispatch eligibility, no automatic retry after
  a persisted REQUESTED or uncertain outcome. Missing/corrupt state rejects ingestion.
- Read-only status/evaluate commands inspect local inputs without state mutation or dispatch.
- 61 focused tests cover readiness, exact CI/cycle SHAs, drafts/closed PRs, invalid bindings/types,
  required checks, duplicates, HEAD movement, old findings, late PASS, corrupt history, uncertainty,
  persistence failure, crash/restart, competing ownership, duplicate JSON keys and read-only CLI.
- No existing cycle, runner, tracking or retry behavior was modified. Only the existing OS ownership
  primitive is imported. No PDF/model/translation/OCR/CUDA or dependency effects.
- README, CHANGELOG, contract documentation and affected Wiki workflow/log updated.

## Validation
- `uv run pytest tests/test_independent_review.py --no-cov --basetemp=temp/pdftr49-focused`:
  PASS, 61 tests.
- `scripts/check.ps1` through Windows PowerShell with repository-local pytest basetemp:
  PASS, 1207 passed, 3 skipped, 89.54% package coverage. Wiki lint, Ruff format/check, mypy all PASS.
- `uv run python scripts/project_wiki/wiki_lint.py`: PASS, 15 pages, no errors/warnings.
- CLI `--help` smoke test: PASS.
- Windows execution verified locally. Hosted Windows/Ubuntu CI verification is blocked:
  `gh run list` refused without GitHub authentication. No CI success is claimed; the pushed
  revision must be checked by the authenticated runner/operator.
- No live GitHub/YouTrack mutation, Work dispatch, model downloads, CUDA, OCR or manual PDF tests.

## Trust and remaining limitations
- No webhook/Work/publication/merge integration. Store APIs are trusted-parent APIs, never agent
  tools. The CLI exposes no result-ingestion or authorization mutation command.
- Future integrations MUST refresh authoritative facts, isolate write-capable harness code/state
  from agent-writable mounts and accept reviewer evidence only through a trusted transport.
  Shared writable files are not an authenticated identity service; local inspection is not approval.
- State retains request identity/result evidence; STALE status is derived history. Reverting to a
  previously stale SHA fails closed rather than reviving approval or manufacturing a generation.
- The store owns its OS lock and must not be called while that same ticket lock is already held.
  Same-filesystem temp/atomic replacement is required. Process-crash safety is tested; full
  power-loss durability across every filesystem is not claimed.
- Crash after intent persistence sacrifices automatic delivery rather than risk duplicate dispatch.
  Uncertain dispatch needs human reconciliation. No automated retry or merge grant exists.
- YouTrack remains outside authorization. Supplied integration warnings (not newly reproduced):
  ["YouTrack identity mismatch; remote mutation refused", "YouTrack authentication failed"].

## Human review correction: head/base SHA binding (2026-10-07)

Finding: P1/HIGH on reviewed SHA `768575baa3fdbf14423f13900a784d237b17fad9`.
The human explicitly requested this narrow correction and commit/push on the existing branch.
The starting working tree was clean; this is a Level 1 policy fix.

### Changes and compatibility

- Every generation now requires full lowercase `requested_base_sha`; repository/PR configuration
  plus requested head/base form its identity. Uniqueness and duplicate suppression use that pair.
- Refresh marks records STALE if either head or base changes, independently of readiness. New pairs
  become eligible only after the existing PR/cycle/exact-head CI predicates pass.
- PASS requires requested/reviewed head and requested base to match current facts. A base-only move
  invalidates PASS immediately, even before history is refreshed or another generation is allocated.
- Late results retain their immutable generation and evidence as STALE. Returning to historical
  pairs cannot revive PASS or create duplicate history. Reviewer result schema remains unchanged;
  its generation binds the immutable requested head/base context.
- Legacy/malformed history without valid base binding fails closed, including historical entries.
  No inferred migration or history reset is introduced.
- Persistence/locking, uncertainty fencing, result immutability, agent boundaries, YouTrack
  independence and human merge ownership are preserved. No webhook/Work integration or dependencies.
- README/CHANGELOG/contract and only affected Wiki workflow/log updated. Harness cycle files were
  not rewritten; the old cycle result is not claimed as approval of this correction.

### Investigation and regression evidence

Graphify scoped query located policy/store/tests. CRG incremental update and qualified caller
queries confirmed source-verified boundaries; slash/backslash duplicate graph nodes were handled
with qualified names and source search. Post-change update succeeded; impact remains the store
and focused test file. No module/PDF/model/translation/OCR/CUDA boundary changed, so no graph rebuild.

Before implementation, 15 pure base-movement regression cases failed for the expected reasons:
PASS survived B1-to-B2 movement and active/completed generations retained their old status.
The initial sandboxed test attempt also hit Windows sandbox temporary-directory ACL restrictions;
complete validation runs outside that sandbox with all new temporary output under repository temp/.

- Focused command: `uv run --no-sync pytest tests/test_independent_review.py -o addopts='--strict-config
  --strict-markers -q' --cov=scripts.independent_review_policy --cov=scripts.independent_review
  --cov-report=term-missing --cov-fail-under=80 --basetemp=temp/pdftr49-base-final
  -o cache_dir=temp/pytest-cache-pdftr49`.
- Focused result: PASS, 96 tests (35 new regression cases); policy statement/branch coverage 100%,
  policy plus persistence adapter coverage 94.15%.
- Coverage includes PASS B1-to-B2/new generation, active REQUESTED/RUNNING/DISPATCH_UNCERTAIN,
  late PASS before/after a new request, readiness gates, duplicates, historical pair return,
  immutable old result, durable restart and malformed/missing bindings in current/historical records.
- Full `scripts/check.ps1`: PASS, exit 0; 1242 passed, 3 skipped in 510.50 seconds,
  package coverage 89.54%. Wiki lint: 15 pages, 0 errors/warnings; Ruff format/check and mypy PASS.
  UV/pytest/Ruff/mypy/coverage/runtime temporary output was configured under repository temp/.
- YouTrack `get_issue(PDFTR-49)` returned `Issue not found`; fields and attachments could not be
  updated. The existing ticket Markdown and completion review remain saved locally.
