# Implementation Report

## Ticket

PDFTR-16 — Fix false protected token detection for slash-separated prose and PDF ligatures.

## Workflow

- Level: 1
- Graphify: existing graph queried for protected-token context.
- CRG: updated successfully after setting UTF-8 output.
- Working tree before changes: dirty; user PDF fixture changes were present and preserved.

## Scope

- Modules: `src/pdftranslate/translation/text.py`
- Tests: `tests/test_translation.py`
- Documentation: `CHANGELOG.md`
- Pipeline stages: translation text preparation, protected-token matching, cache/source text
  normalization.
- Dependency impact: none.
- Model/device/OCR impact: none.
- CLI/public contract impact: none.
- PDF/output integrity impact: no source or output PDF writes changed.

## Investigation

- Current behavior: the generic protected-token regex treated any `word/word` span as a path-like
  token, so ordinary slash-separated prose could bypass translation.
- Expected behavior: ordinary prose such as `nature/agreement`, `virtue/pleasure`, and `and/or`
  remains translatable while real paths and existing protected tokens remain protected.
- Root cause: the bare path branch had no path/file specificity beyond containing `/`.
- Secondary gap: NFC normalization preserved common PDF ligature code points such as `ﬁ` and `ﬂ`.
- Main symbols: `normalize_source_text`, `should_skip_translation`, `protect_text`.
- Expected blast radius: local to translation preparation, cache identity, and protected-token
  restoration inputs.

## Changes

- Added explicit normalization for common PDF ligatures before cache/source normalization, skip
  checks, and protected-token matching.
- Replaced broad slash path matching with stricter relative, absolute POSIX, and file-like bare
  path patterns.
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
- Compatibility concerns: ligature normalization changes cache identity for affected text, which is
  intended because model input should use decomposed prose characters.

## Validation

- `uv run pytest tests/test_translation.py -q --no-cov`: passed.
- `uv run pytest tests/test_glossary.py tests/test_translation.py -q --no-cov`: passed.
- `uv run ruff format --check src\pdftranslate\translation\text.py tests\test_translation.py`:
  passed.
- `uv run ruff check src\pdftranslate\translation\text.py tests\test_translation.py`: passed.
- `uv run mypy src\pdftranslate\translation\text.py`: passed.
- `.\scripts\check.ps1`: passed, 202 passed and 1 skipped.
- Manual representative PDF check: opened the provided 4-page PDF with PyMuPDF and found no
  slash-prose candidates or slash protected-token matches on that sample.

## Documentation

- Updated: `CHANGELOG.md`.
- README not updated because the public CLI contract and documented token categories did not
  change.

## Remaining risks

- The file-path heuristic remains conservative and may not protect every extensionless bare Unix
  path. Explicit relative/absolute paths and file-like paths are covered.
