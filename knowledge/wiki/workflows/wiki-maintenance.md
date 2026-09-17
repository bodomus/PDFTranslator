---
title: Wiki maintenance workflow
type: workflow
status: active
created: 2026-09-17
updated: 2026-09-17
tags:
- project-wiki
- maintenance
- provenance
sources:
- ../../../Tickets/PDFTR-19.md
- ../../AGENTS.md
related:
- ../index.md
- ../decisions/wiki-as-markdown.md
- ../constraints/raw-sources-immutable.md
- ../testing/wiki-validation.md
---

# Wiki maintenance workflow

Update ProjectWiki only when a non-trivial ticket creates durable knowledge: a component,
architectural decision, constraint, failure mode, integration, important testing rule, or replaced
approach. Formatting and narrowly local changes do not justify Wiki churn.

## Read and search

Start from the curated [index](../index.md). If it does not identify the needed page, run lexical
search over titles, tags, headings, and bodies. Follow related links selectively and open canonical
evidence whenever a claim can affect implementation.

## Update

- Prefer a focused edit to an existing topic page over a new ticket-shaped page.
- Preserve facts, inferences, uncertainty, contradictions, and deprecated approaches distinctly.
- Add or update frontmatter sources with real relative paths; do not invent provenance.
- Add a page to the index only when it improves navigation.
- Append a short log entry only for meaningful knowledge-base changes.
- Never rewrite raw evidence or regenerate the entire Wiki automatically.

## Validate

Run the linter after every Wiki change. Run a representative search when navigation, tags, titles,
or search behavior changed. Keep local and CI validation network-free.

For the next 2–3 non-trivial tickets, implementation reports must also record the concrete pilot
observations listed in [Phase 1 pilot evaluation](../testing/pilot-evaluation.md).
