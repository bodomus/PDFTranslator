# PDFTR-17 — Fix missing translated paragraphs during render

## Goal

Fix the next real end-to-end failure exposed after PDFTR-16.

Use a new branch from current `master` after PDFTR-16 is merged:

```text
codex/PDFTR-17-render-missing-translated-paragraphs
```

Do not weaken renderer validation and do not silently skip missing translations.

## Reproducer

Use the same real PDF:

```powershell
uv run pdftranslate ".\tests\Robitzsch Jan Maximilian - Epicurean Justice. Nature, Agreement, and Virtue - 2024_50.pdf" `
  --device cuda `
  --output .\test10textpages.ru.pdf
```

Current behavior:

```text
1/6 Inspect
2/6 OCR
3/6 Extract
4/6 Translate   ✅ 61/61 completed
5/6 Render      ❌

translated text is missing for paragraph(s):
p0001-b0008
p0002-b0007
p0003-b0007
p0004-b0005
```

The translation stage completes successfully on CUDA. The defect is now between translated
paragraph state and renderer input/validation.

## Required investigation

Follow the repository pre-ticket workflow and inspect at minimum:

- paragraph reconstruction model/schema;
- repeated-element / anchor paragraph behavior;
- translation result mapping;
- translated JSON serialization/deserialization;
- renderer paragraph selection;
- paragraph IDs listed above;
- resume/cache/workspace interaction;
- schema 1.3 rendering path.

Trace these exact paragraph IDs end-to-end:

```text
p0001-b0008
p0002-b0007
p0003-b0007
p0004-b0005
```

For each ID determine:

1. source paragraph/block exists?
2. classified as body/repeated/anchor/etc.?
3. sent to translation?
4. received translated text?
5. persisted to `translated.json`?
6. loaded back before render?
7. renderer expects translation or should reuse another paragraph translation?
8. why renderer reports it as missing?

Do not guess. Record the exact lifecycle of each ID.

## Constraints

- Do NOT disable or weaken missing-translation validation.
- Do NOT disable renderer structural validation.
- Do NOT insert source English text as a silent fallback.
- Do NOT generate empty translated strings to satisfy validation.
- Do NOT special-case the four IDs.
- Fix the underlying mapping/state rule.

## Tests

Add a deterministic generated regression reproducing the same state shape.

Cover at minimum:

1. repeated/anchor paragraph translation reuse;
2. logical paragraph with mapped source blocks;
3. serialization round-trip;
4. render receives a complete translation mapping;
5. genuinely missing translation still raises the current error.

Do not rely only on the real PDF test.

## Real regression validation

After implementation, rerun the CUDA command above.

Required evidence:

- render proceeds beyond the previous missing-paragraph error;
- record the effective CUDA device;
- if another later failure occurs, record it exactly;
- only claim full success if all 6 stages complete and final PDF is published.

If render succeeds, inspect the resulting PDF visually and verify that the four affected paragraph
locations contain Russian text and are not duplicated.

## Required artifacts

Create/update:

```text
.implementation-plans/implementation-plan-PDFTR-17.md
.implementation-reports/implementation-report-PDFTR-17.md
reviews/review-PDFTR-17.md
CHANGELOG.md
```

The implementation report must include the exact lifecycle of:

```text
p0001-b0008
p0002-b0007
p0003-b0007
p0004-b0005
```

and the real CUDA regression result.

## Notes

Attachment support for YouTrack is unavailable in the current tool set; this file is saved locally
under `Tickets/` as required by the repository workflow.
