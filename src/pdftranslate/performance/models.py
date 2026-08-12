"""Versioned performance-report contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PerformanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TimingDistribution(PerformanceModel):
    count: int = Field(ge=0)
    minimum: float | None = Field(default=None, ge=0)
    median: float | None = Field(default=None, ge=0)
    percentile_95: float | None = Field(default=None, ge=0)
    maximum: float | None = Field(default=None, ge=0)


class RunTimings(PerformanceModel):
    process_wall_seconds: float = Field(ge=0)
    runtime_open_seconds: float | None = Field(default=None, ge=0)
    model_load_seconds: float | None = Field(default=None, ge=0)
    first_inference_seconds: float | None = Field(default=None, ge=0)
    translation_seconds: float = Field(ge=0)
    cache_only_seconds: float | None = Field(default=None, ge=0)
    total_seconds: float = Field(ge=0)


class CpuMemory(PerformanceModel):
    metric: Literal["rss"] = "rss"
    rss_before_model: int | None = Field(default=None, ge=0)
    rss_after_model_load: int | None = Field(default=None, ge=0)
    rss_peak: int | None = Field(default=None, ge=0)
    rss_after_run: int | None = Field(default=None, ge=0)


class CudaMemory(PerformanceModel):
    allocated_before: int | None = Field(default=None, ge=0)
    reserved_before: int | None = Field(default=None, ge=0)
    allocated_after: int | None = Field(default=None, ge=0)
    reserved_after: int | None = Field(default=None, ge=0)
    peak_allocated: int | None = Field(default=None, ge=0)
    peak_reserved: int | None = Field(default=None, ge=0)


class IntegrityEvidence(PerformanceModel):
    passed: bool
    output_count: int = Field(ge=0)
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    placeholder_leaks: int = Field(ge=0)
    protected_token_violations: int = Field(ge=0)
    glossary_violations: int = Field(ge=0)


class BenchmarkScenario(PerformanceModel):
    name: str
    device_request: Literal["cpu", "cuda", "auto"]
    effective_device: Literal["cpu", "cuda"]
    batch_size: int = Field(ge=1)
    iteration: int = Field(ge=0)
    warmup: bool
    cache_state: Literal["empty", "fresh", "warm"]
    model_state: Literal["cold", "warm"]
    documents: int = Field(ge=1)
    paragraphs: int = Field(ge=0)
    segments: int = Field(ge=0)
    characters: int = Field(ge=0)
    source_tokens: int | None = Field(default=None, ge=0)
    translator_calls: int = Field(ge=0)
    model_facing_segments: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    cache_misses: int = Field(ge=0)
    model_load_count: int = Field(ge=0)
    paragraphs_per_second: float = Field(ge=0)
    segments_per_second: float = Field(ge=0)
    characters_per_second: float = Field(ge=0)
    timings: RunTimings
    cpu_memory: CpuMemory
    cuda_memory: CudaMemory | None = None
    integrity: IntegrityEvidence


class BenchmarkMetadata(PerformanceModel):
    timestamp_utc: datetime
    os: str
    python: str
    application_version: str
    git_commit: str
    backend: str
    model: str
    device_request: Literal["cpu", "cuda", "auto"]
    max_input_tokens: int = Field(ge=8)
    translation_behavior_revision: int = Field(ge=1)
    pipeline_behavior_revision: int = Field(ge=1)
    offline: bool
    torch_version: str | None = None
    torch_cuda_runtime: str | None = None
    cuda_available: bool
    cuda_device_name: str | None = None
    cuda_capability: tuple[int, int] | None = None
    cuda_total_memory: int | None = Field(default=None, ge=0)
    cpu_model: str | None = None
    logical_cpu_count: int | None = Field(default=None, ge=1)
    system_ram: int | None = Field(default=None, ge=0)


class DatasetMetadata(PerformanceModel):
    version: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    paragraphs: int = Field(ge=100)
    characters: int = Field(ge=1)
    length_classes: dict[str, int]
    glossary_fingerprint: str | None = None
    document_schema_version: str


class BenchmarkReport(PerformanceModel):
    schema_version: Literal["1.0"] = "1.0"
    complete: bool
    mode: Literal["synthetic", "real-model"]
    metadata: BenchmarkMetadata
    dataset: DatasetMetadata
    scenarios: tuple[BenchmarkScenario, ...]
    timing_distributions: dict[str, TimingDistribution] = Field(default_factory=dict)
    comparisons: dict[str, float | int | str | bool | None]
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
