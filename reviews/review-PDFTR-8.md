# Review — PDFTR-8

## Outcome

Implemented a reusable, opt-in real-PDF validation harness and produced executable evidence for
both a successful real NLLB pipeline run and a deterministic real-world failure. Existing pipeline,
translation, OCR, rendering, and Typer contracts were not changed.

## Review focus

- Source safety: compare SHA-256/size before and after every success and failure.
- Failure safety: confirm no partial output is published when translation fails.
- Reports: inspect JSON/Markdown schema 1.0, per-stage timing/status, logs, OCR/cache/resume fields,
  manual checklist, and defect mapping.
- Resource lifetime: confirm one model/cache runtime per corpus and complete stage reuse on resume.
- Scope: verify the harness remains opt-in and tests never load/download NLLB or invoke OCR tools.

## Automated evidence

- Full gate: 129 passed, 1 opt-in OCR integration skipped, 86.78% coverage.
- Ruff format/lint and strict mypy passed.
- Focused pipeline/OCR/batch/validation regression: 40 passed.
- Source checksums remained unchanged in all controlled real scenarios.

## Real evidence to inspect

- Positive report: `C:\tmp\pdftr8-real-success\validation-summary.md`
- Positive output:
  `C:\tmp\pdftr8-real-success\outputs\The_Sword_And_The_Shield_The_Mitrokhin_Archive_And_The_Secret_History_1.ru.pdf`
- Defect report: `C:\tmp\pdftr8-real-full\validation-summary.md`
- Dry-run matrix: `C:\tmp\pdftr8-real-dry-run\validation-summary.md`

The successful run covered one mixed/image page and one text page, reopened as a 10-page PDF,
contained searchable/extractable Russian text, preserved the page-3 image count, and reused all six
stages in 0.49 seconds. The failure run did not publish a PDF and reproduced the same protected-token
failure after resume.

## Known defect

- Severity: major
- Stage: translation
- Reproducibility: deterministic
- Root cause evidence: NLLB output did not preserve protected token `1900-1`
- Follow-up: PDFTR-9 — Translation quality benchmark

## Manual review required

Open the positive output in PDF-XChange Editor and complete
`C:\tmp\pdftr8-real-success\manual-review-template.json`. Automated checks establish PDF reopening,
page count, extracted/searchable Russian text, image count, cache/resume, output safety, and source
integrity; they do not replace human judgments about visual layout, column/table usability,
selection, or clipboard behavior.

## All remarks

1. Pages 3-7 expose a deterministic major translation defect: NLLB does not preserve protected
   token `1900-1`. Resume reproduces it; the follow-up is PDFTR-9.
2. The positive real run intentionally covers only pages 3 and 5 (text plus mixed/image), not the
   failing pages or the entire document.
3. PDF-XChange Editor is installed, but visual layout, selection, clipboard, columns, and tables
   require a human and remain `not_checked` in the manual-review template.
4. The positive output passed automated reopen, 10/10 page count, searchable/extractable Russian
   text, page-3 image count 1->1, output-size, source-checksum, and resume checks.
5. Real pages 1, 2, and 8 require OCR. OCRmyPDF, Tesseract, Ghostscript, and English OCR data are
   unavailable, accounting for the one skipped opt-in integration test.
6. An RTX 4080 is present, but Torch is CPU-only (`2.13.0+cpu`), so CUDA was not validated.
7. The available real corpus is one pre-existing 10-page, 73,160-byte PDF; it does not cover the
   full private 100-300-page/table/two-column matrix. PDFTR-8 added no PDF.
8. NLLB ran offline from the existing Hugging Face cache through temporary junction
   `C:\tmp\pdftr8-real-cache\models`; no model/cache artifact was added to the repository.
9. Transformers warned that `max_new_tokens=1024` overrode default `max_length=200`, and Hugging
   Face printed an unauthenticated-request warning in the cache-backed run. Neither blocked the
   successful pages 3/5 run.
10. CRG rebuilt, but it ignores untracked new files until stage/commit and its Windows brief panel
    hit a cp1251 `UnicodeEncodeError`; Graphify and source/executable evidence filled that gap.
11. Graphify refreshed the structural graph and only warned that two non-code JSON files
    (`hooks.json` and the example corpus manifest) yielded zero nodes.
12. `git diff --check` passed; Git emitted only expected LF/CRLF conversion warnings for
    `.gitignore`, README, and CHANGELOG.
13. User-owned untracked `Tasks/` files were preserved. Nothing was staged, committed, pushed,
    installed, or started for the next ticket.
14. Every automated quality gate passed: 129 tests passed, 1 environment-dependent OCR test was
    skipped, coverage is 86.78%, Ruff is clean, and strict mypy is clean.

## Recommendation

Move PDFTR-8 to In Review, complete the PDF-XChange checklist, and review the implementation report
and real result folders before starting PDFTR-9.
