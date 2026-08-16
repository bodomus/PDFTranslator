# Implementation Report

## Ticket

PDFTR-18 — Diagnose and fix post-save Cyrillic render validation failure.

## Workflow

- Level: 2
- Graphify: used for renderer/pipeline orientation
- CRG: rebuilt before and after implementation
- Working tree before changes: dirty with unrelated `temp/.agents.zip` deletion and untracked
  test PDFs

## Scope

- Modules: `src/pdftranslate/rendering/renderer.py`
- Pipeline stages: render, post-save output validation
- Dependency impact: none
- Model/device impact: none
- OCR impact: none
- CLI/public contract impact: debug-layout mode can now preserve a failed render PDF under an
  explicit diagnostic filename
- PDF/output integrity impact: final output remains atomic; failed PDFs are not published under
  the requested output path

## Investigation

- Current behavior: the Robitzsch CUDA run reached render and failed with
  `generated PDF is missing inserted Cyrillic text on page 1`.
- Expected behavior: post-save validation should accept text that is visibly inserted and
  extractable with equivalent Unicode semantics, while still rejecting missing or truncated text.
- Exact failed unit: page 1, block/paragraph `p0001-b0003`.
- Source bbox: `(67.35, 169.53, 378.22, 305.85)`.
- Final bbox: `(67.35, 169.53, 378.22, 305.85)`.
- Font path: `C:\Windows\Fonts\segoeui.ttf`.
- Font size: `10.958999633789062`.
- Overflow: `False`.
- Expanded: `False`.
- Expected text included normal parentheses around `см. местоимя ipsi ...`.
- Saved-PDF extraction returned the same inserted Cyrillic text in the same rectangle, but mapped
  the parentheses to `U+FD3E` and `U+FD3F`.
- Classification: false-negative validation caused by PDF text extraction punctuation
  representation, not missing insertion, clipping, or broken Cyrillic Unicode mapping.

## Changes

- Replaced anonymous page-level expected strings with `_ExpectedText` render-unit records that
  carry page number, block ID, source/translated text, source/final bboxes, font path, font size,
  overflow, and expansion state.
- Post-save validation now uses a padded extraction clip around each render unit's final bbox as
  the authoritative proof of insertion. Page-wide extraction is retained only for diagnostics and
  cannot make a missing duplicate render unit pass.
- Normalization now maps PDF extraction hyphen variants and `U+FD3E`/`U+FD3F` parenthesis forms
  to their common comparison forms.
- Validation failure diagnostics now include block ID, page, expected snippet, extracted clip
  snippet, page-text snippet, source/final bboxes, font path, font size, overflow, and expansion
  state.
- When `debug_layout` is enabled, a failed temporary render is copied to
  `<output-stem>.failed-render.pdf`; normal runs keep cleanup behavior and never publish failed
  output as the requested final PDF.

## Graph and source validation

- Graphify identified renderer ownership around `PdfRenderer.render`, `_plan_page`,
  `_insert_page`, `_validate_saved_pdf`, `RenderOptions`, and pipeline `_render`.
- CRG was rebuilt on `codex/PDFTR-18-post-save-cyrillic-validation` before implementation and
  after implementation.
- Source validation confirmed the CLI/pipeline reaches the renderer through
  `src/pdftranslate/pipeline/runner.py::_render`.
- Source validation confirmed production output remains atomic: the temporary PDF is validated
  before `temporary_output.replace(output)`.

## Post-change impact

- CRG updated: yes, `118 files`, `1055 nodes`, `9263 edges`.
- Blast radius: localized to renderer post-save validation and rendering tests.
- Unexpected dependants: none found.
- Compatibility concerns: no schema, cache, translation, OCR, dependency, or model contract change.

## Validation

- Focused tests: `uv run pytest --no-cov tests/test_rendering.py` — `16 passed`.
- Duplicate-text regression: two expected units with identical Russian text now fail if the
  second unit's local bbox is empty, even though the same text exists elsewhere on the page.
- Ruff format: `uv run ruff format --check .` — `153 files already formatted`.
- Ruff lint: `uv run ruff check .` — `All checks passed`.
- mypy: `uv run mypy src` — `Success: no issues found in 83 source files`.
- Full gate: `.\scripts\check.ps1` — `230 passed, 1 skipped`, coverage `88.62%`.

## Real-model Validation

Command:

```powershell
uv run pdftranslate ".\tests\Robitzsch Jan Maximilian - Epicurean Justice. Nature, Agreement, and Virtue - 2024_50.pdf" --device cuda --output .\test10textpages.ru.pdf
```

Result:

- Effective device: `cuda`.
- Previous error `generated PDF is missing inserted Cyrillic text on page 1` no longer occurs.
- PDFTR-18A local-validation refinement did not regress the real run.
- All stages completed: `1/6 Inspect`, `2/6 Ocr`, `3/6 Extract`, `4/6 Translate`,
  `5/6 Render`, `6/6 Validate`.
- Output published atomically to `test10textpages.ru.pdf`.
- File size: `602870` bytes.
- Translation stats: `61/61` blocks, `57` cache hits, `0` misses.

## PDF Manual Validation

- Page count: `4`.
- Page 1 contains selectable/extractable Cyrillic text according to PyMuPDF extraction.
- Visual PNG inspection of page 1 confirmed Russian text is present and no obvious duplicate
  overlays or missing blocks are visible.

## Documentation

- Updated: `CHANGELOG.md`.
- README update not required because the CLI contract did not change; debug-layout behavior only
  gained an additional failed-render diagnostic artifact.

## Remaining risks

- PyMuPDF and PDF viewers may expose additional equivalent punctuation or presentation-form
  extraction differences on other PDFs; the validator now has unit-level diagnostics to identify
  future cases precisely.
