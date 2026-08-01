# Real-PDF validation

PDFTR-8 adds an explicit local harness for validating representative PDFs without committing the
corpus, model weights, generated outputs, or logs.

## Quick start

Keep the corpus outside the repository and run from PowerShell:

```powershell
.\scripts\validate-real-pdfs.ps1 `
  -CorpusRoot "J:\PdfTestCorpus" `
  -OutputRoot "J:\PdfValidationResults" `
  -DryRun
```

Dry-run performs inspection, page classification, source hashing, subset resolution, and OCR
planning. It never constructs the translation model, invokes OCR, creates pipeline workspaces, or
publishes translated PDFs.

Run the actual pipeline only as an explicit opt-in:

```powershell
.\scripts\validate-real-pdfs.ps1 `
  -CorpusRoot "J:\PdfTestCorpus" `
  -OutputRoot "J:\PdfValidationResults" `
  -ManifestPath "J:\PdfTestCorpus\validation-corpus.json" `
  -Device cpu `
  -Ocr auto `
  -Offline
```

Remove `-Offline` only when downloading a missing model is deliberate. Standard tests and CI never
run this command or download a model.

## Corpus manifest and subsets

Copy `docs/validation-corpus.example.json` to the private corpus and use paths relative to the
corpus root. Categories form the validation matrix and are also valid subset selectors.

```powershell
.\scripts\validate-real-pdfs.ps1 `
  -CorpusRoot "J:\PdfTestCorpus" `
  -OutputRoot "J:\PdfValidationResults" `
  -ManifestPath "J:\PdfTestCorpus\validation-corpus.json" `
  -Subset "tables", "two-column" `
  -DryRun
```

Without a manifest, the harness discovers PDFs recursively, excludes `.ru.pdf` files and the
selected result tree, assigns anonymized deterministic IDs, and labels categories as
`unclassified`. A subset may be a document ID, category, or case-insensitive relative-path glob.

## Results

The selected output root contains:

```text
validation-summary.json
validation-summary.md
manual-review-template.json
document-results/<document-id>.json
logs/<document-id>.log
outputs/<relative-path>/<document-name>.ru.pdf
```

Reports contain relative paths only. Per-document JSON records SHA-256 before and after execution,
source and output sizes, page classifications, stage timing/status, backend and effective device,
OCR decision/pages, cache hits/misses, reused stages, warnings, failures, manual results, and mapped
defects. Pipeline logs are copied into the result tree; workspaces remain in the configured
application cache.

The harness hashes every source again after success or failure. A mismatch is a critical defect and
causes the validation summary to fail. The production pipeline continues to prevent source/output
aliases and publishes only a separately reopened, validated final PDF.

Do not count isolated title fragments, page numbers, or intentional blank-page labels as a
successful real-world translation. Positive evidence requires at least one complete English
paragraph translated into coherent Russian. Render that page and verify that the source English
paragraph is not visible or extractable underneath, the Russian text remains in the intended area,
and a searched rectangle can be selected and copied from the PDF text layer.

## PDF-XChange manual review

Open each generated output in PDF-XChange Editor and fill the matching entry in
`manual-review-template.json`. Record these checks as `passed`, `failed`, `not_checked`, or
`not_applicable`:

- output opens and page count matches;
- Russian text is selectable, searchable, and copyable;
- images remain;
- original English is not duplicated;
- columns and tables remain usable;
- the source is unchanged;
- resume works;
- a failed/partial run is never presented as success.

Save the completed file outside version control and merge it into a fresh report:

```powershell
.\scripts\validate-real-pdfs.ps1 `
  -CorpusRoot "J:\PdfTestCorpus" `
  -OutputRoot "J:\PdfValidationResults" `
  -ManifestPath "J:\PdfTestCorpus\validation-corpus.json" `
  -ManualResultsPath "J:\PdfValidationResults\manual-review-template.json" `
  -Resume
```

A failed manual check becomes a normalized compatibility defect with a recommended follow-up.

## Failure and dependency behavior

The default is continue-on-error so every selected document receives a result. Use `-FailFast` to
stop execution after the first failed document while still recording remaining documents as not
run. `-Ocr off` records a deterministic OCR-required defect for scanned selections. Real OCR runs
only when OCRmyPDF, Tesseract, required language data, and supporting system tools are installed.
Use `pdftranslate doctor` before an opt-in OCR run.

Use `-Resume` to verify reuse of compatible inspect/OCR/extract/translate/render/validate artifacts.
`-Resume` and `-Overwrite` are mutually exclusive, and neither is valid with `-DryRun`.
