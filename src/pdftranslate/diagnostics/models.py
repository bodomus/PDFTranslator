"""Versioned, privacy-safe diagnostic report contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from pdftranslate.domain.text_block import BoundingBox, DomainModel
from pdftranslate.reconstruction import ParagraphReconstruction
from pdftranslate.repeated import RepeatedElementKind, RepeatedElementPolicy


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
    REPEATED_ELEMENT_AMBIGUOUS = "REPEATED_ELEMENT_AMBIGUOUS"
    GLOSSARY_CONFLICT = "GLOSSARY_CONFLICT"
    GLOSSARY_MATCH_AMBIGUOUS = "GLOSSARY_MATCH_AMBIGUOUS"
    GLOSSARY_TARGET_MISSING = "GLOSSARY_TARGET_MISSING"
    GLOSSARY_PRESERVE_VIOLATION = "GLOSSARY_PRESERVE_VIOLATION"
    GLOSSARY_PLACEHOLDER_LEAK = "GLOSSARY_PLACEHOLDER_LEAK"
    GLOSSARY_ENTRY_UNUSED = "GLOSSARY_ENTRY_UNUSED"


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
    repeated_classification: RepeatedElementKind = RepeatedElementKind.BODY
    repeated_confidence: float = Field(default=1.0, ge=0, le=1)
    repeated_group_id: str | None = None
    repeated_policy: RepeatedElementPolicy = RepeatedElementPolicy.TRANSLATE
    repeated_ambiguous: bool = False
    glossary_entry_ids: tuple[str, ...] = ()
    glossary_occurrences: int = Field(default=0, ge=0)
    glossary_modes: tuple[str, ...] = ()
    glossary_compliance: Literal["not_applicable", "compliant", "violation"] = "not_applicable"


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
    raw_lines: int = Field(default=0, ge=0)
    logical_paragraphs: int = Field(default=0, ge=0)
    ambiguous_decisions: int = Field(default=0, ge=0)
    cross_page_merges: int = Field(default=0, ge=0)
    repeated_elements: dict[str, int] = Field(default_factory=dict)
    ambiguous_repeated_elements: int = Field(default=0, ge=0)

    glossary_enabled: bool = False
    glossary_schema_version: str | None = None
    glossary_version: str | None = None
    glossary_fingerprint: str | None = None
    glossary_total_entries: int = Field(default=0, ge=0)
    glossary_matched_entries: int = Field(default=0, ge=0)
    glossary_unmatched_entries: int = Field(default=0, ge=0)
    glossary_applied_occurrences: int = Field(default=0, ge=0)
    glossary_preserved_occurrences: int = Field(default=0, ge=0)
    glossary_translation_occurrences: int = Field(default=0, ge=0)
    glossary_violations: int = Field(default=0, ge=0)
    glossary_conflicts: int = Field(default=0, ge=0)
    glossary_ambiguous_matches: int = Field(default=0, ge=0)


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
    reconstruction: ParagraphReconstruction | None = None
