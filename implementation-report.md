# Implementation Report — PDFTR-12

## Ticket and repository state

- Ticket: PDFTR-12 — Repeated headers, footers and boilerplate detection.
- Branch: `codex/PDFTR-12-repeated-headers-footers-and-boilerplate-detection`.
- PDFTR-11 prerequisite: `master` was fast-forwarded and pushed from `3b0bd0f` to `a3887db`
  before this branch was created, as explicitly authorized by the user.
- Initial PDFTR-12 tree: clean at `a3887db`; ticket Markdown was then added under `Tickets/`.
- YouTrack: moved from Open to In Progress. The ticket already contained its Markdown attachment.

## Workflow and repository intelligence

- Level: 2 — the change crosses extraction, domain serialization, reconstruction, translation,
  rendering, pipeline/cache identity, batch, CLI and PDFTR-10 diagnostics.
- Graphify preflight identified the extraction → reconstruction → translation → renderer →
  diagnostics path and was source-verified. Post-change refresh initially hit Windows access
  denial inside the restricted process, then succeeded with the approved elevated retry: 1,665
  nodes, 3,704 edges and 110 communities.
- CRG was rebuilt/updated: 824 nodes, 7,000 edges across 93 files. Its post-change heuristic reports
  47 changed symbols, risk 0.60 and 42 possible test gaps. The generic gap list includes indirectly
  exercised dataclass/CLI orchestration symbols; focused CLI, policy, generated-PDF and full-suite
  tests are authoritative. Source inspection confirmed all important graph relationships.
- Design followed KISS/separation of concerns: the pure classifier is independent from Typer,
  PyMuPDF mutation and translation backends; existing pipeline components consume typed evidence.

## Capability implemented

- Added classifications: `body`, `page_number`, `running_header`, `running_footer`,
  `repeated_boilerplate`, `watermark_candidate`, and `unknown_repeated`.
- Added explicit policies: `translate`, `preserve`, `skip`, and `remove`. Automatic classification
  never selects `remove`. Page numbers and uncertain groups remain untouched in the source PDF;
  watermark candidates skip model/render work but are not erased.
- Classifier evidence uses normalized text, margin/central position, normalized bounding boxes,
  font similarity, recurrence ratio, odd/even parity, page-number sequence and first/last-page
  exceptions. Every physical source block receives a classification and remains serialized.
- Confirmed and uncertain repeated units receive separate logical paragraph kinds, preventing body
  and cross-page merging. Original fragment mappings and page anchors remain intact.
- Repeated translatable strings use normal in-run deduplication/cache once and are rendered on each
  source page. Preserve/skip policies do not call the model.
- Pipeline behavior revision changed from 3 to 4; `auto|off` is included in resume/workspace
  identity and propagated through root, extract and batch paths.
- CLI adds `--repeated-elements auto|off` to root translation, `extract`, and `batch`.
- Typed `PDFTRANSLATE_REPEATED_*` settings control margin, recurrence/parity, geometry/font,
  watermark-font and minimum-page thresholds.
- PDFTR-10 diagnostics add document counts and per-unit confidence, group ID, policy and ambiguity,
  plus stable warning code `REPEATED_ELEMENT_AMBIGUOUS`. Source/translation text remains excluded
  unless the existing explicit diagnostics opt-in is used.

## Main files and symbols

- `src/pdftranslate/repeated/models.py`: typed kinds, policies, options and persisted evidence.
- `src/pdftranslate/repeated/classifier.py`: `classify_repeated_elements()` and conservative rules.
- `src/pdftranslate/pdf/pymupdf_backend.py`: classification before reconstruction.
- `src/pdftranslate/reconstruction/reconstructor.py`: typed repeated boundaries and paragraph kinds.
- `src/pdftranslate/domain/document.py`: optional schema 1.2/1.3 evidence with exact block coverage.
- `src/pdftranslate/translation/paragraphs.py`: translate/preserve/skip/remove policy execution.
- `src/pdftranslate/rendering/renderer.py`: leave preserve/skip source content untouched; render
  translated units per page; redact-only behavior remains available for explicit remove policy.
- `src/pdftranslate/pipeline/{models.py,runner.py}`, `batch/models.py`, `config.py`, and `cli.py`:
  settings, behavior identity and end-to-end propagation.
- `src/pdftranslate/diagnostics/{models.py,builder.py}`: summary/block evidence and warning.
- `tests/test_repeated_elements.py`: generated model and real generated-PDF coverage.
- `scripts/benchmark-repeated-elements.py`: deterministic synthetic noise benchmark.
- README, CHANGELOG, investigation, plan, ticket copy and completion review were updated.

## Validation results

- Focused and adjacent suite:
  `uv run pytest tests/test_repeated_elements.py tests/test_paragraph_reconstruction.py
  tests/test_translation.py tests/test_rendering.py tests/test_diagnostics.py tests/test_cli.py
  tests/test_batch_cli.py tests/test_serialization.py -q --no-cov` → **52 passed**.
- Direct CLI help: root, batch and extract commands exited 0; batch/extract help contains
  `--repeated-elements`, and the existing required batch options remain present.
- Static checks: `ruff format --check .`, `ruff check .`, and `mypy src` → passed.
- Full `scripts/check.ps1` → **174 passed, 1 skipped**, coverage **87.47%** (required 80%).
- GitHub Actions CI #30 for commit `5fd40d2` completed successfully in 1m 20s:
  <https://github.com/bodomus/PDFTranslator/actions/runs/31087523817>.

- Generated-PDF evidence: a three-page PDF was extracted, fake-translated and rendered; each page
  retained its own page number, contained its page-specific translated body and the repeated header,
  and preserved page-number units without redrawing them.
- Diagnostics evidence: tests assert repeated counts/classification/confidence/group/policy fields,
  stable ambiguity code, and absence of source/translated text under default privacy behavior.

## Benchmark results

Command:
`uv run python scripts/benchmark-repeated-elements.py --output
temp/pdftr12-benchmark/repeated-elements.json`

- Fixture: eight generated pages with alternating headers, unique body, copyright footer and
  sequential page number.
- Baseline body blocks: 32.
- Classified body blocks: 8.
- Service/noise blocks removed from body reconstruction: 24 (**75% reduction**).
- Counts: body 8, page number 8, running header 8, repeated boilerplate 8.
- Groups: 4; ambiguous blocks: 0.
- JSON and Markdown results were generated under `./temp/` and intentionally are not committed.

## Limitations, findings and deferred validation

- No private real-world corpus PDF was provided for PDFTR-12. Real-PDF evidence here is a PDF
  generated and reopened with PyMuPDF; it validates extraction/render page placement, not the full
  diversity of publisher layouts.
- Real NLLB, CUDA and OCR were not run: they are outside the classifier behavior and normal tests
  must not download models or require GPU/OCR tools. Translation reuse was verified with a fake
  backend and real SQLite cache path.
- Exact normalized-text grouping intentionally does not attempt fuzzy chapter-title similarity or
  OCR-error correction. Chapter-dependent/short-document groups remain ambiguous and preserved.
- Watermark classification is intentionally a candidate with ambiguity; `skip` keeps the visible
  source watermark. Automatic cleaning/removal is explicitly out of scope.
- CRG's 42 reported gaps are conservative static heuristics, not 42 failing or absent acceptance
  tests. The key production path is covered, but additional real-corpus calibration remains useful.

## Final status

Local implementation, branch push and GitHub Actions are complete and green. Ready for review;
do not start PDFTR-13 until this report and the real results are reviewed.

---

# Implementation Report — PDFTR-11

## Ticket

PDFTR-11 — Paragraph reconstruction and reading order.

Branch: `codex/PDFTR-11-paragraph-reconstruction-and-reading-order`.

## Workflow

- Level: 2 (document schema and extraction/translation/rendering pipeline architecture).
- Graphify: mandatory preflight query was source-verified; post-change code graph refreshed successfully to 1,576 nodes, 3,467 edges, and 112 communities.
- CRG: preflight and post-change update completed. Post-change heuristic: 44 changed symbols, risk 0.60, 39 reported test gaps. The graph does not infer pytest fixture/CLI/dynamic coverage reliably; authoritative focused and full tests cover the new pipeline.
- Working tree before changes: clean `master` at `3b0bd0f`.
- Ticket workflow: ticket Markdown saved under `Tickets/`; YouTrack moved from Open to In Progress and received a branch/workflow comment.

## Scope

- Modules: typed domain models, PyMuPDF extraction, reconstruction engine, serialization, translation orchestration, cache/resume identity, renderer, diagnostics, CLI, batch options, configuration, tests, benchmark script, README, CHANGELOG.
- Pipeline stages: inspect/extract/translate/render/validate; OCR behavior itself is unchanged.
- Dependency impact: none.
- Model/device impact: no backend/model/CUDA behavior change and no model download in tests.
- OCR impact: reconstruction runs against the selected post-OCR physical text layer; OCR subprocess behavior is unchanged.
- CLI/public contract impact: new `--paragraph-reconstruction conservative|off` on root, `extract`, and `batch`; new `PDFTRANSLATE_PARAGRAPH_*` settings.
- PDF/output integrity impact: raw physical blocks remain immutable; every mapped source fragment is redacted and each logical translation is inserted exactly once.

## Investigation

- Current behavior: extraction flattened lines into physical blocks and an older helper destructively merged adjacent blocks. Translation and rendering operated independently per physical block, losing reversible line/block evidence and providing no conservative document-level reading order.
- Expected behavior: preserve typed raw spans/lines/blocks, reconstruct logical translation paragraphs using auditable conservative signals, retain reversible source mapping, and avoid duplicate rendering.
- Implementation gap: no logical paragraph model existed between PyMuPDF extraction and translation; schemas 1.0/1.1 could not represent reconstruction decisions or mapping.
- Main symbols: `TextLine`, `LogicalParagraph`, `ParagraphFragment`, `SourceBlockMapping`, `ParagraphReconstructionOptions`, `reconstruct_paragraphs`, `translate_paragraphs`, `PdfRenderer.render`, `_redact_paragraph_fragments`.
- Configuration/schema: extracted schema 1.2 and translated schema 1.3; legacy 1.0/1.1 remain readable. Pipeline behavior revision is 3.
- Expected blast radius: extraction JSON, translation units/cache/resume, renderer source validation, diagnostics, CLI/batch identity, and tests. Model loading, OCR execution, and source-PDF mutation boundaries remain unchanged.

## Changes

### Typed reconstruction

- Added `src/pdftranslate/reconstruction/models.py` and `reconstructor.py`.
- Preserved stable physical `TextBlock` values and added typed `TextLine` values with IDs, geometry, original order, and spans.
- Added immutable logical paragraph, fragment, mapping, decision, reason, metrics, and options contracts.
- Conservative decisions use page and column boundaries, horizontal alignment, indentation, vertical gap/line height, width similarity, typography/style, punctuation, lowercase continuation, headings, lists, captions, footnotes, repeated headers/footers, and page-edge evidence.
- Two-column content is ordered column-by-column and is never merged through the gutter.
- Headings/body, separate list items, captions, footnotes, and repeated margin text remain separate.
- Cross-page merging requires consecutive pages, body text, same column/alignment, top/bottom edge proximity, and continuation evidence.
- Soft line-break hyphenation is removed only for a conservative alphabetic split; options, IDs, already compound tokens, and known legitimate prefixes remain protected.
- `off` mode produces exactly one logical unit per physical block.

### Schema, pipeline, and translation

- Extraction emits schema 1.2 with raw pages, logical paragraphs, reversible mappings, decisions, and metrics.
- Translation emits schema 1.3 and translates/caches/checkpoints logical paragraphs instead of duplicating work per physical fragment.
- Raw block text and geometry are unchanged in translated JSON.
- Resume validates paragraph identity and settings; pipeline identity includes reconstruction mode and behavior revision 3.
- Legacy 1.0/1.1 documents remain accepted. Legacy serialization omits accidental reconstruction fields from programmatic legacy objects.

### Renderer and diagnostics

- Paragraph rendering builds one insertion plan on the paragraph anchor page.
- Every fragment rectangle is independently redacted, including cross-page tail fragments; duplicate fragment geometry is redacted once and diagnosed.
- The source PDF is re-extracted with the persisted reconstruction mode and the current paragraph text/fragments are compared with translated JSON before rendering.
- Diagnostics now embed complete reconstruction evidence, the effective typed configuration, and summary metrics for raw lines, logical paragraphs, ambiguity, and cross-page merges.
- Ambiguous decisions produce stable `READING_ORDER_AMBIGUOUS` findings.
- JSON/HTML text evidence follows logical paragraph IDs in schema 1.3.

### CLI and configuration

- Added `--paragraph-reconstruction conservative|off` to root, `extract`, and `batch` workflows.
- Added typed environment settings for alignment, indentation, gap, width, gutter, heading/footnote ratios, margin regions, cross-page edges, and repeated margin occurrence count.
- No Typer dependency leaked into domain/reconstruction/translation code.

## Graph and source validation

- Graphify initially identified `_merge_adjacent_text_blocks`, `ExtractedDocument`, `translate_document`, `PdfRenderer`, and `build_success_report` as the relevant chain; each relationship was verified in source.
- CRG verified `_extract_page` as the old merge caller and renderer/pipeline reachability. Post-change update found no affected registered flow, which is a known limitation for dynamic Typer/Pydantic and fixture-driven Python paths.
- Source verification confirms root/extract/batch CLI construction reaches `PipelineOptions`, pipeline extraction reaches `reconstruct_paragraphs`, schema 1.2 reaches paragraph translation, and schema 1.3 reaches paragraph rendering and diagnostics.
- Graphify post-change refresh succeeded. The first sandboxed refresh failed with WinError 5; the same confirmed command succeeded with permitted local graph writes.
- The first CRG post-change command updated the graph but its panel failed under Windows CP1251; rerunning with `PYTHONIOENCODING=utf-8` completed cleanly.

## Post-change impact

- CRG updated: yes.
- Blast radius: planned extraction → translation → rendering → diagnostics/CLI path only.
- Unexpected dependants: none found.
- Compatibility: 1.0/1.1 JSON remains readable; new extraction defaults to 1.2 and new translations to 1.3. Existing resume workspaces are invalidated by behavior revision 3 rather than silently reused.
- Source safety: source PDF is never overwritten; output still uses temporary validation and atomic publication.

## Validation

- Focused reconstruction: `5 passed`.
- Expanded focused extraction/translation/rendering/pipeline/batch suite: `83 passed`.
- Full `scripts/check.ps1`: `166 passed, 1 skipped in 8.97s`; coverage `86.81%` (required 80%).
- GitHub Actions run `30787940211` for commit `8f69024` completed successfully: Python 3.12 on `ubuntu-latest` and `windows-latest` both passed. Run: https://github.com/bodomus/PDFTranslator/actions/runs/30787940211
- Ruff format: final check reported `110 files already formatted`.
- Ruff lint: passed.
- mypy: no issues in 67 source files.
- CLI smoke tests: root, extract, and batch help exit 0; the new mode is registered on all applicable workflows.
- Benchmark: `scripts/benchmark-paragraph-reconstruction.py --blocks 1000` produced 1,000 blocks, 999 decisions, 999 merged fragments, one logical paragraph, deterministic repeated output, 0.011996 s and 83,357.65 blocks/s on this machine. Artifact: `temp/PDFTR-11-benchmark.json` (not committed).
- Generated end-to-end evidence: schema 1.3 translated JSON and a 570,368-byte rendered PDF were created under `temp/pytest-pdftr11d/test_complete_pipeline_uses_ca0/`. The PDF reopened successfully; extracted text contains `Русский перевод` and does not contain `English source paragraph`.
- Real-model validation: not run; fake translator used to avoid model downloads.
- CUDA validation: not run/not required.
- Real-world PDF validation: not claimed; generated PyMuPDF fixtures were used.
- OCR integration validation: not run; OCR path is unchanged and normal tests remain model/OCR independent.

## Documentation

- Updated `README.md` for schemas 1.2/1.3, reconstruction behavior, renderer mapping, CLI option, settings, compatibility, and limitations.
- Updated `CHANGELOG.md`.
- Added `Tickets/PDFTR-11-paragraph-reconstruction.md`, `investigation.md`, `implementation-plan.md`, benchmark script, focused tests, this report, and `reviews/review-PDFTR-11.md`.

## Remaining risks

- PDF producer quirks can still expose ambiguous geometry; those boundaries are intentionally kept separate and reported instead of guessed.
- Cross-page reconstruction is conservative and can under-merge when page-edge/style evidence is incomplete.
- Paragraph insertion uses the union of anchor-page fragments; complex non-rectangular shapes may still need renderer fitting/overflow handling.
- The generated fixture proves selectable/searchable extracted Russian text and source-text removal programmatically, but this ticket does not claim a new real-model or real-world PDF visual validation.
- The performance benchmark is synthetic and measures reconstruction only; it is not a model, OCR, or rendering benchmark.
