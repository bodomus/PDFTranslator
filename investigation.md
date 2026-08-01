# Investigation — PDFTR-10

## Baseline

- Branch: `codex/PDFTR-10-layout-diagnostics-and-reporting`.
- Base: `b490ff3` (`master` at branch creation).
- Workflow: Level 2.
- Working tree before ticket files: clean; Git emits a permission warning for ignored `.temppytest-cache/`.
- PDFTR-9A commit `a6027c4` is not in `master` and was not transplanted, per the explicit request to branch from `master`.

## Current behavior

- `run_pipeline()` owns inspect → OCR → extract → translate → render → validate orchestration.
- `PdfRenderer.render()` already returns block-level source/final boxes, initial/final font sizes, expansion and overflow, plus aggregate warnings and an optional separate debug PDF.
- The pipeline currently discards `RenderResult` and does not enable renderer debug output.
- `TranslationMetadata.statistics` exposes aggregate block, cache and segment counters, but not per-block segment/cache evidence.
- OCR exposes processed pages and warnings; extracted pages expose classification, dimensions, blocks and stable block IDs.
- Batch and validation have separate reports, but there is no privacy-safe per-translation JSON/HTML report or centralized stable diagnostic-code vocabulary.
- CLI `run` exposes no report options.

## Expected behavior

An explicitly requested report must be JSON, self-contained offline HTML, or both. It must combine available inspect/OCR/translation/render/validation evidence, omit text by default, optionally include it, and retain a best-effort failure report when a stage fails after report initialization. `--debug-layout` must publish a separate annotated PDF without changing normal output.

## Smallest coherent design

1. Add a focused `diagnostics` package with stable codes, immutable report models, a builder, and atomic JSON/HTML writers.
2. Extend `PipelineOptions` with report/debug settings; keep them out of artifact identity because they do not change translation output.
3. Preserve and return `RenderResult` from the render stage; use it for block diagnostics.
4. Build success/failure reports in pipeline orchestration, where all stage evidence and errors are visible. Reporting failures must not replace the primary pipeline error.
5. Reuse renderer debug-layout support and atomically copy its validated artifact to the requested report directory.
6. Keep Typer limited to parsing options and printing artifact paths.

## Boundaries and compatibility

- No dependency additions are required; HTML uses the standard library and escaped content.
- Existing output PDF publication, source immutability, document schema and cache keys remain unchanged.
- Machine-readable reports contain plain strings only.
- Per-block `segmentation_count` and `cache_status` can only be `unknown` with the current callback contract; aggregate values remain exact. Inventing evidence would be incorrect.
- Peak RAM can be measured with `tracemalloc`; peak VRAM is nullable unless reliably exposed without a dependency.
- Resume may lack historical block fitting evidence; unavailable values must remain explicit.

## Graph and source evidence

- Graphify BFS connected `run_pipeline`, `PipelineOptions`, `PipelineWorkspace`, `PdfRenderer`, `TranslationStatistics`, `OcrProcessor`, validation and tests.
- CRG refreshed at `4797ab7` with 705 FTS rows. Exact symbol searches confirmed the same owners; multi-term searches returned no matches.
- CRG's decorative console panel fails under Windows CP1251 after emitting valid counts; source and tests remain authoritative.

## Test areas

- Diagnostics models/writers/builders: privacy, opt-in Cyrillic text, stable codes, offline HTML, success and failure.
- Rendering: annotated IDs/rectangles and normal-output separation.
- Pipeline: report production, cache/OCR/overflow data and failure best effort.
- CLI: option propagation and help.
- Full gate plus generated PDF validation; no model, CUDA or OCR downloads.
