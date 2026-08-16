# Implementation Plan — PDFTR-16

## Ticket

PDFTR-16 — Fix false protected token detection for slash-separated prose and PDF ligatures.

## Workflow

- Level: 1 local translation text-preparation fix.
- Branch: `codex/PDFTR-16-fix-protected-token-detection`.
- Initial working tree: dirty before this ticket because of user PDF fixture changes.
- Graphify: existing graph queried for protected-token context.
- CRG: updated/queryable after setting UTF-8 output.

## Investigation

- Current behavior: `_PROTECTED` treats any `word/word` span as a path-like protected token.
- Expected behavior: ordinary slash-separated prose remains model input, while real paths, URLs,
  emails, measurements, and numeric identifiers remain protected.
- Root cause: the relative path branch has no file/path specificity beyond containing `/`.
- Secondary gap: source normalization uses NFC, which keeps PDF compatibility ligatures such as
  `ﬁ` and `ﬂ` intact.

## Scope

- `src/pdftranslate/translation/text.py`
- `tests/test_translation.py`
- `CHANGELOG.md`

## Plan

1. Add explicit PDF ligature normalization in text preparation.
2. Narrow the generic path-protection regex to paths with an explicit relative/absolute prefix or
   a file-like final segment.
3. Preserve existing protection for URLs, emails, Windows paths, measurements, and numeric IDs.
4. Add regression tests for slash-separated prose, real relative paths, and PDF ligatures.
5. Run focused tests, then repository check script.
