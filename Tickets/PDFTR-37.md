# PDFTR-37 — Console lifecycle output and role/model presets

Source: https://bodomus.youtrack.cloud/issue/PDFTR-37

# Console lifecycle output and role/model presets

## Summary

Improve `scripts/pi_ticket_cycle.py` usability without changing its orchestration semantics.

This ticket has two goals:

1. provide visible lifecycle/progress output while a Pi child is running;

2. make implementer/reviewer provider+model selection easier to switch through explicit presets/configuration.

This is workflow infrastructure only.

Do not change PDF translation behavior.

Do not add new orchestration features.

Do not change the two-round state machine.

**---**

# Motivation

The first real end-to-end run exposed a usability problem:

```text

uv run python scripts/pi_ticket_cycle.py PDFTR-36

```

could sit silently for many minutes while the implementer was actively working.

The only way to determine whether the process was alive was to open a second terminal and run:

```powershell

uv run python scripts/agent_cycle.py status PDFTR-36

```

That is poor operator visibility.

At the same time, the current runner already supports separate implementer/reviewer provider and model arguments, but changing role assignments is too verbose for repeated experiments.

We need a small usability layer, not a new orchestration architecture.

**---**

# Goals

## G1 — Console lifecycle output

The runner must emit concise lifecycle messages for major state transitions.

Expected style:

```text

[PDFTR-37] cycle initialized

[PDFTR-37] implementer started: deepseek / deepseek-v4-pro

[PDFTR-37] implementer running... 5m

[PDFTR-37] implementer finished: exit 0

[PDFTR-37] validating implementer handoff...

[PDFTR-37] handoff accepted: \<sha>

[PDFTR-37] reviewer started: openai-codex / gpt-6.1-sol

[PDFTR-37] reviewer running... 5m

[PDFTR-37] reviewer finished: exit 0

[PDFTR-37] review round 1: PASS

[PDFTR-37] cycle PASSED

```

Exact wording may differ, but the lifecycle must be obvious.

### Required lifecycle events

At minimum emit:

```text

cycle initialization

implementation phase start

implementer provider/model

periodic implementer heartbeat

implementer process exit

handoff validation start/result

review phase start

reviewer provider/model

periodic reviewer heartbeat

reviewer process exit

review validation result

second implementation/review round start when applicable

STOPPED / PASSED final state

```

### Heartbeat

While a Pi child process is still running, emit a periodic message.

Recommended interval:

```text

5 minutes

```

The interval should be a constant or simple internal setting, not a new CLI subsystem.

Do not print one line every few seconds.

### No chain-of-thought / agent transcript

Do not stream model reasoning.

Do not dump full child stdout/stderr live.

Existing logs remain the detailed diagnostic source.

Console output should expose lifecycle only.

**---**

## G2 — Role/model presets

Provider and model assignment must remain role-based and configurable.

The runner must continue to treat:

```text

implementer

reviewer

```

as workflow roles, not product names.

Add an ergonomic preset mechanism so common combinations can be selected without repeating multiple CLI arguments.

At minimum support these presets:

```text

deepseek-codex

codex-deepseek

codex-codex

deepseek-deepseek

```

Suggested meanings:

```text

deepseek-codex:

  implementer = deepseek / deepseek-v4-pro

  reviewer    = openai-codex / gpt-6.1-sol

codex-deepseek:

  implementer = openai-codex / gpt-6.1-sol

  reviewer    = deepseek / deepseek-v4-pro

codex-codex:

  implementer = openai-codex / gpt-6.1-sol

  reviewer    = openai-codex / gpt-6.1-sol

deepseek-deepseek:

  implementer = deepseek / deepseek-v4-pro

  reviewer    = deepseek / deepseek-v4-pro

```

Same-model presets still run as separate Pi child processes and separate contexts.

**---**

# CLI behavior

Add a simple option such as:

```powershell

uv run python scripts/pi_ticket_cycle.py PDFTR-38 --preset codex-codex

```

Manual role overrides must remain possible.

Recommended precedence:

```text

explicit role/provider/model CLI override

&nbsp;&nbsp;&nbsp;&nbsp;>

preset

&nbsp;&nbsp;&nbsp;&nbsp;>

existing defaults

```

Example:

```powershell

uv run python scripts/pi_ticket_cycle.py PDFTR-38 `

  --preset codex-codex `

  --reviewer-model gpt-6.1-sol

```

If the explicit override equals the preset value, that is fine.

Unknown preset names must fail clearly before cycle state changes.

Do not introduce YAML/JSON configuration files in this ticket unless investigation proves they are strictly necessary.

**---**

# Reviewer tool safety

Role/model swapping must not weaken reviewer tool restrictions.

Regardless of provider/model:

```text

reviewer tools = read,grep,find,ls

```

by default.

A same-model setup such as:

```text

implementer = Codex

reviewer = Codex

```

must still run the reviewer with the existing read-only allowlist.

Do not couple reviewer write permissions to model identity.

**---**

# Same-model independence

When implementer and reviewer use the same provider/model:

```text

codex-codex

deepseek-deepseek

```

they must still be launched as independent Pi processes with separate prompts/contexts.

Do not reuse one interactive Pi session between roles.

Do not share hidden conversation state.

This ticket does not claim that same-model review is equivalent to cross-model review; it only makes the configuration possible.

**---**

## G3 — Status output during active implementation

The current `agent_cycle.py status` behavior may report:

```text

ERROR: working-tree cleanliness differs from manifest

```

while:

```text

State: IMPLEMENTING

Active agent: implementer

Working tree: dirty

```

During active implementation, a dirty working tree is expected.

Improve status reporting so this expected transient state is not presented as a false error.

Expected style:

```text

State: IMPLEMENTING

Active agent: implementer

Working tree: dirty (expected during implementation)

```

Do not weaken clean-tree enforcement at actual workflow gates.

This is presentation/status logic only.

A dirty tree must still fail where the workflow currently requires cleanliness:

```text

initialization

handoff

review start

terminal validation

```

**---**

# Architecture constraints

Do not duplicate state-machine logic from `scripts/agent_cycle.py`.

`pi_ticket_cycle.py` remains a process sequencer.

`agent_cycle.py` remains authoritative for:

```text

ticket binding

branch

HEAD

cleanliness gates

active role

handoff

review round

verdict

terminal state

```

Presets are runtime configuration only.

Lifecycle logging must observe state; it must not become a second source of truth.

**---**

# Implementation guidance

Prefer a very small internal abstraction, for example:

```text

RolePreset

ProgressReporter

```

or equivalent.

Do not build:

```text

event bus

logging framework

daemon

TUI

web UI

rich dashboard

persistent telemetry

```

Plain console output is sufficient.

For heartbeat during `subprocess.communicate()`, use a design that preserves process cleanup guarantees from PDFTR-35/35A/35B.

Do not reintroduce child-process leaks.

If `communicate()` must be wrapped by a small polling/thread mechanism, keep ownership deterministic and regression-test cancellation/error cleanup.

**---**

# Investigation

Before implementation, create:

```text

.implementation-plans/investigation-PDFTR-37.md

```

Answer briefly:

1. Where does `SubprocessExecutor.run()` currently block while the child runs?

2. What is the smallest safe way to emit a heartbeat without streaming model output?

3. How can heartbeat logic preserve Windows Job Object and POSIX process-group cleanup guarantees?

4. Where should lifecycle messages be emitted: executor, runner, or both?

5. Which messages require ticket/role/model context unavailable inside the executor?

6. What current CLI options define implementer/reviewer provider/model?

7. What is the simplest preset representation?

8. How should explicit CLI overrides interact with presets?

9. Where is reviewer read-only validation enforced?

10. Why does `agent_cycle.py status` flag dirty tree during active implementation?

11. How can status presentation distinguish expected active-role dirtiness from invalid terminal/gate dirtiness?

12. Which exact files must change?

Do not implement before investigation is complete.

**---**

# Required tests

Add deterministic tests for lifecycle output and presets.

At minimum:

```text

preset deepseek-codex resolves correct roles

preset codex-deepseek resolves correct roles

preset codex-codex resolves correct roles

preset deepseek-deepseek resolves correct roles

explicit role override wins over preset

unknown preset fails before cycle initialization

reviewer read-only tools remain enforced for every preset

same-model roles still launch separate child invocations

```

Lifecycle tests:

```text

implementer start message emitted

reviewer start message emitted

provider/model displayed

child completion message emitted

handoff validation message emitted

review verdict message emitted

final PASSED message emitted

final STOPPED message emitted

heartbeat emitted for a long-running fake child

short child does not require heartbeat

```

Status tests:

```text

IMPLEMENTING + active implementer + dirty tree

→ informational expected state, not false cleanliness error

REVIEWING + reviewer + dirty tree

→ still treated according to existing safety rules

NEW / READY_FOR_REVIEW / PASSED / STOPPED cleanliness validation unchanged

```

Do not call real LLM providers.

Use fake executors / deterministic timing hooks where possible.

Avoid tests that actually sleep five minutes.

**---**

# Console-output rules

Console output must not include:

```text

auth tokens

provider credentials

full prompts

full agent stdout/stderr

translated document content

hidden reasoning

```

It may include:

```text

ticket

role

provider

model

elapsed duration

exit code

SHA

round

verdict

state

```

**---**

# Example target UX

Example first round:

```text

[PDFTR-38] cycle initialized

[PDFTR-38] implementer started: openai-codex / gpt-6.1-sol

[PDFTR-38] implementer running... 5m

[PDFTR-38] implementer running... 10m

[PDFTR-38] implementer finished: exit 0

[PDFTR-38] validating handoff...

[PDFTR-38] handoff accepted: 0123456789abcdef...

[PDFTR-38] reviewer started: openai-codex / gpt-6.1-sol

[PDFTR-38] reviewer finished: exit 0

[PDFTR-38] review round 1: CHANGES_REQUIRED

[PDFTR-38] implementer round 2 started: openai-codex / gpt-6.1-sol

...

[PDFTR-38] review round 2: PASS

[PDFTR-38] cycle PASSED

```

Example stop:

```text

[PDFTR-38] review round 2: CHANGES_REQUIRED

[PDFTR-38] cycle STOPPED: review limit reached

```

Exact formatting is flexible.

**---**

# Non-goals

Do not add:

```text

single-agent mode

GitHub PR automation

ChatGPT Work integration

JEV

Pi-Harness

dynamic model routing

automatic model selection

cost tracking

token tracking

parallel agents

worktrees

automatic merge

automatic PR creation

new retry engine

new state-machine transitions

```

Those are future discussions.

**---**

# Quality gate

Run:

```powershell

uv run pytest tests/test_pi_ticket_cycle.py tests/test_agent_cycle.py

uv run pytest

uv run python scripts/project_wiki/wiki_lint.py

.\\scripts\\check.ps1

```

Windows and Ubuntu CI must pass.

**---**

# Completion

PDFTR-37 is complete when:

```text

runner visibly reports lifecycle progress

long-running child has periodic heartbeat

no model transcript/reasoning is streamed

implementer/reviewer models can be swapped by preset

same model can occupy both roles in separate contexts

manual CLI overrides still work

reviewer remains technically read-only

active implementation dirty-tree status is no longer shown as a false error

existing two-round orchestration semantics remain unchanged

existing child-process cleanup guarantees remain intact

full regression suite passes

Windows CI passes

Ubuntu CI passes

```

Final merge remains a human decision.
