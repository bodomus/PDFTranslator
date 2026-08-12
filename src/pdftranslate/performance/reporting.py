"""Atomic JSON and human-readable performance reports."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from pdftranslate.performance.metrics import bytes_to_human
from pdftranslate.performance.models import BenchmarkReport


def write_performance_reports(report: BenchmarkReport, output: Path) -> tuple[Path, Path]:
    root = output.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "performance.json"
    markdown_path = root / "performance.md"
    _atomic_write(json_path, report.model_dump_json(indent=2) + "\n")
    _atomic_write(markdown_path, _markdown(report))
    return json_path, markdown_path


def _markdown(report: BenchmarkReport) -> str:
    lines = [
        "# PDFTR-14 Performance Benchmark",
        "",
        f"- Status: **{'complete' if report.complete else 'incomplete'}**",
        f"- Mode: `{report.mode}`",
        f"- Commit: `{report.metadata.git_commit}`",
        f"- Backend/model: `{report.metadata.backend}` / `{report.metadata.model}`",
        f"- Device request / max input tokens: `{report.metadata.device_request}` / "
        f"`{report.metadata.max_input_tokens}`",
        f"- Torch/CUDA: `{report.metadata.torch_version}` / `{report.metadata.torch_cuda_runtime}`",
        f"- GPU: `{report.metadata.cuda_device_name or 'n/a'}`",
        f"- Dataset: `{report.dataset.version}` / `{report.dataset.sha256}`",
        f"- Behavior revisions: translation `{report.metadata.translation_behavior_revision}`, "
        f"pipeline `{report.metadata.pipeline_behavior_revision}`",
        f"- Paragraphs: {report.dataset.paragraphs}",
        "",
        "## Scenarios",
        "",
        "| Scenario | Device | Batch | Model | Cache | Paragraphs | Segments | Wall s | "
        "Translation s | Paragraphs/s | Characters/s | Peak RAM | Peak VRAM | Cache hit rate |",
        "| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | "
        "---: | ---: | ---: |",
    ]
    for item in report.scenarios:
        total_cache = item.cache_hits + item.cache_misses
        hit_rate = item.cache_hits / total_cache if total_cache else 0.0
        peak_vram = item.cuda_memory.peak_reserved if item.cuda_memory is not None else None
        lines.append(
            f"| {item.name}{' (warmup)' if item.warmup else ''} | {item.effective_device} | "
            f"{item.batch_size} | {item.model_state} | {item.cache_state} | {item.paragraphs} | "
            f"{item.segments} | {item.timings.process_wall_seconds:.4f} | "
            f"{item.timings.translation_seconds:.4f} | {item.paragraphs_per_second:.2f} | "
            f"{item.characters_per_second:.2f} | {bytes_to_human(item.cpu_memory.rss_peak)} | "
            f"{bytes_to_human(peak_vram)} | {hit_rate:.1%} |"
        )
    lines.extend(
        [
            "",
            "## Timing distributions",
            "",
            "| Measurement | Count | Min s | Median s | P95 s | Max s |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name, distribution in sorted(report.timing_distributions.items()):
        values = (
            distribution.minimum,
            distribution.median,
            distribution.percentile_95,
            distribution.maximum,
        )
        rendered = ["n/a" if value is None else f"{value:.4f}" for value in values]
        lines.append(
            f"| {name} | {distribution.count} | {rendered[0]} | {rendered[1]} | "
            f"{rendered[2]} | {rendered[3]} |"
        )
    lines.extend(["", "## Comparisons", ""])
    for key, value in sorted(report.comparisons.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {value}" for value in report.limitations)
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {value}" for value in report.warnings)
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, content: str) -> None:
    pending: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.stem}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            pending = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        pending.replace(path)
    finally:
        if pending is not None and pending.exists():
            pending.unlink()
