# Investigation — PDFTR-13

## Baseline

- Branch: `codex/PDFTR-13-glossary-protected-terms-and-terminology-consistency`.
- Base: clean `master` at `5737801`; PDFTR-11 and PDFTR-12 are merged and `origin/master` matches.
- Runtime: uv 0.5.26, Python 3.12.10; no dependency change is planned.
- Workflow: Level 2 because glossary behavior crosses translation preparation, protected tokens,
  cache/resume identity, batch runtime reuse, CLI, serialization and diagnostics.
- Ticket Markdown was downloaded from the existing YouTrack attachment into `Tickets/`; the issue
  was moved from Open to In Progress.

## Graph and source findings

- Graphify identified `LogicalParagraph` → `translate_paragraphs()` → `protect_text()` /
  `segment_text()` → translator → `TranslationCache` as the owning translation path, reached by
  root pipeline, direct `translate`, and shared batch runtime. Source inspection confirmed it.
- PDFTR-12 policy is evaluated before skip/cache/model work in `translate_paragraphs()`; therefore
  glossary preparation must remain after policy handling so preserve/skip always wins.
- Protected tokens are converted to `__PDFTR_####__` before segmentation and restored after segment
  recombination. Glossary replacement must precede generic protection so explicit glossary spans
  own overlaps; generic protection can then protect the internal glossary sentinel itself.
- Cache keys currently include backend/model/language/normalized source only. Pipeline workspace
  identity has behavior revision 4 but no glossary fields. Both are insufficient for terminology.
- Batch opens one `TranslationRuntime`, one translator and one SQLite cache, but has no shared
  validated behavior object. The runtime is the correct owner for one loaded glossary per batch.
- `TranslationMetadata` and PDFTR-10 diagnostics are additive typed boundaries suitable for
  optional glossary identity/evidence while keeping legacy no-glossary JSON readable.
- CRG updated successfully at the base and reported broad historical changes relative to its stored
  baseline (92 symbols, risk 0.60). Its dynamic Typer/Pydantic/test mapping is advisory; every
  ticket-relevant relation above was checked in current source.

## Missing capability

1. There is no versioned glossary schema, strict loader, conflict detector or deterministic matcher.
2. Mandatory/preserved terminology cannot take precedence over generic protected-token matching.
3. Cache, checkpoints and workspace resume can reuse translations produced without the same terms.
4. Batch cannot validate/load terminology once before file processing.
5. Translated JSON and diagnostics cannot prove which entries applied or whether output complied.

## Smallest coherent design

- Add a Typer/PyMuPDF/Transformers-independent `pdftranslate.glossary` package containing Pydantic
  contracts, strict UTF-8 loader/fingerprint, deterministic matcher and preparation/restoration.
- Support the ticket's required `translate|preserve`, `whole_word|phrase|exact`, case behavior and
  `fixed|allow_model`. `fixed` and preserve use collision-safe sentinels; `allow_model` is not a
  morphology generator and only validates that the preferred target appears.
- Resolve valid overlaps by priority, length, case sensitivity, match specificity and ID; reject
  semantically conflicting normalized duplicates before model construction.
- Extend generic protection to own glossary sentinels after glossary matching. Restore generic
  protected tokens first, then glossary values, then fail on missing target or any sentinel leak.
- Add optional glossary evidence to translation metadata, not to reconstruction models. Paragraph
  IDs/fragments/mappings remain immutable and full glossary text is never copied per paragraph.
- Include normalized content fingerprint, schema/version, language pair and glossary behavior
  revision in translation cache and pipeline workspace identity. Bump pipeline/cache behavior.
- Add only `--glossary PATH` in strict mode to root, batch and direct translate; defer warn/off
  because optional modes must not be added without complete semantics and tests.
- Load the glossary into `TranslationRuntime`, allowing a batch to validate/load exactly once.

## Compatibility and risk

- No glossary preserves user-visible translation behavior, but cache/workspace identities are
  deliberately invalidated by a behavior revision to prevent silent use of legacy cache entries.
- Legacy schema 1.0–1.3 without glossary metadata remains readable through optional fields.
- Glossary failures occur before model loading/publication. Source PDFs and renderer/OCR heuristics
  remain unchanged.
- Matching is paragraph-bounded and exact/normalized, not fuzzy OCR correction. `allow_model` can
  fail strictly when the backend chooses a different inflection; this is intentional and visible.
- Tests must cover loader conflicts, precedence, protected overlaps, cache/resume, repeated policy,
  diagnostics privacy, CLI/batch validation, generated PDF and a 50–100 paragraph benchmark.

---

# Investigation — PDFTR-12

## Baseline and workflow

- PDFTR-11 was complete and green but absent from `master`; with the user's authorization,
  `master` was fast-forwarded from `3b0bd0f` to `a3887db` and pushed before this branch was made.
- Branch: `codex/PDFTR-12-repeated-headers-footers-and-boilerplate-detection` from `a3887db`.
- Workflow level: Level 2 because classification affects extraction, paragraph reconstruction,
  translation/cache behavior, rendering, pipeline identity, batch, CLI, diagnostics and schemas.
- YouTrack PDFTR-12 was moved from Open to In Progress; its Markdown attachment already existed,
  and the repository copy is under `Tickets/`.

## Repository intelligence and source verification

- Graphify traced the production path from PyMuPDF extraction through paragraph reconstruction,
  document serialization, paragraph translation, rendering and PDFTR-10 diagnostics.
- CRG was rebuilt at the branch base: 93 files parsed and approximately 826 nodes / 6,996 edges.
  It found six callers/tests/benchmark relationships for `reconstruct_paragraphs`; source review
  additionally confirmed the PyMuPDF adapter call that CRG did not expose.
- Source inspection confirmed that PDFTR-11's repeated-margin logic was local to reconstruction,
  had only a normalized-text/page-margin count, and could not persist classification evidence or
  influence translation, rendering, diagnostics, resume identity or batch behavior.

## Capability gap

1. Page numbers, alternating headers, first/last-page exceptions, legal boilerplate, watermark
   candidates and uncertain repeated text had no distinct typed classifications.
2. Repeated physical blocks were retained, but the old reconstruction-only rule could label only
   repeated top/bottom text and had no group, confidence, policy, parity, geometry or font evidence.
3. Translation could translate page numbers/watermarks unnecessarily, and policy behavior was not
   explicit. Rendering could not intentionally retain source-only repeated units.
4. Diagnostics did not report repeated-element counts or per-unit classification evidence.
5. Pipeline/cache identity did not distinguish automatic classification from compatibility-off mode.

## Smallest coherent design

- Add a pure `pdftranslate.repeated` classifier and immutable typed evidence models, independent of
  Typer, translation backends and PyMuPDF mutation.
- Classify every original block. Automatic policy is conservative: translate confirmed headers,
  footers and legal text; preserve page numbers and uncertain groups; skip watermark translation
  while leaving its source content untouched; never select `remove` automatically.
- Run classification before reconstruction, isolate confirmed non-body units from merging, persist
  evidence in schema 1.2/1.3, and propagate `auto|off` through root/extract/batch options.
- Use the normal translation cache/deduplication for repeated translatable text, apply policy during
  translation/rendering, expose evidence in diagnostics, and bump pipeline behavior revision.

## Risks and validation obligations

- Heuristics can produce false positives; short documents and weak evidence must remain ambiguous
  and preserved. Legitimately repeated body text with unstable geometry must remain body.
- Generated fixtures must cover all requested classes, parity, first-page exceptions, policy,
  translation reuse, page-specific rendering, privacy-safe diagnostics and compatibility-off mode.
- No model, CUDA or OCR dependency belongs in normal tests. A deterministic benchmark must quantify
  reduced body noise; full `scripts/check.ps1` and post-change Graphify/CRG checks remain required.

---

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
