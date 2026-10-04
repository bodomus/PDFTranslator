# Implementation Report — PDFTR-42

## Workflow
- Level 2; initial working tree clean on assigned task branch.
- Graphify: queried affected symbols, refreshed with `graphify update . --no-cluster`, source-verified.
- CRG: pre/post `update --brief`; successful with PYTHONIOENCODING=utf-8 after initial cp1251
  console encoding failure. Graph test-gap estimates disagree with executable fixture coverage.
- External ticket service and Context7 tools unavailable; existing ticket Markdown retained.

## Scope and investigation
The runner previously rejected any existing non-NEW cycle and always started implementation.
The validator capped cumulative numbering at two. Changed only orchestration scripts, deterministic
service tests and operational docs/contracts. No dependencies, translation/PDF pipeline, model,
CUDA, OCR, provider selection, merge or PR automation changes.
Investigation and plan: `.implementation-plans/investigation-PDFTR-42.md` and
`.implementation-plans/implementation-plan-PDFTR-42.md`.

## Changes
- NEW/CHANGES_REQUIRED/HUMAN_APPROVED_REWORK dispatch to implementation; idle review states
  dispatch directly to the exact-SHA reviewer without repeating implementation.
- PASSED reports completion without children. BLOCKED/STOPPED and active phases fail closed with
  actionable state/HEAD/round/reason diagnostics; existing ownership is never guessed.
- Explicit runner --recover plus --reason, or validator reopen --reason, authorizes one further
  implementation/review pair only after exhausted STOPPED review states. Clean tree, branch,
  unchanged HEAD, base and fingerprint binding remain enforced.
- Strict optional human_recoveries metadata preserves approval reason, prior stop reason, round,
  SHA, next attempt and previous handoff. Legacy manifests are supported without destructive migration.
- Cumulative immutable review numbering and immutable implementation handoff snapshots preserve
  history. Rework rejects every previously reviewed SHA; stale implementer input is removed before
  launching a new attempt. Independent reviewer remains restricted to the existing read-only tools.
- MAX_REVIEW_ROUNDS remains two. Each recovery review requesting changes stops again; another
  implementation/review pair requires another explicit human approval.

## Graph/source validation and impact
Source confirms run_cycle routes through validator transitions, not parallel coordination logic.
Both CLIs reach reopen_cycle. Existing process containment and reviewer Git extension are unchanged.
Graphify refresh succeeded (four unrelated JSON sources produced no AST nodes). No package pipeline
callers or unexpected runtime dependants were found; graph broad shared-symbol neighbors are not
pipeline coupling. Coordination state remains ignored local runtime data.

## Validation
- Focused: PASS — tests/test_pi_cycle_resume.py, tests/test_agent_cycle.py,
  tests/test_pi_ticket_cycle.py, tests/test_reviewer_git.py; deterministic local Git/FakePi, no providers.
- Full `powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/check.ps1`: PASS,
  696 passed, 3 skipped; 89.54% coverage. Wiki lint, Ruff format/lint and mypy all passed.
- Full quality gate repeated after final source changes; latest run 174.43 seconds.
- git diff --check: PASS.
- Windows process-tree and reviewer safety regressions passed; POSIX-specific fixtures skip on Windows.
- Windows/Ubuntu hosted CI not observed in this local session; no hosted-CI success claimed.
- Real-model/CUDA/PDF/OCR manual validation not applicable to orchestration-only scope.

## Documentation
README, CHANGELOG, handoff contract, development-workflow Wiki and Wiki log updated.
Ticket review summary: reviews/review-PDFTR-42.md. External attachment/workflow updates unavailable.

## Remaining operational boundaries
Human approval is an explicit operator action, not authenticated identity verification. Agents are
instructed not to self-approve. Corrupt state, arbitrary operational stops and active phases still
need manual inspection; the wrapper does not silently take over an in-flight agent. Final human
review/merge and hosted CI remain outside this implementation's local validation authority.
