# PDFTranslate

PDFTranslate is a Windows-first Python command-line application for translating English PDF
content into Russian. It can inspect text-based PDFs, extract layout-aware text blocks into a
stable JSON intermediate format, translate those blocks locally with NLLB, and render Russian text
into a validated copy of the source PDF. OCR is not implemented yet.

## Prerequisites

- Windows 11 is the primary development platform; Linux is also validated in CI.
- Python 3.12 (the project intentionally supports `>=3.12,<3.13`).
- [uv](https://docs.astral.sh/uv/) on `PATH`.
- Git, required for pre-commit hooks.

No CUDA toolkit, NVIDIA GPU, model download, or administrator privileges are required for tests.
PyMuPDF is the PDF backend; PyTorch and Transformers provide local inference. NLLB weights are
downloaded only when translation runs without an already cached model.

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

## One-command translation

Run the complete local pipeline with a PDF path as the first argument:

```powershell
uv run pdftranslate .\manual.pdf
uv run pdftranslate .\manual.pdf --output .\manual.ru.pdf
uv run pdftranslate .\manual.pdf --pages 1-20
uv run pdftranslate .\manual.pdf --device cuda
uv run pdftranslate .\manual.pdf --offline
uv run pdftranslate .\manual.pdf --resume
```

Without `--output`, the destination is a sibling named `<input-stem>.ru.pdf`. The root command
runs and reports five stages:

```text
1/5 Inspect
2/5 Extract
3/5 Translate
4/5 Render
5/5 Validate
```

Translation also reports completed blocks and translation-memory hits/misses. The existing
`inspect`, `extract`, `translate`, and `render` subcommands remain available for advanced or
diagnostic workflows.

Pipeline artifacts are stored outside the repository under the platform application cache:

```text
<cache>/workspaces/<run-id>/
  inspection.json
  extracted.json
  translated.json
  rendered.pdf
  manifest.json
  pipeline.log
  failure.json       # present after a failed or interrupted run
```

The stable run ID includes the immutable source fingerprint/path and behavior-affecting options.
`--resume` requires that exact identity, validates each completed artifact, reports reused stages,
and continues a translation checkpoint without repeating completed model translations. A changed
source or relevant option is rejected rather than consuming stale state. Normal translation-memory
cache reuse remains active without `--resume`.

Rendering targets the workspace candidate first. Validation reopens the candidate, copies it to a
temporary sibling of the requested destination, validates that copy, and only then atomically
publishes the final filename. Failures retain intermediate artifacts and detailed diagnostics but
never publish a partial PDF under the final name. Existing output is protected unless
`--overwrite` is explicit; `--overwrite` and `--resume` are mutually exclusive.

Preview the selected pages and expected work without constructing or downloading a model:

```powershell
uv run pdftranslate .\manual.pdf --pages 1-20 --dry-run
```

Dry-run reports page classifications, estimated blocks, OCR requirement, backend, requested
device, output path, and expected stages. Selected scanned pages fail a real run with the dedicated
OCR-required category because OCR is still outside the implemented scope.

### Exit codes

The root pipeline command uses centralized stable categories:

| Code | Category |
| ---: | --- |
| 0 | Success |
| 2 | Invalid arguments or incompatible resume state |
| 3 | Unsupported, missing, encrypted, empty, or corrupt PDF |
| 4 | OCR required |
| 5 | Local model unavailable |
| 6 | Translation failure |
| 7 | Rendering failure |
| 8 | Output validation/publication failure |
| 130 | Ctrl+C or simulated interruption |

## Local translation

Translate extracted JSON while retaining every original block:

```powershell
uv run pdftranslate translate .\manual.document.json `
  --output .\manual.ru.json `
  --from en `
  --to ru `
  --backend nllb `
  --device auto
```

The default backend is `facebook/nllb-200-distilled-600M` with `eng_Latn` to `rus_Cyrl`.
The model loads once per process. `--device auto` uses CUDA only after availability and allocation
probes succeed; `--device cpu` forces CPU, while explicit `--device cuda` fails clearly when CUDA
is unavailable. Automatic CUDA out-of-memory recovery is bounded and can fall back to CPU once;
explicit CUDA failures are not hidden.

Useful runtime options:

```text
--model
--device auto|cpu|cuda
--batch-size
--max-input-tokens
--cache-dir
--overwrite
--offline
--resume
```

Normal mode may download missing model files and reports this before loading. `--offline` uses
local files only and fails clearly when they are absent. The upstream model repository was
approximately 2.5 GB when this documentation was written; cache size, RAM, and VRAM requirements
vary by revision and precision. The [NLLB model card](https://huggingface.co/facebook/nllb-200-distilled-600M) identifies
the checkpoint as CC-BY-NC-4.0, so
confirm that license fits the intended use.

The cache root defaults to the platform application cache and can be changed with
`PDFTRANSLATE_CACHE_DIR` or `--cache-dir`. Model files live below `models`; translation memory is a
SQLite database in the same root. Default runtime data is not written into the repository.

The translator skips whitespace, standalone page numbers, obvious code, measurement-only values,
and numeric identifiers. Embedded URLs, email addresses, file paths, measurements, and identifiers
are protected and must be restored exactly. Long blocks split at paragraph/sentence boundaries
where possible; forced splits produce warnings instead of silent truncation.

Translated output uses schema 1.1. It preserves schema 1.0 source fields and original block text,
adds `translated_text`, and records model/device/settings, timestamps, warnings, counters, and
completion state. Atomic checkpoints make interruption visible; `--resume` validates the source
fingerprint, block structure, backend, model, language pair, batch size, and token limit.

## Render translated PDFs

Render a completed schema 1.1 translation into a new PDF:

```powershell
uv run pdftranslate render .\manual.pdf .\manual.ru.json `
  --output .\manual.ru.pdf `
  --allow-expand
```

The renderer validates the source SHA-256 and file size, page count and dimensions, source page
indexes, block IDs, original text, bounding boxes, completed translation state, and translated
text before publication. `--force-source-mismatch` bypasses only the size/fingerprint comparison;
layout and block validation still run. The source PDF is never overwritten. Output is saved to a
temporary sibling, reopened and checked, then atomically published.

Use `--font PATH` to select a TrueType or OpenType font. Without it, PDFTranslate searches Windows
fonts (Segoe UI, Arial, then Calibri) and common DejaVu/Liberation locations on Linux. The selected
font is loaded before rendering and every required Cyrillic glyph is validated. No font files are
bundled in this repository.

Layout options are:

```text
--min-font-size
--font-size-step
--line-height
--redaction-padding
--allow-expand
--debug-layout
--force-source-mismatch
--overwrite
```

Text is wrapped inside the extracted block rectangle and reduced in deterministic steps. Optional
expansion stops at the page edge or the next horizontally overlapping text block. Unresolved
overflow is reported and is not silently clipped. `--debug-layout` writes a separate sibling named
`<output-stem>.debug.pdf`; it marks source rectangles in blue, fitted rectangles in green,
expanded rectangles in orange, and overflow in red.

Original text regions are redacted while PyMuPDF is instructed to retain overlapping image and
vector objects. A median color sampled from the source rectangle is used instead of assuming a
white page. This is conservative: complex gradients, patterned backgrounds, text intersecting
line art, and unusually dense layouts may still require manual review. OCR and text inside images
are not rendered by this stage.

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

The suite generates small PDF fixtures at runtime for extraction, translation, rendering,
image/vector preservation, fitting, overflow, source mismatch, debug layout, and Unicode paths.
Translation tests use deterministic fake backends and never load or download NLLB. No binary
fixtures are committed.

Run the coverage-oriented test helper:

```powershell
.\scripts\test.ps1
```

## Roadmap

1. Add OCR support for scanned documents.
2. Add directory batch orchestration for the existing one-document pipeline.

Large models, generated PDFs, extracted document JSON, and local model caches must remain outside
version control.
