# PDFTR-19 implementation plan

## Scope

Introduce the Phase 1 ProjectWiki as a small, reusable, Git-friendly Markdown knowledge subsystem
without changing PDFTranslate runtime behavior or adding dependencies.

## Plan

1. Create the required `knowledge/raw` and `knowledge/wiki` directory structure, keeping canonical
   repository documents in place and using raw storage only for a concise reference-research note.
2. Add `knowledge/AGENTS.md` with the required read, search, evidence, implementation, update, and
   validation workflow plus explicit immutable-source boundaries.
3. Create the curated starter pages required by PDFTR-19, including system overview, development
   and Wiki-maintenance workflows, Markdown and immutability decisions, validation guidance, the
   pilot-evaluation page, compact index, and meaningful log.
4. Implement dependency-free shared Markdown/frontmatter parsing, a deterministic lint CLI, and a
   deterministic weighted lexical-search CLI under `scripts/project_wiki/`.
5. Add focused pytest coverage for valid lint, broken links, missing sources, invalid types/dates,
   duplicate titles, and title/tag/heading/body search behavior.
6. Integrate Wiki lint into `scripts/check.ps1` and the existing GitHub Actions quality job.
7. Add concise ProjectWiki entry points to root `AGENTS.md`, `.codex/PRE_TICKET_WORKFLOW.md`, and
   `README.md`; record the user-visible addition in `CHANGELOG.md`.
8. Run focused checks, real Wiki smoke tests, the full quality gate, then refresh CRG and inspect
   the final diff/blast radius.
9. Produce `.implementation-reports/implementation-report-PDFTR-19.md` and
   `reviews/review-PDFTR-19.md`, attach the review to YouTrack, and update ticket workflow fields
   after explicit confirmation for representational UI actions.

## Design constraints

- Standard library only; no YAML dependency, embeddings, vector store, database, MCP server, LLM
  API, QMD, background process, or automatic bulk ingestion.
- Generic scripts must not import `pdftranslate` or encode PDFTranslator-specific page categories.
- Ordinary relative Markdown links remain readable in GitHub, IDEs, and plain text editors.
- Wiki pages consolidate knowledge; they do not copy whole tickets/reports or supersede source,
  tests, Git history, Graphify, CRG, or canonical reports.
- Empty required raw directories must remain present in Git without fabricated source content.
- The implementation must not touch the unrelated pre-existing PDF/temp working-tree changes.

## Verification

- `uv run pytest tests/test_project_wiki.py -q --no-cov`
- `uv run python scripts/project_wiki/wiki_lint.py`
- `uv run python scripts/project_wiki/wiki_search.py "ProjectWiki"`
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run mypy src`
- `uv run pytest -q`
- `./scripts/check.ps1`
- `code-review-graph update --base master --brief`
