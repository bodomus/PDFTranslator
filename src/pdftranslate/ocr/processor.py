"""Controlled OCRmyPDF subprocess adapter."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from pdftranslate.ocr.diagnostics import OcrDependencies, inspect_ocr_dependencies
from pdftranslate.ocr.errors import OcrOutputError, OcrProcessError, OcrTimeoutError
from pdftranslate.ocr.models import OcrExecution, OcrOptions

RunProcess = Callable[..., subprocess.CompletedProcess[str]]
DependencyProbe = Callable[[], OcrDependencies]


class OcrProcessor:
    """Run OCRmyPDF with explicit arguments, bounded time, and retained logs."""

    def __init__(
        self,
        *,
        run_process: RunProcess = subprocess.run,
        dependency_probe: DependencyProbe = inspect_ocr_dependencies,
    ) -> None:
        self._run_process = run_process
        self._dependency_probe = dependency_probe

    def process(
        self,
        input_path: Path,
        output_path: Path,
        *,
        log_path: Path,
        sidecar_path: Path,
        pages: tuple[int, ...],
        options: OcrOptions,
    ) -> OcrExecution:
        if input_path.resolve() == output_path.resolve():
            raise OcrOutputError("OCR output must not replace the source PDF")
        dependencies = self._dependency_probe()
        dependencies.require(options.language)
        assert dependencies.ocrmypdf.path is not None

        output_path.parent.mkdir(parents=True, exist_ok=True)
        pending = output_path.with_name(f".{output_path.stem}.pending.pdf")
        pending.unlink(missing_ok=True)
        command = _build_command(
            dependencies.ocrmypdf.path,
            input_path,
            pending,
            sidecar_path,
            pages,
            options,
        )
        try:
            result = self._run_process(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=options.timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            stdout = _stream_text(error.stdout)
            stderr = _stream_text(error.stderr)
            _write_log(log_path, command, stdout, stderr, "timeout")
            raise OcrTimeoutError(
                f"OCRmyPDF exceeded the {options.timeout_seconds:g}-second timeout"
            ) from error
        except OSError as error:
            _write_log(log_path, command, "", str(error), "launch failed")
            raise OcrProcessError(f"could not start OCRmyPDF: {error}") from error

        _write_log(log_path, command, result.stdout, result.stderr, str(result.returncode))
        if result.returncode != 0:
            detail = _last_line(result.stderr) or _last_line(result.stdout) or "no diagnostics"
            raise OcrProcessError(f"OCRmyPDF exited with code {result.returncode}: {detail}")
        if not pending.is_file() or pending.stat().st_size == 0:
            raise OcrOutputError("OCRmyPDF reported success but produced no usable PDF")
        pending.replace(output_path)
        return OcrExecution(
            output_path=output_path,
            processed_pages=pages,
            command=tuple(command),
            stdout=result.stdout,
            stderr=result.stderr,
        )


def _build_command(
    executable: str,
    input_path: Path,
    output_path: Path,
    sidecar_path: Path,
    pages: tuple[int, ...],
    options: OcrOptions,
) -> list[str]:
    mode = "force" if options.force else "skip"
    command = [
        executable,
        "--mode",
        mode,
        "--language",
        options.language,
        "--output-type",
        "pdf",
        "--optimize",
        "0",
        "--sidecar",
        str(sidecar_path),
    ]
    if pages:
        command.extend(("--pages", ",".join(str(page) for page in pages)))
    if options.deskew:
        command.append("--deskew")
    if options.clean:
        command.append("--clean")
    if options.rotate_pages:
        command.append("--rotate-pages")
    command.extend((str(input_path), str(output_path)))
    return command


def _write_log(
    path: Path,
    command: list[str],
    stdout: str,
    stderr: str,
    result: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        f"command: {subprocess.list2cmdline(command)}\n"
        f"result: {result}\n"
        f"stdout:\n{stdout}\n"
        f"stderr:\n{stderr}\n"
    )
    path.write_text(payload, encoding="utf-8", newline="\n")


def _stream_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or ""


def _last_line(value: str) -> str:
    return next((line.strip() for line in reversed(value.splitlines()) if line.strip()), "")
