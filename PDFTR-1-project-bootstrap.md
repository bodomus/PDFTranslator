# PDFTR-1 — Initialize PDFTranslate project from an empty directory

## Summary

Initialize the complete `PDFTranslate` project from an empty directory and leave the repository in a clean, reproducible, tested state.

The user provides only the target project directory. Codex must create and configure everything else required for further development.

## Context

`PDFTranslate` is a Windows-first Python CLI utility that translates English PDF documents into Russian PDF documents.

Initial technical direction:

- Python 3.12;
- CLI application;
- `src` layout;
- PyMuPDF for PDF processing;
- local translation engines;
- CUDA support where available;
- OCR support will be implemented later;
- no GUI;
- development is performed primarily on Windows 11.

This ticket is infrastructure-only. It must not implement real PDF translation yet.

## Goal

After this ticket, the project must:

- be a valid Git repository;
- have a reproducible Python environment;
- install successfully in editable mode;
- expose a working `pdftranslate` CLI command;
- pass formatting, linting, type-checking, and tests;
- have a green GitHub Actions workflow;
- contain clear developer documentation;
- be ready for subsequent feature tickets.

## Starting conditions

Assume only the following exists:

```text
<project-root>/
```

Do not assume that any files, Git repository, virtual environment, configuration, package structure, or CI workflow already exists.

Codex must inspect the directory before changing it and preserve any unrelated existing files if the directory is not completely empty.

## Required technology

Use:

- Python `3.12`;
- `pyproject.toml`;
- package manager and environment workflow based on `uv`;
- Typer for the CLI;
- Rich for structured console output;
- pytest for tests;
- Ruff for linting and formatting;
- mypy for static typing;
- pre-commit for local quality checks;
- GitHub Actions for CI;
- `src/pdftranslate` package layout.

Do not introduce Poetry, Pipenv, Hatch, Conda, or multiple competing environment managers.

## Required repository structure

Create at least:

```text
PDFTranslate/
├── .github/
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── .pre-commit-config.yaml
├── AGENTS.md
├── CHANGELOG.md
├── LICENSE
├── README.md
├── pyproject.toml
├── uv.lock
├── scripts/
│   ├── bootstrap.ps1
│   ├── check.ps1
│   └── test.ps1
├── src/
│   └── pdftranslate/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── logging_config.py
│       └── py.typed
└── tests/
    ├── __init__.py
    ├── test_cli.py
    └── test_package.py
```

Minor additions are allowed when justified. Do not create empty architectural layers that have no current purpose.

## Package metadata

Configure the project as an installable package named:

```text
pdftranslate
```

The console command must be:

```text
pdftranslate
```

The initial version must be:

```text
0.1.0
```

Use a suitable modern build backend compatible with `uv` and editable installs.

The package must declare Python compatibility explicitly:

```text
>=3.12,<3.13
```

## Initial runtime dependencies

Add only the runtime dependencies needed by this ticket:

- `typer`;
- `rich`;
- `pydantic`;
- `pydantic-settings`;
- `platformdirs`.

Do not add PyMuPDF, Torch, Transformers, OCRmyPDF, or translation models in this ticket. They belong to later tickets.

## Development dependencies

Configure development dependencies for:

- pytest;
- pytest-cov;
- Ruff;
- mypy;
- pre-commit.

Pin or constrain versions through the lockfile. Do not hard-code dependency paths tied to one workstation.

## CLI behavior

Implement the following commands:

```bash
pdftranslate --version
pdftranslate doctor
```

### `pdftranslate --version`

Must print the package version and exit with code `0`.

Expected semantic output:

```text
PDFTranslate 0.1.0
```

### `pdftranslate doctor`

Must perform lightweight environment diagnostics without downloading models or requiring a PDF.

It must report:

- application version;
- Python version;
- operating system;
- project/config directory;
- cache directory;
- whether CUDA appears available;
- whether a supported NVIDIA GPU can be detected, when possible;
- an overall status.

CUDA detection must be optional and defensive. The command must not fail merely because PyTorch or NVIDIA tools are absent.

Example semantic output:

```text
PDFTranslate doctor
Application: 0.1.0
Python: 3.12.x
OS: Windows 11
Config directory: ...
Cache directory: ...
CUDA: not checked or unavailable
Status: OK
```

Exact formatting may use Rich.

## Configuration foundation

Create a typed settings model for future project configuration.

Requirements:

- settings must use `pydantic-settings`;
- environment variable prefix must be:

```text
PDFTRANSLATE_
```

- default cache and config paths must use `platformdirs`;
- no user-specific absolute paths may appear in source control;
- settings loading must be covered by tests;
- configuration files do not need to be persisted yet.

Suggested initial settings:

```python
log_level: str = "INFO"
cache_dir: Path
config_dir: Path
```

## Logging foundation

Implement centralized logging setup.

Requirements:

- support at least `DEBUG`, `INFO`, `WARNING`, and `ERROR`;
- default to `INFO`;
- console output must remain readable;
- libraries must not configure global logging at import time;
- CLI commands must initialize logging explicitly;
- test output must not be polluted by unexpected logs.

## PowerShell scripts

### `scripts/bootstrap.ps1`

Must:

1. verify that `uv` is available;
2. verify that Python 3.12 can be resolved through `uv`;
3. synchronize the environment;
4. install pre-commit hooks;
5. run a smoke test of `pdftranslate --version`;
6. exit non-zero on failure.

It must work when launched from any current working directory by resolving the repository root relative to the script file.

### `scripts/check.ps1`

Must run:

- Ruff format check;
- Ruff lint;
- mypy;
- pytest.

### `scripts/test.ps1`

Must run the test suite with useful console output and coverage.

All scripts must use strict PowerShell error handling.

## Quality configuration

### Ruff

Configure:

- formatting;
- import sorting;
- common correctness rules;
- reasonable line length;
- `src` layout awareness.

Avoid enabling an excessive rule set that causes noise without value.

### mypy

Configure strict or near-strict typing for `src/pdftranslate`.

Tests may use slightly relaxed rules when justified.

### pytest

Configure:

- test discovery;
- concise default output;
- coverage for `src/pdftranslate`;
- failure when package import is broken.

Do not set an unrealistically high coverage threshold for the bootstrap ticket. A minimum around 80% is acceptable if the implemented code remains small.

### pre-commit

Include hooks for:

- trailing whitespace;
- end-of-file fixes;
- YAML validation;
- TOML validation;
- Ruff lint;
- Ruff formatting.

## Git initialization

If the directory is not already a Git repository:

```bash
git init
```

Create a suitable `.gitignore` covering:

- Python caches;
- virtual environments;
- `uv`;
- pytest, Ruff, mypy, and coverage caches;
- IDE metadata where appropriate;
- generated PDF output;
- temporary files;
- local model caches;
- logs;
- OS-specific files.

Do not delete an existing Git history.

Do not create a remote repository and do not push anything.

Do not commit automatically unless the execution environment explicitly requires it.

## GitHub Actions

Create `.github/workflows/ci.yml`.

The workflow must:

- run on pushes and pull requests;
- use Windows and Linux jobs, or a justified matrix;
- install `uv`;
- install Python 3.12;
- restore dependencies from `uv.lock`;
- run Ruff formatting check;
- run Ruff lint;
- run mypy;
- run pytest with coverage;
- avoid downloading any ML models;
- avoid requiring CUDA;
- use dependency caching where practical.

The workflow must be deterministic and use the committed lockfile.

## Documentation

### README.md

Document:

- project purpose;
- current bootstrap status;
- prerequisites;
- Windows setup;
- environment bootstrap;
- CLI examples;
- quality commands;
- test commands;
- high-level roadmap;
- explicit statement that translation is not yet implemented.

### AGENTS.md

Provide instructions for future Codex work:

- inspect repository state before editing;
- use the existing `uv` workflow;
- run `scripts/check.ps1` before completion;
- do not add dependencies without justification;
- keep domain code independent from Typer;
- preserve Windows compatibility;
- avoid user-specific absolute paths;
- add or update tests with every behavior change;
- update README and CHANGELOG when user-visible behavior changes;
- never download large models during unit tests or CI;
- never commit generated PDFs or model weights.

### CHANGELOG.md

Initialize it using a Keep a Changelog-style structure with an `Unreleased` section.

### LICENSE

Use the MIT license unless an existing repository file indicates another license.

## Tests

Implement tests covering at least:

1. package imports successfully;
2. package version is `0.1.0`;
3. `pdftranslate --version` exits with `0`;
4. version output contains `PDFTranslate` and `0.1.0`;
5. `pdftranslate doctor` exits with `0`;
6. `doctor` works when CUDA-related tools are absent;
7. default settings paths are valid `Path` values;
8. environment variables with the `PDFTRANSLATE_` prefix override defaults;
9. logging initialization accepts supported levels;
10. unsupported CLI usage exits predictably.

Use Typer's testing support. Do not invoke external network services.

## Acceptance criteria

- [ ] The project can be created from an empty target directory.
- [ ] `uv sync` completes successfully.
- [ ] `uv run pdftranslate --version` prints `PDFTranslate 0.1.0`.
- [ ] `uv run pdftranslate doctor` completes without requiring CUDA.
- [ ] `uv run pytest` passes.
- [ ] `uv run ruff format --check .` passes.
- [ ] `uv run ruff check .` passes.
- [ ] `uv run mypy src` passes.
- [ ] `scripts/bootstrap.ps1` works from outside the repository directory.
- [ ] `scripts/check.ps1` passes.
- [ ] `uv.lock` is committed.
- [ ] GitHub Actions CI is syntactically valid and does not download models.
- [ ] No absolute workstation-specific paths are committed.
- [ ] README, AGENTS, CHANGELOG, and LICENSE are present.
- [ ] The working tree contains no generated PDF, model, cache, or virtual-environment files.

## Non-goals

Do not implement:

- PDF parsing;
- PDF rendering;
- translation engines;
- Hugging Face model loading;
- OCR;
- batch processing;
- GUI;
- Docker;
- executable packaging;
- installer creation;
- cloud APIs.

## Implementation constraints

- Keep the bootstrap small and maintainable.
- Do not hide failures behind broad exception handlers.
- Do not perform network access during tests.
- Do not require administrator privileges.
- Do not write into the source tree at runtime.
- Do not couple configuration or logging directly to CLI command implementations.
- Prefer simple functions and typed models over premature dependency injection frameworks.

## Required completion report

At the end, provide:

1. files created and modified;
2. commands executed;
3. test, lint, formatting, and type-check results;
4. any assumptions made;
5. any remaining risks;
6. exact command the user should run first:

```powershell
.\scripts\bootstrap.ps1
```
