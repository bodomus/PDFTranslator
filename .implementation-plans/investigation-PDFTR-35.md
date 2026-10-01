# Investigation — PDFTR-35 Pi sequential two-agent runner MVP

## Ticket

PDFTR-35 — Pi sequential two-agent runner MVP. Automate the proven PDFTR-33/PDFTR-34
manual two-agent sequence with one command while keeping `scripts/agent_cycle.py` as the
only authority for workflow state, exact-SHA binding, rounds, ownership, and fail-closed
safety.

## Workflow classification

- Level 2 (structural/operational change: new orchestration script, subprocess boundary,
  two-agent sequencing, CI-relevant tests).
- Graphify: available and used (`graphify update .`, `graphify query`), with the coordination
  symbols now present in community 13. Source remains authoritative.
- CRG: available and used (`code-review-graph update --brief`; graph refreshed).
- Baseline: branch `master`, HEAD `aab58cc`, clean except one pre-existing untracked file
  `.github/workflows/opencode.yml` (unrelated), which was locally excluded via `.git/info/exclude`
  per explicit user direction so the agent-cycle clean-tree gate is meaningful.

## Current behavior

`scripts/agent_cycle.py` is a deterministic validator/recorder, not an orchestrator. A human
runs `init`, `begin-implementation`, `handoff`, `begin-review`, `record-review`, `status`, and
`stop` by hand. PDFTR-33/PDFTR-34 proved this sequence works but required manual driving. There
is no single command that launches the implementer, waits for it, validates the handoff, starts
the exact-SHA read-only reviewer, persists the reviewer JSON, and stops after round two.

## Expected behavior

One command, `uv run python scripts/pi_ticket_cycle.py <TICKET>`, runs exactly:

```text
agent_cycle preflight/init
→ Pi implementer (deepseek / deepseek-v4-pro)
→ wait for exit
→ deterministic Git + handoff validation
→ exact SHA
→ agent_cycle begin-review
→ Pi reviewer (openai-codex / gpt-6.1-sol, read-only tools)
→ validate structured reviewer JSON
→ agent_cycle record-review
   ├─ PASS → PASSED → stop / human
   ├─ BLOCKED → stop
   └─ CHANGES_REQUIRED → implementer again (new SHA) → reviewer round 2
        └─ round 2 CHANGES_REQUIRED → terminal STOPPED (never a third round)
```

No automatic PR, merge, fetch, stash, reset, clean, checkout, or retry loop.

## Root cause / implementation gap

The state machine exists and is trustworthy, but the process sequencing layer does not. PDFTR-35
adds only that missing layer.

## Investigation answers (ticket questions 1–12)

1. **Reused `agent_cycle.py` functions.** `validate_ticket_id`, `cycle_directory`,
   `collect_git_facts`, `initialize_cycle`, `begin_implementation`, `record_handoff`,
   `begin_review`, `record_review`, `stop_cycle`, `cycle_status`, and `CycleError`. The runner
   never re-derives or mutates manifest/handoff state itself.

2. **Import functions, not spawn the CLI.** Direct import is simpler and safer: one interpreter,
   typed `CycleError` propagation instead of parsing CLI exit codes and stderr, no argument
   drift, and the same in-process validation used by `tests/test_agent_cycle.py`. `scripts` is a
   package (`scripts/__init__.py`), so `from scripts.agent_cycle import ...` is a stable boundary.
   The only file-writing indirection is the role-input JSON, which `agent_cycle` already accepts
   via `--file`/path parameters.

3. **Thinnest runner boundary.** The runner owns process order only: choose the role from the
   manifest state returned by `agent_cycle`, build the Pi command, wait, capture exit/output,
   and hand results back to `agent_cycle`. It never computes SHA meaning, round limits, verdict
   validity, ownership, or cleanliness; those come from `collect_git_facts` and the
   `begin_*`/`record_*`/`stop`/`status` functions.

4. **Exact Pi CLI arguments.**
   - Implementer: `pi --provider deepseek --model deepseek-v4-pro -p <prompt>` (coding tools
     unrestricted; implementer is the only project-file writer).
   - Reviewer: `pi --provider openai-codex --model gpt-6.1-sol --tools read,grep,find,ls -p <prompt>`
     (technically read-only; no `write`, `edit`, or `bash`).

5. **stdout/stderr and logs.** `subprocess.Popen(..., stdout=PIPE, stderr=PIPE, text=True,
   shell=False)` then `communicate()`. Captured stdout is parsed for the reviewer JSON; both
   streams are written to ignored diagnostic logs
   `.agent-cycle/<TICKET>/pi-implementer-round-<n>.log` and `pi-reviewer-round-<n>.log`.

6. **Unambiguous reviewer JSON extraction.** Require one sentinel-delimited block:
   `<<<AGENT_CYCLE_REVIEW_JSON>>>` … `<<<END_AGENT_CYCLE_REVIEW_JSON>>>`. Fall back to exactly one
   ```` ```json ```` fence, then to a whole-stdout object. Zero or multiple candidates, or invalid
   JSON, fail closed. The parsed object is persisted by the runner and passed to the real
   `record_review`, so `agent_cycle` re-validates ticket, round, SHA, verdict, findings, and
   blocked reason.

7. **Windows/Linux cancellation.** `Popen` + `communicate()`; on `KeyboardInterrupt` terminate the
   child, then kill after a short grace, and raise `RunnerCancelled`. Because the runner waits for
   each child to fully exit before it even builds the next command, cancellation cannot start the
   next role. No `shell=True`, no signal handling that differs per platform.

8. **Replacing real Pi in tests.** Inject a `PiExecutor` protocol. Production uses
   `SubprocessExecutor`, which resolves `pi` through `shutil.which` and raises an actionable
   `RunnerError` when missing. Tests inject a scripted fake that records commands, simulates
   commits/handoff/JSON and exit codes, on isolated real Git repositories under `temp/`.

9. **Round-1 findings to the second implementer.** After `record_review` writes
   `review-1.json`, the runner reads that artifact and embeds its `findings` array in the round-2
   implementer prompt. `record_handoff` independently rejects a round-2 handoff whose SHA equals
   the round-1 reviewed SHA.

10. **Standard-library only.** Yes. `argparse`, `dataclasses`, `json`, `shutil`, `subprocess`,
    `pathlib`, `typing`, and `collections.abc`. `agent_cycle.py` is already stdlib-only; no new
    runtime or dev dependency is introduced.

11. **Expected blast radius.** New `scripts/pi_ticket_cycle.py` and
    `tests/test_pi_ticket_cycle.py`; documentation in `README.md`, `CHANGELOG.md`, and affected
    `knowledge/wiki/` pages; ticket artifacts. No change to `src/pdftranslate`, the CLI, JSON
    schemas, translation, rendering, OCR, batch, model, or cache code. No dependency or lockfile
    change. `scripts/agent_cycle.py` is not modified: no missing seam was proven — all required
    transitions already exist.

12. **Reusable helpers.** `scripts/agent_cycle.collect_git_facts`/`_run_git` for Git facts;
    `tests/test_agent_cycle.py` patterns (`_git`, isolated `git_repo` fixture, `_write_json`,
    `_commit_attempt`) are the model for the new tests. `tests/conftest.py` PDF fixtures are not
    needed.

## Architectural findings (Graphify + source)

- `scripts/agent_cycle.py` is an isolated community (community 13) with test-only dependants;
  nothing under `src/pdftranslate` imports it. Adding a sibling importer does not cross package
  or pipeline boundaries.
- No CLI/console-script registration is involved; the runner is invoked as a script/module, so
  Typer, settings, schemas, PDF, model, cache, and OCR code are untouched.
- The runner has no reachability from `src/pdftranslate`, so it cannot affect source-PDF safety,
  output-PDF integrity, model loading, memory use, or cache correctness.

## Safety assessment

- Source PDFs, translation quality, segmentation, batching, protected tokens, model lifecycle,
  CUDA/CPU selection, OCR dependency detection, and cache/resume behavior are unaffected.
- New filesystem writes are limited to ignored `.agent-cycle/<TICKET>/` logs and role inputs and
  to whatever the implementer Pi itself is instructed to do (project files, commits).
- The runner performs no destructive Git operations and stops on unexpected Git state.

## Validation plan

- Focused: `uv run pytest tests/test_pi_ticket_cycle.py -q`.
- Full repository: `uv run pytest -q`, `uv run ruff format --check .`, `uv run ruff check .`,
  `uv run mypy src`, `uv run python scripts/project_wiki/wiki_lint.py`, `.\scripts\check.ps1`.
- Deterministic and offline: tests never invoke real Pi, providers, or network.
- Real-Pi end-to-end is explicitly out of scope for unit/CI validation; it is the next real
  feature ticket's practical test.

## Documentation obligations

- `README.md`: document the one-command runner and its read-only/stop semantics.
- `CHANGELOG.md`: add an `Added` entry.
- `knowledge/wiki/workflows/development-workflow.md`: describe the automated runner boundary.
- `knowledge/wiki/log.md`: append a meaningful entry.
