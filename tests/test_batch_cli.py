from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from click import unstyle
from typer.testing import CliRunner

from pdftranslate.batch import (
    BatchFileFailure,
    BatchOptions,
    BatchReport,
    BatchResult,
)
from pdftranslate.cli import app
from pdftranslate.pipeline import ExitCode

runner = CliRunner()


def _result(root: Path, *, failed: bool = False) -> BatchResult:
    output = root.with_name(f"{root.name}_ru")
    report_path = output / "batch-report.json"
    failures = (
        (
            BatchFileFailure(
                input_path=str(root / "bad.pdf"),
                output_path=str(output / "bad.ru.pdf"),
                exit_code=int(ExitCode.RENDERING_FAILED),
                error="render failed",
                elapsed_seconds=0.1,
            ),
        )
        if failed
        else ()
    )
    exit_code = ExitCode.BATCH_FAILED if failed else ExitCode.SUCCESS
    now = datetime.now(UTC)
    report = BatchReport(
        status="failed" if failed else "completed",
        started_at=now,
        finished_at=now,
        elapsed_seconds=0.1,
        input_root=str(root),
        output_root=str(output),
        report_path=str(report_path),
        recursive=False,
        include_pattern="*.pdf",
        continue_on_error=False,
        discovered_files=(),
        successful_files=(),
        failed_files=failures,
        skipped_files=(),
        pages_processed=0,
        ocr_pages=0,
        translated_blocks=0,
        cache_hits=0,
        final_exit_code=int(exit_code),
    )
    return BatchResult(report=report, report_path=report_path, exit_code=exit_code)


def test_batch_help_lists_required_options() -> None:
    result = runner.invoke(
        app,
        ["batch", "--help"],
        color=False,
        terminal_width=160,
    )

    assert result.exit_code == 0

    help_text = unstyle(result.stdout)

    for option in (
        "--output-dir",
        "--recursive",
        "--glob",
        "--exclude",
        "--overwrite",
        "--resume",
        "--continue-on-error",
        "--ocr",
        "--device",
        "--report",
        "--repeated-elements",
        "--glossary",
    ):
        assert option in help_text


def test_batch_cli_builds_options_and_returns_partial_failure_code(tmp_path: Path) -> None:
    root = tmp_path / "Книги с пробелами"
    root.mkdir()
    captured: list[BatchOptions] = []

    def fake_run(options: BatchOptions, **_kwargs: object) -> BatchResult:
        captured.append(options)
        return _result(root, failed=True)

    with patch("pdftranslate.cli.run_batch", side_effect=fake_run):
        result = runner.invoke(
            app,
            [
                "batch",
                str(root),
                "--recursive",
                "--glob",
                "**/*.pdf",
                "--exclude",
                "**/draft.pdf",
                "--continue-on-error",
                "--ocr",
                "off",
                "--repeated-elements",
                "off",
                "--device",
                "cpu",
            ],
        )

    assert result.exit_code == int(ExitCode.BATCH_FAILED)
    assert captured[0].recursive is True
    assert captured[0].include_pattern == "**/*.pdf"
    assert captured[0].exclude_patterns == ("**/draft.pdf",)
    assert captured[0].continue_on_error is True
    assert captured[0].ocr == "off"
    assert captured[0].repeated_elements == "off"
    assert captured[0].device == "cpu"
    assert "PDFTranslate batch" in result.stdout
    assert "render failed" in result.stderr


def test_batch_cli_rejects_resume_with_overwrite(tmp_path: Path) -> None:
    root = tmp_path / "input"
    root.mkdir()

    result = runner.invoke(app, ["batch", str(root), "--resume", "--overwrite"])

    assert result.exit_code == int(ExitCode.INVALID_ARGUMENTS)
    assert "cannot be used together" in result.stderr
