"""Read-only discovery and version diagnostics for external OCR tools."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass

RunProcess = Callable[..., subprocess.CompletedProcess[str]]
FindExecutable = Callable[[str], str | None]


@dataclass(frozen=True)
class ExecutableStatus:
    name: str
    path: str | None
    version: str | None


@dataclass(frozen=True)
class OcrDependencies:
    ocrmypdf: ExecutableStatus
    tesseract: ExecutableStatus
    ghostscript: ExecutableStatus
    languages: tuple[str, ...]
    language_check_error: str | None = None

    def require(self, language: str) -> None:
        from pdftranslate.ocr.errors import OcrDependencyError

        if self.ocrmypdf.path is None:
            raise OcrDependencyError(
                "OCRmyPDF is unavailable; install it in an isolated Python environment and "
                "ensure ocrmypdf is on PATH (https://ocrmypdf.readthedocs.io/en/latest/installation.html)"
            )
        if self.tesseract.path is None:
            raise OcrDependencyError(
                "Tesseract is unavailable; install 64-bit Tesseract and ensure it is on PATH"
            )
        requested = {part.strip() for part in language.split("+") if part.strip()}
        missing = requested.difference(self.languages)
        if missing:
            names = ", ".join(sorted(missing))
            raise OcrDependencyError(
                f"Tesseract language data unavailable: {names}; install the matching "
                ".traineddata file(s)"
            )


def inspect_ocr_dependencies(
    *,
    run_process: RunProcess = subprocess.run,
    find_executable: FindExecutable = shutil.which,
) -> OcrDependencies:
    """Inspect external OCR tools without installing or changing the system."""
    ocrmypdf = _status("OCRmyPDF", ("ocrmypdf",), ("--version",), run_process, find_executable)
    tesseract = _status("Tesseract", ("tesseract",), ("--version",), run_process, find_executable)
    ghostscript = _status(
        "Ghostscript",
        ("gswin64c", "gswin32c", "gs"),
        ("--version",),
        run_process,
        find_executable,
    )
    languages: tuple[str, ...] = ()
    language_error = None
    if tesseract.path is not None:
        try:
            result = run_process(
                [tesseract.path, "--list-langs"],
                capture_output=True,
                check=False,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                languages = tuple(
                    line.strip() for line in result.stdout.splitlines()[1:] if line.strip()
                )
            else:
                language_error = _concise(result.stderr) or "language query failed"
        except (OSError, subprocess.SubprocessError) as error:
            language_error = str(error)
    return OcrDependencies(
        ocrmypdf=ocrmypdf,
        tesseract=tesseract,
        ghostscript=ghostscript,
        languages=languages,
        language_check_error=language_error,
    )


def _status(
    name: str,
    candidates: Sequence[str],
    version_args: tuple[str, ...],
    run_process: RunProcess,
    find_executable: FindExecutable,
) -> ExecutableStatus:
    path = next((resolved for item in candidates if (resolved := find_executable(item))), None)
    if path is None:
        return ExecutableStatus(name=name, path=None, version=None)
    try:
        result = run_process(
            [path, *version_args],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
        output = result.stdout or result.stderr
        version = _concise(output) if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        version = None
    return ExecutableStatus(name=name, path=path, version=version)


def _concise(value: str) -> str:
    return next((line.strip() for line in value.splitlines() if line.strip()), "")
