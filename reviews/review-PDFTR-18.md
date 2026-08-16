# PDFTR-18 review

## Completed work

- Diagnosed the page-1 post-save validation failure as a false negative for render unit
  `p0001-b0003`.
- Replaced page-wide anonymous validation with render-unit-aware validation carrying IDs,
  geometry, font, and state diagnostics.
- Tightened PDFTR-18A local validation so page-wide text can no longer make a missing repeated
  render unit pass; the expected unit's own clip is authoritative.
- Added PDF extraction normalization for `U+FD3E`/`U+FD3F` parenthesis forms while preserving
  existing hyphen normalization.
- Added debug-only failed temporary render preservation as `<output-stem>.failed-render.pdf`.
- Added deterministic tests for extraction-order tolerance, duplicate-text missing-unit failure,
  partial/missing text failure, Unicode extraction, schema 1.3 rendering, and diagnostic
  preservation.

## Validation

- `uv run pytest --no-cov tests/test_rendering.py`: `16 passed`
- `uv run ruff format --check .`: passed
- `uv run ruff check .`: passed
- `uv run mypy src`: passed
- `.\scripts\check.ps1`: `230 passed, 1 skipped`, coverage `88.62%`
- Real CUDA Robitzsch run: completed all 6 stages and published `test10textpages.ru.pdf`

## Residual risk

Future PDFs may reveal more PDF extraction presentation-form variants. The new failure message
identifies the exact render unit and its local extracted text so those cases can be handled
without weakening validation.
