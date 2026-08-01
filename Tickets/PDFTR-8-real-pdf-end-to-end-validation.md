# PDFTR-8 — Real PDF end-to-end validation

## Summary

Validate the complete pipeline on representative real-world PDFs and produce a structured compatibility report.

## Dependencies

Requires completion of PDFTR-1 through PDFTR-7 unless this ticket explicitly refers to findings that can be gathered in parallel.

## Required workflow

Treat this as a Level 2 task under `.codex/PRE_TICKET_WORKFLOW.md`.

Before implementation:

1. inspect the current repository, Git state, `AGENTS.md`, workflow instructions, tests, CLI, schemas and relevant pipeline stages;
2. run confirmed Graphify and CRG preflight when available;
3. validate graph findings in Python source;
4. create `investigation.md` and `implementation-plan.md`;
5. preserve unrelated user changes;
6. implement the smallest coherent solution.

## Goal

Prove that PDFTranslate works outside synthetic fixtures, identify deterministic failure modes, and establish evidence for the next stabilization tickets.

## Scope and requirements

Create a local, reproducible validation matrix covering where available:

- text-heavy book;
- technical manual;
- two-column PDF;
- tables;
- images and captions;
- scanned PDF;
- mixed text/scanned PDF;
- long PDF of about 100–300 pages;
- paths with spaces and Cyrillic characters.

Do not commit copyrighted or large PDFs. Store only checksums, anonymized metadata, generated fixtures and reproduction instructions.

Add a validation harness, for example:

```powershell
.\scripts\validate-real-pdfs.ps1 -CorpusRoot "J:\PdfTestCorpus"
```

It must never modify sources, must support dry run and subset selection, and must produce:

```text
validation-summary.json
validation-summary.md
document-results/<document-id>.json
logs/
```

Record per document: source checksum, page classifications, stage results, backend, device, OCR decision, durations, cache/resume data, file sizes, warnings and failures.

Perform manual checks in PDF-XChange Editor: output opens, page count matches, Russian text is selectable/searchable/copyable, images remain, original English is not duplicated, columns and tables remain usable, source is unchanged, resume works, and partial output is never reported as success.

Classify every defect by severity, affected stage, reproducibility, root cause and recommended follow-up ticket.

## Tests and validation

Test the validation harness with generated PDFs and fake translators. Cover success, extraction/translation/render/OCR/validation failures, continuation after failure, report generation, Cyrillic paths and checksum preservation.

Normal unit tests and CI must not download translation models, require CUDA, or require OCR system tools. Use generated fixtures, fakes and mocks. Real-model, GPU, OCR and real-PDF tests must be explicit opt-in checks.

## Acceptance criteria

- [ ] Reusable validation harness exists.
- [ ] JSON and Markdown reports are generated.
- [ ] At least one text PDF is validated end to end.
- [ ] At least one image-containing PDF is validated.
- [ ] Scanned/OCR-required behavior is evaluated when dependencies exist.
- [ ] PDF-XChange Editor manual result is recorded.
- [ ] Search, copy, cache and resume are checked.
- [ ] Source files remain unchanged.
- [ ] Defects are mapped to follow-up tickets.
- [ ] All checks pass.

## Non-goals

Do not add a new model, major layout redesign, glossary, GUI, packaging, or copyrighted fixtures.

## Documentation

Update the applicable files:

- `README.md`;
- `CHANGELOG.md`;
- CLI `--help`;
- configuration/schema documentation;
- troubleshooting or Windows instructions where relevant.

## Required completion report

Provide:

1. repository state before changes;
2. workflow level and Graphify/CRG status;
3. investigation findings and root cause or capability gap;
4. files and symbols changed;
5. commands actually executed;
6. focused and full test results;
7. Ruff, mypy and script results;
8. real-model, CUDA, OCR and real-PDF validation status;
9. remaining risks and deferred work.
