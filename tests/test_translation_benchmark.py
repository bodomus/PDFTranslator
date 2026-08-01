from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from pdftranslate.benchmark import (
    BenchmarkDataset,
    BenchmarkOptions,
    compare_with_baseline,
    read_dataset,
    read_report,
    run_benchmark,
    write_report_json,
    write_report_markdown,
)
from pdftranslate.benchmark.checks import analyze_stage_trace
from pdftranslate.benchmark.models import (
    BenchmarkFinding,
    BenchmarkSample,
    HumanReview,
    StageTrace,
)
from pdftranslate.cli import app
from pdftranslate.translation.errors import TranslationBackendError


class FakeTranslator:
    backend_name = "fake"
    model_name = "fake-model"
    device = "cpu"

    def __init__(self, **_kwargs: object) -> None:
        self.batches: list[list[str]] = []

    def count_tokens(self, text: str) -> int:
        return len(text.split()) + 2

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        self.batches.append(list(texts))
        return [f"Перевод: {text}" for text in texts]


class TokenDroppingTranslator(FakeTranslator):
    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        return [text.replace("__PDFTR_0000__", "") for text in texts]


class MissingSegmentTranslator(FakeTranslator):
    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        return []


class FilenameDamagingTranslator(FakeTranslator):
    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        self.batches.append(list(texts))
        return [text.replace("data.json", "данные.json") for text in texts]


class FailingTranslator(FakeTranslator):
    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        self.batches.append(list(texts))
        raise TranslationBackendError("model unavailable")


def _sample(index: int, *, source: str | None = None) -> BenchmarkSample:
    text = source or f"Synthetic sentence number {index}."
    return BenchmarkSample(
        id=f"sample-{index:02d}",
        category="synthetic",
        source=text,
        reference=f"Синтетическое предложение номер {index}.",
        provenance="synthetic:test",
    )


def _dataset(*, repeated: bool = False) -> BenchmarkDataset:
    return BenchmarkDataset(
        dataset_version="1.0.0",
        title="Test dataset",
        license="CC0-1.0",
        samples=tuple(
            _sample(index, source="Repeated source sentence." if repeated else None)
            for index in range(50)
        ),
    )


def test_repository_dataset_is_versioned_safe_and_contains_pdftr8_inputs() -> None:
    dataset = read_dataset(Path("benchmarks/translation-en-ru-v1.json"))

    assert dataset.dataset_version == "1.0.0"
    assert len(dataset.samples) == 61
    by_id = {sample.id: sample for sample in dataset.samples}
    assert by_id["pdftr8-token-1900-1"].protected_tokens == ("1900-1",)
    assert "F\ufffe" in (by_id["pdftr8-page7-numbers-junk"].stage_trace.observed_translation or "")


def test_dataset_rejects_duplicate_ids_and_invalid_human_scores() -> None:
    samples = list(_dataset().samples)
    samples[-1] = samples[0].model_copy()
    with pytest.raises(ValidationError, match="must be unique"):
        BenchmarkDataset(
            dataset_version="1.0.0",
            title="Duplicate",
            license="CC0-1.0",
            samples=tuple(samples),
        )
    with pytest.raises(ValidationError):
        HumanReview(
            reviewer="reviewer",
            adequacy=0,
            fluency=3,
            terminology=3,
            token_preservation=3,
            segmentation=3,
            overall_acceptability=3,
        )


def test_runner_reuses_one_translator_and_reports_exact_cache_hits(tmp_path: Path) -> None:
    translator = FakeTranslator()
    report = run_benchmark(
        _dataset(repeated=True),
        translator=translator,
        options=BenchmarkOptions(commit="abc123"),
        repository_root=tmp_path,
    )

    assert report.metadata.commit == "abc123"
    assert report.metadata.sample_count == 50
    assert report.metadata.cache_hits == 49
    assert report.metadata.cache_misses == 1
    assert len(translator.batches) == 1
    assert all(result.status == "passed" for result in report.results)


def test_cache_hit_reanalyzes_sample_specific_protected_tokens() -> None:
    samples = list(_dataset().samples)
    shared_source = "Run data.json now."
    samples[0] = _sample(0, source=shared_source)
    samples[1] = BenchmarkSample(
        id="sample-01",
        category="synthetic",
        source=shared_source,
        reference="Запустите data.json сейчас.",
        protected_tokens=("data.json",),
        provenance="synthetic:test",
    )
    translator = FilenameDamagingTranslator()

    report = run_benchmark(
        _dataset().model_copy(update={"samples": tuple(samples)}),
        translator=translator,
    )

    first, second = report.results[:2]
    assert report.metadata.cache_hits == 1
    assert report.metadata.cache_misses == 49
    assert first.status == "passed"
    assert first.findings == ()
    assert second.cache_hit is True
    assert second.status == "failed"
    assert any(finding.code == "protected-token-damaged" for finding in second.findings)


def test_cache_hit_reanalyzes_sample_specific_human_review() -> None:
    samples = list(_dataset().samples)
    shared_source = "Review this sentence."
    samples[0] = _sample(0, source=shared_source)
    samples[1] = BenchmarkSample(
        id="sample-01",
        category="synthetic",
        source=shared_source,
        reference="Проверьте это предложение.",
        provenance="synthetic:test",
        human_review=HumanReview(
            reviewer="reviewer",
            adequacy=1,
            fluency=5,
            terminology=5,
            token_preservation=5,
            segmentation=5,
            overall_acceptability=2,
        ),
    )
    translator = FakeTranslator()

    report = run_benchmark(
        _dataset().model_copy(update={"samples": tuple(samples)}),
        translator=translator,
    )

    first, second = report.results[:2]
    assert report.metadata.cache_hits == 1
    assert report.metadata.cache_misses == 49
    assert first.status == "passed"
    assert second.cache_hit is True
    assert second.status == "failed"
    assert {finding.code for finding in second.findings} >= {
        "human-adequacy",
        "human-overall-acceptability",
    }


def test_cache_hit_applies_human_review_after_reused_runtime_error() -> None:
    samples = list(_dataset().samples)
    shared_source = "Review this failed translation."
    samples[0] = _sample(0, source=shared_source)
    samples[1] = BenchmarkSample(
        id="sample-01",
        category="synthetic",
        source=shared_source,
        reference="Проверьте этот неудачный перевод.",
        provenance="synthetic:test",
        human_review=HumanReview(
            reviewer="reviewer",
            adequacy=1,
            fluency=5,
            terminology=5,
            token_preservation=5,
            segmentation=5,
            overall_acceptability=2,
        ),
    )

    report = run_benchmark(
        _dataset().model_copy(update={"samples": tuple(samples)}),
        translator=FailingTranslator(),
    )

    first, second = report.results[:2]
    assert first.status == "error"
    assert {finding.code for finding in first.findings} == {"benchmark-execution-error"}
    assert second.cache_hit is True
    assert second.status == "error"
    assert {finding.code for finding in second.findings} >= {
        "benchmark-execution-error",
        "human-adequacy",
        "human-overall-acceptability",
    }


def test_cache_hit_keeps_historical_stage_trace_sample_specific() -> None:
    samples = list(_dataset().samples)
    shared_source = "Value 1900-1 remains clean."
    samples[0] = BenchmarkSample(
        id="sample-00",
        category="synthetic",
        source=shared_source,
        reference="Значение 1900-1 не повреждено.",
        protected_tokens=("1900-1",),
        provenance="synthetic:test",
        stage_trace=StageTrace(observed_translation="Значение 1900 1 повреждено."),
    )
    samples[1] = BenchmarkSample(
        id="sample-01",
        category="synthetic",
        source=shared_source,
        reference="Значение 1900-1 не повреждено.",
        protected_tokens=("1900-1",),
        provenance="synthetic:test",
    )
    translator = FakeTranslator()

    report = run_benchmark(
        _dataset().model_copy(update={"samples": tuple(samples)}),
        translator=translator,
    )

    first, second = report.results[:2]
    assert report.metadata.cache_hits == 1
    assert report.metadata.cache_misses == 49
    assert any(finding.origin == "historical_trace" for finding in first.findings)
    assert second.cache_hit is True
    assert all(finding.origin != "historical_trace" for finding in second.findings)


def test_stage_trace_separates_extraction_segmentation_tokens_model_and_rendering() -> None:
    sample = BenchmarkSample(
        id="trace",
        category="regression",
        source="Value 1900-1 is clean.",
        reference="Значение 1900-1 не повреждено.",
        protected_tokens=("1900-1",),
        provenance="synthetic:test",
        stage_trace=StageTrace(
            extracted_text="Value 1900-1 is clean. extra",
            source_segments=("Value 1900-1 is clean.", "extra"),
            translated_segments=("Значение 1900 1 повреждено F\ufffe.",),
            observed_translation="Значение 1900 1 повреждено F\ufffe.",
            rendered_text="Значение повреждено.",
        ),
    )

    findings = analyze_stage_trace(sample)
    stages = {finding.stage for finding in findings}
    codes = {finding.code for finding in findings}
    assert {"extraction", "segmentation", "protected_token", "model", "rendering"} <= stages
    assert "suspicious-character" in codes
    assert "protected-token-damaged" in codes
    assert {finding.origin for finding in findings} == {"historical_trace"}


def test_historical_trace_does_not_fail_a_clean_current_run() -> None:
    samples = list(_dataset().samples)
    samples[0] = BenchmarkSample(
        id="historical",
        category="regression",
        source="Value 1900-1 remains clean.",
        reference="Значение 1900-1 не повреждено.",
        protected_tokens=("1900-1",),
        provenance="synthetic:test",
        stage_trace=StageTrace(observed_translation="Значение 1900 1 повреждено."),
    )
    dataset = _dataset().model_copy(update={"samples": tuple(samples)})

    report = run_benchmark(dataset, translator=FakeTranslator())

    assert report.results[0].status == "passed"
    assert report.results[0].findings[0].origin == "historical_trace"


def test_runner_reports_protected_token_restoration_failure() -> None:
    samples = list(_dataset().samples)
    samples[0] = BenchmarkSample(
        id="protected",
        category="regression",
        source="Archive entry 1900-1 must remain.",
        reference="Запись архива 1900-1 должна сохраниться.",
        protected_tokens=("1900-1",),
        provenance="synthetic:test",
    )
    dataset = _dataset().model_copy(update={"samples": tuple(samples)})

    report = run_benchmark(dataset, translator=TokenDroppingTranslator())

    result = report.results[0]
    assert result.status == "failed"
    assert any(finding.stage == "protected_token" for finding in result.findings)


def test_runner_reports_segment_count_mismatch_without_aborting_dataset() -> None:
    report = run_benchmark(_dataset(), translator=MissingSegmentTranslator())

    assert report.metadata.sample_count == 50
    assert report.metadata.failed_samples == 50
    assert all(
        any(finding.code == "segment-count-mismatch" for finding in result.findings)
        for result in report.results
    )


def test_json_markdown_and_baseline_comparison_are_reproducible(tmp_path: Path) -> None:
    baseline = run_benchmark(_dataset(), translator=FakeTranslator())
    changed_result = baseline.results[0].model_copy(
        update={
            "status": "failed",
            "findings": (
                BenchmarkFinding(
                    code="number-damaged",
                    stage="model",
                    severity="error",
                    message="number lost",
                ),
            ),
        }
    )
    current = baseline.model_copy(update={"results": (changed_result, *baseline.results[1:])})
    comparison = compare_with_baseline(current, baseline)
    current = current.model_copy(update={"comparison": comparison})
    json_path = write_report_json(current, tmp_path / "result.json")
    markdown_path = write_report_markdown(current, tmp_path / "result.md")

    assert read_report(json_path) == current
    assert "sample-00" in comparison.regressed_samples
    assert "sample-00:current_run:model:number-damaged" in comparison.new_findings
    assert "Baseline comparison" in markdown_path.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_report_json(current, json_path)


def test_malformed_dataset_has_actionable_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text('{"schema_version":"1.0"}', encoding="utf-8")

    with pytest.raises(ValueError, match="invalid benchmark file"):
        read_dataset(path)


def test_cli_benchmark_uses_fake_backend_and_writes_both_reports(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(_dataset().model_dump_json(indent=2), encoding="utf-8")
    output = tmp_path / "results.json"
    runner = CliRunner()

    with patch("pdftranslate.cli.NllbTranslator", side_effect=FakeTranslator) as loader:
        result = runner.invoke(
            app,
            [
                "benchmark-translation",
                str(dataset_path),
                "--output",
                str(output),
                "--cache-dir",
                str(tmp_path / "cache"),
                "--offline",
            ],
        )

    assert result.exit_code == 0, result.output
    assert output.is_file()
    assert output.with_suffix(".md").is_file()
    assert "Benchmarked 50 sample(s)" in result.output
    assert loader.call_args.kwargs["offline"] is True
