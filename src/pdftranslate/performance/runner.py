"""Scenario orchestration through the production paragraph translation path."""

from __future__ import annotations

import ctypes
import hashlib
import importlib
import os
import platform
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pdftranslate import __version__
from pdftranslate.performance.dataset import DATASET_VERSION, PerformanceDataset
from pdftranslate.performance.metrics import aggregate_timings, throughput
from pdftranslate.performance.models import (
    BenchmarkMetadata,
    BenchmarkReport,
    BenchmarkScenario,
    CpuMemory,
    CudaMemory,
    DatasetMetadata,
    IntegrityEvidence,
    RunTimings,
)
from pdftranslate.performance.sampler import RssSampler, current_rss_bytes
from pdftranslate.pipeline.models import PIPELINE_BEHAVIOR_REVISION
from pdftranslate.translation import TranslationCache, TranslationOptions, translate_document
from pdftranslate.translation.cache import TRANSLATION_BEHAVIOR_REVISION
from pdftranslate.translation.protocol import Translator

DeviceRequest = Literal["cpu", "cuda", "auto"]
Mode = Literal["synthetic", "real-model"]
TranslatorFactory = Callable[[], Translator]


@dataclass(frozen=True)
class BenchmarkConfig:
    mode: Mode
    device: DeviceRequest
    batch_sizes: tuple[int, ...] = (1, 4, 8)
    iterations: int = 5
    warmup: int = 1
    max_input_tokens: int = 64
    offline: bool = False

    def __post_init__(self) -> None:
        if not self.batch_sizes or any(value < 1 for value in self.batch_sizes):
            raise ValueError("batch sizes must contain positive integers")
        if self.iterations < 1 or self.warmup < 0:
            raise ValueError("iterations must be positive and warmup cannot be negative")
        if self.max_input_tokens < 8:
            raise ValueError("max input tokens must be at least 8")


class MeasuredTranslator:
    def __init__(self, translator: Translator) -> None:
        self._translator = translator
        self.call_durations: list[float] = []
        self.segment_counts: list[int] = []

    @property
    def backend_name(self) -> str:
        return self._translator.backend_name

    @property
    def model_name(self) -> str:
        return self._translator.model_name

    @property
    def device(self) -> Literal["cpu", "cuda"]:
        return self._translator.device

    def count_tokens(self, text: str) -> int:
        return self._translator.count_tokens(text)

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        started = time.perf_counter()
        try:
            return self._translator.translate_batch(texts)
        finally:
            self.call_durations.append(time.perf_counter() - started)
            self.segment_counts.append(len(texts))


class DeterministicTranslator:
    backend_name = "deterministic-fake"
    model_name = "pdftr-14-fake-v1"

    def __init__(self, device: DeviceRequest) -> None:
        self._device: Literal["cpu", "cuda"] = "cuda" if device == "cuda" else "cpu"

    @property
    def device(self) -> Literal["cpu", "cuda"]:
        return self._device

    def count_tokens(self, text: str) -> int:
        return len(text.split()) + 2

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        return [f"RU {text}" for text in texts]


def run_performance_benchmark(
    dataset: PerformanceDataset,
    *,
    config: BenchmarkConfig,
    translator_factory: TranslatorFactory,
    output_root: Path,
) -> BenchmarkReport:
    root = output_root.expanduser().resolve()
    repository_temp = (Path.cwd() / "temp").resolve()
    if root != repository_temp and repository_temp not in root.parents:
        raise ValueError("performance benchmark output must be below repository-local ./temp")
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(
            f"performance benchmark output is not empty; select a run-specific path: {root}"
        )
    root.mkdir(parents=True, exist_ok=True)
    started_wall = time.perf_counter()
    rss_before = current_rss_bytes()
    load_started = time.perf_counter()
    measured = MeasuredTranslator(translator_factory())
    model_load_seconds = time.perf_counter() - load_started
    rss_after_load = current_rss_bytes()
    if config.device == "cuda" and measured.device != "cuda":
        raise RuntimeError("explicit CUDA benchmark resolved to CPU")

    scenarios: list[BenchmarkScenario] = []
    cold_cache = root / "cold.sqlite3"
    cold = _run_documents(
        dataset,
        measured,
        config,
        cache_path=cold_cache,
        name=f"cold-{measured.device}",
        batch_size=config.batch_sizes[0],
        iteration=0,
        warmup=False,
        cache_state="empty",
        model_state="cold",
        documents=1,
        model_load_seconds=model_load_seconds,
        rss_before_model=rss_before,
        rss_after_model_load=rss_after_load,
    )
    scenarios.append(cold)
    expected_segments = cold.segments

    warm_model_cache = root / "warm-model.sqlite3"
    scenarios.append(
        _run_documents(
            dataset,
            measured,
            config,
            cache_path=warm_model_cache,
            name=f"warm-model-{measured.device}",
            batch_size=config.batch_sizes[0],
            iteration=0,
            warmup=False,
            cache_state="fresh",
            model_state="warm",
            documents=1,
            expected_segments=expected_segments,
            rss_before_model=rss_before,
            rss_after_model_load=rss_after_load,
        )
    )

    for length_class in dataset.length_classes:
        length_dataset = dataset.select_length_class(length_class)
        scenarios.append(
            _run_documents(
                length_dataset,
                measured,
                config,
                cache_path=root / f"length-{length_class}.sqlite3",
                name=f"length-{length_class}-{measured.device}",
                batch_size=config.batch_sizes[0],
                iteration=0,
                warmup=False,
                cache_state="fresh",
                model_state="warm",
                documents=1,
                rss_before_model=rss_before,
                rss_after_model_load=rss_after_load,
            )
        )
    scenarios.append(
        _run_documents(
            dataset,
            measured,
            config,
            cache_path=cold_cache,
            name=f"warm-cache-{measured.device}",
            batch_size=config.batch_sizes[0],
            iteration=0,
            warmup=False,
            cache_state="warm",
            model_state="warm",
            documents=1,
            expected_segments=expected_segments,
            rss_before_model=rss_before,
            rss_after_model_load=rss_after_load,
        )
    )

    for batch_size in config.batch_sizes:
        for iteration in range(config.warmup + config.iterations):
            is_warmup = iteration < config.warmup
            measured_iteration = iteration if is_warmup else iteration - config.warmup
            scenarios.append(
                _run_documents(
                    dataset,
                    measured,
                    config,
                    cache_path=root / f"matrix-b{batch_size}-i{iteration}.sqlite3",
                    name=f"matrix-{measured.device}-b{batch_size}",
                    batch_size=batch_size,
                    iteration=measured_iteration,
                    warmup=is_warmup,
                    cache_state="fresh",
                    model_state="warm",
                    documents=1,
                    expected_segments=expected_segments,
                    rss_before_model=rss_before,
                    rss_after_model_load=rss_after_load,
                )
            )

    scenarios.append(
        _run_documents(
            dataset,
            measured,
            config,
            cache_path=root / "batch-reuse.sqlite3",
            name=f"batch-reuse-{measured.device}",
            batch_size=config.batch_sizes[-1],
            iteration=0,
            warmup=False,
            cache_state="fresh",
            model_state="warm",
            documents=3,
            expected_segments=expected_segments * 3,
            rss_before_model=rss_before,
            rss_after_model_load=rss_after_load,
        )
    )

    hashes = {
        scenario.integrity.output_hash
        for scenario in scenarios
        if scenario.documents == 1 and not scenario.name.startswith("length-")
    }
    measured_matrix = [
        scenario
        for scenario in scenarios
        if scenario.name.startswith("matrix-") and not scenario.warmup
    ]
    timing_distributions = {
        f"batch_size_{batch_size}_total_seconds": aggregate_timings(
            [
                item.timings.total_seconds
                for item in measured_matrix
                if item.batch_size == batch_size
            ]
        )
        for batch_size in config.batch_sizes
    }
    median_rates = {
        batch_size: aggregate_timings(
            [
                item.characters_per_second
                for item in measured_matrix
                if item.batch_size == batch_size
            ]
        ).median
        for batch_size in config.batch_sizes
    }
    best_batch_size = max(median_rates, key=lambda value: median_rates[value] or 0.0)
    warm_cache = next(item for item in scenarios if item.name.startswith("warm-cache-"))
    warm_model = next(item for item in scenarios if item.name.startswith("warm-model-"))
    comparisons: dict[str, float | int | str | bool | None] = {
        "best_batch_size": best_batch_size,
        "best_characters_per_second": median_rates[best_batch_size],
        "warm_cache_speedup": (
            warm_model.timings.translation_seconds / warm_cache.timings.translation_seconds
            if warm_cache.timings.translation_seconds > 0
            else None
        ),
        "outputs_identical_within_device": len(hashes) == 1,
        "model_load_count": 1,
        "process_wall_seconds": time.perf_counter() - started_wall,
    }
    cpu_memory_complete = all(
        item.cpu_memory.rss_before_model is not None
        and item.cpu_memory.rss_after_model_load is not None
        and item.cpu_memory.rss_peak is not None
        and item.cpu_memory.rss_after_run is not None
        for item in scenarios
    )
    cuda_memory_complete = measured.device != "cuda" or all(
        item.cuda_memory is not None
        and item.cuda_memory.peak_allocated is not None
        and item.cuda_memory.peak_reserved is not None
        for item in scenarios
    )
    warnings = []
    if not cpu_memory_complete:
        warnings.append("One or more required process RSS measurements are unavailable.")
    if not cuda_memory_complete:
        warnings.append("One or more required CUDA memory measurements are unavailable.")
    return BenchmarkReport(
        complete=(
            all(item.integrity.passed for item in scenarios)
            and cpu_memory_complete
            and cuda_memory_complete
        ),
        mode=config.mode,
        metadata=_metadata(measured, config),
        dataset=DatasetMetadata(
            version=DATASET_VERSION,
            sha256=dataset.sha256,
            paragraphs=len(dataset.document.paragraphs),
            characters=sum(len(item.text) for item in dataset.document.paragraphs),
            length_classes=dataset.length_classes,
            glossary_fingerprint=(dataset.glossary.fingerprint if dataset.glossary else None),
            document_schema_version=dataset.document.schema_version,
        ),
        scenarios=tuple(scenarios),
        timing_distributions=timing_distributions,
        comparisons=comparisons,
        warnings=tuple(warnings),
        limitations=(
            "Wall-clock results are workstation-specific and include Python/runtime "
            "scheduling noise.",
            "RSS is process resident set/working set sampled at 10 ms; short peaks may be missed.",
            "Synthetic mode validates accounting only and is not an NLLB performance claim.",
        ),
    )


def _run_documents(
    dataset: PerformanceDataset,
    translator: MeasuredTranslator,
    config: BenchmarkConfig,
    *,
    cache_path: Path,
    name: str,
    batch_size: int,
    iteration: int,
    warmup: bool,
    cache_state: Literal["empty", "fresh", "warm"],
    model_state: Literal["cold", "warm"],
    documents: int,
    expected_segments: int | None = None,
    model_load_seconds: float | None = None,
    rss_before_model: int | None,
    rss_after_model_load: int | None,
) -> BenchmarkScenario:
    calls_before = len(translator.call_durations)
    segments_before = sum(translator.segment_counts)
    torch_runtime = _torch_runtime() if translator.device == "cuda" else None
    cuda_before = _cuda_before(torch_runtime)
    rss_before_run = current_rss_bytes()
    started = time.perf_counter()
    results = []
    with RssSampler() as rss_sampler, TranslationCache(cache_path) as cache:
        for _document_index in range(documents):
            results.append(
                translate_document(
                    dataset.document,
                    translator=translator,
                    cache=cache,
                    options=TranslationOptions(
                        batch_size=batch_size,
                        max_input_tokens=config.max_input_tokens,
                        glossary=dataset.glossary,
                    ),
                )
            )
    if torch_runtime is not None:
        torch_runtime.cuda.synchronize()
    translation_seconds = time.perf_counter() - started
    calls = len(translator.call_durations) - calls_before
    model_segments = sum(translator.segment_counts) - segments_before
    stats = [result.translation.statistics for result in results if result.translation is not None]
    cache_hits = sum(item.cache_hits for item in stats)
    cache_misses = sum(item.cache_misses for item in stats)
    translated_segments = sum(item.translated_segments for item in stats)
    segments = expected_segments if expected_segments is not None else translated_segments
    paragraphs = len(dataset.document.paragraphs) * documents
    characters = sum(len(item.text) for item in dataset.document.paragraphs) * documents
    source_tokens = (
        sum(translator.count_tokens(item.text) for item in dataset.document.paragraphs) * documents
    )
    output_text = [
        paragraph.translated_text or "" for result in results for paragraph in result.paragraphs
    ]
    output_hash = hashlib.sha256("\n".join(output_text).encode("utf-8")).hexdigest()
    placeholder_leaks = sum("__PDFTR_" in text for text in output_text)
    protected_violations = sum(
        token in paragraph.text and token not in (paragraph.translated_text or "")
        for result in results
        for paragraph in result.paragraphs
        for token in dataset.protected_tokens
    )
    glossary_violations = sum(
        result.translation.glossary.statistics.violations
        for result in results
        if result.translation is not None and result.translation.glossary is not None
    )
    integrity = IntegrityEvidence(
        passed=(
            len(output_text) == paragraphs
            and placeholder_leaks == 0
            and protected_violations == 0
            and glossary_violations == 0
        ),
        output_count=len(output_text),
        output_hash=output_hash,
        placeholder_leaks=placeholder_leaks,
        protected_token_violations=protected_violations,
        glossary_violations=glossary_violations,
    )
    first_inference = translator.call_durations[calls_before] if calls else None
    cache_only = translation_seconds if calls == 0 else None
    return BenchmarkScenario(
        name=name,
        device_request=config.device,
        effective_device=translator.device,
        batch_size=batch_size,
        iteration=iteration,
        warmup=warmup,
        cache_state=cache_state,
        model_state=model_state,
        documents=documents,
        paragraphs=paragraphs,
        segments=segments,
        characters=characters,
        source_tokens=source_tokens,
        translator_calls=calls,
        model_facing_segments=model_segments,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        model_load_count=1 if model_state == "cold" else 0,
        paragraphs_per_second=throughput(paragraphs, translation_seconds),
        segments_per_second=throughput(segments, translation_seconds),
        characters_per_second=throughput(characters, translation_seconds),
        timings=RunTimings(
            process_wall_seconds=translation_seconds + (model_load_seconds or 0),
            runtime_open_seconds=model_load_seconds,
            model_load_seconds=model_load_seconds,
            first_inference_seconds=first_inference,
            translation_seconds=translation_seconds,
            cache_only_seconds=cache_only,
            total_seconds=translation_seconds + (model_load_seconds or 0),
        ),
        cpu_memory=CpuMemory(
            rss_before_model=rss_before_model,
            rss_after_model_load=rss_after_model_load,
            rss_peak=rss_sampler.peak,
            rss_after_run=current_rss_bytes() or rss_before_run,
        ),
        cuda_memory=_cuda_after(torch_runtime, cuda_before),
        integrity=integrity,
    )


def _torch_runtime() -> Any:
    return importlib.import_module("torch")


def _cuda_before(torch_runtime: Any) -> tuple[int, int] | None:
    if torch_runtime is None:
        return None
    torch_runtime.cuda.synchronize()
    torch_runtime.cuda.reset_peak_memory_stats()
    return (
        int(torch_runtime.cuda.memory_allocated()),
        int(torch_runtime.cuda.memory_reserved()),
    )


def _cuda_after(torch_runtime: Any, before: tuple[int, int] | None) -> CudaMemory | None:
    if torch_runtime is None or before is None:
        return None
    return CudaMemory(
        allocated_before=before[0],
        reserved_before=before[1],
        allocated_after=int(torch_runtime.cuda.memory_allocated()),
        reserved_after=int(torch_runtime.cuda.memory_reserved()),
        peak_allocated=int(torch_runtime.cuda.max_memory_allocated()),
        peak_reserved=int(torch_runtime.cuda.max_memory_reserved()),
    )


def _metadata(translator: MeasuredTranslator, config: BenchmarkConfig) -> BenchmarkMetadata:
    torch_runtime: Any | None = None
    with suppress(ImportError):
        torch_runtime = _torch_runtime()
    cuda_available = bool(torch_runtime is not None and torch_runtime.cuda.is_available())
    cuda_device_name: str | None = None
    cuda_capability: tuple[int, int] | None = None
    cuda_total_memory: int | None = None
    if cuda_available and torch_runtime is not None:
        cuda_device_name = str(torch_runtime.cuda.get_device_name(0))
        cuda_capability = tuple(torch_runtime.cuda.get_device_capability(0))
        cuda_total_memory = int(torch_runtime.cuda.get_device_properties(0).total_memory)
    return BenchmarkMetadata(
        timestamp_utc=datetime.now(UTC),
        os=platform.platform(),
        python=sys.version.split()[0],
        application_version=__version__,
        git_commit=_git_commit(),
        backend=translator.backend_name,
        model=translator.model_name,
        device_request=config.device,
        max_input_tokens=config.max_input_tokens,
        translation_behavior_revision=TRANSLATION_BEHAVIOR_REVISION,
        pipeline_behavior_revision=PIPELINE_BEHAVIOR_REVISION,
        offline=config.offline,
        torch_version=(str(torch_runtime.__version__) if torch_runtime is not None else None),
        torch_cuda_runtime=(str(torch_runtime.version.cuda) if torch_runtime is not None else None),
        cuda_available=cuda_available,
        cuda_device_name=cuda_device_name,
        cuda_capability=cuda_capability,
        cuda_total_memory=cuda_total_memory,
        cpu_model=platform.processor() or None,
        logical_cpu_count=os.cpu_count(),
        system_ram=_system_ram_bytes(),
    )


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _system_ram_bytes() -> int | None:
    if platform.system() != "Windows":
        try:
            sysconf = getattr(os, "sysconf", None)
            if not callable(sysconf):
                return None
            pages = int(sysconf("SC_PHYS_PAGES"))
            page_size = int(sysconf("SC_PAGE_SIZE"))
            return int(pages * page_size)
        except (OSError, ValueError):
            return None

    class _MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    windll = ctypes.__dict__["windll"]
    if windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return int(status.ullTotalPhys)
    return None
