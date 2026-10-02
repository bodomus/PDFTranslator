---
title: Development workflow
type: workflow
status: active
created: 2026-09-17
updated: 2026-10-01
tags:
- development
- tickets
- validation
sources:
- ../../../AGENTS.md
- ../../../.codex/PRE_TICKET_WORKFLOW.md
- ../../../scripts/check.ps1
- ../../../scripts/agent_cycle.py
- ../../../scripts/pi_ticket_cycle.py
- ../../../.agents/skills/two-agent-ticket-workflow/SKILL.md
related:
- ../index.md
- wiki-maintenance.md
- ../testing/wiki-validation.md
---

# Development workflow

Non-trivial work follows the repository intelligence workflow before implementation. The current
source tree, tests, dependency files, runtime evidence, and maintained documentation are
authoritative; Graphify and CRG guide discovery but do not replace source verification.

## Before implementation

1. Read repository and nested instructions, the ticket, and the [Wiki index](../index.md).
2. Record Git branch, commit, working-tree state, Python, and uv baselines.
3. Classify the workflow level and protect unrelated user changes.
4. Query ProjectWiki, Graphify, and CRG as applicable, then verify findings in source.
5. For Level 2 work, write ticket-scoped investigation and implementation-plan artifacts.

## During implementation

- Keep scope ticket-focused and dependencies explicit.
- Add tests for behavior changes and preserve platform/runtime safety constraints.
- Update user documentation and changelog for visible behavior.
- Do not update Wiki pages until implementation knowledge is known.

## Sequential two-agent tickets

Tickets that explicitly use the agent cycle add repository-local coordination under the ignored
`.agent-cycle/<TICKET>/` root. `manifest.json` is authoritative system state. `handoff.json` has
three ownership sections: validator-derived `system`, claims from `implementer`, and an exact-SHA
result from `reviewer`. Concrete LLM products may be assignment metadata but never state-machine
roles or ownership keys.

The implementer is the single repository writer. The reviewer runs only after handoff, checks the
recorded SHA read-only, and returns `PASS`, `CHANGES_REQUIRED`, or `BLOCKED`. A new implementation SHA makes the
earlier result stale. The validator enforces one active role, clean-tree review gates, immutable
review artifacts, exact repeated-finding detection, and at most two automated review rounds.
Round-two changes required stops for human inspection. Final review and merge remain human-owned.

`scripts/agent_cycle.py` validates and records this state; it is not an orchestrator and does not
launch agents, fetch, retry, merge, or create pull requests. PDFTR-33 is the explicit bootstrap
exception in which Codex implemented the validator before the post-ticket role boundary existed.
Recovery is conservative: invalid or corrupt state fails closed rather than being guessed or
silently regenerated.

`scripts/pi_ticket_cycle.py` automates that validated sequence for explicitly assigned tickets. It
imports the validator rather than reimplementing it: it initializes or reuses a `NEW` cycle, runs
the Pi implementer, validates the handoff and exact SHA from Git plus `agent_cycle`, runs a
technically read-only Pi reviewer on that SHA, and records the reviewer JSON through
`record-review`. It allows one fix/review retry with a required new SHA, stops on abnormal exit,
a dirty tree, or malformed/wrong-SHA output, and returns control to the human after `PASS`,
`BLOCKED`, or the two-round limit. Ownership is explicit: the implementer writes project files and
only its role-owned handoff input, the reviewer returns one structured JSON object on stdout and
never writes a coordination file, and the runner persists that result into ignored `.agent-cycle`
state. The parser accepts exactly one supported review envelope and fails closed otherwise. The
runner owns every child process tree and terminates descendants through a Windows Job Object or a
saved POSIX process group on success, cancellation, or any post-spawn failure. Provider, model, and
tool names are configuration; deterministic tests replace Pi and never contact providers or the
network.

## Completion

1. Run focused validation, then the full `scripts/check.ps1` quality gate.
2. Refresh CRG and inspect the final blast radius; refresh Graphify only for qualifying structural
   architecture changes.
3. Produce the ticket implementation report and review.
4. Update only affected Wiki pages, append a meaningful log entry, and run Wiki lint.
5. Update the external ticket and attach required artifacts when authorized.
