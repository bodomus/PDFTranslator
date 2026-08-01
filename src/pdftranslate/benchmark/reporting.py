"""Atomic benchmark dataset/report I/O, Markdown, and baseline comparison."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import ValidationError

from pdftranslate.benchmark.models import (
    BaselineComparison,
    BenchmarkDataset,
    BenchmarkReport,
)


def read_dataset(path: Path) -> BenchmarkDataset:
    return _read_model(path, BenchmarkDataset)


def read_report(path: Path) -> BenchmarkReport:
    return _read_model(path, BenchmarkReport)


def write_report_json(report: BenchmarkReport, path: Path, *, overwrite: bool = False) -> Path:
    return _atomic_write(path, report.model_dump_json(indent=2) + "\n", overwrite=overwrite)


def write_report_markdown(report: BenchmarkReport, path: Path, *, overwrite: bool = False) -> Path:
    metadata = report.metadata
    lines = [
        "# Translation benchmark report",
        "",
        f"- Dataset: `{metadata.dataset_version}`",
        f"- Commit: `{metadata.commit}`",
        f"- Backend/model: `{metadata.backend}` / `{metadata.model}`",
        f"- Tokenizer: `{metadata.tokenizer}`",
        f"- Device: `{metadata.device}`",
        f"- Settings: batch {metadata.batch_size}, max input tokens {metadata.max_input_tokens}",
        f"- Elapsed: {metadata.elapsed_seconds:.3f} s",
        f"- Cache: {metadata.cache_hits} hit(s), {metadata.cache_misses} miss(es)",
        f"- Result: {metadata.passed_samples} passed, {metadata.failed_samples} failed, "
        f"{metadata.error_samples} error",
        "",
        "## Stage summary",
        "",
        "| Stage | Current findings | Historical findings | Current errors |",
        "| --- | ---: | ---: | ---: |",
    ]
    stages = (
        "extraction",
        "segmentation",
        "protected_token",
        "model",
        "terminology",
        "rendering",
    )
    all_findings = [finding for result in report.results for finding in result.findings]
    for stage in stages:
        selected = [finding for finding in all_findings if finding.stage == stage]
        current = [finding for finding in selected if finding.origin == "current_run"]
        historical = [finding for finding in selected if finding.origin == "historical_trace"]
        lines.append(
            f"| {stage} | {len(current)} | {len(historical)} | "
            f"{sum(finding.severity == 'error' for finding in current)} |"
        )
    lines.extend(
        [
            "",
            "## Samples",
            "",
            "| Sample | Category | Status | Findings | Human review |",
            "| --- | --- | --- | ---: | --- |",
        ]
    )
    for result in report.results:
        review = (
            f"{result.human_review.overall_acceptability}/5"
            if result.human_review is not None
            else "not reviewed"
        )
        lines.append(
            f"| `{result.sample_id}` | {result.category} | {result.status} | "
            f"{len(result.findings)} | {review} |"
        )
        for finding in result.findings:
            evidence = ", ".join(f"`{value}`" for value in finding.evidence)
            suffix = f" Evidence: {evidence}." if evidence else ""
            lines.append(
                f"  - **{finding.origin}/{finding.stage}/{finding.code} "
                f"({finding.severity})**: "
                f"{finding.message}{suffix}"
            )
    if report.comparison is not None:
        comparison = report.comparison
        lines.extend(
            [
                "",
                "## Baseline comparison",
                "",
                f"- Baseline dataset: `{comparison.baseline_dataset_version}`",
                f"- Regressed samples: {', '.join(comparison.regressed_samples) or 'none'}",
                f"- Improved samples: {', '.join(comparison.improved_samples) or 'none'}",
                f"- New findings: {', '.join(comparison.new_findings) or 'none'}",
                f"- Resolved findings: {', '.join(comparison.resolved_findings) or 'none'}",
            ]
        )
    lines.extend(
        [
            "",
            "## Human-review scale",
            "",
            "1 = unacceptable, 2 = major problems, 3 = usable with edits, "
            "4 = good, 5 = excellent. Automated checks do not replace adequacy or fluency review.",
        ]
    )
    return _atomic_write(path, "\n".join(lines) + "\n", overwrite=overwrite)


def compare_with_baseline(
    current: BenchmarkReport, baseline: BenchmarkReport
) -> BaselineComparison:
    current_by_id = {result.sample_id: result for result in current.results}
    baseline_by_id = {result.sample_id: result for result in baseline.results}
    shared = sorted(set(current_by_id) & set(baseline_by_id))
    regressed = tuple(
        sample_id
        for sample_id in shared
        if baseline_by_id[sample_id].status == "passed"
        and current_by_id[sample_id].status != "passed"
    )
    improved = tuple(
        sample_id
        for sample_id in shared
        if baseline_by_id[sample_id].status != "passed"
        and current_by_id[sample_id].status == "passed"
    )
    current_findings = _finding_keys(current)
    baseline_findings = _finding_keys(baseline)
    return BaselineComparison(
        baseline_dataset_version=baseline.metadata.dataset_version,
        regressed_samples=regressed,
        improved_samples=improved,
        new_findings=tuple(sorted(current_findings - baseline_findings)),
        resolved_findings=tuple(sorted(baseline_findings - current_findings)),
    )


def _finding_keys(report: BenchmarkReport) -> set[str]:
    return {
        f"{result.sample_id}:{finding.origin}:{finding.stage}:{finding.code}"
        for result in report.results
        for finding in result.findings
    }


def _read_model[ModelT: (BenchmarkDataset, BenchmarkReport)](
    path: Path, model_type: type[ModelT]
) -> ModelT:
    source = path.expanduser().resolve()
    try:
        payload = source.read_text(encoding="utf-8")
        return model_type.model_validate_json(payload)
    except (OSError, UnicodeError, ValidationError) as error:
        raise ValueError(f"invalid benchmark file {source}: {error}") from error


def _atomic_write(path: Path, content: str, *, overwrite: bool) -> Path:
    destination = path.expanduser().resolve()
    if destination.exists() and not overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{destination.stem}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            pending = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        pending.replace(destination)
    finally:
        if pending is not None and pending.exists():
            pending.unlink()
    return destination
