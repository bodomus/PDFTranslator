"""Translation-quality benchmark API."""

from pdftranslate.benchmark.models import BenchmarkDataset, BenchmarkReport
from pdftranslate.benchmark.reporting import (
    compare_with_baseline,
    read_dataset,
    read_report,
    write_report_json,
    write_report_markdown,
)
from pdftranslate.benchmark.runner import BenchmarkOptions, run_benchmark

__all__ = [
    "BenchmarkDataset",
    "BenchmarkOptions",
    "BenchmarkReport",
    "compare_with_baseline",
    "read_dataset",
    "read_report",
    "run_benchmark",
    "write_report_json",
    "write_report_markdown",
]
