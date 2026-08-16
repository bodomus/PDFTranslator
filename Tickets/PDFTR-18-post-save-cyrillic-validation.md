# PDFTR-18 — Diagnose and fix post-save Cyrillic render validation failure

## Goal

Fix the next real end-to-end failure after PDFTR-17 in branch
`codex/PDFTR-18-post-save-cyrillic-validation`.

The renderer currently reaches post-save validation on the Robitzsch PDF and fails with:

```text
generated PDF is missing inserted Cyrillic text on page 1
```

The fix must diagnose whether this is a false-negative validator, broken Unicode mapping,
actual missing/partial insertion, extraction-order mismatch, or another renderer defect.

## Constraints

- Do not weaken or disable renderer validation.
- Do not publish failed output under the requested final output filename.
- Preserve atomic production behavior and source-PDF safety.
- Add diagnostic evidence for failed render units.
- Preserve failed temporary PDFs only when a diagnostic/debug/report option is enabled.
- Add deterministic tests for success, real missing text, partial text, Unicode extraction,
  schema 1.3, and existing hyphen normalization.

## Reproducer

```powershell
uv run pdftranslate ".\tests\Robitzsch Jan Maximilian - Epicurean Justice. Nature, Agreement, and Virtue - 2024_50.pdf" `
  --device cuda `
  --output .\test10textpages.ru.pdf
```

## Required artifacts

- `.implementation-plans/implementation-plan-PDFTR-18.md`
- `.implementation-reports/implementation-report-PDFTR-18.md`
- `reviews/review-PDFTR-18.md`
- `CHANGELOG.md`

Attachment upload is not available from the current tool surface; this local copy stores the
ticket text for the repository workflow.
