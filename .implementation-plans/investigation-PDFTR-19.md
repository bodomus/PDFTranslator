# PDFTR-19 investigation

## Classification and baseline

- Workflow level: 2 (new repository subsystem, agent workflow, validation tooling, tests,
  documentation, and CI/local quality-gate integration).
- Baseline commit: `da838681be2bf7343fc1ad22234710e356565807` on `master`.
- Work branch: `codex/PDFTR-19-project-wiki`, created directly from `master`.
- The working tree already contained unrelated deleted/generated PDF artifacts. They must remain
  untouched and outside this ticket's change set.
- Python 3.12 and the existing `uv` workflow remain authoritative. No dependency is needed.

## Current behavior

- Project knowledge is distributed across `README.md`, `CHANGELOG.md`, tickets, implementation
  reports, reviews, source, tests, Graphify, and CRG.
- Repository instructions require Graphify/CRG preflight, implementation plans/reports, and ticket
  artifacts, but there is no curated cross-ticket knowledge entry point.
- `scripts/check.ps1` and GitHub Actions run Ruff, mypy, and pytest. They do not validate project
  knowledge documents.
- The repository has no local tool for searching project knowledge or validating Markdown
  frontmatter, source references, and relative links.

## Expected behavior

- A small Git-tracked `knowledge/` tree separates immutable evidence from curated Wiki pages.
- Future agents start with a compact index, search only when necessary, consult canonical evidence
  for important claims, and update only affected Wiki pages after non-trivial work.
- Every Wiki page follows a deterministic frontmatter schema and uses ordinary relative Markdown
  links.
- Standard-library lint and lexical search tools work locally and in CI without network access,
  models, embeddings, databases, daemons, or external services.
- The first 2–3 non-trivial tickets record concrete pilot observations before any Phase 2 decision.

## Reference review

- Andrej Karpathy's LLM Wiki gist supplies the three-layer model: immutable raw sources, an
  agent-maintained Markdown Wiki, and an index-first query workflow. It explicitly notes that a
  simple search script is sufficient before RAG infrastructure is justified.
- `praneybehl/llm-wiki-plugin` reinforces readable canonical Markdown, source citations, bounded
  pages, local lexical retrieval, and surgical updates. Its embeddings, SQLite vector cache,
  plugin commands, and broader ingest automation exceed this pilot's scope.
- `Programming-With-Maury/Karpathy-LLM-Wiki` reinforces source-backed concise pages, explicit
  uncertainty, durable agent rules, and synchronized index/log maintenance. Its UI, domain
  routing, staging, revisions, background ingestion, and provider integration also exceed scope.
- The PDFTR-19 ticket deliberately narrows these ideas to a project-local, dependency-free Phase 1.

## Repository intelligence

### Graphify

- The existing graph was queried for repository workflow, quality checks, documentation, and
  standalone scripts.
- It identified `AGENTS.md`, `README.md`, `scripts/check.ps1`, ticket/report conventions, tests,
  and GitHub Actions as the relevant integration neighborhood.
- Source verification confirmed those files and showed that CI currently invokes the quality
  commands directly rather than calling `scripts/check.ps1`.

### Code Review Graph

- A fresh full build on the PDFTR-19 branch parsed 118 files and recorded 1056 nodes and 9296
  edges before implementation.
- The baseline change analysis found only the newly added ticket Markdown file and no changed
  Python symbols, flows, or test gaps.
- CRG does not model Markdown semantics or standalone script behavior completely, so direct source
  inspection and executable tests remain authoritative.

## Smallest coherent change

1. Add the required `knowledge/raw`, `knowledge/wiki`, and `knowledge/AGENTS.md` structure.
2. Seed only verified, useful Wiki pages and one concise external-reference research note.
3. Implement a small shared frontmatter/parser module plus separate lint and lexical-search CLIs.
4. Add focused pytest coverage for required lint/search behavior.
5. Invoke Wiki lint from both `scripts/check.ps1` and the existing CI workflow.
6. Add concise ProjectWiki entry points to repository instructions and user documentation.
7. Produce ticket-scoped plan, implementation report, and review artifacts.

## Affected contracts and blast radius

- New filesystem contract: `knowledge/` contains tracked Markdown knowledge and source evidence.
- New developer commands: `python scripts/project_wiki/wiki_lint.py` and
  `python scripts/project_wiki/wiki_search.py "query"`.
- Local/CI quality gates gain a deterministic, network-free Wiki lint step.
- No production package, CLI, PDF schema, translation/rendering/OCR behavior, cache, model,
  device, resume, or source/output PDF contract changes.
- The main compatibility risk is rejecting valid Wiki Markdown incorrectly; focused fixtures and
  execution against the real Wiki will cover schema, links, dates, and sources.

## Validation required

- Focused ProjectWiki tests.
- Real Wiki lint and representative title/body searches.
- Ruff formatting and lint.
- mypy for `src` (production package unchanged).
- Full pytest suite.
- `./scripts/check.ps1`.
- Post-change CRG update and blast-radius inspection.
- Source review of all ProjectWiki claims and links.
