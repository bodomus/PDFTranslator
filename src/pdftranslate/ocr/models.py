"""Typed OCR configuration and execution results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

OcrMode = Literal["auto", "on", "off"]


@dataclass(frozen=True)
class OcrOptions:
    """Options passed across the stable OCR subprocess boundary."""

    mode: OcrMode = "auto"
    language: str = "eng"
    deskew: bool = False
    clean: bool = False
    rotate_pages: bool = False
    force: bool = False
    timeout_seconds: float = 600.0

    def __post_init__(self) -> None:
        if self.mode not in {"auto", "on", "off"}:
            raise ValueError("ocr mode must be one of: auto, on, off")
        if not self.language.strip():
            raise ValueError("OCR language cannot be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("OCR timeout must be greater than zero")
        processing_requested = self.deskew or self.clean or self.rotate_pages or self.force
        if self.mode == "off" and processing_requested:
            raise ValueError("OCR processing options cannot be used with --ocr off")
        if self.force and self.mode != "on":
            raise ValueError("--ocr-force requires --ocr on")


@dataclass(frozen=True)
class OcrExecution:
    """Successful external OCR execution details."""

    output_path: Path
    processed_pages: tuple[int, ...]
    command: tuple[str, ...]
    stdout: str
    stderr: str
