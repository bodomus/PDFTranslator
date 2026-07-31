# PDFTR-6 — Add OCR preprocessing for scanned and mixed PDFs

## Summary

Add optional OCR preprocessing so scanned and mixed PDF documents can enter the existing extraction and translation pipeline.

## Dependencies

Requires completion of `PDFTR-1` through `PDFTR-5`.

## Goal

Support:

```bash
pdftranslate scanned.pdf --ocr auto
pdftranslate scanned.pdf --ocr on
pdftranslate text.pdf --ocr off
```

## OCR backend

Use OCRmyPDF with Tesseract as an external tool integration.

Do not import and tightly couple OCRmyPDF internals when a subprocess boundary is more stable.

## Modes

### `--ocr auto`

- inspect the document;
- run OCR only when scanned or mixed pages require it;
- skip OCR for normal text PDFs;
- report the decision.

### `--ocr on`

- force OCR preprocessing;
- use safe options that preserve existing text where possible;
- reject unsafe combinations clearly.

### `--ocr off`

- never run OCR;
- fail with the dedicated `OCR required` exit category when meaningful pages lack extractable text.

## Dependency diagnostics

Extend:

```bash
pdftranslate doctor
```

Report:

- OCRmyPDF availability and version;
- Tesseract availability and version;
- Ghostscript availability when required;
- English OCR language availability;
- executable resolution paths.

The command must provide installation guidance without trying to install system dependencies automatically.

## OCR workspace

- write OCR output into the run workspace;
- never overwrite the source;
- preserve the original page size;
- retain OCR logs;
- reuse valid OCR output during resume;
- invalidate it when source or OCR settings change.

## Required options

Support at least:

```text
--ocr auto|on|off
--ocr-language eng
--ocr-deskew
--ocr-clean
--ocr-rotate-pages
--ocr-force
```

Choose conservative defaults.

## Mixed PDFs

For mixed documents:

- preserve existing text where reliable;
- OCR pages that need it;
- avoid duplicate text layers;
- report how many pages were OCR-processed.

## Validation

After OCR:

- reopen the result;
- compare page count;
- verify page geometry;
- rerun page classification;
- confirm that extractable text increased where expected;
- warn when OCR produced little or no usable text.

## Tests

Unit tests must mock the external process.

Add integration tests that run only when OCR dependencies are available.

Cover:

- auto skips text PDF;
- auto selects scanned PDF;
- off fails with OCR-required status;
- missing OCRmyPDF;
- missing Tesseract;
- subprocess failure;
- timeout;
- resume reuse;
- OCR output validation;
- paths containing spaces and Cyrillic characters.

CI must not require OCR system packages unless placed in an explicit optional integration job.

## Acceptance criteria

- [ ] OCR modes `auto`, `on`, and `off` exist.
- [ ] Text PDFs are not OCR-processed in auto mode.
- [ ] Scanned PDFs are detected.
- [ ] Missing system dependencies produce actionable diagnostics.
- [ ] Source files are never overwritten.
- [ ] OCR artifacts participate in resume logic.
- [ ] Mixed PDFs are handled conservatively.
- [ ] Unit tests do not require installed OCR tools.
- [ ] Optional integration tests are clearly separated.
- [ ] All quality checks pass.
- [ ] README and CHANGELOG are updated.

## Non-goals

Do not implement:

- Russian source OCR;
- handwriting recognition;
- translation of text embedded inside diagrams as separate image editing;
- GUI installation assistant;
- automatic system package installation.
