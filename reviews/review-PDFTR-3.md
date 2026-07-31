# PDFTR-3 Review

## Result

Implemented the local English-to-Russian translation stage:

```powershell
pdftranslate translate document.json --output document.ru.json
```

The implementation consumes extracted schema 1.0 JSON and writes compatible schema 1.1 JSON
containing original and translated block text plus lifecycle metadata.

## Implementation

- Added a backend-independent `Translator` protocol.
- Added the direct NLLB backend for `facebook/nllb-200-distilled-600M` with `eng_Latn` to
  `rus_Cyrl`.
- Added CPU, CUDA, and probed `auto` device selection.
- The NLLB tokenizer/model are constructed once per command process and reused for every block.
- Transformers/PyTorch values remain inside the NLLB adapter.
- Added local-only offline loading, configured model cache paths, tokenizer-limit validation,
  inference mode plus evaluation mode, and clear missing-model failures.
- Added bounded CUDA OOM recovery: automatic mode can move to CPU once, and batches are split by
  repeated halving without an unbounded retry loop.
- Added deterministic skip rules, protected URLs/email/path/measurement/identifier restoration,
  sentence/paragraph-aware segmentation, forced-split warnings, and no tokenizer truncation.
- Added SQLite translation memory keyed by backend, model, language pair, and normalized source.
- Added atomic in-progress/interrupted/completed checkpoints and validated `--resume`.
- Added plain-log-friendly model loading, per-block progress, cache counters, device, elapsed time,
  and final statistics.
- Added every required CLI option.

## Data and safety

- Schema 1.0 remains readable and serializes without translation-only fields.
- Schema 1.1 retains source identity, layout, and original text and adds `translated_text`.
- Source PDF files are never opened by the translation layer and cannot be overwritten by the
  existing serializer.
- Default model and translation-memory data live under the platform application cache, not the
  repository.
- Cache corruption and protected-token loss are explicit recoverable failures.
- Unit tests and CI use injected fakes and never download or load NLLB weights.

## Dependencies and documentation

- Added locked PyTorch and Hugging Face Transformers dependencies because the ticket requires a
  local NLLB backend.
- Context7 was consulted for current tokenizer, CUDA, inference-mode, and OOM behavior.
- The official NLLB model card was used for direct loading guidance, the approximate 2.5 GB
  repository size, and the CC-BY-NC-4.0 license notice.
- README documents command usage, all runtime options, cache/offline/device behavior, storage
  estimate, protected text, schema 1.1, interruption/resume, and limitations.
- CHANGELOG documents the new user-visible behavior and safety properties.

## Verification

Required `.\scripts\check.ps1` result:

- Ruff formatting: passed.
- Ruff lint: passed.
- strict mypy: passed.
- pytest: 63 passed.
- branch coverage: 85.28% (required minimum: 80%).
- CLI `translate --help`: passed with all required options.
- Installed locked runtime versions used for the smoke check: PyTorch 2.13.0+cpu and
  Transformers 5.14.1.
- No model weights were downloaded.

Test coverage includes:

- translator abstraction and fake backend;
- batching and bounded OOM splitting;
- long-block segmentation and paragraph breaks;
- empty/page-number/code/measurement/identifier skip behavior;
- exact protected token restoration and failure;
- duplicate and cross-run cache hits plus corrupt-cache handling;
- CPU/CUDA/auto selection and CUDA probe fallback;
- offline missing-model reporting and tokenizer-limit enforcement;
- one-time NLLB loading and automatic CUDA OOM CPU fallback;
- schema 1.0 compatibility and schema 1.1 output integrity;
- interruption checkpoint and successful resume;
- CLI success/progress and unsupported-backend failure.

## Repository intelligence

- Graphify 0.9.8 was queried before implementation and incrementally refreshed afterward.
- Post-change code graph: 607 nodes and 1,247 edges.
- The graph connects `translate_json`, `translate_document`, `NllbTranslator`,
  `TranslationCache`, protection/segmentation helpers, schema models, and tests.
- Changed Markdown was not semantically re-indexed because no Graphify semantic backend was
  configured; all documentation conclusions were verified directly in source.
- Code-review-graph was refreshed and used for exact reachability/blast-radius checks. Its final
  staged-source result is recorded in the ticket comment and commit handoff.

## Non-goals preserved

No PDF rendering, OCR, cloud translation API, GUI, extra language pair, fine-tuning, or glossary
editor was added.
