# PDFTR-17 implementation report

## Summary

Fixed the false schema 1.3 render failure where PDF private-use marker-only logical
paragraphs were treated as normal prose, sent through translation, and persisted with
empty `translated_text`.

## Root cause

The failing source blocks split into multiple logical paragraphs with the same physical
source block ID. The prose paragraph translated correctly, but the marker-only paragraph
contained only PDF private-use glyphs. Those markers were not recognized as non-linguistic
pass-through text, so the model returned an empty string. JSON serialization preserved
that empty string, and the renderer correctly rejected the translate-policy paragraph as
missing.

The renderer validation was not the bug; it exposed invalid translated state.

## Fix

- `should_skip_translation()` now treats text containing private-use characters and no
  alphabetic text as a non-linguistic marker.
- Mixed private-use glyphs plus prose remain translatable, so headings such as
  private-use prefix plus `The Logismos Phase` still go through the model.
- The strict renderer missing-translation validation remains unchanged.

## Four-ID lifecycle after fix

CUDA repro workspace:
`C:\Users\bodom\AppData\Local\PDFTranslate\Cache\workspaces\d41e2dbaad273bbf50a98a36d99e058258e23423db5814aa1349982cb7a3c900`

- `p0001-b0008`
  - paragraph 0: source exists, body, policy `translate`, text `\uf646\uf64b`,
    skipped by private-use marker rule, persisted/loaded as `\uf646\uf64b`.
  - paragraph 1: source exists, body, policy `translate`, text `The Origin of Justice`,
    reused from cache, persisted/loaded as non-empty Russian text.
- `p0002-b0007`
  - paragraph 22: source exists, body, policy `translate`, mixed marker/prose
    `\uf644.\uf647The Logismos Phase`, translated from cache as non-empty Russian text.
  - paragraph 23: source exists, body, policy `translate`, marker `\uf646\uf64c`,
    skipped by private-use marker rule, persisted/loaded as `\uf646\uf64c`.
- `p0003-b0007`
  - paragraph 36: source exists, body, policy `translate`, marker `\uf647\uf643`,
    skipped by private-use marker rule, persisted/loaded as `\uf647\uf643`.
  - paragraph 37: source exists, body, policy `translate`, text `The Origin of Justice`,
    reused from cache, persisted/loaded as non-empty Russian text.
- `p0004-b0005`
  - paragraph 49: source exists, body, policy `translate`, mixed marker/prose
    `\uf644.\uf647The Logismos Phase`, translated from cache as non-empty Russian text.
  - paragraph 50: source exists, body, policy `translate`, marker `\uf647\uf644`,
    skipped by private-use marker rule, persisted/loaded as `\uf647\uf644`.

Translation metadata after rerun: schema `1.3`, status `completed`, effective device
`cuda`, `total_blocks=61`, `completed_blocks=61`, `skipped_blocks=4`,
`cache_hits=57`, `cache_misses=0`, `translated_segments=0`.

## Validation

- `uv run pytest --no-cov tests/test_translation.py::test_paragraph_pipeline_preserves_pdf_private_use_markers_without_model tests/test_rendering.py::test_schema_1_3_render_accepts_split_block_when_marker_translation_is_present tests/test_rendering.py::test_schema_1_3_render_still_rejects_empty_translate_policy_paragraph`
  - `3 passed`
- `uv run pytest --no-cov tests/test_translation.py tests/test_rendering.py tests/test_serialization.py`
  - `49 passed`
- `uv run ruff format`
  - `150 files left unchanged` after final formatting
- `uv run ruff check`
  - `All checks passed`
- `uv run mypy src`
  - `Success: no issues found in 83 source files`
- `.\scripts\check.ps1`
  - `225 passed, 1 skipped`, coverage `88.53%`

## Real CUDA repro result

Command:

```powershell
uv run pdftranslate ".\tests\Robitzsch Jan Maximilian - Epicurean Justice. Nature, Agreement, and Virtue - 2024_50.pdf" --device cuda --output .\test10textpages.ru.pdf
```

Result:

- The previous failure `translated text is missing for paragraph(s): p0001-b0008,
  p0002-b0007, p0003-b0007, p0004-b0005` no longer occurs.
- The pipeline reached stage `5/6 Render`.
- Render then failed on the next independent validation:
  `generated PDF is missing inserted Cyrillic text on page 1`.
- Because render did not publish a final PDF, visual inspection of the four affected
  locations was not possible in this ticket run.

## Notes

- No ID-specific special cases were added.
- No renderer structural or missing-translation validation was weakened.
- No empty translations or English prose fallbacks were inserted to satisfy validation.
