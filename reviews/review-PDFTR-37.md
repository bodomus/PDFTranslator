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
