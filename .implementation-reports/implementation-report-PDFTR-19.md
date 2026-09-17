# Implementation Report

## Ticket

PDFTR-19 — Task: Create ProjectWiki and integrate it into PDFTranslator

## Summary

Implemented the Phase 1 ProjectWiki as a Git-tracked, source-backed Markdown knowledge subsystem.
It adds a curated agent entry point, immutable raw-evidence boundary, deterministic frontmatter and
link validation, weighted lexical search, focused tests, and local/CI quality-gate integration. No
production PDFTranslate runtime behavior or dependency changed.

## Workflow

- Level: 2
- Graphify: used before implementation, source-verified, and refreshed after implementation
- CRG: rebuilt before implementation and rebuilt after implementation with new untracked files
  temporarily staged so they were included; staging was removed immediately afterward
- Working tree before changes: dirty with unrelated deleted/generated PDF artifacts, all preserved
- Branch: `codex/PDFTR-19-project-wiki`, created directly from `master`
- Baseline: `da838681be2bf7343fc1ad22234710e356565807`

## Scope

- Modules: repository-local `scripts.project_wiki` tooling only; production `src/pdftranslate`
  modules were not changed
- Pipeline stages: none
- Dependency impact: none; Python standard library only
- Model/device impact: none
- OCR impact: none
- CLI/public contract impact: two new developer commands for Wiki lint/search; no `pdftranslate`
  CLI change
- PDF/output integrity impact: none

## Investigation

- Current behavior: durable knowledge was spread across tickets, reports, reviews, source, tests,
  README, Graphify, and CRG without a curated cross-ticket entry point or knowledge validator.
- Expected behavior: future agents can begin with a compact Wiki index, follow source-backed
  relative links, search locally, and validate knowledge changes in the normal quality gate.
- Root implementation gap: no `knowledge/` structure, maintenance rules, schema validator, search
  command, tests, or quality-gate integration existed.
- Main symbols: `WikiPage`, `parse_page`, `validate_wiki`, `ValidationReport`, `search_wiki`, and
  `SearchResult`.
- Configuration/schema: fixed small frontmatter vocabulary and allowed type/status sets; no runtime
  setting or serialized PDF schema changed.
- Expected blast radius: documentation, agent workflow, standalone scripts, their tests, local
  check script, and CI only.

## Files created

- Ticket/planning/reporting:
  - `Tickets/PDFTR-19.md`
  - `.implementation-plans/investigation-PDFTR-19.md`
  - `.implementation-plans/implementation-plan-PDFTR-19.md`
  - `.implementation-reports/implementation-report-PDFTR-19.md`
  - `reviews/review-PDFTR-19.md`
- ProjectWiki instructions/evidence:
  - `knowledge/AGENTS.md`
  - `knowledge/raw/README.md`
  - `knowledge/raw/sources/llm-wiki-references.md`
  - tracked placeholders for required empty raw categories
- Curated Wiki:
  - `knowledge/wiki/index.md`
  - `knowledge/wiki/overview.md`
  - `knowledge/wiki/architecture/system-overview.md`
  - `knowledge/wiki/workflows/development-workflow.md`
  - `knowledge/wiki/workflows/wiki-maintenance.md`
  - `knowledge/wiki/decisions/wiki-as-markdown.md`
  - `knowledge/wiki/constraints/raw-sources-immutable.md`
  - `knowledge/wiki/testing/wiki-validation.md`
  - `knowledge/wiki/testing/pilot-evaluation.md`
  - `knowledge/wiki/log.md`
  - tracked placeholders for required empty Wiki categories
- Tooling/tests:
  - `scripts/__init__.py`
  - `scripts/project_wiki/__init__.py`
  - `scripts/project_wiki/wiki_common.py`
  - `scripts/project_wiki/wiki_lint.py`
  - `scripts/project_wiki/wiki_search.py`
  - `scripts/project_wiki/README.md`
  - `tests/test_project_wiki.py`

## Files modified

- `AGENTS.md` and `.codex/PRE_TICKET_WORKFLOW.md`: concise ProjectWiki entry point and lifecycle.
- `README.md`: user/developer overview and commands.
- `CHANGELOG.md`: Phase 1 addition.
- `scripts/check.ps1`: Wiki validation in the mandatory local quality gate.
- `.github/workflows/ci.yml`: matching network-free Wiki validation on Windows and Linux.

## Design decisions

- Kept raw evidence, curated knowledge, and agent/validation rules as separate conceptual layers.
- Referenced canonical repository artifacts in place rather than copying historical ticket/report
  collections into `knowledge/raw/`.
- Added only one concise external-reference research note; no reference repository was vendored.
- Used a small shared parser because lint and search require the exact same frontmatter semantics.
  The public tools remain thin synchronous CLIs; no framework, service layer, inheritance, plugin,
  model, database, or background process was introduced.
- Implemented a deliberately small YAML subset sufficient for scalar/list frontmatter, avoiding a
  dependency solely for metadata parsing.
- Search ranks exact/token occurrences deterministically by title, tags, headings, then body. It
  does not claim semantic equivalence.
- Lint checks only local filesystem targets and ignores external URL reachability, keeping CI
  deterministic and offline.

## Graph and source validation

- Graphify initially identified repository instructions, README, quality scripts, tickets/reports,
  and tests as the integration neighborhood. Source inspection confirmed that GitHub Actions ran
  quality commands directly instead of invoking `scripts/check.ps1`.
- Graphify's final update parsed 216 files and produced 2392 nodes, 4902 edges, and 152 communities.
- CRG's final full build included 124 Python/PowerShell files, 1101 loaded nodes/9716 edges before
  its normalized status view (1097 nodes/9635 edges). It found no affected production flow.
- CRG reported static test gaps for standalone helper symbols even though the focused pytest suite
  exercises the public APIs directly and the CLIs through subprocesses. This is consistent with
  CRG's documented dynamic/subprocess limitation and was resolved with executable evidence.
- Source review verified imports, direct-script execution on Windows/Linux, repository-relative
  defaults, CI commands, frontmatter paths, and all initial Wiki claims.
- Graphify's first sandboxed post-change refresh failed with Windows access denied; the required
  elevated retry succeeded. CRG's first brief output hit a CP1251 rendering error after updating;
  rerunning with `PYTHONIOENCODING=utf-8` produced the complete report.

## Post-change impact

- CRG updated: yes, full rebuild after temporarily staging only PDFTR-19 files
- Blast radius: standalone ProjectWiki Python tools/tests, PowerShell quality gate, CI, and docs
- Unexpected dependants: none
- Compatibility/migration: none; existing PDFTranslate behavior and environments are unchanged

## Verification

- `uv run ruff format scripts/project_wiki tests/test_project_wiki.py`
- `uv run ruff check scripts/project_wiki tests/test_project_wiki.py`
- `uv run pytest tests/test_project_wiki.py -q --no-cov`
- `uv run python scripts/project_wiki/wiki_lint.py`
- `uv run python scripts/project_wiki/wiki_search.py "ProjectWiki"`
- `uv run python scripts/project_wiki/wiki_search.py "atomic publication"`
- `./scripts/check.ps1`
- `graphify update .`
- `graphify query "How does ProjectWiki integrate with repository instructions, quality checks, CI, tests, and source evidence?" --budget 3000`
- `code-review-graph build`
- `code-review-graph detect-changes --base master --brief`

## Test results

- Focused ProjectWiki tests: 9 passed with `--no-cov`.
- Real Wiki lint: 10 pages, 39 local links/source references, 0 errors, 0 warnings.
- Search smoke tests: title/body ranking returned deterministic expected pages.
- Ruff format: 177 files already formatted after final formatting pass.
- Ruff lint: passed.
- mypy: no issues in 83 production source files.
- Full pytest: 239 passed, 1 skipped; total production coverage 88.62% (required 80%).
- Mandatory `scripts/check.ps1`: passed.
- Real-model, CUDA, PDF manual, and OCR integration validation: not required because no production
  pipeline, model, PDF, device, or OCR behavior changed.

The first focused pytest invocation omitted `--no-cov`; the repository-wide coverage policy then
reported 0% because that focused file imports no production `pdftranslate` module. All nine tests
themselves passed, and the corrected focused invocation plus the full suite passed.

## Documentation

Updated repository instructions, pre-ticket workflow, README, changelog, Wiki instructions,
curated Wiki pages, tool README, implementation plan/report, and review.

## Deferred features

- semantic/vector search and embeddings
- QMD
- MCP
- automatic LLM ingestion or whole-Wiki rewriting
- knowledge graph generation
- external services, databases, UI, daemons, domain routing, staging, and revision manifests

These remain explicitly deferred until the 2–3 ticket pilot provides concrete evidence.

## ProjectWiki pilot

- Ticket ID: PDFTR-19 (pilot creation ticket, not one of the next evaluation tickets)
- Wiki pages consulted before implementation: none existed
- Canonical sources opened: ticket, repository instructions, README, changelog, quality scripts,
  CI, tests, source layout, Graphify/CRG output, and the three requested external references
- Missing/stale Wiki knowledge: the Wiki itself was the missing capability
- Wiki pages updated after implementation: all initial pages listed above
- Prevented rediscovery: not yet measurable; evaluate in the next 2–3 non-trivial tickets
- Review-exposed gaps: none after lint, focused tests, full quality gate, and graph review

## Remaining risks

- The deliberate YAML subset does not support arbitrary YAML features; the documented schema does
  not require them.
- Lexical search can miss synonyms; this is an accepted Phase 1 limitation.
- Lint proves structural integrity, not factual truth. Agents must still source-verify claims.
- CRG cannot fully infer subprocess-driven tests, so runtime pytest evidence remains authoritative.

## Recommendation

ProjectWiki is ready for the next PDFTranslator ticket. Keep Phase 1 unchanged while collecting
the required concrete observations over 2–3 non-trivial tickets before deciding whether to keep,
adjust, expand, or abandon it.
