# PDFTR-37 — implementation completion summary

This artifact records implementer work; it is not an independent SHA-bound reviewer verdict.

- Added lifecycle output and five-minute heartbeat without streaming child output/reasoning.
- Added four role/model presets with explicit CLI field precedence and unchanged reviewer tools.
- Corrected active implementation dirty-tree status without relaxing workflow gates.
- Preserved transitions, two-round semantics, process-tree ownership/cleanup, and PDF behavior.
- Focused validation: 125 passed, 2 skipped. Full `check.ps1`: 486 passed, 3 skipped;
  coverage 89.10%; Wiki/Ruff/mypy checks clean.
- Updated README/CHANGELOG and affected Wiki documentation. Implementation report:
  `.implementation-reports/implementation-report-PDFTR-37.md`.

Delivery branch: `codex/pdftr-37-console-lifecycle`. Remote CI results are not implied by the
local checks. Reviewer execution and merge are left to the user as requested.

## CI coverage follow-up

Windows CI on the original SHA failed during coverage combine after 486 tests passed. Preserved
data prove that both heartbeat cleanup parameterizations' `spawn_tree.py` children/grandchildren
start statement-only coverage in their temporary cwd. Test-module environment isolation now
prevents automatic coverage startup in these service children while leaving parent branch
coverage and production process semantics unchanged. A real executor diagnostic detects active
child coverage, leaked startup variables, and coverage artifacts; it fails when isolation is
disabled. See the implementation report for exact PID/data evidence and final validation.

Follow-up validation: focused diagnostic/heartbeat tests 3 passed; full `uv run pytest` and
`scripts/check.ps1` each 487 passed, 3 skipped, branch coverage 89.10%. Wiki/Ruff/mypy clean.
Remote CI for the follow-up commit is not implied; no reviewer was launched.
