# PDFTR-42 investigation

- Workflow: level 2, assigned branch, initially clean tree; uv Python 3.12.10.
- Current gap: run_cycle preflight accepts only NEW and its loop always begins implementation.
  begin_review caps cumulative numbering at two, preventing audited follow-up review artifacts.
- Expected: idle-state dispatch, terminal/active fail-closed behavior and explicit human approval
  granting just one additional implementation/exact-SHA review pair after exhausted reviews.
- Smallest coherent boundary: keep validator authoritative; wrapper chooses idle next role.
  Optional strict human_recoveries metadata supports legacy manifests without rewriting reviews.
- Affected symbols: CycleState, begin_implementation, record_handoff, begin_review, manifest/review
  validation, reopen_cycle, cycle_status, validator CLI, run_cycle and runner CLI.
- Contracts: branch/base/fingerprint/clean-tree/exact-SHA binding retained; role inputs unchanged;
  review filenames cumulative and immutable; accepted implementation handoffs archived by attempt.
- No translation, PDF integrity, OCR, model, cache, provider-selection or dependency changes.
  Process containment and reviewer extension/tool allowlists stay unchanged.
- Graphify query found both scripts/test neighborhoods; update . --no-cluster succeeded after code
  changes. Graph has broad Path/shared-module neighbors: source limits actual blast radius to
  operational scripts/tests/docs. Four unrelated JSON files yielded no AST nodes, reported by tool.
- CRG update --brief initially failed printing Unicode under cp1251; retry with
  PYTHONIOENCODING=utf-8 succeeded. Dynamic fixture-driven tests appear as graph test gaps despite
  executable coverage. Source/executable evidence wins.
- Validation: deterministic local Git/FakePi tests; full PowerShell quality gate and Wiki lint.
  No provider/model downloads or external-network integration required.
- External ticket service and Context7 tool unavailable in this session. Existing ticket Markdown
  is retained; attachment/workflow updates cannot be performed from the available tools.
