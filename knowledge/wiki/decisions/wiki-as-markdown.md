---
title: ProjectWiki uses Git-tracked Markdown
type: decision
status: active
created: 2026-09-17
updated: 2026-09-17
tags:
- project-wiki
- markdown
- git
- phase-1
sources:
- ../../../Tickets/PDFTR-19.md
- ../../raw/sources/llm-wiki-references.md
related:
- ../overview.md
- ../constraints/raw-sources-immutable.md
- ../testing/pilot-evaluation.md
---

# ProjectWiki uses Git-tracked Markdown

## Decision

Phase 1 stores canonical Wiki knowledge as ordinary Markdown with small YAML frontmatter blocks,
relative links, and Git history. Validation and search use Python's standard library.

## Why

The format stays readable in GitHub, IDEs, plain text editors, and coding agents. It fits the
existing Python/uv repository without adding runtime infrastructure, makes changes reviewable as
normal diffs, and keeps source traceability explicit.

## Rejected for Phase 1

- vector databases and embeddings;
- Qdrant, Chroma, Elasticsearch, Neo4j, PostgreSQL, or a second history database;
- cloud services, LLM APIs, MCP servers, and QMD;
- background daemons, automatic graph generation, and automatic whole-Wiki rewriting;
- bulk import of historical tickets, reports, conversations, or source code.

These are deferred, not endorsed future work. The [pilot](../testing/pilot-evaluation.md) must first
show concrete gaps that a more complex Phase 2 would solve.

## Consequences

Agents must curate pages and provenance deliberately. Lexical search can miss synonyms, and lint
can validate structure but not truth. Source/tests/runtime evidence therefore remain authoritative.
