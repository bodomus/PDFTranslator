# ProjectWiki agent instructions

These rules apply to everything under `knowledge/` and complement the repository-level
`AGENTS.md`. Source code, executable tests, current configuration, and canonical evidence remain
more authoritative than Wiki summaries.

## Required workflow for non-trivial tickets

1. Read the repository-level `AGENTS.md` and `.codex/PRE_TICKET_WORKFLOW.md`.
2. Read `knowledge/wiki/index.md`.
3. Search the Wiki for the subsystem being modified.
4. Inspect relevant raw or canonical source documents when a claim affects implementation.
5. Inspect Graphify and CRG results when required by the repository workflow.
6. Implement the ticket and run the applicable tests and quality gates.
7. Produce or update the ticket implementation report.
8. Update only the Wiki pages whose durable project knowledge changed.
9. Append a concise `knowledge/wiki/log.md` entry for meaningful Wiki changes.
10. Run `uv run python scripts/project_wiki/wiki_lint.py`.

Wiki updates happen after implementation knowledge is known. Level 0 formatting, spelling, and
other trivial changes do not require Wiki updates.

## Raw evidence boundary

- Treat existing files under `knowledge/raw/` as immutable evidence during normal Wiki work.
- Add a new raw source only when explicitly instructed or when stable evidence genuinely belongs
  there. Prefer a link to an existing canonical tracked document over a duplicate copy.
- Never rewrite historical evidence to make it agree with the Wiki. Record conflicts and mark them
  unresolved until current source or runtime evidence resolves them.
- Do not bulk-copy tickets, reports, reviews, docs, conversations, generated graphs, or source code
  into `knowledge/raw/`.

## Wiki maintenance boundary

- Use Markdown with the schema documented in `knowledge/wiki/testing/wiki-validation.md`.
- Keep pages concise, source-backed, and organized by durable topic rather than ticket number.
- Cite local evidence through frontmatter `sources` and normal relative Markdown links.
- Label inferences and uncertainty explicitly. Never invent a source or undocumented architecture.
- Update an existing page when the knowledge belongs there; do not create near-duplicates.
- Keep `index.md` curated and append to `log.md` only for meaningful knowledge changes.
- Never auto-regenerate or rewrite the entire Wiki from source, reports, Graphify, or CRG output.
- Do not edit existing raw evidence automatically.

## Validation

Run both tools from the repository root:

```powershell
uv run python scripts/project_wiki/wiki_search.py "subsystem or decision"
uv run python scripts/project_wiki/wiki_lint.py
```

The linter is required after any Wiki change. It validates only local filesystem targets and does
not make network requests for external URLs.
