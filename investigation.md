# Investigation — PDFTR-11

## Baseline

- Branch: `codex/PDFTR-11-paragraph-reconstruction-and-reading-order`.
- Base: `3b0bd0f` (`master` at branch creation).
- Initial working tree: clean before the required local ticket Markdown was added.
- Workflow level: Level 2 because the feature crosses extraction, domain serialization,
  translation, rendering, diagnostics, pipeline identity, CLI, benchmarks and documentation.
- Runtime baseline: uv 0.5.26 and Python 3.12.10.
- YouTrack: PDFTR-11 is assigned to `bodomus`, moved from Open to In Progress, and already has
  `PDFTR-11-paragraph-reconstruction.md` attached.

## Repository intelligence

- Graphify graph exists and was queried after `graphify reflect --if-stale`; vocabulary-expanded
  BFS covered paragraph, fragment, block, extraction, document, translation, renderer,
  diagnostics, order, page, layout and dehyphenation concepts.
- Graphify identified `_merge_adjacent_text_blocks()`, `ExtractedDocument`,
  `translate_document()`, `PdfRenderer` and `build_success_report()` as the main path. Source
  inspection confirmed each relationship.
- CRG updated successfully at base SHA `3b0bd0f`: 725 nodes and 6,082 edges across 81 files.
  Scoped queries found `_extract_page()` as the production caller of
  `_merge_adjacent_text_blocks()`, plus two direct extraction tests. CRG's `tests_for` heuristic
  missed those direct callers, so source and pytest remain authoritative.

## Current behavior and capability gap

1. `_text_block_from_dict()` flattens PyMuPDF lines into a newline-delimited `TextBlock` and
   flattens spans; line identity and geometry are not retained as typed values.
2. `_merge_adjacent_text_blocks()` destructively joins nearby blocks only when the next block
   starts lowercase, widths are similar, left edges are within 8 points, vertical distance is
   small and the previous text is unfinished.
3. The destructive merge replaces all source rectangles with one bounding-box union, renumbers
   blocks and loses the original block-ID mapping. It cannot explain a decision.
4. A trailing hyphen followed by lowercase is always removed. The rule cannot distinguish a soft
   line-break hyphen from a legitimate compound, CLI option or identifier.
5. There is no explicit column, list, heading, caption, footnote, repeated header/footer or
   cross-page continuation model.
6. `translate_document()` translates every `page.text_blocks` entry independently and caches by
   normalized block text. It has no logical-paragraph unit.
7. `PdfRenderer` validates and renders one rectangle per translated block. It cannot redact a
   reversible set of source rectangles while inserting one paragraph translation once.
8. PDFTR-10 diagnostics join translation and rendering evidence by block ID and only infer a
   generic reading-order warning from page warning strings; merge decisions and metrics are absent.

## Expected behavior

- Preserve raw lines, spans, source blocks and their geometry.
- Reconstruct deterministic logical paragraphs before translation with conservative typed rules.
- Keep columns, headings, list items, captions and footnotes separate unless evidence is strong.
- Permit cross-page continuation only for consecutive pages and strong aligned body-text evidence.
- Store every merge/keep/ambiguous decision with stable reason codes.
- Translate each logical paragraph once.
- Redact every mapped source rectangle and render the translated paragraph once in a deterministic
  anchor rectangle: the union of that paragraph's fragments on its first page. Cross-page tail
  rectangles are redacted, not rendered again; fitting/overflow diagnostics remain explicit.

## Smallest coherent architecture

- Add a focused `reconstruction` package with immutable typed models, options and a pure
  deterministic reconstructor. Do not place paragraph rules in Typer, PyMuPDF or the translator.
- Extend the document model with raw line geometry and optional reconstruction evidence while
  keeping legacy schema 1.0/1.1 readable.
- Introduce schema 1.2 for reconstructed extracted documents and 1.3 for their translated form.
- Keep physical `TextBlock` values on pages for reversible validation; store logical paragraphs at
  document level and make translation/rendering select paragraph units only for schema 1.2/1.3.
- Add one CLI mode (`conservative` default, `off` compatibility mode); keep tolerances in a typed
  `ParagraphReconstructionOptions` built from validated Settings fields.
- Increment the pipeline behavior revision so resume/workspace artifacts cannot mix old and new
  extraction semantics.

## Adjacent contracts and risks

- JSON: schema versions and Pydantic validators must distinguish legacy block translation from
  reconstructed paragraph translation and preserve UTF-8 round trips.
- Cache: paragraph text changes cache identity naturally; the workspace behavior revision must
  invalidate old extracted/translated artifacts.
- Rendering: source PDF remains immutable; all mapped rectangles must be validated against the
  current source extraction; no translated paragraph may be inserted twice.
- Hyphens: conservative soft-hyphen removal needs negative tests for compounds, `--options`,
  identifiers, numeric tokens and dash punctuation.
- Cross-page layout: the anchor-only strategy is deterministic and duplicate-safe, but long
  translations may overflow the first-page anchor; this must remain visible rather than clipped.
- OCR: reconstructed text is based on the post-OCR PDF through the same extractor; no subprocess
  boundary changes are required.
- Model/CUDA: model loading, device selection and inference code remain unchanged; tests use fakes.
- Batch: the selected reconstruction mode is behavior-affecting and must propagate into every
  per-file `PipelineOptions` value.

## Validation obligations

- Pure generated model fixtures for every rule and ambiguity decision.
- Generated PDFs for ordinary wrapping, two columns and reversible multi-rectangle rendering.
- Translation tests proving one call/result per paragraph.
- Serialization round trip and legacy schema compatibility tests.
- Diagnostic JSON/HTML evidence for decisions and metrics.
- Before/after reconstruction benchmark cases with deterministic expected text/mapping.
- Focused extraction/reconstruction/translation/rendering/diagnostic/pipeline/CLI tests.
- Full `.\scripts\check.ps1`, post-change CRG, Graphify refresh because domain and pipeline
  relationships change, and an honest record of opt-in real-model/CUDA/OCR/real-PDF status.

## Documentation impact

- README extraction, schema, CLI and troubleshooting guidance.
- CHANGELOG Unreleased entries.
- Typer help for reconstruction mode.
- Ticket implementation report and `reviews/review-PDFTR-11.md`.
