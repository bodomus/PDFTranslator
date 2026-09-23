# PDFTR-27 implementation plan — typography evidence and style baseline

## Outcome

Add a source-backed, typed, deterministic paragraph-occurrence typography baseline for downstream
PDFTR-28 style reconstruction without changing current rendering output.

## Implementation steps

1. Extend `TextSpan` with optional raw `font_flags` and `origin`; populate them in the existing
   PyMuPDF extraction pass and update focused extraction/serialization tests.
2. Add `pdftranslate.typography` typed models for confidence, provenance, fallback, role,
   alignment, RGB, mixed-style flags, per-occurrence evidence, and document baseline.
3. Implement a pure service over `ExtractedDocument`:
   - meaningful-character-weighted dominant font name, size, booleans, and color;
   - conservative six-uppercase-letter subset-prefix normalization;
   - explicit mixed-style detection;
   - role-region geometry and conservative alignment inference;
   - baseline-distance line height and ratio;
   - first-line and whole-paragraph indent evidence;
   - canonical observed gap-before spacing with gap-after left unknown;
   - occurrence index as the serialized primary locator.
4. Add `python -m scripts.typography_inspect` for compact console or JSON inspection without a new
   public end-user CLI command.
5. Add deterministic tests covering all 20 ticket scenarios, including duplicate paragraph IDs,
   unknown/ambiguous outcomes, serialization, and unchanged production reflow behavior.
6. Run focused tests, generate and review Robitzsch page 1/3/4 evidence, and document direct,
   inferred, ambiguous, and unavailable properties. Do not commit generated PDF/output artifacts.
7. Add `docs/typography-evidence.md`, update the affected ProjectWiki architecture page/index/log,
   README developer command, and CHANGELOG.
8. Run Wiki lint, formatter/linter/type checker, `scripts/check.ps1`, post-change CRG update/blast
   review, and Graphify refresh because a production module boundary is added.
9. Write `.implementation-reports/implementation-report-PDFTR-27.md` and
   `reviews/review-PDFTR-27.md`; then, with action-time confirmation, attach the review and update
   the YouTrack workflow fields.

## Verification commands

```powershell
uv run pytest tests/test_typography.py tests/test_pdf_extraction.py tests/test_reflow_production.py
uv run python -m scripts.typography_inspect "tests/Robitzsch Jan Maximilian - Epicurean Justice. Nature, Agreement, and Virtue - 2024_50.pdf" --pages 1,3,4
uv run python scripts/project_wiki/wiki_lint.py
uv run ruff format --check .
uv run ruff check .
uv run mypy src
.\scripts\check.ps1
code-review-graph update --base master --brief
code-review-graph detect-changes --base master --brief
graphify update .
```

## Stop conditions

Stop and reassess before expanding scope if the evidence contract requires a document schema bump,
changes render geometry, reopens the PDF per paragraph, alters translation/cache behavior, or
cannot distinguish unknown from inferred properties.
