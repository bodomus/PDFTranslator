# Implementation Report

## Ticket
PDFTR-40 — Reviewer read-only Git inspection (attempt 1)

## Workflow
- Level: 2. Initial tree clean; supplied task branch confirmed before changes.
- Investigation completed before implementation; ticket already saved under Tickets/PDFTR-40.md.
- Graphify: scoped query reused existing graph; source-verified runner/test neighborhood.
- CRG: UTF-8 retry and post-change update succeeded; graph test-gap warnings source-verified as false negatives.
- External ticket attachment/state updates unavailable: no ticket-service tool exposed.

## Scope and changes
- Added reviewer-only Pi `git_readonly` tool and dependency-free Node `GitReadonlyInspector`.
- Explicit operations: status, HEAD/full commit resolution, branch, exact endpoint diff, staged/unstaged diff, metadata/stat/patch show, merge-base and log (1–100 records).
- Root captured from runner-bound cwd; no reviewer path, executable, argv, environment, format or output-file parameters. Internal subprocess methods are private.
- Absolute trusted PATH Git executable outside the repository (no cwd/PATH hijacking).
- Direct Git execution with no shell, external diff, textconv, pager, fsmonitor, hooks, signature programs, network protocols, recursive submodules or optional index locks. Inherited GIT_* overrides stripped; replacement objects/lazy fetch disabled; partial clones/alternates/gitfile redirects rejected.
- Disables all configured clean/smudge/process filters, including status hashing paths. Preserves legitimate Windows system/global/local line-ending semantics; unknown filter names fail closed.
- Every Git process has 30-second timeout and 4-MiB output bound; errors/overflow/cancellation fail closed, never truncate evidence silently.
- Runner explicitly loads trusted reviewer adapter with discovery disabled; CLI allowlist and runtime guard retain file tools and forbid writes/shell for every preset. Implementer permissions and independent same-model contexts unchanged.
- Prompt requires independent HEAD/status/SHA/base-diff/branch/merge-base evidence. Validator, state transitions, handoff/verdict schema, maximum two rounds and human merge ownership unchanged.
- Deterministic real-Git and fake-cycle regressions, malicious local helper configs, injection/rejection, fixed-root, bounds/cancellation and runtime tool guard tests. CI installs Node 22 for these tests.
- No new Python/npm dependencies, product/PDF/translation/model/device/cache/OCR behavior changes.

## Validation
- Focused inspector tests: PASS (75 tests, no providers/network, including LF/CRLF adapter source variants).
- Focused runner/validator tests: PASS, including separate contexts for all four presets and fake-cycle independent Git evidence. Focused workflow-only tests use `--no-cov` because they do not import the product coverage target.
- Full `uv run pytest`: PASS, 593 passed / 3 skipped; total coverage 89%, above 80% gate.
- `uv run python scripts/project_wiki/wiki_lint.py`: PASS, zero errors/warnings.
- `scripts/check.ps1` via Windows PowerShell: PASS; Ruff format/check PASS; mypy PASS (97 source files); full tests/coverage PASS again.
- Installed Pi extension offline help-load smoke: PASS, no provider called. Node tests exercise actual inspector and adapter registration/guard.
- `git diff --check`: PASS.
- Initial push CI: Ubuntu PASS; Windows revealed a CRLF-only adapter-test import-stripping failure.
  Corrected the test harness to accept CRLF and added deterministic LF/CRLF variants; production
  adapter/inspector unchanged. Final-push CI and exact-SHA reviewer verdict require subsequent
  evidence, not preclaimed in this report.
- Real model/CUDA/OCR/PDF manual runs not applicable to workflow-only changes.

## Documentation and impact
Updated README, CHANGELOG, reviewer contract/skill/new Git-safety reference, affected workflow Wiki and Wiki log; ticket-scoped plan, investigation and completion review included. Source and graph analysis confirm no product-module dependants. Existing process containment paths remain untouched.

## Remaining risks / intentional limits
- Unsupported linked worktrees/gitfile redirects, alternate object stores and partial clones fail closed.
- Disabled content filters may make filtered repositories appear dirty; reviewer must block rather than execute a helper to repair evidence.
- Large diffs fail at the output cap; no automatic file publication or hidden truncation.
- Capability enforcement is not an OS sandbox against compromised trusted binaries/extensions or concurrent external writers; existing file-read tools are not a filesystem sandbox.
- Remote CI and final exact-SHA review/merge decisions remain outside the implementer phase.
