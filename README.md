# PDFTranslate

PDFTranslate is a Windows-first Python command-line application for translating English PDF
content into Russian. The current release foundation can inspect text-based PDFs, classify pages,
and extract layout-aware text blocks into a stable JSON intermediate format. Translation, OCR,
and PDF reconstruction are not implemented yet.

## Prerequisites

- Windows 11 is the primary development platform; Linux is also validated in CI.
- Python 3.12 (the project intentionally supports `>=3.12,<3.13`).
- [uv](https://docs.astral.sh/uv/) on `PATH`.
- Git, required for pre-commit hooks.

No CUDA toolkit, NVIDIA GPU, model download, or administrator privileges are required for setup
or tests. PyMuPDF is installed from the lock file as the PDF backend.

## Windows setup

From PowerShell, clone or open the repository and run:

```powershell
.\scripts\bootstrap.ps1
```

The script resolves the repository from its own location, so it can also be launched from another
working directory. It verifies Python 3.12 through uv, creates/synchronizes `.venv`, installs
pre-commit hooks, and runs a CLI smoke test.

The equivalent manual environment command is:

```powershell
uv sync --frozen --all-groups
```

## CLI

Basic diagnostics:

```powershell
uv run pdftranslate --version
uv run pdftranslate doctor
uv run python -m pdftranslate --version
```

Inspect a PDF as a Rich table or clean machine-readable JSON:

```powershell
uv run pdftranslate inspect .\manual.pdf
uv run pdftranslate inspect .\manual.pdf --json
```

Extract all pages or a validated one-based page selection:

```powershell
uv run pdftranslate extract .\manual.pdf --output .\manual.document.json
uv run pdftranslate extract .\manual.pdf --pages 1,3-5 --output .\selected.json
uv run pdftranslate extract .\manual.pdf --output .\manual.document.json --compact --overwrite
```

The version 1.0 JSON schema includes the absolute source path, byte size and SHA-256 fingerprint,
PDF metadata, total and selected pages, page dimensions and rotation, classification, actual image
placements, extraction warnings, and text blocks with bounding boxes, original/normalized order,
and span typography. Coordinates are numeric values in PyMuPDF's effective page coordinate system.
JSON is written as UTF-8 through an atomic sibling file; existing output and the source PDF are
protected unless the applicable explicit option is supplied.

Encrypted PDFs can be identified by `inspect`, but `extract` rejects password-required documents
because password input is outside this ticket. OCR is not run, so `scanned` pages contain no
recognized text.

## Page classification

Each page is classified as `text`, `scanned`, `mixed`, or `empty`. The deterministic defaults are:

| Environment setting | Default | Meaning |
| --- | ---: | --- |
| `PDFTRANSLATE_CLASSIFICATION_MIN_TEXT_CHARACTERS` | `20` | Minimum meaningful extracted characters |
| `PDFTRANSLATE_CLASSIFICATION_MAX_INCIDENTAL_TEXT_BLOCKS` | `1` | Maximum block count still considered incidental |
| `PDFTRANSLATE_CLASSIFICATION_MIXED_IMAGE_AREA_RATIO` | `0.15` | Image coverage that makes a meaningful-text page mixed |
| `PDFTRANSLATE_CLASSIFICATION_SCANNED_IMAGE_AREA_RATIO` | `0.65` | Expected coverage for a strong scanned-page signal |

Image coverage is the sum of actual image-placement bounding-box areas divided by visible page
area, capped at 1. Image-only pages remain `scanned` below the strong threshold and receive a
warning. Settings use the standard `PDFTRANSLATE_` environment prefix.

## Reading-order limitation

Extraction preserves PyMuPDF's `sort=False` block order, removes empty blocks, normalizes line
whitespace, and exposes both original and normalized indexes. It deliberately does not merge or
geometrically reorder unrelated columns. Complex multi-column reading order may therefore need a
later, document-specific stage.

## Quality and tests

Run the complete local quality gate:

```powershell
.\scripts\check.ps1
```

Or run individual checks:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

The suite generates small PDF fixtures at runtime for text, empty, image-only, mixed, encrypted,
multiple-page, stable-order, and Unicode-path scenarios. No binary fixtures are committed.

Run the coverage-oriented test helper:

```powershell
.\scripts\test.ps1
```

## Roadmap

1. Add local English-to-Russian translation engines with optional CUDA acceleration.
2. Reconstruct translated PDFs while preserving useful document structure.
3. Add OCR support for scanned documents.

Large models, generated PDFs, extracted document JSON, and local model caches must remain outside
version control.
