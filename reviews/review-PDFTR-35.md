# Review — PDFTR-35

## Scope reviewed

PDFTR-35 adds `scripts/pi_ticket_cycle.py`, a sequential Pi implementer/reviewer runner built on the
unchanged `scripts/agent_cycle.py` authority. This file documents implementation readiness; it is
not an agent-cycle PASS artifact and does not replace the read-only exact-SHA reviewer result or the
human merge decision.

## Delivered

- `scripts/pi_ticket_cycle.py`:
  - imports `scripts/agent_cycle` transitions instead of duplicating state, SHA, round, ownership,
    verdict, or cleanliness logic;
  - `RoleConfig`/`RunnerConfig` keep provider/model/tool names as configuration;
  - `SubprocessExecutor` waits for each child, captures stdout/stderr, logs diagnostics under the
    ignored `.agent-cycle/<TICKET>/` root, resolves `pi` through `shutil.which`, and handles
    cancellation cleanly;
  - reviewer output must be exactly one unambiguous JSON object; malformed, wrong-ticket,
    wrong-round, wrong-SHA, invalid-verdict, PASS-with-findings, CHANGES_REQUIRED-without-findings,
    and BLOCKED-without-reason all fail closed;
  - one fix/review retry is supported and requires a new SHA; a third review cannot start;
  - no automatic PR, merge, fetch, stash, reset, clean, or checkout, and no retry loop.
- `tests/test_pi_ticket_cycle.py`: deterministic `FakePi` executor and isolated real Git fixtures
  covering all 14 required cases plus extraction unit tests; no real providers, network, or models.
- Documentation: `README.md`, `CHANGELOG.md`, and affected Wiki pages and log.

## Verification

- `.\scripts\check.ps1` — Wiki lint OK, Ruff format/check OK, mypy OK, `418 passed, 1 skipped`,
  coverage 89.10%.
- Post-change CRG `detect-changes --brief` — 0 changed functions/classes, 0 affected flows.

## Boundary

- `scripts/agent_cycle.py` remains the deterministic authority and was not modified.
- Provider, model, and tool names are configuration, never state-machine concepts.
- Human review and merge remain outside the runner.
