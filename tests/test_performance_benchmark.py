from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from pdftranslate.glossary import load_glossary
from pdftranslate.performance import (
    BenchmarkConfig,
    aggregate_timings,
    build_performance_dataset,
    bytes_to_human,
    run_performance_benchmark,
    throughput,
    write_performance_reports,
)
from pdftranslate.performance.models import BenchmarkReport, CudaMemory
from pdftranslate.performance.runner import (
    DeterministicTranslator,
    _cuda_after,
    _cuda_before,
)
from pdftranslate.performance.sampler import RssSampler, current_rss_bytes


def _output(name: str) -> Path:
    return Path("temp") / f"pytest-pdftr14-{name}-{uuid4().hex}"


def test_metrics_are_zero_safe_and_deterministic() -> None:
    assert throughput(10, 2) == 5
    assert throughput(10, 0) == 0
    assert throughput(0, 2) == 0
    distribution = aggregate_timings([3.0, 1.0, 2.0])
    assert distribution.model_dump() == {
        "count": 3,
        "minimum": 1.0,
        "median": 2.0,
        "percentile_95": 3.0,
        "maximum": 3.0,
    }
    assert aggregate_timings([]).median is None
    assert bytes_to_human(None) == "n/a"
    assert bytes_to_human(1024) == "1.00 KiB"


def test_synthetic_scenarios_use_production_path_cache_and_batch_reuse() -> None:
    dataset = build_performance_dataset(load_glossary(Path("docs/glossary.example.json")))
    output = _output("scenarios")
    report = run_performance_benchmark(
        dataset,
        config=BenchmarkConfig(
            mode="synthetic",
            device="cpu",
            batch_sizes=(1, 4, 8),
            iterations=1,
            warmup=1,
            max_input_tokens=16,
        ),
        translator_factory=lambda: DeterministicTranslator("cpu"),
        output_root=output,
    )

    assert report.complete is True
    assert report.dataset.paragraphs == 120
    assert report.dataset.length_classes["forced_segmentation"] == 10
    assert report.comparisons["model_load_count"] == 1
    assert report.comparisons["best_batch_size"] in {1, 4, 8}
    assert report.timing_distributions["batch_size_1_total_seconds"].count == 1
    cold = next(item for item in report.scenarios if item.name == "cold-cpu")
    warm_cache = next(item for item in report.scenarios if item.name == "warm-cache-cpu")
    batch = next(item for item in report.scenarios if item.name == "batch-reuse-cpu")
    assert cold.cache_misses > 0
    assert cold.model_facing_segments > cold.cache_misses
    assert warm_cache.cache_hits > 0
    assert warm_cache.cache_misses == 0
    assert warm_cache.translator_calls == 0
    assert warm_cache.model_facing_segments == 0
    assert batch.documents == 3
    assert batch.model_load_count == 0
    assert batch.cache_hits > cold.cache_hits
    assert {item.batch_size for item in report.scenarios if item.name.startswith("matrix-")} == {
        1,
        4,
        8,
    }
    length_scenarios = {
        item.name: item for item in report.scenarios if item.name.startswith("length-")
    }
    assert set(length_scenarios) == {
        "length-short-cpu",
        "length-medium-cpu",
        "length-long-cpu",
        "length-forced_segmentation-cpu",
    }
    assert length_scenarios["length-forced_segmentation-cpu"].segments > 10
    assert all(item.integrity.passed for item in report.scenarios)
    assert all(item.integrity.placeholder_leaks == 0 for item in report.scenarios)
    assert all(item.integrity.protected_token_violations == 0 for item in report.scenarios)
    assert all(item.integrity.glossary_violations == 0 for item in report.scenarios)


def test_reports_are_versioned_and_mark_incomplete_runs() -> None:
    dataset = build_performance_dataset()
    output = _output("reports")
    report = run_performance_benchmark(
        dataset,
        config=BenchmarkConfig(
            mode="synthetic",
            device="cpu",
            batch_sizes=(1,),
            iterations=1,
            warmup=0,
            max_input_tokens=32,
        ),
        translator_factory=lambda: DeterministicTranslator("cpu"),
        output_root=output,
    )
    incomplete = report.model_copy(update={"complete": False})
    json_path, markdown_path = write_performance_reports(incomplete, output)

    assert '"schema_version": "1.0"' in json_path.read_text(encoding="utf-8")
    validated = BenchmarkReport.model_validate_json(json_path.read_text(encoding="utf-8"))
    assert validated.complete is False
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "**incomplete**" in markdown
    assert "warm-cache-cpu" in markdown
    assert "Peak VRAM" in markdown
    assert "Timing distributions" in markdown
    assert str(Path.home()) not in json_path.read_text(encoding="utf-8")


def test_benchmark_caches_stay_inside_selected_temp_output() -> None:
    output = _output("cache-isolation")
    report = run_performance_benchmark(
        build_performance_dataset(),
        config=BenchmarkConfig(
            mode="synthetic",
            device="cpu",
            batch_sizes=(1,),
            iterations=1,
            warmup=0,
        ),
        translator_factory=lambda: DeterministicTranslator("cpu"),
        output_root=output,
    )

    assert report.complete
    caches = tuple(output.resolve().glob("*.sqlite3"))
    assert caches
    assert all(output.resolve() in cache.parents for cache in caches)

    with pytest.raises(FileExistsError, match="run-specific path"):
        run_performance_benchmark(
            build_performance_dataset(),
            config=BenchmarkConfig(
                mode="synthetic",
                device="cpu",
                batch_sizes=(1,),
                iterations=1,
                warmup=0,
            ),
            translator_factory=lambda: DeterministicTranslator("cpu"),
            output_root=output,
        )


def test_placeholder_leak_marks_run_incomplete() -> None:
    class LeakingTranslator(DeterministicTranslator):
        def translate_batch(self, texts: Sequence[str]) -> list[str]:
            return [f"{text} __PDFTR_LEAK__" for text in texts]

    report = run_performance_benchmark(
        build_performance_dataset(),
        config=BenchmarkConfig(
            mode="synthetic",
            device="cpu",
            batch_sizes=(1,),
            iterations=1,
            warmup=0,
        ),
        translator_factory=lambda: LeakingTranslator("cpu"),
        output_root=_output("placeholder-leak"),
    )

    assert report.complete is False
    assert any(item.integrity.placeholder_leaks > 0 for item in report.scenarios)


def test_explicit_cuda_may_not_resolve_to_cpu() -> None:
    dataset = build_performance_dataset()
    with pytest.raises(RuntimeError, match="resolved to CPU"):
        run_performance_benchmark(
            dataset,
            config=BenchmarkConfig(
                mode="synthetic",
                device="cuda",
                batch_sizes=(1,),
                iterations=1,
                warmup=0,
            ),
            translator_factory=lambda: DeterministicTranslator("cpu"),
            output_root=_output("cuda-fallback"),
        )


def test_missing_cuda_metrics_are_explicitly_optional() -> None:
    assert CudaMemory().peak_allocated is None


def test_cuda_sampler_resets_synchronizes_and_records_all_counters() -> None:
    calls: list[str] = []
    cuda = SimpleNamespace(
        synchronize=lambda: calls.append("synchronize"),
        reset_peak_memory_stats=lambda: calls.append("reset"),
        memory_allocated=lambda: 10,
        memory_reserved=lambda: 20,
        max_memory_allocated=lambda: 30,
        max_memory_reserved=lambda: 40,
    )
    runtime = SimpleNamespace(cuda=cuda)

    before = _cuda_before(runtime)
    after = _cuda_after(runtime, before)

    assert calls == ["synchronize", "reset"]
    assert before == (10, 20)
    assert after == CudaMemory(
        allocated_before=10,
        reserved_before=20,
        allocated_after=10,
        reserved_after=20,
        peak_allocated=30,
        peak_reserved=40,
    )


def test_rss_sampler_returns_positive_process_memory() -> None:
    with RssSampler() as sampler:
        assert current_rss_bytes()
    assert sampler.peak is not None
    assert sampler.peak > 0
