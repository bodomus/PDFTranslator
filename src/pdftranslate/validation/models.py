"""Typed contracts for opt-in real-PDF validation reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from pdftranslate.domain.text_block import DomainModel
from pdftranslate.pipeline.models import DeviceRequest, OcrMode, PipelineStage

CheckStatus = Literal["passed", "failed", "not_checked", "not_applicable"]
DocumentStatus = Literal["planned", "passed", "failed"]
StageStatus = Literal["planned", "passed", "failed", "reused", "not_run"]

MANUAL_CHECK_NAMES = (
    "output_opens",
    "page_count_matches",
    "russian_text_selectable",
    "russian_text_searchable",
    "russian_text_copyable",
    "images_preserved",
    "original_english_not_duplicated",
    "columns_usable",
    "tables_usable",
    "source_unchanged",
    "resume_works",
    "partial_output_not_reported_as_success",
)


@dataclass(frozen=True)
class ValidationOptions:
    """Behavior-affecting options for one corpus validation run."""

    corpus_root: Path
    output_root: Path
    manifest_path: Path | None = None
    manual_results_path: Path | None = None
    subsets: tuple[str, ...] = ()
    dry_run: bool = False
    continue_on_error: bool = True
    pages: str | None = None
    backend: str = "nllb"
    model: str = "facebook/nllb-200-distilled-600M"
    device: DeviceRequest = "auto"
    batch_size: int = 8
    max_input_tokens: int = 512
    cache_dir: Path | None = None
    offline: bool = False
    resume: bool = False
    overwrite: bool = False
    font_path: Path | None = None
    ocr: OcrMode = "auto"

    def __post_init__(self) -> None:
        if self.resume and self.overwrite:
            raise ValueError("resume and overwrite cannot be used together")
        if self.dry_run and (self.resume or self.overwrite):
            raise ValueError("dry-run cannot be combined with resume or overwrite")

    @property
    def resolved_corpus_root(self) -> Path:
        return self.corpus_root.expanduser().resolve()

    @property
    def resolved_output_root(self) -> Path:
        return self.output_root.expanduser().resolve()


class CorpusDocument(DomainModel):
    """One relative, reproducible corpus entry."""

    document_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    path: str = Field(min_length=1)
    categories: tuple[str, ...] = ("unclassified",)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_categories(self) -> CorpusDocument:
        if not self.categories or any(not item.strip() for item in self.categories):
            raise ValueError("categories must contain non-empty values")
        return self


class CorpusManifest(DomainModel):
    """Optional description of a local corpus."""

    schema_version: Literal["1.0"] = "1.0"
    documents: tuple[CorpusDocument, ...]

    @model_validator(mode="after")
    def validate_unique_ids(self) -> CorpusManifest:
        identifiers = [item.document_id.casefold() for item in self.documents]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("manifest document IDs must be unique")
        return self


class ManualReview(DomainModel):
    """Human observations from PDF-XChange Editor."""

    editor: str = "PDF-XChange Editor"
    reviewer: str | None = None
    reviewed_at: datetime | None = None
    output_opens: CheckStatus = "not_checked"
    page_count_matches: CheckStatus = "not_checked"
    russian_text_selectable: CheckStatus = "not_checked"
    russian_text_searchable: CheckStatus = "not_checked"
    russian_text_copyable: CheckStatus = "not_checked"
    images_preserved: CheckStatus = "not_checked"
    original_english_not_duplicated: CheckStatus = "not_checked"
    columns_usable: CheckStatus = "not_checked"
    tables_usable: CheckStatus = "not_checked"
    source_unchanged: CheckStatus = "not_checked"
    resume_works: CheckStatus = "not_checked"
    partial_output_not_reported_as_success: CheckStatus = "not_checked"
    notes: str | None = None

    @property
    def status(self) -> Literal["passed", "failed", "partial", "not_checked"]:
        values = [getattr(self, name) for name in MANUAL_CHECK_NAMES]
        if "failed" in values:
            return "failed"
        checked = [value for value in values if value not in {"not_checked", "not_applicable"}]
        if not checked:
            return "not_checked"
        if any(value == "not_checked" for value in values):
            return "partial"
        return "passed"


class ManualReviewEntry(DomainModel):
    document_id: str = Field(min_length=1)
    review: ManualReview = Field(default_factory=ManualReview)


class ManualReviewManifest(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    documents: tuple[ManualReviewEntry, ...]

    @model_validator(mode="after")
    def validate_unique_ids(self) -> ManualReviewManifest:
        identifiers = [item.document_id.casefold() for item in self.documents]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("manual-review document IDs must be unique")
        return self


class StageValidationResult(DomainModel):
    stage: PipelineStage
    status: StageStatus
    elapsed_seconds: float = Field(ge=0)


class ValidationFailure(DomainModel):
    exit_code: int = Field(ge=1)
    stage: PipelineStage | None = None
    error: str = Field(min_length=1)
    diagnostics_log: str | None = None


class ValidationDefect(DomainModel):
    document_id: str = Field(min_length=1)
    severity: Literal["critical", "major", "normal", "minor"]
    stage: str = Field(min_length=1)
    reproducibility: Literal["deterministic", "intermittent", "unknown"]
    summary: str = Field(min_length=1)
    root_cause: str = Field(min_length=1)
    recommended_follow_up: str = Field(min_length=1)


class DocumentValidationResult(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    document_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    categories: tuple[str, ...]
    status: DocumentStatus
    started_at: datetime
    finished_at: datetime
    elapsed_seconds: float = Field(ge=0)
    source_sha256_before: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256_after: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_size_before: int = Field(ge=0)
    source_size_after: int | None = Field(default=None, ge=0)
    source_unchanged: bool
    page_count: int | None = Field(default=None, ge=0)
    page_classifications: tuple[str, ...] = ()
    stage_results: tuple[StageValidationResult, ...]
    backend: str = Field(min_length=1)
    requested_device: DeviceRequest
    effective_device: Literal["cpu", "cuda"] | None = None
    ocr_decision: str = Field(min_length=1)
    ocr_pages: tuple[int, ...] = ()
    cache_hits: int = Field(default=0, ge=0)
    cache_misses: int = Field(default=0, ge=0)
    resume_requested: bool = False
    reused_stages: tuple[PipelineStage, ...] = ()
    output_relative_path: str | None = None
    output_size: int | None = Field(default=None, ge=0)
    workspace_size: int | None = Field(default=None, ge=0)
    warnings: tuple[str, ...] = ()
    failure: ValidationFailure | None = None
    manual_review: ManualReview = Field(default_factory=ManualReview)
    defects: tuple[ValidationDefect, ...] = ()


class ValidationSummary(DomainModel):
    """Complete corpus result with references to individual JSON files."""

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["planned", "passed", "failed"]
    started_at: datetime
    finished_at: datetime
    elapsed_seconds: float = Field(ge=0)
    dry_run: bool
    corpus_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_subsets: tuple[str, ...] = ()
    discovered_documents: int = Field(ge=0)
    selected_documents: int = Field(ge=0)
    passed_documents: int = Field(ge=0)
    failed_documents: int = Field(ge=0)
    planned_documents: int = Field(ge=0)
    source_integrity_failures: int = Field(ge=0)
    manual_reviews_passed: int = Field(ge=0)
    manual_reviews_failed: int = Field(ge=0)
    manual_reviews_pending: int = Field(ge=0)
    categories_covered: tuple[str, ...]
    document_result_files: tuple[str, ...]
    defects: tuple[ValidationDefect, ...] = ()
