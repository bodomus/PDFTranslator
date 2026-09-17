# LLM Wiki reference review for PDFTR-19

Date reviewed: 2026-09-17

This is a concise external-research note, not a vendored copy of any reference implementation.

## Andrej Karpathy LLM Wiki

Source: <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>

Useful Phase 1 ideas:

- keep raw sources immutable;
- maintain a separate interlinked Markdown Wiki;
- use a compact content index before reading individual pages;
- prefer incremental synthesis over retrieving and re-deriving from every raw source;
- start with simple search before adding embedding infrastructure.

## praneybehl/llm-wiki-plugin

Source: <https://github.com/praneybehl/llm-wiki-plugin>

Useful Phase 1 ideas:

- canonical knowledge stays readable and versionable as Markdown;
- source citations mitigate authoritative-looking drift;
- local lexical search is a valid dependency-free retrieval path;
- validation, compact indexes, bounded pages, and surgical edits protect maintainability.

Deferred from this pilot: plugin packaging, slash commands, embeddings, vector caches, SQLite,
automatic ingest, graph tooling, and skill-evolution workflows.

## Programming-With-Maury/Karpathy-LLM-Wiki

Source: <https://github.com/Programming-With-Maury/Karpathy-LLM-Wiki>

Useful Phase 1 ideas:

- durable agent rules belong beside the Wiki;
- pages should preserve uncertainty and distinguish evidence from interpretation;
- prefer updating existing concise pages over creating duplicates;
- keep the index and knowledge-change log synchronized.

Deferred from this pilot: web UI, domain routing, staging, revision manifests, provider-backed
ingestion, background jobs, and reusable generated query artifacts.

## PDFTranslator adaptation

PDFTR-19 is intentionally smaller than these implementations. It uses the repository's existing
ticket/report/review evidence, `uv` workflow, pytest suite, Graphify, CRG, and quality gates. It adds
only curated Markdown, deterministic schema/link validation, and lexical search.
