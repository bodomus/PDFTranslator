# PDFTR-18 implementation plan

## Scope

Diagnose and fix the post-save Cyrillic validation failure that appears after PDFTR-17
when rendering the Robitzsch PDF.

## Investigation

- Reproduce the page-1 validation failure from the current translated workspace.
- Identify the exact render unit that fails validation, including ID, expected text,
  extracted text, bboxes, font, font size, overflow, and expansion state.
- Classify the failure as validator false-negative, broken Unicode mapping, actual
  missing/partial insertion, extraction-order mismatch, or another renderer defect.

## Implementation approach

- Replace page-wide whole-string validation with render-unit-aware validation that keeps
  strict integrity checks while tolerating PDF extraction ordering differences.
- Store expected render units with block/paragraph IDs and geometry instead of only page
  text strings.
- Preserve failed temporary PDFs only when debug layout is enabled.
- Improve failure diagnostics without dumping excessive text into normal logs.

## Tests

- Generated fixture with multiple Cyrillic textboxes on one page where page extraction
  order can differ.
- Missing render unit still fails.
- Partial render unit still fails.
- Unicode extraction remains selectable/copyable.
- Schema 1.3 logical paragraph rendering path is covered.
- Existing hyphen normalization behavior remains covered.

## Validation

- Focused rendering tests.
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run mypy src`
- `.\scripts\check.ps1`
- Real CUDA Robitzsch reproducer.
