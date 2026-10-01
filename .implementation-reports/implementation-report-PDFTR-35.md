# Implementation Report

## Ticket

PDFTR-35 — Pi sequential two-agent runner MVP.

## Workflow

- Level: 2 (new orchestration script, subprocess boundary, sequential two-agent workflow, CI tests).
- Graphify: used (`graphify update .`; `graphify query` confirmed `scripts/agent_cycle.py` is an
  isolated community with test-only dependants).
- CRG: used (`code-review-graph update --brief` before and after; `detect-changes --brief`).
- Working tree before changes: clean after the pre-existing, unrelated
  `.github/workflows/opencode.yml` was locally excluded via `.git/info/exclude` with explicit user
  direction. That file was never modified, staged, or committed.

## Scope

- Modules: new `scripts/pi_ticket_cycle.py`; new `tests/test_pi_ticket_cycle.py`; docs
  (`README.md`, `CHANGELOG.md`, `knowledge/wiki/workflows/development-workflow.md`,
  `knowledge/wiki/log.md`); ticket artifacts.
- Pipeline stages: none. The runner orchestrates the repository agent cycle; it does not touch
  inspect, extract, translate, render, OCR, or batch code.
- Dependency impact: none. Standard library only; `pyproject.toml` and `uv.lock` unchanged.
- Model/device impact: none. Provider/model/tool names are configuration values.
- OCR impact: none.
- CLI/public contract impact: new standalone developer command
  (`uv run python scripts/pi_ticket_cycle.py <TICKET>`); no change to the `pdftranslate` CLI.
- PDF/output integrity impact: none.
- `scripts/agent_cycle.py` was not modified: no missing integration seam was proven.

## Investigation

- Current behavior: `scripts/agent_cycle.py` validates and records two-agent state but does not
  launch agents; a human drives every transition.
- Expected behavior: one command drives the proven sequence — Pi implementer, deterministic handoff,
  exact-SHA read-only Pi reviewer, structured review recording, one optional fix/review retry, then
  stop for human review.
- Root cause or implementation gap: only the process-sequencing layer was missing; the state
  machine already exists.
- Main symbols: `run_cycle`, `execute`/`SubprocessExecutor`, `RoleConfig`/`RunnerConfig`,
  `extract_review_json`, `_implementer_prompt`, `_reviewer_prompt`, `resolve_executable`.
- Configuration/schema: no schema change; `.agent-cycle/<TICKET>/` continues to be validator-owned
  and Git-ignored.
- Expected blast radius: `scripts/` and `tests/` plus documentation; no package or cross-stage
  impact.

## Changes

- Added `scripts/pi_ticket_cycle.py`:
  - imports `scripts.agent_cycle` functions as the only workflow authority;
  - `RoleConfig`/`RunnerConfig` hold provider, model, and tool names as configuration;
  - `SubprocessExecutor` uses `subprocess.Popen` + `communicate` (no `shell=True`), captures
    stdout/stderr, writes ignored diagnostic logs, resolves `pi` via `shutil.which` with an
    actionable error, adapts `.cmd`/`.bat`/`.ps1` shims, and converts Ctrl+C into a clean
    `RunnerCancelled`;
  - `extract_review_json` requires exactly one unambiguous JSON result (sentinel, single fence, or
    whole-stdout object) and fails closed;
  - the loop calls `initialize_cycle`, `begin_implementation`, `record_handoff`, `begin_review`,
    `record_review`, and `stop_cycle`; it never reimplements their rules;
  - abnormal exit, dirty tree, missing handoff, stale SHA, malformed/wrong reviewer payload, and
    cancellation all stop the cycle and return control to the human;
  - no automatic PR, merge, fetch, stash, reset, clean, checkout, or retry loop.
- Added `tests/test_pi_ticket_cycle.py` with a deterministic `FakePi` executor and isolated real Git
  repositories under `temp/`. It covers all 14 ticket cases plus extraction unit coverage. Tests
  never invoke Pi, providers, network, models, CUDA, or OCR.
- Updated `README.md`, `CHANGELOG.md`, and the affected Wiki pages and log.

## Graph and source validation

- Graphify findings: before the refresh the graph lacked `scripts/agent_cycle.py`; after
  `graphify update .` the coordination module appears as isolated community 13 with test-only
  dependants. Source inspection confirms no `src/pdftranslate` importer.
- CRG findings: pre-change update refreshed 15 files; post-change `detect-changes --brief` reports
  5 changed files, 0 changed functions/classes, 0 affected flows, risk 0.00.
- Source/configuration validations: `scripts/agent_cycle.py` read end to end; its exported
  functions, manifest/handoff keys, review validation, and two-round limit were reused verbatim.
- Discrepancies: none. Graph coverage of the new script is limited because it is a script rather
  than package code; the source and tests are authoritative.

## Post-change impact

- CRG updated: yes.
- Blast radius: `scripts/pi_ticket_cycle.py`, `tests/test_pi_ticket_cycle.py`, docs, ticket
  artifacts. No `src/pdftranslate` symbols changed.
- Unexpected dependants: none.
- Compatibility or migration concerns: none. No schema, dependency, CLI, cache, or filesystem
  contract changed.

## Validation

- Focused tests: `uv run pytest tests/test_pi_ticket_cycle.py --no-cov -q` — 28 passed. (`--no-cov`
  avoids the repository-wide 80% coverage gate when running one file.)
- Full tests: `.\scripts\check.ps1` — `418 passed, 1 skipped`, total coverage 89.10%.
- Ruff format: `271 files already formatted`.
- Ruff lint: `All checks passed!`.
- mypy: `Success: no issues found in 97 source files`.
- Bootstrap/check scripts: `.\scripts\check.ps1` completed successfully.
- CLI smoke tests: not applicable to the package CLI; the runner CLI parser and command
  construction are covered by unit tests (provider, model, and read-only tool assertions).
- Real-model validation: not run (not required; ticket explicitly forbids real providers in
  tests/CI).
- CUDA validation: not run (not applicable).
- PDF manual validation: not applicable.
- OCR integration validation: not applicable.
- Wiki lint: `uv run python scripts/project_wiki/wiki_lint.py` — 15 pages, 110 links, 0 errors,
  0 warnings, OK.

## Documentation

- Updated: `README.md` (one-command runner), `CHANGELOG.md` (`Added` entry),
  `knowledge/wiki/workflows/development-workflow.md` (runner boundary and source list),
  `knowledge/wiki/log.md` (dated entry and source).
- Not required because: no package, schema, translation, rendering, OCR, model, or cache behavior
  changed.

## Remaining risks

- Real Pi end-to-end execution (provider authentication, exact CLI behavior, `.cmd`/`.ps1` shim
  handling on the maintainer workstation) is not exercised by deterministic tests; it is the next
  practical validation and is explicitly outside this ticket's CI scope.
- The implementer handoff check values (`focused_tests`, `full_tests`, `check_ps1`) are claims
  accepted by the validator, as in the existing contract; the runner does not re-run the quality
  gate inside the child process, by design.
- The implementation commit SHA is authoritative only in the validator-owned
  `.agent-cycle/PDFTR-35/handoff.json`, because a tracked report cannot contain its own commit SHA.
