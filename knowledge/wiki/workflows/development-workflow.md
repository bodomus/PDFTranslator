---
title: Development workflow
type: workflow
status: active
created: 2026-09-17
updated: 2026-09-17
tags:
- development
- tickets
- validation
sources:
- ../../../AGENTS.md
- ../../../.codex/PRE_TICKET_WORKFLOW.md
- ../../../scripts/check.ps1
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

## Completion

1. Run focused validation, then the full `scripts/check.ps1` quality gate.
2. Refresh CRG and inspect the final blast radius; refresh Graphify only for qualifying structural
   architecture changes.
3. Produce the ticket implementation report and review.
4. Update only affected Wiki pages, append a meaningful log entry, and run Wiki lint.
5. Update the external ticket and attach required artifacts when authorized.
