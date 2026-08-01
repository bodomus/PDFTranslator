"""Reusable translation benchmark runner independent from Typer and PDF rendering."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pdftranslate import __version__
from pdftranslate.benchmark.checks import (
    analyze_human_review,
    analyze_sample_output,
    analyze_stage_trace,
)
from pdftranslate.benchmark.models import (
    BenchmarkDataset,
    BenchmarkFinding,
    BenchmarkMetadata,
    BenchmarkReport,
    SampleBenchmarkResult,
    SampleStatus,
    SegmentEvidence,
)
from pdftranslate.translation.errors import ProtectedTokenError, TranslationError
from pdftranslate.translation.protocol import Translator
from pdftranslate.translation.text import (
    protect_text,
    recombine_segments,
    segment_text,
)


@dataclass(frozen=True)
class BenchmarkOptions:
    batch_size: int = 8
    max_input_tokens: int = 512
    commit: str | None = None

    def __post_init__(self) -> None:
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if self.max_input_tokens < 8:
            raise ValueError("max_input_tokens must be at least 8")


_DEFAULT_OPTIONS = BenchmarkOptions()


@dataclass(frozen=True)
class _CachedTranslation:
    output: str | None
    segments: tuple[SegmentEvidence, ...]
    source_segment_count: int
    output_segment_count: int
    segmentation_warning: bool
    protection_error: str | None
    runtime_error: str | None


def run_benchmark(
    dataset: BenchmarkDataset,
    *,
    translator: Translator,
    options: BenchmarkOptions = _DEFAULT_OPTIONS,
    repository_root: Path | None = None,
) -> BenchmarkReport:
    """Run every sample through one loaded translator and retain stage evidence."""
    started_at = datetime.now(UTC)
    started = time.perf_counter()
    cache: dict[str, _CachedTranslation] = {}
    results: list[SampleBenchmarkResult] = []
    cache_hits = 0
    cache_misses = 0

    for sample in dataset.samples:
        sample_started = time.perf_counter()
        effective_source = (
            sample.stage_trace.extracted_text
            if sample.stage_trace is not None and sample.stage_trace.extracted_text is not None
            else sample.source
        )
        cached_translation = cache.get(effective_source)
        cache_hit = cached_translation is not None
        if cache_hit:
            cache_hits += 1
            assert cached_translation is not None
        else:
            cache_misses += 1
            output: str | None = None
            evidence: list[SegmentEvidence] = []
            source_segment_count = 0
            output_segment_count = 0
            segmentation_warning = False
            protection_error: str | None = None
            runtime_error: str | None = None
            try:
                protected = protect_text(effective_source)
                segmentation = segment_text(
                    protected.value,
                    count_tokens=translator.count_tokens,
                    max_tokens=options.max_input_tokens,
                )
                source_segments = [segment.text for segment in segmentation.segments]
                translated_segments: list[str] = []
                for offset in range(0, len(source_segments), options.batch_size):
                    translated_segments.extend(
                        translator.translate_batch(
                            source_segments[offset : offset + options.batch_size]
                        )
                    )
                for index, source_segment in enumerate(source_segments):
                    model_output = (
                        translated_segments[index] if index < len(translated_segments) else ""
                    )
                    evidence.append(
                        SegmentEvidence(
                            source=segmentation.segments[index].text,
                            protected_source=source_segment,
                            model_output=model_output,
                        )
                    )
                source_segment_count = len(segmentation.segments)
                output_segment_count = len(translated_segments)
                segmentation_warning = segmentation.quality_warning
                if output_segment_count == source_segment_count:
                    combined = recombine_segments(segmentation.segments, translated_segments)
                    try:
                        output = protected.restore(combined)
                    except ProtectedTokenError as error:
                        protection_error = str(error)
                        output = combined
                else:
                    output = " ".join(translated_segments)
            except (TranslationError, ValueError) as error:
                runtime_error = str(error)
            cached_translation = _CachedTranslation(
                output=output,
                segments=tuple(evidence),
                source_segment_count=source_segment_count,
                output_segment_count=output_segment_count,
                segmentation_warning=segmentation_warning,
                protection_error=protection_error,
                runtime_error=runtime_error,
            )
            cache[effective_source] = cached_translation

        current_findings: tuple[BenchmarkFinding, ...]
        if cached_translation.runtime_error is not None:
            current_findings = (
                BenchmarkFinding(
                    code="benchmark-execution-error",
                    stage="model",
                    severity="error",
                    message=cached_translation.runtime_error,
                ),
                *analyze_human_review(sample.human_review),
            )
        else:
            assert cached_translation.output is not None
            current_findings = analyze_sample_output(
                sample,
                effective_source,
                cached_translation.output,
                source_segment_count=cached_translation.source_segment_count,
                output_segment_count=cached_translation.output_segment_count,
                segmentation_warning=cached_translation.segmentation_warning,
                protection_error=cached_translation.protection_error,
            )
        current_findings = _merge_findings(current_findings)
        status = _status(current_findings, cached_translation.runtime_error is not None)
        findings = _merge_findings((*current_findings, *analyze_stage_trace(sample)))
        results.append(
            SampleBenchmarkResult(
                sample_id=sample.id,
                category=sample.category,
                status=status,
                source=sample.source,
                effective_source=effective_source,
                reference=sample.reference,
                output=cached_translation.output,
                segments=cached_translation.segments,
                findings=findings,
                human_review=sample.human_review,
                elapsed_seconds=time.perf_counter() - sample_started,
                cache_hit=cache_hit,
            )
        )

    finished_at = datetime.now(UTC)
    passed = sum(result.status == "passed" for result in results)
    failed = sum(result.status == "failed" for result in results)
    errors = sum(result.status == "error" for result in results)
    root = (repository_root or Path.cwd()).expanduser().resolve()
    metadata = BenchmarkMetadata(
        application_version=__version__,
        commit=options.commit or _git_commit(root),
        dataset_version=dataset.dataset_version,
        backend=translator.backend_name,
        model=translator.model_name,
        tokenizer=translator.model_name,
        device=translator.device,
        batch_size=options.batch_size,
        max_input_tokens=options.max_input_tokens,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=time.perf_counter() - started,
        sample_count=len(results),
        passed_samples=passed,
        failed_samples=failed,
        error_samples=errors,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
    )
    return BenchmarkReport(metadata=metadata, results=tuple(results))


def _status(findings: tuple[BenchmarkFinding, ...], runtime_error: bool) -> SampleStatus:
    if runtime_error:
        return "error"
    if any(finding.severity == "error" for finding in findings):
        return "failed"
    return "passed"


def _merge_findings(findings: tuple[BenchmarkFinding, ...]) -> tuple[BenchmarkFinding, ...]:
    unique: dict[tuple[str, str, tuple[str, ...]], BenchmarkFinding] = {}
    for finding in findings:
        unique[(finding.stage, finding.code, finding.evidence)] = finding
    return tuple(unique.values())


def _git_commit(repository_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"
