"""Versioned, privacy-safe diagnostic report contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from pdftranslate.domain.text_block import BoundingBox, DomainModel


class DiagnosticCode(StrEnum):
    """Stable machine-readable warning and error codes."""

    READING_ORDER_AMBIGUOUS = "READING_ORDER_AMBIGUOUS"
    TRANSLATION_TOKEN_MISMATCH = "TRANSLATION_TOKEN_MISMATCH"
    FONT_REDUCED = "FONT_REDUCED"
    BLOCK_EXPANDED = "BLOCK_EXPANDED"
    BLOCK_OVERFLOW = "BLOCK_OVERFLOW"
    OCR_LOW_TEXT_GAIN = "OCR_LOW_TEXT_GAIN"
    OUTPUT_VALIDATION_FAILED = "OUTPUT_VALIDATION_FAILED"
    PIPELINE_STAGE_FAILED = "PIPELINE_STAGE_FAILED"
    RENDER_WARNING = "RENDER_WARNING"


class DiagnosticFinding(DomainModel):
    code: DiagnosticCode
    severity: Literal["info", "warning", "error"]
    stage: str
    message: str
    page_number: int | None = Field(default=None, ge=1)
    block_id: str | None = None


class BlockDiagnostic(DomainModel):
    block_id: str
    page_number: int = Field(ge=1)
    source_bbox: BoundingBox
    final_bbox: BoundingBox | None = None
    initial_font_size: float | None = None
    final_font_size: float | None = None
    fitting_attempts: int | None = None
    segmentation_count: int | None = None
    cache_status: Literal["hit", "miss", "skipped", "unknown"] = "unknown"
    final_state: Literal["rendered", "expanded", "overflow", "skipped", "unknown"]
    warning_codes: tuple[DiagnosticCode, ...] = ()
    source_text: str | None = None
    translated_text: str | None = None


class PageDiagnostic(DomainModel):
    page_number: int = Field(ge=1)
    classification: str
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    ocr_status: Literal["processed", "not_processed", "unknown"]
    warning_codes: tuple[DiagnosticCode, ...] = ()
    blocks: tuple[BlockDiagnostic, ...] = ()


class ReportSummary(DomainModel):
    page_count: int = Field(ge=0)
    pages_by_type: dict[str, int]
    blocks_extracted: int = Field(ge=0)
    blocks_translated: int = Field(ge=0)
    blocks_skipped: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    cache_misses: int = Field(ge=0)
    translated_segments: int = Field(ge=0)
    ocr_pages: int = Field(ge=0)
    font_reductions: int = Field(ge=0)
    expanded_blocks: int = Field(ge=0)
    overflow_blocks: int = Field(ge=0)
    input_size: int = Field(ge=0)
    output_size: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0)
    stage_durations: dict[str, float]
    peak_ram_bytes: int | None = Field(default=None, ge=0)
    peak_vram_bytes: int | None = Field(default=None, ge=0)
    selected_font: str | None = None


class TranslationReport(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    status: Literal["success", "failed", "interrupted"]
    started_at: datetime
    finished_at: datetime
    input_path: str
    output_path: str
    failed_stage: str | None = None
    summary: ReportSummary
    pages: tuple[PageDiagnostic, ...]
    findings: tuple[DiagnosticFinding, ...] = ()
    text_included: bool = False
    debug_layout_path: str | None = None
