"""Typed contracts for directory discovery, batch execution, and JSON reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from pdftranslate.domain.text_block import DomainModel
from pdftranslate.pipeline.exit_codes import ExitCode
from pdftranslate.pipeline.models import DeviceRequest, OcrMode, PipelineOptions
from pdftranslate.reconstruction import ReconstructionMode


@dataclass(frozen=True)
class BatchOptions:
    """Behavior-affecting settings for one sequential directory batch."""

    input_dir: Path
    output_dir: Path | None = None
    recursive: bool = False
    include_pattern: str = "*.pdf"
    exclude_patterns: tuple[str, ...] = ()
    overwrite: bool = False
    resume: bool = False
    continue_on_error: bool = False
    ocr: OcrMode = "auto"
    paragraph_reconstruction: ReconstructionMode = "conservative"
    device: DeviceRequest = "auto"
    report_path: Path | None = None
    cache_dir: Path | None = None
    backend: str = "nllb"
    model: str = "facebook/nllb-200-distilled-600M"
    batch_size: int = 8
    max_input_tokens: int = 512
    offline: bool = False
    font_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.include_pattern.strip():
            raise ValueError("--glob pattern cannot be empty")
        if any(not pattern.strip() for pattern in self.exclude_patterns):
            raise ValueError("--exclude pattern cannot be empty")
        if self.overwrite and self.resume:
            raise ValueError("--resume and --overwrite cannot be used together")
        if self.device not in {"auto", "cpu", "cuda"}:
            raise ValueError("device must be one of: auto, cpu, cuda")
        if self.paragraph_reconstruction not in {"conservative", "off"}:
            raise ValueError("paragraph reconstruction must be conservative or off")
        if self.ocr not in {"auto", "on", "off"}:
            raise ValueError("ocr mode must be one of: auto, on, off")
        if self.report_path is not None and self.report_path.suffix.casefold() != ".json":
            raise ValueError("--report must have a .json extension")

    @property
    def resolved_input_dir(self) -> Path:
        return self.input_dir.expanduser().resolve()

    @property
    def resolved_output_dir(self) -> Path:
        selected = self.output_dir or default_batch_output_dir(self.input_dir)
        return selected.expanduser().resolve()

    @property
    def resolved_report_path(self) -> Path:
        selected = self.report_path or self.resolved_output_dir / "batch-report.json"
        return selected.expanduser().resolve()

    def pipeline_options(self, source: Path, output: Path) -> PipelineOptions:
        """Create one source-specific pipeline request with common batch settings."""
        return PipelineOptions(
            input_path=source,
            output_path=output,
            backend=self.backend,
            model=self.model,
            device=self.device,
            batch_size=self.batch_size,
            max_input_tokens=self.max_input_tokens,
            cache_dir=self.cache_dir,
            offline=self.offline,
            resume=self.resume,
            overwrite=self.overwrite,
            font_path=self.font_path,
            ocr=self.ocr,
            paragraph_reconstruction=self.paragraph_reconstruction,
        )


@dataclass(frozen=True)
class BatchDiscovery:
    """Deterministically ordered PDF discovery with explicit exclusions."""

    discovered_files: tuple[Path, ...]
    selected_files: tuple[Path, ...]
    skipped_files: tuple[BatchSkippedFile, ...]


class BatchSkippedFile(DomainModel):
    """A discovered PDF intentionally omitted from processing."""

    input_path: str = Field(min_length=1)
    output_path: str | None = None
    reason: str = Field(min_length=1)


class BatchFileSuccess(DomainModel):
    """Metrics for one successfully validated output PDF."""

    input_path: str = Field(min_length=1)
    output_path: str = Field(min_length=1)
    pages_processed: int = Field(ge=0)
    ocr_pages: int = Field(ge=0)
    translated_blocks: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0)
    reused_stages: tuple[str, ...] = ()


class BatchFileFailure(DomainModel):
    """Stable error details for one failed source PDF."""

    input_path: str = Field(min_length=1)
    output_path: str = Field(min_length=1)
    exit_code: int = Field(ge=1)
    error: str = Field(min_length=1)
    diagnostics_path: str | None = None
    elapsed_seconds: float = Field(ge=0)


class BatchReport(DomainModel):
    """Versioned complete machine-readable result of a directory batch."""

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["completed", "partial", "failed", "interrupted"]
    started_at: datetime
    finished_at: datetime
    elapsed_seconds: float = Field(ge=0)
    input_root: str = Field(min_length=1)
    output_root: str = Field(min_length=1)
    report_path: str = Field(min_length=1)
    recursive: bool
    include_pattern: str = Field(min_length=1)
    exclude_patterns: tuple[str, ...] = ()
    continue_on_error: bool
    discovered_files: tuple[str, ...]
    successful_files: tuple[BatchFileSuccess, ...]
    failed_files: tuple[BatchFileFailure, ...]
    skipped_files: tuple[BatchSkippedFile, ...]
    pages_processed: int = Field(ge=0)
    ocr_pages: int = Field(ge=0)
    translated_blocks: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    final_exit_code: int = Field(ge=0)


@dataclass(frozen=True)
class BatchResult:
    """Batch report plus its publication path and process result."""

    report: BatchReport
    report_path: Path
    exit_code: ExitCode


@dataclass(frozen=True)
class BatchProgress:
    """One file-level transition for terminal reporting."""

    index: int
    total: int
    input_path: Path
    output_path: Path


def default_batch_output_dir(input_dir: Path) -> Path:
    """Return the documented sibling `<input-dir>_ru` output root."""
    source = input_dir.expanduser()
    return source.with_name(f"{source.name}_ru")
