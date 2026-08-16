# Review — PDFTR-16

## Verdict

Ready for review.

## Reviewed scope

- `src/pdftranslate/translation/text.py`
- `src/pdftranslate/translation/cache.py`
- `src/pdftranslate/pipeline/models.py`
- `tests/test_translation.py`
- `tests/test_end_to_end_pipeline.py`
- `CHANGELOG.md`
- Translation preparation boundary: source normalization, skip checks, protected-token matching,
  segmentation inputs, cache identity, workspace resume identity.

## Findings

- No blocking issues found.
- The generic slash path matcher is now constrained enough to leave ordinary prose translatable.
- Bare slash paths are protected only with structural file evidence: a file-like final segment with
  an extension. Explicit relative paths, absolute POSIX paths, and Windows paths remain protected.
- Common PDF ligatures are normalized before protected-token detection and cache identity.
- Translation cache revision is bumped to 3, and pipeline workspace identity now records
  `translation_behavior_revision`, preventing stale pre-PDFTR-16 cache/resume reuse.
- Exact `men/ﬁrst` regression coverage verifies deterministic normalization, no false protected
  token, no false `ProtectedTokenError`, and unchanged strict failure for genuine lost protected
  placeholders.

## Verification

- Focused translation tests passed.
- Glossary plus translation tests passed.
- Ruff format/check passed through the full project gate.
- Mypy passed for `src`.
- Full `.\scripts\check.ps1` passed: 222 passed, 1 skipped.
- CRG post-change update succeeded with UTF-8 output.
- Real CUDA regression on the Robitzsch PDF proceeded past the previous
  `translator did not preserve protected token 'men/ﬁrst'` failure. Translation completed with
  `effective_device=cuda`, then stage `5/6 Render` failed with
  `translated text is missing for paragraph(s): p0001-b0008, p0002-b0007, p0003-b0007, p0004-b0005`.
  No final `test10textpages.ru.pdf` was published.

## Limitations

- The provided PDF did not contain slash-prose candidates in the extracted text inspected during
  this run, so the representative-PDF check was smoke evidence rather than a reproducer.
- Extensionless bare `word/word` paths without `./`, `../`, or leading `/` may now be translated
  as prose. This is intentional because that shape overlaps with natural-language alternatives.
- The CUDA run exposed a later rendering validation issue unrelated to the original protected-token
  regression.

## Recommendation

Merge after normal branch review.
