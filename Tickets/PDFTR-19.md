# Task: Create ProjectWiki and integrate it into PDFTranslator

We want to introduce a small local knowledge-management subsystem inspired by Andrej Karpathy's LLM Wiki concept.

The first pilot project is **PDFTranslator**.

The goal is NOT to build a large RAG platform or a complex knowledge graph.

The goal is to create a small, transparent, Git-friendly Markdown knowledge base that coding agents can read and maintain between tickets.

---

# Main goals

Create a reusable lightweight subsystem called:

`ProjectWiki`

and integrate its first instance into:

`PDFTranslator`

The Wiki must help future Codex sessions answer questions such as:

- How is this subsystem designed?
- Why was this architectural decision made?
- Which approaches were rejected?
- Which known bugs or failure modes already exist?
- What constraints must not be violated?
- Which ticket/report/source introduced this knowledge?
- What should Codex read before implementing the next ticket?

The Wiki must complement existing project tools.

It must NOT replace:

- source code;
- Git history;
- issue tracker;
- implementation reports;
- Graphify;
- CRG / Code Review Graph;
- tests.

---

# Reference implementations

Before implementation, inspect the ideas and structure from:

1. Andrej Karpathy LLM Wiki gist
   https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

2. `praneybehl/llm-wiki-plugin`

3. `Programming-With-Maury/Karpathy-LLM-Wiki`

Use them only as references.

Do NOT vendor or copy entire repositories into PDFTranslator.

Reuse only concepts that are useful for our minimal implementation.

Prefer simple local files and scripts over new infrastructure.

---

# Architecture principles

Use three conceptual layers:

```text
Immutable sources
        ↓
Generated / maintained knowledge
        ↓
Agent instructions and validation
```

## 1. Raw sources

Raw files are evidence.

They should be considered immutable by the Wiki maintenance process.

Examples:

- tickets;
- implementation reports;
- investigation reports;
- code reviews;
- test reports;
- design notes;
- specifications;
- external research;
- selected Codex reports.

## 2. Wiki

The Wiki stores accumulated project knowledge.

Wiki pages must NOT simply duplicate raw reports.

They should consolidate knowledge from multiple sources.

Example:

BAD:

```markdown
# PDFTR-12

Ticket PDFTR-12 implemented parser changes...
```

GOOD:

```markdown
# PDF text extraction

## Current design

...

## Why

...

## Known failure modes

...

## Constraints

...

## Related pages

...

## Sources

...
```

## 3. Agent rules

Provide instructions telling Codex:

- when to read the Wiki;
- how to search it;
- when to update it;
- what must never be edited automatically;
- how to cite sources;
- how to validate changes.

---

# Required directory structure

Create this under PDFTranslator:

```text
PDFTranslator/
├── knowledge/
│   ├── raw/
│   │   ├── tickets/
│   │   ├── reports/
│   │   ├── reviews/
│   │   ├── tests/
│   │   ├── sources/
│   │   └── decisions/
│   │
│   ├── wiki/
│   │   ├── architecture/
│   │   ├── components/
│   │   ├── workflows/
│   │   ├── decisions/
│   │   ├── constraints/
│   │   ├── known-issues/
│   │   ├── testing/
│   │   ├── integrations/
│   │   ├── index.md
│   │   ├── overview.md
│   │   └── log.md
│   │
│   └── AGENTS.md
│
├── scripts/
│   └── project_wiki/
│       ├── wiki_lint.py
│       ├── wiki_search.py
│       └── README.md
```

If there is a better location consistent with the existing PDFTranslator repository structure, document the reason before changing it.

---

# Wiki page format

Use Markdown with YAML frontmatter.

Example:

```yaml
---
title: PDF text extraction
type: component
status: active
created: 2026-09-12
updated: 2026-09-12
tags:
  - pdf
  - extraction
sources:
  - ../raw/tickets/PDFTR-001.md
related:
  - ../workflows/pdf-processing.md
---
```

Allowed `type` values:

```text
architecture
component
workflow
decision
constraint
failure-mode
testing
integration
index
log
```

Use `index` only for navigation/index pages and `log` only for the Wiki change log.

For normal Wiki pages require these frontmatter fields:

```text
title
type
status
created
updated
tags
sources
```

`related` is optional.

Allowed `status` values should stay deliberately small:

```text
active
deprecated
to-be-documented
```

`index.md` and `log.md` may use the same frontmatter schema with `type: index` and `type: log`.
This keeps lint behavior deterministic and avoids special-case ambiguity.

Do not over-engineer the schema.

---

# Wiki linking

Use normal relative Markdown links.

Example:

```markdown
[PDF extraction](../components/pdf-extraction.md)
```

Do not require a proprietary wiki format.

The Wiki must remain readable in:

- GitHub;
- IDE;
- plain text editor;
- Codex;
- future tooling.

---

# Required initial pages

Create useful starter pages, but do NOT invent undocumented PDFTranslator architecture.

Where project facts are unknown, explicitly mark them as:

```text
Status: To be documented
```

Create at least:

```text
knowledge/wiki/index.md
knowledge/wiki/overview.md

knowledge/wiki/architecture/system-overview.md

knowledge/wiki/workflows/development-workflow.md
knowledge/wiki/workflows/wiki-maintenance.md

knowledge/wiki/decisions/wiki-as-markdown.md

knowledge/wiki/constraints/raw-sources-immutable.md

knowledge/wiki/testing/wiki-validation.md

knowledge/wiki/log.md
```

---

# index.md

`index.md` should act as the primary navigation entry point for agents.

It should contain sections such as:

```markdown
# PDFTranslator Knowledge Base

## Start here

- Overview
- System architecture
- Development workflow

## Architecture

...

## Components

...

## Decisions

...

## Known issues

...

## Testing

...
```

Keep it small and curated.

Do not turn it into a dump of every Markdown file.

---

# overview.md

Explain:

- what PDFTranslator is;
- what ProjectWiki is;
- what belongs in `raw`;
- what belongs in `wiki`;
- what does not belong in the Wiki;
- how future agents should use it.

Only include verified PDFTranslator facts.

Do not hallucinate missing architecture.

---

# Raw source policy

Files under:

```text
knowledge/raw/
```

must be treated as immutable source evidence by normal Wiki maintenance.

Codex may add new source files there when explicitly instructed, but should not rewrite old reports merely to make the Wiki consistent.

Prefer referencing an existing canonical tracked document in place instead of copying it into
`knowledge/raw/` when the repository already has the source, for example:

```text
Tickets/
.implementation-reports/
reviews/
docs/
benchmarks/
```

Avoid creating two mutable copies of the same report.

Use `knowledge/raw/` for source evidence that genuinely needs to live there, stable snapshots,
external research notes, or small source indexes that point to canonical repository documents.

If source information conflicts, record the conflict in the Wiki instead.
Never rewrite historical evidence to make the conflict disappear.

---

# Wiki maintenance rules

Add `knowledge/AGENTS.md`.

It must instruct coding agents to follow this process before implementation:

```text
1. Read repository-level AGENTS.md if present.
2. Read knowledge/wiki/index.md.
3. Search the Wiki for the subsystem being modified.
4. Inspect relevant raw sources when needed.
5. Inspect Graphify / CRG results if they are part of the project workflow.
6. Implement the ticket.
7. Run tests.
8. Produce/update implementation report.
9. Update affected Wiki pages.
10. Run Wiki validation.
```

The Wiki update should happen only after implementation knowledge is known.

---

# Wiki update policy

Codex should update the Wiki when a ticket introduces:

- a new component;
- architectural change;
- important implementation decision;
- new constraint;
- new known failure mode;
- new integration;
- important testing rule;
- replacement of an old approach.

Do NOT update the Wiki for trivial code formatting or small local changes that do not affect project knowledge.

---

# Source traceability

Important claims should point back to source documents.

Sources may be either:

1. immutable files under `knowledge/raw/`; or
2. canonical tracked repository documents that already exist elsewhere.

Example:

```markdown
## Sources

- [PDFTR-12](../../../Tickets/PDFTR-12.md)
- [Implementation report](../../../.implementation-reports/implementation-report-PDFTR-12.md)
```

Do not invent sources.

If a claim is inferred rather than directly stated by a source, label it clearly as an inference.
If two sources conflict, record both and mark the Wiki statement as unresolved until verified.

---

# wiki_lint.py

Create a small Python validator.

Keep dependencies to Python standard library unless there is a compelling reason otherwise.

Validate at minimum:

1. Markdown files in `knowledge/wiki`.
2. Required frontmatter fields.
3. Allowed `type` and `status` values.
4. Duplicate page titles.
5. Broken relative Markdown links.
6. Missing referenced local source files from frontmatter `sources`.
7. Invalid or empty titles.
8. Invalid date values for `created` / `updated` when present.
9. `updated` earlier than `created`.

Only validate local filesystem targets. Do not make lint depend on network access to verify external
URLs.

Return non-zero exit code on validation errors.

Example usage:

```bash
python scripts/project_wiki/wiki_lint.py
```

Output should be concise and suitable for CI.

Example:

```text
ProjectWiki validation

Pages: 12
Links: 31
Errors: 0
Warnings: 2

OK
```

---

# wiki_search.py

Create a simple local search tool.

Do NOT implement embeddings yet.

Use simple text search.

Support something similar to:

```bash
python scripts/project_wiki/wiki_search.py "PDF extraction"
```

Search:

- title;
- tags;
- headings;
- body.

Return ranked or at least clearly grouped matches.

Prefer a simple deterministic implementation.

This is intentionally Phase 1.

---

# Curation and update boundaries

ProjectWiki is curated knowledge, not a generated mirror of the repository.

Do NOT:

- regenerate every Wiki page from source code on each run;
- update every page after every ticket;
- auto-rewrite old pages merely because a newer report exists;
- treat Wiki text as more authoritative than current source/tests;
- make Wiki maintenance a prerequisite for trivial Level 0 changes.

A normal non-trivial ticket should update only the pages whose project knowledge actually changed.

---

# Do NOT add yet

Do not introduce these in the first implementation:

- vector database;
- embeddings;
- Qdrant;
- Chroma;
- Elasticsearch;
- Neo4j;
- PostgreSQL;
- external cloud services;
- LLM API dependency;
- MCP server;
- QMD;
- automatic graph generation;
- automatic rewriting of the entire Wiki;
- background daemons.

These may be evaluated later.

---

# ProjectWiki portability

Although the first implementation lives in PDFTranslator, design the scripts and rules so they can later be reused in:

- DubPipeline;
- PriceCrawler;
- Megascans Library Viewer;
- UE57Editor;
- VoiceTray.

Avoid PDFTranslator-specific assumptions inside generic scripts.

For example:

GOOD:

```text
scripts/project_wiki/wiki_lint.py
```

BAD:

```text
scripts/pdftranslate_wiki_lint.py
```

---

# Git integration

The Wiki should be committed to Git.

Git history is our audit trail.

Do not create a second history database.

Add appropriate `.gitignore` entries only if temporary/cache files are introduced.

The actual Markdown Wiki must remain tracked.

---

# Optional README

Create:

```text
scripts/project_wiki/README.md
```

Explain:

```bash
python scripts/project_wiki/wiki_lint.py

python scripts/project_wiki/wiki_search.py "query"
```

and briefly describe the directory model.

---

# Tests

PDFTranslator already has a Python/pytest test structure, so add focused pytest coverage for
ProjectWiki tooling rather than introducing a separate test framework.

At minimum test:

- valid Wiki passes lint;
- broken link fails;
- invalid type fails;
- duplicate title fails;
- search finds title;
- search finds body text.

Do not introduce a large testing framework solely for this feature if none exists.

A small standard-library `unittest` test suite is acceptable.

---

# CI and existing quality gate

PDFTranslator already has an established repository quality gate.

Prefer integrating Wiki validation into the existing local check flow, ideally through
`scripts/check.ps1`, so local and CI validation stay aligned.

Use the repository's existing `uv` environment when practical, for example:

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

Do not create a second Python environment or duplicate CI workflow logic just for ProjectWiki.

If `scripts/check.ps1` is already called by CI, prefer adding Wiki lint there rather than editing
multiple GitHub Actions workflows.

If integration would make normal checks fragile or require new external dependencies, document the
proposed integration instead of forcing it.

---

# Initial import

Do NOT attempt to ingest every historical PDFTranslator conversation automatically.

For this pilot:

1. inspect the repository;
2. identify existing architecture/design/implementation Markdown files;
3. prefer references to canonical tracked files over copies;
4. place only clearly useful evidence/snapshots under `knowledge/raw` when there is a real reason;
5. preserve originals;
6. create a small initial Wiki from verified facts.

Do NOT bulk-copy `Tickets/`, `.implementation-reports/`, `reviews/`, `docs/`, or historical
conversations into `knowledge/raw`.

Avoid duplicating large amounts of information.

---

# Integration with future ticket workflow

Create or update project documentation so future tickets can include this block:

```markdown
## ProjectWiki update

After implementation:

1. Add relevant implementation evidence to `knowledge/raw/` if needed.
2. Update affected Wiki pages.
3. Record new decisions, constraints, or known failure modes.
4. Update `knowledge/wiki/index.md` only if navigation changed.
5. Append a concise entry to `knowledge/wiki/log.md`.
6. Run:

   python scripts/project_wiki/wiki_lint.py
```

---

# Phase 1 pilot evaluation

This implementation is a pilot. We specifically want to evaluate ProjectWiki over the next
**2–3 real PDFTranslator tickets** before adding semantic search, embeddings, or other infrastructure.

Create:

```text
knowledge/wiki/testing/pilot-evaluation.md
```

Keep it short.

For each of the next 2–3 non-trivial tickets, the implementation report should include a small
`ProjectWiki pilot` section recording:

```text
ticket ID
Wiki pages consulted before implementation
whether raw/canonical sources still had to be opened
missing or stale Wiki knowledge discovered
Wiki pages updated after implementation
whether the Wiki prevented obvious rediscovery of already-known project facts
whether review exposed a Wiki gap
```

Use concrete observations, not vague claims.

Do NOT claim token savings, time savings, or percentage improvements unless those values were
actually measured.

After 2–3 tickets, add a short evaluation to `pilot-evaluation.md`:

```text
keep as-is
adjust
expand
or abandon
```

and explain why.

The purpose of this measurement is to decide whether Phase 2 is justified.

---

# Wiki log

`knowledge/wiki/log.md` is NOT a duplicate Git log.

Use it only for meaningful knowledge-base changes.

Example:

```markdown
## 2026-09-12

- Created initial ProjectWiki structure.
- Added Wiki maintenance rules.
- Added Markdown lint and search tools.
```

---

# Investigation first

Before modifying code or files:

1. inspect the PDFTranslator repository;
2. inspect existing `AGENTS.md`, README, scripts and docs;
3. inspect the reference LLM Wiki implementations;
4. identify conflicts with existing repository conventions;
5. write a concise implementation plan.

Do not blindly create files before understanding the repository.

---

# Deliverables

Follow the existing PDFTranslator repository conventions.

If this work has a ticket ID, store:

```text
.implementation-plans/implementation-plan-<TICKET-ID>.md
.implementation-reports/implementation-report-<TICKET-ID>.md
reviews/review-<TICKET-ID>.md
```

If no ticket ID has been assigned, do not invent one; ask the user before choosing permanent
ticket/report filenames.

The implementation report must contain:

## Summary

What was implemented.

## Files created

List all significant files.

## Files modified

List all significant modified files.

## Design decisions

Especially decisions made while adapting LLM Wiki ideas.

## Verification

Exact commands executed.

## Test results

Results of lint/tests.

## Deferred features

Explicitly list:

- semantic/vector search;
- QMD;
- MCP;
- automatic LLM ingestion;
- knowledge graph.

## Recommendation

State whether ProjectWiki is ready to be used for the next PDFTranslator ticket.

---

# Acceptance criteria

The task is complete when:

- `knowledge/raw` exists;
- `knowledge/wiki` exists;
- `knowledge/AGENTS.md` exists;
- root `AGENTS.md` / pre-ticket workflow contain a concise ProjectWiki entry point;
- initial Wiki navigation exists;
- raw and Wiki responsibilities are documented;
- source traceability is supported;
- `wiki_lint.py` works;
- `wiki_search.py` works;
- Wiki files are Git-friendly Markdown;
- no external service is required;
- no vector database is required;
- existing PDFTranslator functionality is unaffected;
- lint passes;
- relevant tests pass;
- implementation report is produced;
- `knowledge/wiki/testing/pilot-evaluation.md` exists for the planned 2–3 ticket trial.

---

# Important

Keep this implementation deliberately small.

The purpose of Phase 1 is to test whether a maintained Markdown Wiki improves Codex work across several PDFTranslator tickets.

Do not optimize for scale before we have evidence that the workflow is useful.
