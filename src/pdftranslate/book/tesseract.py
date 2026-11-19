"""Tesseract TSV parsing and a bounded subprocess adapter."""

from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from pdftranslate.book.models import OcrLine, OcrParagraph, OcrWord, PageOcr

RunProcess = Callable[..., subprocess.CompletedProcess[str]]
FindExecutable = Callable[[str], str | None]

_VERSION = re.compile(r"tesseract\s+v?(\S+)", re.IGNORECASE)


class TesseractError(RuntimeError):
    """Tesseract is missing or failed on a page."""


def parse_tsv(tsv: str, page_number: int) -> PageOcr:
    """Convert Tesseract TSV output into paragraphs of positioned lines."""
    reader = csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)
    width = height = 0
    order: list[tuple[int, int]] = []
    lines: dict[tuple[int, int], dict[int, list[OcrWord]]] = {}
    for row in reader:
        try:
            level = int(row["level"])
        except (KeyError, TypeError, ValueError):
            continue
        if level == 1:
            width, height = int(row["width"]), int(row["height"])
            continue
        if level != 5:
            continue
        text = (row.get("text") or "").strip()
        if not text:
            continue
        key = (int(row["block_num"]), int(row["par_num"]))
        if key not in lines:
            lines[key] = {}
            order.append(key)
        lines[key].setdefault(int(row["line_num"]), []).append(
            OcrWord(
                text=text,
                left=int(row["left"]),
                top=int(row["top"]),
                width=int(row["width"]),
                height=int(row["height"]),
                confidence=float(row["conf"]),
            )
        )
    paragraphs = tuple(
        OcrParagraph(tuple(OcrLine(tuple(lines[key][number])) for number in sorted(lines[key])))
        for key in order
    )
    return PageOcr(page_number=page_number, width=width, height=height, paragraphs=paragraphs)


class TesseractRunner:
    """Run the Tesseract CLI on one page image and return TSV text."""

    def __init__(
        self,
        *,
        language: str = "eng",
        page_segmentation_mode: int = 3,
        timeout_seconds: float = 300.0,
        run_process: RunProcess = subprocess.run,
        find_executable: FindExecutable = shutil.which,
    ) -> None:
        executable = find_executable("tesseract")
        if executable is None:
            raise TesseractError(
                "Tesseract is unavailable; install 64-bit Tesseract and ensure it is on PATH"
            )
        self.executable = executable
        self.language = language
        self.page_segmentation_mode = page_segmentation_mode
        self._timeout = timeout_seconds
        self._run = run_process

    def version(self) -> str | None:
        try:
            result = self._run(
                [self.executable, "--version"],
                capture_output=True,
                check=False,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        match = _VERSION.search(f"{result.stdout}\n{result.stderr}")
        return match.group(1) if match else None

    def recognize(self, image_path: Path, dpi: int) -> str:
        command = [
            self.executable,
            str(image_path),
            "stdout",
            "-l",
            self.language,
            "--psm",
            str(self.page_segmentation_mode),
            "--dpi",
            str(dpi),
            "tsv",
        ]
        try:
            result = self._run(
                command,
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                timeout=self._timeout,
                env=_single_threaded_environment(),
            )
        except subprocess.TimeoutExpired as error:
            raise TesseractError(f"Tesseract timed out on {image_path.name}") from error
        except OSError as error:
            raise TesseractError(f"could not start Tesseract: {error}") from error
        if result.returncode != 0:
            detail = (result.stderr or "").strip().splitlines()
            message = detail[-1] if detail else f"exit code {result.returncode}"
            raise TesseractError(f"Tesseract failed on {image_path.name}: {message}")
        return result.stdout


def _single_threaded_environment() -> dict[str, str]:
    """Pages run in parallel processes; OpenMP threads inside each one only oversubscribe."""
    environment = dict(os.environ)
    environment["OMP_THREAD_LIMIT"] = "1"
    return environment
