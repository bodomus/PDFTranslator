"""Production-path performance benchmark primitives."""

from pdftranslate.performance.dataset import PerformanceDataset, build_performance_dataset
from pdftranslate.performance.metrics import aggregate_timings, bytes_to_human, throughput
from pdftranslate.performance.models import (
    BenchmarkReport,
    BenchmarkScenario,
    IntegrityEvidence,
    RunTimings,
)
from pdftranslate.performance.reporting import write_performance_reports
from pdftranslate.performance.runner import BenchmarkConfig, run_performance_benchmark

__all__ = [
    "BenchmarkConfig",
    "BenchmarkReport",
    "BenchmarkScenario",
    "IntegrityEvidence",
    "PerformanceDataset",
    "RunTimings",
    "aggregate_timings",
    "build_performance_dataset",
    "bytes_to_human",
    "run_performance_benchmark",
    "throughput",
    "write_performance_reports",
]
