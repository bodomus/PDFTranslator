# Implementation Report — PDFTR-13

## Git state

- Branch: `codex/PDFTR-13-glossary-protected-terms-and-terminology-consistency`.
- Base commit: `5737801fa38d394fea8243467b60e020b8f8db30` (`master`, including PDFTR-11 and PDFTR-12).
- Working tree before changes: clean; ticket Markdown was then downloaded from the existing YouTrack attachment.
- PDFTR-11/PDFTR-12 prerequisite confirmation: schema 1.2 logical paragraphs and repeated-element policy evidence were present on `master` and source-verified before implementation.

## Investigation

- Current paragraph translation path: `translate_document` dispatches schema 1.2 to `translate_paragraphs`; physical blocks remain immutable and schema 1.3 persists paragraph translations.
- Protected-token path: generic tokens are replaced before segmentation/model inference and restored only after recombination.
- Repeated-element policy path: paragraph fragments are mapped to repeated classifications; `preserve` and `skip` are handled before cache/model work.
- Cache/resume identity: cache keys previously covered backend/model/languages/source only; pipeline workspace identity used behavior revision 4 and no glossary identity.
- Diagnostics path: PDFTR-10 report models/builders consume translated metadata and expose text only through explicit opt-in.
- Graphify/CRG: preflight found the reachable path `CLI/batch -> PipelineOptions -> TranslationRuntime -> translate_document -> translate_paragraphs -> cache/checkpoint -> renderer/diagnostics`. Post-change Graphify was rebuilt to 1,824 nodes/3,974 edges/119 communities. CRG indexed 891 rows; its heuristic change scan reports risk 0.55 and 49 possible gaps, while the focused and full executable gates below cover the public flow. The first Graphify refresh failed with sandbox `WinError 5`; the required elevated retry succeeded.

## Glossary design

- Schema: strict immutable UTF-8 JSON schema `1.0`, semantic `glossary_version`, EN→RU language pair, non-empty typed entries, unknown fields forbidden.
- Matching: paragraph-bounded `whole_word`, `phrase`, and `exact`; optional case-insensitivity; deterministic overlap ordering by priority, length, case specificity, match specificity, stable ID.
- Conflict rules: duplicate IDs, conflicting normalized sources/targets, preserve/translate conflicts, invalid policy combinations, and reserved placeholder collisions fail at load time.
- Placeholder strategy: fixed translate and preserve spans become `__PDFTR_GLOSSARY_NNNN__`; `allow_model` remains visible to the model but final preferred-target validation is strict.
- Protected-token precedence: repeated preserve/skip wins first; otherwise explicit glossary span owns the source overlap. The glossary sentinel is itself protected by the generic token layer. Generic restoration therefore occurs first, followed by glossary restoration and final validation. This source-verified nesting intentionally differs from the ticket’s illustrative restore ordering and prevents model exposure of either placeholder layer.
- Inflection: `fixed` is exact replacement; `allow_model` only validates the configured target and makes no automatic morphology claim.
- Fingerprint: SHA-256 over canonical schema/version/languages/behavior revision and effective entries sorted by ID. File path, mtime, notes, and semantically equivalent entry order do not affect it.

## Implementation

- Modules: new `src/pdftranslate/glossary/{models,errors,loader,matcher,processor}.py` package and public exports.
- Pipeline integration: glossary preparation runs on logical paragraphs before generic protection/segmentation; only final restored and validated text reaches cache/checkpoints/rendering.
- Repeated elements: preserve/skip precedes glossary; translated identical headers deduplicate through the existing in-run work map and share evidence per paragraph ID.
- Cache/resume changes: translation behavior revision is 2; cache keys include semantic fingerprint or explicit `no-glossary`; pipeline behavior revision is 5; workspaces and resume metadata include fingerprint/schema/version/languages/behavior revision.
- Batch behavior: `open_translation_runtime` loads and validates one immutable glossary before file processing, then reuses it; each success record includes fingerprint and matched/unmatched/applied/preserved/violation counts.
- CLI/configuration: `--glossary PATH` added to root PDF translation, `batch`, and direct `translate`; direct JSON translation validates glossary and schema before constructing NLLB. Strict mode only is exposed.
- Diagnostics: six stable glossary codes, document summary counts/fingerprint/version, per-paragraph entry IDs/modes/count/compliance, and unused-entry findings. Source and target strings remain absent by default.
- Serialization/compatibility: optional glossary evidence was added to translation metadata; legacy no-glossary documents remain readable. No full glossary is duplicated into paragraph records.
- Documentation: README, CHANGELOG, `docs/glossary.md`, public-safe example JSON, ticket plan/investigation, and persistent `.implementation` report rule in `AGENTS.md`.

## Tests

- Loading/validation: valid, malformed JSON, invalid UTF-8, duplicates, conflicts, language, reserved namespace, semantic/path/order fingerprint.
- Matching: case, Unicode boundaries, phrase whitespace, exact paragraph, punctuation, occurrences, priority and overlap.
- Translation integration: fixed/preserve/allow-model, nested generic protection, missing/damaged placeholders, target validation, numbers and identifier `1900-1`.
- Stable text structure: integration runs on schema 1.2 reconstructed paragraphs and retains source mappings/IDs.
- Repeated elements: repeated translated header deduplicates; per-paragraph evidence counts three uses; page numbers remain preserved.
- Cache/resume: changed target/version produces a different fingerprint and cache miss; resume compares persisted glossary fingerprint.
- CLI/batch: help exposes `--glossary` on root translation, batch, and direct translate; batch help assertion remains deterministic and includes it.
- Diagnostics: stable codes, privacy default, summary and paragraph evidence, unused-entry finding behavior.
- Generated PDF: three-page generated fixture translates/searches `Секретная служба`, removes `Secret Service`, preserves `ZX-1900-1` semantically, contains no internal placeholder, and builds privacy-safe diagnostics.

## Benchmark

- Dataset: 64 deterministic synthetic paragraphs, 3,830 characters, two glossary entries, 128 expected matches.
- Baseline: 0 matches; 0.0000043 seconds in the recorded local run.
- With glossary: 128 matches; 0.0015611 seconds.
- Violations: 0.
- False matches: 0 for the deterministic expected set.
- Cache/model calls: 0; this benchmark measures matcher/preparation overhead, not inference or semantic quality.
- Result: `temp/pdftr13-benchmark.json` (intentionally uncommitted).

## Real validation

- PDF: generated three-page fixture at `temp/pytest-pdf2/test_generated_pdf_glossary_is0/glossary-output.pdf` (intentionally uncommitted).
- Pages: 3, with repeated header, body term, identifier, date, and page number.
- Model/device: deterministic fake backend on CPU; no NLLB model download.
- Glossary: strict schema 1.0 with one fixed translation and one preserve entry.
- Expected terms: `Секретная служба` three times; `ZX-1900-1` three times; no `Secret Service` or placeholder.
- Actual terms: expectations passed after normalizing renderer text-extraction U+2010 hyphens to ASCII for comparison.
- Manual review: automated rendered-text/search assertions passed. No claim is made about manual PDF-XChange selection/copy testing in this ticket run.
- Limitations: real NLLB, CUDA, OCR, and external real-world PDF corpus were not run. Renderer text extraction substitutes U+2010 for ASCII hyphen in the identifier/date; glossary metadata/cache retain the configured ASCII value, so this is recorded as renderer-layer behavior rather than glossary/model corruption.

## Full validation

- Focused tests: 62 passed across glossary, translation, reconstruction, repeated elements, rendering, diagnostics, CLI, and batch CLI.
- Full pytest/check gate: 189 passed, 1 skipped.
- Coverage: 87.78% (required ≥80%).
- Ruff format/check: passed; 126 files formatted/verified.
- mypy: passed for 76 source files.
- `scripts/check.ps1`: passed.
- CLI help: `root=True batch=True translate=True` for `--glossary`.
- GitHub Actions: pending push at report creation; update after remote workflow completes.

## Remaining risks

- `allow_model` is strict preferred-target validation, not Russian morphology.
- Matcher ambiguity is eliminated by deterministic precedence; semantic conflicts fail at load. The `GLOSSARY_MATCH_AMBIGUOUS` code is reserved for future warning-mode evidence and is not emitted in strict deterministic success runs.
- A glossary failure stops publication, but failure reports currently surface the pipeline-stage failure plus the actionable exception message; glossary-specific success/unused evidence is richer than failure-report structure.
- Generated fake-backed validation proves pipeline/render/search behavior, not NLLB translation quality.
- Graphify produced a benign warning that JSON examples generate no AST nodes.

## Recommendation

- Ready for review after GitHub Actions is green. PDFTR-14 was not started.
