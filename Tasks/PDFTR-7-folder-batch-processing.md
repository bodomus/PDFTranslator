# PDFTR-7 — Add recursive folder batch processing

## Summary

Allow the CLI to translate multiple PDF files from a directory while loading the translation model only once.

## Dependencies

Requires completion of `PDFTR-1` through `PDFTR-6`.

## Goal

Support:

```bash
pdftranslate batch "J:\Books" --recursive
```

## Required behavior

- discover PDF files;
- preserve relative directory structure in the output folder;
- load the translation model once;
- process files sequentially by default;
- continue after individual file failures when configured;
- produce a final batch report;
- support resume;
- never overwrite source files.

## CLI

Implement:

```bash
pdftranslate batch INPUT_DIR
```

Options:

```text
--output-dir PATH
--recursive
--glob PATTERN
--exclude PATTERN
--overwrite
--resume
--continue-on-error
--ocr auto|on|off
--device auto|cpu|cuda
--report PATH
```

Default output directory:

```text
<input-dir>_ru
```

## Model lifetime

The selected translation backend must be initialized once for the batch and reused across documents.

Do not reload the model for each PDF.

The translation cache must also be shared across the batch.

## Discovery

Requirements:

- deterministic ordering;
- case-insensitive `.pdf` matching on Windows;
- avoid processing files inside the output directory;
- avoid reprocessing `.ru.pdf` outputs by default;
- handle duplicate names in different subdirectories;
- report skipped files and reasons.

## Batch report

Write JSON and human-readable summary containing:

- start and finish time;
- input and output roots;
- discovered files;
- successful files;
- failed files;
- skipped files;
- pages processed;
- OCR pages;
- translated blocks;
- cache hits;
- elapsed time;
- error details;
- output paths.

## Failure policy

Default behavior must be documented.

With `--continue-on-error`, failures in one file must not stop the rest of the batch.

Return a non-zero final exit code if any file failed.

## Tests

Use fake translator backend and generated PDFs.

Cover:

- recursive and non-recursive discovery;
- output structure preservation;
- model initialized once;
- duplicate text cache reuse;
- failure continuation;
- output directory exclusion;
- `.ru.pdf` exclusion;
- deterministic ordering;
- batch report;
- Cyrillic and spaced paths.

## Acceptance criteria

- [ ] Directory batch command exists.
- [ ] Model loads once per batch.
- [ ] Relative structure is preserved.
- [ ] Output files do not enter the discovery set.
- [ ] Resume works per file.
- [ ] Final report is created.
- [ ] Partial failures are represented by a non-zero exit code.
- [ ] All quality checks pass.
- [ ] README and CHANGELOG are updated.

## Non-goals

Do not implement:

- parallel GPU translation;
- distributed processing;
- GUI queue manager;
- cloud jobs;
- watching folders continuously.
