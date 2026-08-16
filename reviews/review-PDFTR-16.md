# Review — PDFTR-16

## Verdict

Ready for review.

## Reviewed scope

- `src/pdftranslate/translation/text.py`
- `tests/test_translation.py`
- `CHANGELOG.md`
- Translation preparation boundary: source normalization, skip checks, protected-token matching,
  segmentation inputs, cache identity.

## Findings

- No blocking issues found.
- The generic slash path matcher is now constrained enough to leave ordinary prose translatable.
- Real path-like values remain covered by explicit relative paths, absolute POSIX paths, file-like
  bare paths, and the existing Windows path branch.
- Common PDF ligatures are normalized before protected-token detection and cache identity.

## Verification

- Focused translation tests passed.
- Glossary plus translation tests passed.
- Ruff format/check passed for changed Python files.
- Mypy passed for `translation/text.py`.
- Full `.\scripts\check.ps1` passed: 202 passed, 1 skipped.
- CRG post-change update succeeded with UTF-8 output.

## Limitations

- The provided PDF did not contain slash-prose candidates in the extracted text inspected during
  this run, so the representative-PDF check was smoke evidence rather than a reproducer.
- Extensionless bare relative paths without `./`, `../`, absolute `/`, digits, dots, underscores,
  or hyphens may now be translated as prose. This is an intentional tradeoff to prevent false
  protected-token detection for slash-separated prose.

## Recommendation

Merge after normal branch review.
