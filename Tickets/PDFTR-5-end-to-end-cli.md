# PDFTR-5 — Add one-command end-to-end PDF translation

## Summary

Combine inspection, extraction, translation, and rendering into one user-facing command.

## Dependencies

Requires:

- `PDFTR-1`;
- `PDFTR-2`;
- `PDFTR-3`;
- `PDFTR-4`.

## Goal

The primary workflow must be:

```bash
pdftranslate input.pdf --output input.ru.pdf
```

The command must run the complete pipeline:

```text
inspect → extract → translate → render → validate
```

## CLI behavior

Required examples:

```bash
pdftranslate manual.pdf
pdftranslate manual.pdf --output manual.ru.pdf
pdftranslate manual.pdf --pages 1-20
pdftranslate manual.pdf --device cuda
pdftranslate manual.pdf --offline
pdftranslate manual.pdf --resume
```

When `--output` is omitted, default to:

```text
<input-stem>.ru.pdf
```

## Pipeline workspace

Use an application cache/work directory, not the repository.

Store resumable artifacts:

- inspection JSON;
- extracted document JSON;
- translated document JSON;
- pipeline manifest;
- logs;
- failure state.

Each run must have a stable identity derived from the source fingerprint and relevant options.

## Resume behavior

With `--resume`:

- reuse valid completed stages;
- reject incompatible stale artifacts;
- continue after interruption;
- do not repeat completed model translations;
- clearly report which stages were reused.

Without `--resume`, normal cache reuse for translated text is still allowed.

## Failure handling

On failure:

- exit non-zero;
- retain useful intermediate artifacts;
- show the failed stage;
- show a concise user-facing error;
- write detailed diagnostics to a log;
- never leave a partial file under the final output name.

Write the final PDF atomically where practical.

## Progress

Show stage-level progress:

```text
1/5 Inspect
2/5 Extract
3/5 Translate
4/5 Render
5/5 Validate
```

Also show translation block progress and final statistics.

## Dry run

Add:

```bash
pdftranslate input.pdf --dry-run
```

It must inspect the document and report:

- page classifications;
- estimated text block count;
- whether OCR would be required;
- selected translation backend;
- selected device;
- output path;
- expected stages.

It must not download a model or create a translated PDF.

## Exit codes

Define and document stable categories for:

- success;
- invalid arguments;
- unsupported or corrupt PDF;
- OCR required;
- model unavailable;
- translation failure;
- rendering failure;
- output validation failure.

Exact numeric values must be centralized.

## Tests

Use fake translation backend and generated PDFs.

Cover:

- default output naming;
- complete successful pipeline;
- dry run;
- resume after translation;
- resume invalidation after option changes;
- source file change invalidates stale state;
- failure does not publish partial final output;
- stable exit-code categories;
- Ctrl+C or simulated interruption handling;
- paths containing spaces and Cyrillic characters.

## Acceptance criteria

- [ ] One command performs the complete translation pipeline.
- [ ] Default output name is `<stem>.ru.pdf`.
- [ ] Intermediate files are stored outside the repository.
- [ ] Resume works by stage.
- [ ] Dry run does not download models.
- [ ] Partial final PDFs are not published.
- [ ] Exit codes are documented and centralized.
- [ ] Detailed logs are retained.
- [ ] All quality checks pass.
- [ ] README and CHANGELOG are updated.

## Non-goals

Do not implement:

- OCR;
- directory batch mode;
- GUI;
- cloud translation;
- translation of image text.
