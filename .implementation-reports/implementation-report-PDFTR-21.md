# PDFTR-21 implementation report

## Summary

Implemented explicit, conservative preservation of Latin/Greek quotations and selected academic
foreign-language terms. Confident whole units bypass NLLB and remain source-exact; protected spans
inside English prose are excluded from model inference and deterministically interleaved back into
the translated result. Classification and privacy-safe evidence survive serialization and appear
in diagnostic reports.

## Workflow and scope

- Workflow level: 2 (translation preprocessing, metadata, cache/resume identity, diagnostics).
- Branch: `codex/PDFTR-21-preserve-foreign-language-text`, created from `master` at `334ef2c`.
- Pre-existing changes preserved: `.gitignore` was modified and `temp/.agents.zip` was deleted.
- Changed boundaries: paragraph translation preprocessing, translation metadata, cache/resume
  compatibility, success-report diagnostics, tests, README/CHANGELOG, and ProjectWiki.
- Dependency impact: none.
- CLI, OCR, model loading/device selection, source PDF integrity, renderer, PDFTR-18 saved-PDF
  validation, and PDFTR-20 completeness behavior remain unchanged.

## Investigation and root cause

The Robitzsch workspace showed that page-1 and page-2 Latin passages both had normal `translate`
policy. Page 1 became Cyrillic-like text, while page 2 only appeared preserved: its NLLB output
changed source words such as `languebat`. Greek units were also altered or dropped. The difference
was accidental model/cache behavior; there was no preservation decision in the pipeline.

Paragraph translation already owned the right composition point: repeated-element and marker
policies, glossary preparation, protected tokens, segmentation, inference, cache, resume, and
metadata. The smallest coherent change was a dedicated preprocessing classifier at this boundary,
not a renderer or backend modification and not a generic protected-token regex expansion.

## Implementation

- Added `ForeignLanguageClassification` with `translate`, `preserve_foreign_unit`, and
  `translate_with_preserved_spans` states.
- Added per-occurrence evidence containing stable unit index, paragraph ID, page, reasons,
  preserved-span count, and whether inference was called in the current run, plus aggregate counts.
- Added a focused classifier:
  - Greek-majority whole units require Unicode Greek-script evidence;
  - Latin whole units require a minimum length and multiple distinct Latin function-word signals;
  - Greek runs and the ticket's narrowly scoped academic terms are recognized inside mixed prose;
  - ambiguous content follows normal translation with an explicit reason.
- Whole-unit preservation sets `translated_text` to source text and never submits the unit to NLLB.
- Mixed spans are split out before inference. Only surrounding prose is translated; exact source
  spans are interleaved afterward. This avoids relying on NLLB to reproduce sentinels.
- Explicit glossary `translate` matches override automatic whole-unit preservation. Otherwise,
  whole-unit classification reads original text so glossary placeholders cannot hide evidence.
- Foreign-span assembly composes with existing glossary and generic protected-token restoration and
  fails closed on inconsistent part counts or stale cached output missing required spans.
- Translation behavior revision is now `5`; SQLite cache keys, direct partial resume, and completed
  pipeline workspace reuse reject pre-PDFTR-21 behavior.
- Existing document schema remains 1.3; new metadata fields have backward-readable defaults.

## Deterministic validation

Coverage includes two independent Latin passages, a Greek quotation, mixed English/Latin and
English/Greek prose, ordinary English, exact span exclusion from model inputs, glossary precedence,
fail-closed assembly, cache revision, stale resume rejection, JSON round-trip, diagnostics,
protected-token behavior, and PDFTR-17 marker pass-through.

- Focused translation/glossary/diagnostics tests passed.
- `uv run python scripts/project_wiki/wiki_lint.py`: 12 pages, 58 links, 0 errors, 0 warnings.
- `uv run ruff format --check .`: passed.
- `uv run ruff check .`: passed.
- `uv run mypy src`: passed for 84 source files.
- Final `scripts/check.ps1`: 250 passed, 1 skipped, coverage 88.65%.

## Real CUDA regression

The controlled run used the ticket's Robitzsch PDF, CUDA, and repository-local `temp/` output. The
first run exposed a real NLLB limitation: a protected foreign sentinel was removed. The pipeline
failed closed, no output PDF was published, and the implementation was strengthened so foreign
spans never enter model inference, even as placeholders. Revision `5` invalidated partial revision-4
cache/workspace data before the repeat.

The repeat completed translation of all 61 logical units, then reached the expected PDFTR-20
boundary: rendering rejected 21 required overflow occurrences and did not publish the requested
PDF. Persisted schema 1.3 `translated.json` in workspace
`a5de639d2daa2dff5617e5f240d378565c0f5e00e7bc6b99bfa5987795c0abf8` proves:

- behavior revision `5`, completed translation status;
- 7 whole foreign units preserved, 5 mixed units, and 12 preserved inline spans;
- page-1 Latin `p0001-b0001` is source-equal and `translator_called=false`;
- page-2 Latin `p0002-b0002` is source-equal and `translator_called=false`;
- Greek whole units are source-equal; the mixed Greek tail remains Greek while surrounding prose
  is translated;
- `ipsi`, `sibi`, `lex`, `ius`, `nomos`, `magistratus`, and `faute de mieux` remain exact inside
  Russian output;
- normal prose still contains Cyrillic translation;
- the known 21-overflow PDFTR-20 invariant remains enforced.

## Graph and source validation

- Graphify preflight located `translate_document` → `translate_paragraphs`, protected-token,
  glossary, cache, renderer, and test boundaries; all material conclusions were source-verified.
- Post-change CRG indexed 1123 rows and reported 24 changed symbols with risk score 0.55. Its static
  test-gap list does not resolve Pydantic model construction or indirect report tests; direct tests
  for translation metadata, report fields, cache/resume, and serialization were source-verified.
- Graphify was refreshed because `translation/foreign_language.py` adds a module boundary: 2591
  nodes, 5218 edges, 190 communities. A follow-up query found the new classifier, paragraph
  orchestration, metadata, cache, diagnostics, serialization, and regression tests.
- No unexpected CLI, OCR, renderer, or backend-construction dependant was introduced.

## ProjectWiki pilot

- Pages consulted before implementation: `index.md`, `architecture/system-overview.md`,
  `failure-modes/render-completeness.md`, and `testing/pilot-evaluation.md`.
- Required searches covered translation, protected tokens, glossary, paragraph reconstruction,
  rendering completeness, and foreign language.
- Canonical sources additionally opened: translation orchestration/text/cache/backend boundary,
  glossary processor/models, document serialization models, reconstruction/repeated policies,
  diagnostics, pipeline resume validation, tests, CRG/Graphify output, and persisted Robitzsch
  artifacts.
- Missing knowledge: no page described foreign-language classification, mixed-span preservation,
  glossary precedence, or compatibility invalidation.
- Updated pages: new `components/foreign-language-preservation.md`, index, system overview, pilot
  evaluation, and Wiki log.
- The Wiki prevented rediscovery of the six-stage publication boundary and preserved the PDFTR-20
  fail-closed constraint during the real regression. Exact translation behavior still required
  canonical source and runtime evidence. No time/token saving is claimed.
- Review confirmed the initial placeholder approach was a Wiki/implementation gap; the page now
  documents the stronger outside-inference design.

## Remaining risks and boundaries

- Latin classification is intentionally conservative and is not universal language detection.
- The built-in inline vocabulary is deliberately narrow; project-specific mandatory terminology
  should continue to use the versioned glossary.
- Splitting mixed prose at protected spans can reduce local NLLB fluency. The ticket guarantees
  source preservation, not general translation-quality improvement.
- The Robitzsch PDF still cannot be published because of the accepted PDFTR-20 fixed-layout
  overflow boundary. Reflow remains a separate follow-up.
