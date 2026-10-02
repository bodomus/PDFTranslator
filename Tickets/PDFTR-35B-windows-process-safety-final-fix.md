# PDFTR-35B — Windows process-safety final fix

Fix only the two defects from the PDFTR-35A review round 2. Do not expand scope. Do not change the
workflow or state machine.

## Defect 1 — R6-SPAWN

A `KeyboardInterrupt`/Ctrl+C at any point after `Popen` — including while creating or assigning the
Windows Job Object guard — must guaranteed-terminate the direct child and every descendant before
control returns.

## Defect 2 — R4-RESUME

The result of `ResumeThread` must be checked. A failure value must trigger fail-closed cleanup of
the whole process tree and a startup error; a suspended process must never be treated as
successfully started.

## Required regression tests

- Deterministic tests for both cases.
- No real LLM providers.

## Quality gate

```powershell
uv run pytest tests/test_pi_ticket_cycle.py
uv run pytest
uv run python scripts/project_wiki/wiki_lint.py
.\scripts\check.ps1
```

## Boundary

- Only `scripts/pi_ticket_cycle.py` and its tests, plus docs.
- No `scripts/agent_cycle.py` changes. No new orchestration features. No new dependencies.
- After implementation: commit, push, stop.
