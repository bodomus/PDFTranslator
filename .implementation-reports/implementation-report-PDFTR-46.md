# Implementation Report — PDFTR-46

## Ticket and workflow
Self-Modifying Runner / Module-Version Skew Safety; attempt 1, Level 2.
Initial working tree clean on the expected ticket branch. Python 3.12.10, uv 0.5.26.
Plan/investigation: `.implementation-plans/implementation-plan-PDFTR-46.md`.
Ticket Markdown already present at `Tickets/PDFTR-46-Self-Modifying-Runner.md`.

## Investigation
Direct CLI execution loads the runner under `__main__`. Tracking's function-local import of
`scripts.pi_ticket_cycle` could later read a changed runner file against startup-cached
`agent_cycle`, reproducing both missing-symbol failures after a completed reviewer.
The smallest correction removes that edge, not state-machine accounting or recovery policy.

## Changes and scope
- Added small, pure `scripts/review_protocol.py`: unchanged sentinel/fence grammar and selection,
  with `ReviewProtocolError`. Both callers import it at startup and translate protocol errors
  into their existing exception types. JSON duplicate-key and schema validation remain unchanged.
- Removed all tracking imports of the runner. The existing parent continues using loaded code;
  edits become active on the next invocation. No reload, module-cache clearing or restart added.
- Save original successful reviewer stdout before parsing as `reviewer-stdout-round-<N>.txt`.
  Unexpected parsing/persistence/recording exceptions now diagnose an internal post-review failure
  and use the existing stop boundary. Logs, stdout and accepted cycle artifacts remain; no PASS
  conversion, automatic reviewer repeat or new recovery policy.
- Added isolated fresh-process disk mutation regressions plus AST dependency-graph enforcement.
  Tests reproduce absent OPERATIONAL_CODES and complete_operational_prelaunch against cached old
  state modules and prove tracking does not load the changed runner. Counterfactual imports really
  fail. Full-cycle tests load version A outside the canonical module name, mutate all six harness
  files during implementation, and record PASS or CHANGES_REQUIRED followed by normal new-SHA PASS.
  Injected ImportError during parsing and recording preserves evidence and prevents reviewer rerun.
- Existing strict competing-verdict, nested/malformed sentinel, duplicate-key, intent-outside and
  intent-inside-envelope regressions remain green.

No dependency, role permission, GitHub/YouTrack contract, review budget, exact-SHA rule,
operational retry, lock, process-tree, journal or human approval change. No PDF/model/OCR impact.

## Import audit
1. Parent repository imports in pi_ticket_cycle, project_tracking, tracking_hooks, agent_cycle,
   agent_progress and review_protocol are startup imports. The only late repository edge was
   tracking → runner; removed. AST tests reject late harness imports and transitive tracking → runner.
2. Remaining function-local imports are immutable stdlib: ctypes/wintypes (Windows Job Object),
   msvcrt (Windows lock), fcntl (POSIX lock). Acceptable; preserved.
3. Reviewer Git and progress Node/TypeScript helpers use top-level stdlib/package/helper imports
   in separate children. They are not imported into the parent Python process. Each child loads
   its own code on launch; no added capabilities or orchestration hot-loading.

## Graph and source validation
- ProjectWiki searched for agent cycle; development workflow claims source-verified.
- Graphify query identified runner/tracking/tests. `graphify update . --no-cluster` refreshed 397
  code files (5402 nodes, 12860 edges), then queried the new protocol neighborhood. Four unrelated
  JSON/config files produced zero nodes; graph output remains ignored.
- `code-review-graph update --brief` initially hit CP1251 console encoding after updating;
  rerun with PYTHONIOENCODING=utf-8 succeeded. Post-change update: 17 files, 287 nodes, 2945 edges.
  Reported test gaps for extract_review_json/_run_cycle/review_without_intent are graph limitations:
  source tests and executed mutation integrations exercise all three.
- Source/diff and AST audit verify the new dependency direction and bounded orchestration blast
  radius. No unexpected PDF/translation dependants or migration concerns.

## Validation
- Focused tests PASS: snapshot, project tracking, ticket runner, progress integration,
  operational retry, cycle resume and validator suites (`--no-cov`). Two platform-specific skips.
- Full `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`: PASS.
  **940 passed, 3 skipped**, 331.47 seconds, **89.54% coverage**.
  Gate repeated successfully after aligning fixture reuse with older pre-commit Ruff.
- Ruff format/check PASS; mypy PASS (98 source files); Wiki lint PASS (15 pages, 142 links).
- `git diff --check`: PASS.
- Real provider/model/GPU/OCR validation not needed or performed; no downloads.

## Documentation
README and CHANGELOG explain intentional startup-snapshot activation and retained evidence.
Updated only affected Wiki development workflow and change log. This report and
`reviews/review-PDFTR-46.md` describe implementer completion, not an independent reviewer verdict.

## Remaining limitations
- Windows local quality gate passed. Ubuntu/remote Windows CI outcomes remain pending external CI;
  they cannot be claimed from this workstation.
- If the filesystem cannot persist raw stdout, existing captured reviewer logs remain the evidence
  fallback; this ticket does not implement disk-failure recovery or reviewer reruns.
- External ticket attachment/state updates are runner-owned; no direct integration calls made.

Integration warnings: ["YouTrack credentials unavailable"]
