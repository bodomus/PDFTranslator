# Implementation Report

## Ticket

PDFTR-16 — Fix false protected token detection for slash-separated prose and PDF ligatures.

## Workflow

- Level: 1
- Graphify: existing graph queried for protected-token context.
- CRG: updated successfully after setting UTF-8 output.
- Working tree before changes: dirty; user PDF fixture changes were present and preserved.

## Scope

- Modules: `src/pdftranslate/translation/text.py`, `src/pdftranslate/translation/cache.py`,
  `src/pdftranslate/pipeline/models.py`
- Tests: `tests/test_translation.py`, `tests/test_end_to_end_pipeline.py`
- Documentation: `CHANGELOG.md`
- Pipeline stages: translation text preparation, protected-token matching, cache/source text
  normalization.
- Dependency impact: none.
- Model/device/OCR impact: CUDA regression was run against the representative PDF; no OCR change.
- CLI/public contract impact: none.
- PDF/output integrity impact: no source or output PDF writes changed.

## Investigation

- Current behavior: the generic protected-token regex treated any `word/word` span as a path-like
  token, so ordinary slash-separated prose could bypass translation.
- Expected behavior: ordinary prose such as `nature/agreement`, `virtue/pleasure`, and `and/or`
  remains translatable while real paths and existing protected tokens remain protected.
- Root cause: the bare path branch had no path/file specificity beyond containing `/`.
- Secondary gap: NFC normalization preserved common PDF ligature code points such as `ﬁ` and `ﬂ`.
- PDFTR-16A gap: translation cache keys were revisioned, but the pipeline workspace identity did
  not include the translation behavior revision, so old resume artifacts could still be compatible.
- Main symbols: `normalize_source_text`, `should_skip_translation`, `protect_text`,
  `TRANSLATION_BEHAVIOR_REVISION`, `PipelineOptions.identity_values`.
- Expected blast radius: local to translation preparation, cache identity, and protected-token
  restoration inputs.

## Changes

- Added explicit normalization for common PDF ligatures before cache/source normalization, skip
  checks, and protected-token matching.
- Replaced broad slash path matching with stricter relative, absolute POSIX, and file-like bare
  path patterns.
- Tightened bare path detection again for PDFTR-16A: bare slash paths require a file-like final
  segment with an extension; explicit `./`, `../`, absolute POSIX paths, and Windows paths remain
  protected without relying on a dictionary of prose examples.
- Bumped `TRANSLATION_BEHAVIOR_REVISION` from 2 to 3 because protected-token preprocessing now
  changes model-facing text for slash-separated prose and PDF ligatures.
- Added `translation_behavior_revision` to pipeline workspace identity so `--resume` cannot reuse
  old translate artifacts after the preprocessing change.
- Added regression coverage for slash-separated prose, retained file-path protection, and ligature
  normalization.
- Updated the changelog.

## Graph and source validation

- Graphify query identified protected-token and translation cache/test neighborhoods; findings were
  source-verified in `translation/text.py`, `translation/pipeline.py`, and `translation/paragraphs.py`.
- CRG `status` and `update --brief` succeeded after UTF-8 output was set.
- Source validation confirmed both legacy block translation and paragraph translation call
  `normalize_source_text`, `should_skip_translation`, `protect_text`, and `segment_text` from the
  same module.
- Discrepancy: initial CRG update printed a Unicode encoding error under cp1251, then succeeded
  with `PYTHONIOENCODING=utf-8`.

## Post-change impact

- CRG updated: yes.
- Blast radius: confined to text normalization/protection helpers and their direct callers.
- Unexpected dependants: none found.
- Compatibility concerns: old translation-memory entries and old pipeline workspaces for identical
  source/options are intentionally invalidated by translation behavior revision 3.

## Validation

- `uv run pytest tests/test_translation.py tests/test_end_to_end_pipeline.py::test_pipeline_identity_includes_behavior_revision -q --no-cov`:
  passed.
- `uv run pytest tests/test_glossary.py tests/test_translation.py -q --no-cov`: passed.
- `uv run ruff format --check .`: passed via `.\scripts\check.ps1`.
- `uv run ruff check .`: passed via `.\scripts\check.ps1`.
- `uv run mypy src`: passed.
- `.\scripts\check.ps1`: passed, 222 passed and 1 skipped.
- Manual representative PDF check: opened the provided 4-page PDF with PyMuPDF and found no
  slash-prose candidates or slash protected-token matches on that sample.
- Real CUDA regression:
  `uv run pdftranslate ".\tests\Robitzsch Jan Maximilian - Epicurean Justice. Nature, Agreement, and Virtue - 2024_50.pdf" --device cuda --output .\test10textpages.ru.pdf`
  proceeded beyond the previous protected-token error. Translation completed with
  `effective_device=cuda`, backend `nllb`, model `facebook/nllb-200-distilled-600M`, and statistics
  `61/61 completed`, `2 cache hit(s)`, `59 cache miss(es)`, `59 translated segment(s)`.
- Real CUDA next failure: stage `5/6 Render` failed with
  `translated text is missing for paragraph(s): p0001-b0008, p0002-b0007, p0003-b0007, p0004-b0005`.
  No `test10textpages.ru.pdf` final output was published.

## Documentation

- Updated: `CHANGELOG.md`.
- README not updated because the public CLI contract and documented token categories did not
  change.

## Remaining risks

- The file-path heuristic intentionally does not protect extensionless bare `word/word` paths
  without `./`, `../`, or leading `/`, because that shape is indistinguishable from common prose
  alternatives.
- The real CUDA run exposed a later rendering validation issue for missing translated text on
  repeated/anchor paragraph IDs; this is beyond the original protected-token failure.
