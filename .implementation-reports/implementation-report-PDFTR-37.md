# Implementation report — PDFTR-37

## Scope and result

Implemented console lifecycle/heartbeat, four explicit runtime role/model presets, and expected
dirty-tree status during active implementation. Only `scripts/pi_ticket_cycle.py` and the status
projection in `scripts/agent_cycle.py` changed in production. PDF translation code, dependencies,
manifest/handoff schemas, transitions, review limits, ownership, and process guards are unchanged.

Task branch: `codex/pdftr-37-console-lifecycle`; base master:
`390467263a4be4961225b7d0b85752b4fd51e02c`. This is implementer delivery only. No Pi/model provider,
independent reviewer, PR, or merge was launched.

## Changes

- A minimal `ProgressReporter` emits flushed ticket/role/provider/model, child exit, validated
  handoff SHA, review round/verdict, and validator-owned terminal-state messages. Second rounds
  and rejected handoffs/reviews are visible. It never receives prompts or captured child output.
- Owned subprocess communication retries on a five-minute timeout, reports elapsed monotonic
  time only while the child is running, sends stdin only once, and retains buffered output.
  No thread, new process owner, retry engine, or live transcript streaming was added.
- Immutable role pairs provide `deepseek-codex`, `codex-deepseek`, `codex-codex`, and
  `deepseek-deepseek`. Explicit CLI fields override their corresponding preset fields;
  unspecified fields retain preset/default values. Unknown choices fail in argparse before
  cycle initialization. Reviewer allowlist validation remains provider-independent.
- Status suppresses only the expected cleanliness mismatch for IMPLEMENTING + active
  implementer + live dirty tree. Text labels the condition and JSON adds
  `working_tree_dirty_expected`. The manifest is never updated by status; other binding errors
  and all clean-tree gates remain strict.

## Investigation and source verification

Required twelve-question investigation and ticket-specific implementation plan were completed
before production edits. ProjectWiki search located the development-workflow page. CRG was
updated before/after implementation; source-verified queries show CLI `main` reaches preset
resolution, executor `run` reaches timed communication, and tests cover both boundaries.
Dependants remained confined to the runner, validator, and their tests. Graphify's older snapshot
was reused for orientation and source-verified; it predates the Pi runner and is not authoritative.
No qualifying module-boundary or new CLI-entry-point change required a broad semantic rebuild.

AST comparisons against the base confirmed nine validator transition/binding/gate functions and
eight process-group/Job Object/cleanup/reviewer-parser helpers are unchanged. Runtime safety
tests cover process descendants, suspended Windows containment, setup/resume interruption,
I/O failures, cancellation, and heartbeat callback failure. The existing two-round regression
tests continue to pass.

## Validation performed on Windows / Python 3.12.10

- Focused: `uv run pytest tests/test_pi_ticket_cycle.py tests/test_agent_cycle.py`
  with runtime outputs under `temp/`: **125 passed, 2 skipped** (POSIX-only cases).
- Full `scripts/check.ps1`: **486 passed, 3 skipped**, coverage **89.10%**.
- ProjectWiki lint: 15 pages, 113 links, no errors/warnings.
- Ruff format/check: clean. Mypy: no issues in 97 source files.
- CLI help exposes all four presets; live status shows expected active implementer dirtiness.
- `git diff --check`: clean. Deterministic tests verify lifecycle order, no transcript disclosure,
  same-model independent invocations, role swapping, override precedence, pre-state rejection,
  heartbeat retry/input ownership, and strict non-implementation status/cleanliness gates.

The initial focused run found a test fake still assuming provider identity/old reviewer wording;
the fake now routes by the actual role prompt and the final focused/full runs above pass.

## Documentation and delivery

README and CHANGELOG explain lifecycle visibility, preset selection/precedence, independent
role contexts, and expected dirty status. Only the affected development-workflow Wiki and its
log were updated. Ticket text is retained under `Tickets/PDFTR-37.md` and attached in YouTrack.
Completion summary: `reviews/review-PDFTR-37.md` (implementer work, not a reviewer verdict).
Unrelated user files are excluded from the implementation commit; clean-tree handoff enforcement
is not weakened to accommodate them.

## Remaining validation

This local gate does not establish Ubuntu or remote Windows CI success. The existing CI matrix
runs on push; its actual result must be checked separately. No real provider/model integration
is necessary for this workflow-only scope. Independent exact-SHA review and merge remain human
decisions; no reviewer is automatically started by this delivery.

## Windows CI coverage follow-up (2026-10-03)

The original SHA `468db7977ecb2c15aea1fc45a254abc8589040b3` failed Windows CI after all
486 tests passed (3 skipped), inside pytest-cov's final combine. Ubuntu passed. Verified run:
https://github.com/bodomus/PDFTranslator/actions/runs/37124132255

Exact new producers: both parameterizations (`KeyboardInterrupt`, `OSError`) of
`test_heartbeat_failure_cleans_owned_process_tree`, through `_make_tree_shim` -> `spawn_tree.py`
-> Python `-c` grandchild. With coverage 7.15.2 / pytest-cov 6.3.0, preserved diagnostic data
identified child PIDs 42212 and 52736, and grandchildren 60628 and 62732; every file had SQLite
`has_arcs=0`. Reading each real file with `CoverageData` and updating branch data reproduced
`DataError: Can't combine statement coverage data with branch data` exactly. Older cancellation
and I/O failure fixtures use the same path and also produce incompatible empty data.

Cause: pytest-cov 6's `set_env` exports `COV_CORE_CONFIG` as the automatic-config sentinel when
its default `.coveragerc` does not exist; `COV_CORE_BRANCH` is only set for an explicit CLI branch
option. The parent reads `branch=true` from `pyproject.toml`; service children running in
`temp/pi-cycle-tests/<id>` cannot find that config, so embedded coverage starts with `branch=False`.
Even service children executing no package lines can save data with statement metadata. Empty
parallel data share a hash, so combine's deduplication/file ordering can mask the mismatch; a
local full baseline passed while the preserved child files still reproduced the incompatibility.
This explains why the earlier local gate did not establish Windows CI compatibility.

Fix: one function-scoped autouse fixture in `tests/test_pi_ticket_cycle.py` removes inherited
`COV_CORE_*` and `COVERAGE_PROCESS_*` startup variables with pytest's reversible monkeypatch.
Only these service fixtures opt out; measurement in the already-running pytest parent continues.
Other modules' real package subprocess coverage is retained. No production file, lockfile, CI
configuration, coverage policy, state machine, process-tree semantics, or cleanup path changed.
No `coverage erase` workaround is used.

Regression: recreate inherited startup variables, run a normal-exit Python child and grandchild
through the actual `SubprocessExecutor` and platform shim, assert both have no active coverage or
startup variables, no `.coverage*` artifacts appear, and the parent's Coverage instance and branch
option remain unchanged. A temporary diagnostic plugin disabling only isolation makes the test
fail with `active=True`; isolation makes it pass. Runtime diagnostics remain ignored under `temp/`.

Repository intelligence: ProjectWiki development workflow searched and source-verified; scoped
CRG callers identify `_spawn_tree_script`'s 12 process-tree test callers. Graphify's existing
2026-10-01 snapshot predates this runner; it is orientation only and was not rebuilt for this
test-only change. Production and domain boundaries remain unchanged.

Final follow-up validation:

- Focused real service-child diagnostic and both heartbeat error variants: 3 passed.
- Regression negative control: fails with child coverage active when isolation is disabled.
- `uv run pytest`: 487 passed, 3 skipped; branch coverage 89.10% (133.70 s).
- `scripts/check.ps1`: Wiki 15 pages / 114 links, no errors/warnings; Ruff format/check clean;
  mypy clean for 97 source files; 487 passed, 3 skipped; branch coverage 89.10% (132.85 s).
- Post-change CRG scope: one test file, no dependent production files; helper callers are
  the autouse fixture and its diagnostic. `git diff --check` clean.

The follow-up is committed/pushed on `codex/pdftr-37-console-lifecycle`. This report establishes
local Windows validation; remote CI for the follow-up SHA is not claimed. No reviewer, PR,
merge, or agent-cycle transition is launched or synthesized by this fix.
