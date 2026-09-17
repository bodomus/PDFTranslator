---
title: Raw source evidence is immutable
type: constraint
status: active
created: 2026-09-17
updated: 2026-09-17
tags:
- sources
- provenance
- immutability
sources:
- ../../../Tickets/PDFTR-19.md
- ../../AGENTS.md
related:
- ../overview.md
- ../workflows/wiki-maintenance.md
- ../decisions/wiki-as-markdown.md
---

# Raw source evidence is immutable

Files already stored under `knowledge/raw/` are evidence and must not be rewritten by normal Wiki
maintenance. New evidence may be added when explicitly required, but an agent must not alter
history merely to make a Wiki summary consistent.

## Canonical sources stay canonical

When a tracked ticket, implementation report, review, document, test, or source file already exists,
Wiki pages should reference it in place instead of creating a second mutable copy. `knowledge/raw/`
is for stable evidence that genuinely needs to live there, such as a concise external-research note.

## Conflicts and uncertainty

If evidence conflicts, cite both sides and mark the Wiki claim unresolved until source or runtime
verification resolves it. If a claim is inferred rather than directly stated, label it as an
inference. Current executable evidence wins over a stale Wiki summary.
