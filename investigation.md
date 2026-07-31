# PDFTR-6 Investigation

## Current behavior

The one-command pipeline inspects and extracts the immutable source PDF, then aborts with exit code 4 when a selected page is classified as scanned. OCR tools are not diagnosed and no OCR workspace artifact exists.

## Expected behavior

An OCR stage must decide from pre-OCR classification whether to skip, run, or reject OCR. It must call OCRmyPDF through a controlled subprocess boundary, preserve source files and existing reliable text, validate the produced PDF, retain logs, and participate in resume identity and artifact validation.

## Source-verified ownership

- `src/pdftranslate/cli.py`: public root command and `doctor` output.
- `src/pdftranslate/pipeline/models.py`: options, ordered stages, result contracts.
- `src/pdftranslate/pipeline/runner.py`: stage orchestration and adapter injection.
- `src/pdftranslate/pipeline/workspace.py`: deterministic identity, artifacts, logs, reuse.
- `src/pdftranslate/pdf/pymupdf_backend.py`: page classification and source identity.
- `tests/test_end_to_end_pipeline.py` and `tests/test_cli.py`: public behavior and exit codes.

## Graph findings and validation

Graphify identified `run_pipeline`, `PipelineWorkspace`, `PdfAnalyzer`, `PdfExtractor`, and CLI as the relevant community boundary. CRG confirmed the CLI and end-to-end tests call `run_pipeline`, which owns all existing stages. Source inspection confirms OCR belongs between inspect and extract and must supply the PDF used by extraction and rendering.

## External contract

Current OCRmyPDF documentation recommends `--mode skip` for mixed documents so pages with existing text are copied without OCR; legacy `--skip-text` remains an alias. `--mode force` rasterizes all pages and is therefore exposed only through explicit `--ocr-force`. OCRmyPDF, Tesseract languages, and Ghostscript are external dependencies and are never installed automatically.

## Risks and constraints

- OCR output must retain page count and page geometry.
- Auto mode must never invoke OCR for ordinary text PDFs.
- Resume compatibility must include every OCR-affecting option and validate `ocr.pdf`.
- Process arguments must be passed as a list so spaces and Cyrillic paths remain intact.
- Timeouts, nonzero exits, missing tools, and low-value OCR output need actionable errors or warnings.
- Unit tests must inject a fake OCR processor; real OCR remains opt-in.
