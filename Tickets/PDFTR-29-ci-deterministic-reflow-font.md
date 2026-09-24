# PDFTR-29 — CI fix: deterministic reflow test font

## Problem

Production reflow tests pass on Windows with Segoe UI but fail in Ubuntu CI with DejaVu Sans
because different font metrics change pagination capacity and leave translated characters
unplaced.

Affected tests:

- `test_renderer_reflows_selectable_foreign_text_and_preserves_anchors`
- `test_renderer_paginates_footnotes_after_body_pages_and_preserves_separator`

## Required fix

- Bundle one freely redistributable Cyrillic-capable test font under `tests/resources/fonts/`.
- Make `cyrillic_font_path` in `tests/conftest.py` return that exact file on every platform.
- Keep production behavior and planner/reflow logic unchanged.
- Do not raise `max_reflow_pages`, weaken `RenderCompletenessError`, or bundle proprietary fonts.
- Include a redistribution-compatible license.

## Validation

```powershell
uv run pytest tests/test_reflow_production.py -vv -s --no-cov
uv run pytest
```

Expected: all tests pass on Windows and Ubuntu while using identical font bytes and metrics.

Final status: `READY FOR REVIEW`.
