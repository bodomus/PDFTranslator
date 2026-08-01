# PDFTR-10A — Stabilize Typer/Rich batch help test in CI

## Context

GitHub Actions reports `1 failed, 160 passed, 1 skipped` for
`tests/test_batch_cli.py::test_batch_help_lists_required_options`. The batch help command exits
successfully, but Typer/Rich ANSI styling and terminal wrapping make the raw output assertion for
`--output-dir` fragile.

## Required fix

- Keep every required batch option assertion.
- Invoke `batch --help` without color and with a stable terminal width.
- Normalize captured output with `click.unstyle` before assertions.
- Do not change production CLI behavior or add dependencies.
- Preserve Windows and GitHub Actions compatibility.

## Required validation

- `uv run pytest tests/test_batch_cli.py::test_batch_help_lists_required_options -q`
- `uv run pytest tests/test_batch_cli.py -q`
- `uv run pdftranslate batch --help`
- `.\scripts\check.ps1`
- Push to `codex/PDFTR-10-layout-diagnostics-and-reporting` and confirm GitHub Actions passes with
  coverage at least 80%.

## Constraints

- Do not start PDFTR-11.
- Do not modify unrelated tests or production files.
