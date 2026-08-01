"""Versioned contracts for translation-quality datasets and reports."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from pdftranslate.domain.text_block import DomainModel

FindingStage = Literal[
    "extraction",
    "segmentation",
    "protected_token",
    "model",
    "terminology",
    "rendering",
]
FindingSeverity = Literal["info", "warning", "error"]
FindingOrigin = Literal["current_run", "historical_trace"]
SampleStatus = Literal["passed", "failed", "error"]


class HumanReview(DomainModel):
    """Optional 1–5 human scores; 1 is unacceptable and 5 is excellent."""

    reviewer: str = Field(min_length=1)
    adequacy: int = Field(ge=1, le=5)
    fluency: int = Field(ge=1, le=5)
    terminology: int = Field(ge=1, le=5)
    token_preservation: int = Field(ge=1, le=5)
    segmentation: int = Field(ge=1, le=5)
    overall_acceptability: int = Field(ge=1, le=5)
    notes: str | None = None


class StageTrace(DomainModel):
    """Optional observed stage snapshots used to attribute historical defects."""

    extracted_text: str | None = None
    source_segments: tuple[str, ...] = ()
    translated_segments: tuple[str, ...] = ()
    observed_translation: str | None = None
    rendered_text: str | None = None

    @model_validator(mode="after")
    def validate_dependencies(self) -> StageTrace:
        if self.translated_segments and not self.source_segments:
            raise ValueError("translated_segments require source_segments")
        if self.rendered_text is not None and self.observed_translation is None:
            raise ValueError("rendered_text requires observed_translation")
        return self


class BenchmarkSample(DomainModel):
    """One safe, attributable English-to-Russian benchmark sample."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    category: str = Field(min_length=1)
    source: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    context: str | None = None
    protected_tokens: tuple[str, ...] = ()
    notes: str | None = None
    provenance: str = Field(min_length=1)
    stage_trace: StageTrace | None = None
    human_review: HumanReview | None = None

    @model_validator(mode="after")
    def validate_tokens(self) -> BenchmarkSample:
        if len(set(self.protected_tokens)) != len(self.protected_tokens):
            raise ValueError("protected_tokens must be unique")
        missing = [token for token in self.protected_tokens if token not in self.source]
        if missing:
            raise ValueError(f"protected tokens are absent from source: {missing}")
        return self


class BenchmarkDataset(DomainModel):
    """Repository-safe benchmark dataset schema 1.0."""

    schema_version: Literal["1.0"] = "1.0"
    dataset_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    title: str = Field(min_length=1)
    license: str = Field(min_length=1)
    samples: tuple[BenchmarkSample, ...] = Field(min_length=50, max_length=100)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> BenchmarkDataset:
        identifiers = [sample.id.casefold() for sample in self.samples]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("benchmark sample IDs must be unique")
        return self


class BenchmarkFinding(DomainModel):
    """One deterministic or human-supplied stage-attributed observation."""

    code: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$")
    stage: FindingStage
    severity: FindingSeverity
    origin: FindingOrigin = "current_run"
    message: str = Field(min_length=1)
    evidence: tuple[str, ...] = ()


class SegmentEvidence(DomainModel):
    source: str
    protected_source: str
    model_output: str


class SampleBenchmarkResult(DomainModel):
    sample_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    status: SampleStatus
    source: str
    effective_source: str
    reference: str
    output: str | None = None
    segments: tuple[SegmentEvidence, ...] = ()
    findings: tuple[BenchmarkFinding, ...] = ()
    human_review: HumanReview | None = None
    elapsed_seconds: float = Field(ge=0)
    cache_hit: bool = False


class BaselineComparison(DomainModel):
    baseline_dataset_version: str = Field(min_length=1)
    regressed_samples: tuple[str, ...] = ()
    improved_samples: tuple[str, ...] = ()
    new_findings: tuple[str, ...] = ()
    resolved_findings: tuple[str, ...] = ()


class BenchmarkMetadata(DomainModel):
    application_version: str = Field(min_length=1)
    commit: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    backend: str = Field(min_length=1)
    model: str = Field(min_length=1)
    tokenizer: str = Field(min_length=1)
    device: Literal["cpu", "cuda"]
    batch_size: int = Field(ge=1)
    max_input_tokens: int = Field(ge=8)
    started_at: datetime
    finished_at: datetime
    elapsed_seconds: float = Field(ge=0)
    sample_count: int = Field(ge=0)
    passed_samples: int = Field(ge=0)
    failed_samples: int = Field(ge=0)
    error_samples: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    cache_misses: int = Field(ge=0)


class BenchmarkReport(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    metadata: BenchmarkMetadata
    results: tuple[SampleBenchmarkResult, ...]
    comparison: BaselineComparison | None = None
