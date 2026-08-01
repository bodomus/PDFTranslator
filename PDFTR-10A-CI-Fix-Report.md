# PDFTR-10A CI Fix Report

## Root cause

- The `batch --help` command was healthy and exited with code 0.
- Typer 0.27.0 / Rich 14.3.4 inserted ANSI styling inside option names when color was forced. At an 80-column terminal, Rich also wrapped the help table. The raw substring assertion therefore could not find `--output-dir` even though the option was registered and displayed.
- The failure was reproduced locally with GitHub Actions-like environment variables (`CI=true`, `GITHUB_ACTIONS=true`, `TERM=xterm-256color`, `FORCE_COLOR=1`, `COLUMNS=80`).

## Files changed

- `tests/test_batch_cli.py` — deterministic help invocation and ANSI normalization.
- `Tickets/PDFTR-10A-stabilize-typer-rich-batch-help-test-in-ci.md` — local ticket record required by the repository workflow.
- `PDFTR-10A-CI-Fix-Report.md` — this completion report.
- `reviews/review-PDFTR-10A.md` — implementation review and validation evidence.

## Fix

- Imported `click.unstyle`; Click was already installed through Typer, so no dependency was added.
- Invoked the help command with `color=False` and `terminal_width=160`.
- Applied `unstyle(result.stdout)` before assertions.
- Preserved the complete required option list: `--output-dir`, `--recursive`, `--glob`, `--exclude`, `--overwrite`, `--resume`, `--continue-on-error`, `--ocr`, `--device`, and `--report`.
- Production CLI code and behavior were not changed.

## Validation

- Focused help test: passed in the reproduced CI-like colored 80-column environment with `--no-cov`.
- Batch CLI tests: `3 passed` with `--no-cov`.
- Exact narrow pytest commands: all selected tests passed, but the repository-wide `--cov-fail-under=80` intentionally makes narrow selections exit non-zero at 26–27% partial-suite coverage. No coverage setting was weakened.
- Direct help command: exited 0 and displayed every required option.
- Full `check.ps1`: passed; formatter, Ruff, mypy, `161 passed, 1 skipped`, total coverage `87.78%`.
- GitHub Actions: [run 30701770322](https://github.com/bodomus/PDFTranslator/actions/runs/30701770322) passed on Ubuntu and Windows for fix commit `84f3bd3`; each job reported `161 passed, 1 skipped` and `87.68%` coverage.

## Final status

- Ready to merge PDFTR-10.
