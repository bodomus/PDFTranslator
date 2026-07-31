# PDFTranslate

PDFTranslate is a Windows-first Python command-line application intended to translate English
PDF documents into Russian PDF documents. The repository currently contains only the tested
application and development foundation. **PDF parsing and translation are not implemented yet.**

## Prerequisites

- Windows 11 is the primary development platform; Linux is also validated in CI.
- Python 3.12 (the project intentionally supports `>=3.12,<3.13`).
- [uv](https://docs.astral.sh/uv/) on `PATH`.
- Git, required for pre-commit hooks.

No CUDA toolkit, NVIDIA GPU, PDF file, model download, or administrator privileges are required
for bootstrap and tests.

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

```powershell
uv run pdftranslate --version
uv run pdftranslate doctor
uv run python -m pdftranslate --version
```

`doctor` reports application, Python, operating-system, configuration, cache, CUDA, and NVIDIA GPU
information. CUDA/GPU checks are defensive and do not require PyTorch or `nvidia-smi`.

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

Run the coverage-oriented test helper:

```powershell
.\scripts\test.ps1
```

## Roadmap

1. Add PDF document inspection and layout-aware processing with PyMuPDF.
2. Add local English-to-Russian translation engines with optional CUDA acceleration.
3. Reconstruct translated PDFs while preserving useful document structure.
4. Add OCR support for scanned documents.

Large models, generated PDFs, and local model caches must remain outside version control.
