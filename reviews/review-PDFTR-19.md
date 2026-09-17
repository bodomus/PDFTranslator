# Review — PDFTR-19

## Result

PDFTR-19 is implemented on `codex/PDFTR-19-project-wiki`. The Phase 1 ProjectWiki is small,
dependency-free, source-backed, integrated into local/CI checks, and isolated from production
PDFTranslate behavior.

## Reviewed scope

- Required `knowledge/raw`, `knowledge/wiki`, and `knowledge/AGENTS.md` structure.
- Ten curated Wiki pages with YAML frontmatter, ordinary relative links, provenance, navigation,
  maintenance rules, and the 2–3 ticket pilot template.
- Standard-library lint for schema, type/status vocabulary, unique titles, dates, local links, and
  local source references.
- Deterministic weighted lexical search over title, tags, headings, and body.
- Focused direct-API and CLI tests plus local/CI quality-gate integration.
- Repository instructions, README, changelog, implementation plan/report, Graphify, and CRG.

## Findings

- No production `src/pdftranslate` module, dependency, PDF schema, CLI command, cache, model, OCR,
  rendering, or output-publication contract changed.
- Initial Wiki facts are traceable to current canonical repository documents or the ticket; the
  external implementation review is preserved as one concise research note rather than vendored
  content.
- Empty required categories are retained with tracked placeholders without fabricating knowledge.
- Lint ignores external URL availability by design, so normal checks stay deterministic offline.
- CRG reported standalone helper test gaps because it cannot fully follow subprocess-based CLI
  coverage; direct API calls and executable pytest evidence cover the public lint/search paths.
- Pre-existing unrelated temp/PDF working-tree changes remain untouched.

## Verification

- ProjectWiki lint: 10 pages, 39 links/source references, 0 errors, 0 warnings.
- Focused tests: 9 passed.
- Full quality gate: Ruff format/lint passed, mypy passed for 83 files, pytest 239 passed / 1
  skipped, coverage 88.62%.
- Graphify refreshed: 2392 nodes, 4902 edges, 152 communities.
- CRG rebuilt with new files: 124 files, no affected production flow or unexpected dependant.
- `git diff --check`: passed before final report creation; final diff check is repeated at handoff.

## Remaining risks

- Lexical retrieval is intentionally not semantic.
- The frontmatter parser supports the documented small schema, not general YAML.
- Wiki truth still depends on disciplined source verification and curation during future tickets.

## Recommendation

Accept PDFTR-19 and use ProjectWiki for the next 2–3 non-trivial PDFTranslator tickets. Record
concrete pilot evidence before considering embeddings, QMD, MCP, automated ingestion, or a
knowledge graph.
