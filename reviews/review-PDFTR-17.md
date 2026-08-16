# PDFTR-17 review

## Completed work

- Fixed private-use marker-only PDF text handling so those logical paragraphs are
  preserved as non-empty pass-through text instead of being sent to the translation model.
- Kept mixed marker/prose paragraphs translatable.
- Added regression coverage for translation skip behavior, JSON round-trip persistence,
  successful schema 1.3 render with split source-block paragraphs, and strict renderer
  rejection of genuinely empty translate-policy paragraphs.
- Updated `CHANGELOG.md`.

## Validation

- Focused PDFTR-17 tests: `3 passed`
- Translation/rendering/serialization tests: `49 passed`
- `ruff format`, `ruff check`, `mypy src`: passed
- `.\scripts\check.ps1`: `225 passed, 1 skipped`, coverage `88.53%`
- Real CUDA repro reached render beyond the previous missing-translation failure, then
  stopped on the next independent saved-PDF text validation error:
  `generated PDF is missing inserted Cyrillic text on page 1`.

## Residual risk

The published PDF could not be visually inspected because the real CUDA run now fails
later in render validation before atomic output publication.
