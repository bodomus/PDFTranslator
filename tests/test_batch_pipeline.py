from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from pdftranslate.batch import BatchOptions, run_batch
from pdftranslate.pdf import PdfAnalyzer, PdfExtractor
from pdftranslate.pipeline import ExitCode, PipelineServices, open_translation_runtime
from pdftranslate.rendering import OutputPdfError, PdfRenderer, validate_output_pdf
from tests.conftest import PdfFactory


class FakeTranslator:
    backend_name = "nllb"
    model_name = "fake-nllb"
    device = "cpu"

    def __init__(self) -> None:
        self.calls = 0

    def count_tokens(self, text: str) -> int:
        return len(text.split()) + 2

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        self.calls += 1
        return [f"Русский перевод: {text}" for text in texts]


class SelectiveFailingRenderer(PdfRenderer):
    def render(self, source_pdf: Path, *args: object, **kwargs: object) -> object:
        if source_pdf.name.casefold().startswith("bad"):
            raise OutputPdfError("simulated per-file rendering failure")
        return super().render(source_pdf, *args, **kwargs)  # type: ignore[arg-type]


def _services(
    translator: FakeTranslator,
    factory_calls: list[Path],
    *,
    renderer: PdfRenderer | None = None,
) -> PipelineServices:
    def factory(_options: object, model_cache: Path) -> FakeTranslator:
        factory_calls.append(model_cache)
        return translator

    return PipelineServices(
        analyzer=PdfAnalyzer(),
        extractor=PdfExtractor(),
        renderer=renderer or PdfRenderer(),
        translator_factory=factory,  # type: ignore[arg-type]
        validator=validate_output_pdf,
    )


def _options(
    root: Path,
    output: Path,
    cache: Path,
    font: Path,
    **changes: object,
) -> BatchOptions:
    values: dict[str, object] = {
        "input_dir": root,
        "output_dir": output,
        "recursive": True,
        "cache_dir": cache,
        "font_path": font,
        "model": "fake-nllb",
    }
    values.update(changes)
    return BatchOptions(**values)  # type: ignore[arg-type]


def test_batch_reuses_model_cache_and_preserves_structure(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    root = tmp_path / "Книги с пробелами"
    first = pdf_factory(root / "one" / "manual.pdf")
    second = pdf_factory(root / "two" / "manual.PDF")
    output = tmp_path / "Результаты"
    translator = FakeTranslator()
    factory_calls: list[Path] = []

    result = run_batch(
        _options(root, output, tmp_path / "cache", cyrillic_font_path),
        services=_services(translator, factory_calls),
    )

    assert result.exit_code == ExitCode.SUCCESS
    assert len(factory_calls) == 1
    assert translator.calls == 1
    assert (output / "one" / "manual.ru.pdf").is_file()
    assert (output / "two" / "manual.ru.pdf").is_file()
    assert {item.input_path for item in result.report.successful_files} == {
        str(first.resolve()),
        str(second.resolve()),
    }
    assert result.report.pages_processed == 2
    assert result.report.translated_blocks == 2
    assert result.report.cache_hits == 1
    payload = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["status"] == "completed"
    assert payload["final_exit_code"] == 0


def test_batch_resume_reuses_each_file_without_loading_model(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    root = tmp_path / "input"
    pdf_factory(root / "one.pdf")
    pdf_factory(root / "nested" / "two.pdf")
    output = tmp_path / "output"
    cache = tmp_path / "cache"
    first_translator = FakeTranslator()
    first_calls: list[Path] = []
    base = _options(root, output, cache, cyrillic_font_path)
    run_batch(base, services=_services(first_translator, first_calls))
    resume_calls: list[Path] = []

    resumed = run_batch(
        _options(root, output, cache, cyrillic_font_path, resume=True),
        services=_services(FakeTranslator(), resume_calls),
    )

    assert resumed.exit_code == ExitCode.SUCCESS
    assert resume_calls == []
    assert all("translate" in item.reused_stages for item in resumed.report.successful_files)


def test_continue_on_error_processes_remaining_files(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    root = tmp_path / "input"
    pdf_factory(root / "bad.pdf")
    pdf_factory(root / "good.pdf")
    output = tmp_path / "output"
    factory_calls: list[Path] = []

    result = run_batch(
        _options(
            root,
            output,
            tmp_path / "cache",
            cyrillic_font_path,
            continue_on_error=True,
        ),
        services=_services(
            FakeTranslator(),
            factory_calls,
            renderer=SelectiveFailingRenderer(),
        ),
    )

    assert result.exit_code == ExitCode.BATCH_FAILED
    assert result.report.status == "partial"
    assert len(result.report.failed_files) == 1
    assert len(result.report.successful_files) == 1
    assert (output / "good.ru.pdf").is_file()
    assert not (output / "bad.ru.pdf").exists()
    assert len(factory_calls) == 1


def test_default_failure_policy_is_fail_fast(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    root = tmp_path / "input"
    pdf_factory(root / "bad.pdf")
    pdf_factory(root / "good.pdf")

    result = run_batch(
        _options(root, tmp_path / "output", tmp_path / "cache", cyrillic_font_path),
        services=_services(
            FakeTranslator(),
            [],
            renderer=SelectiveFailingRenderer(),
        ),
    )

    assert result.exit_code == ExitCode.BATCH_FAILED
    assert len(result.report.failed_files) == 1
    assert any("not processed" in item.reason for item in result.report.skipped_files)


def test_existing_output_is_reported_as_skipped(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    root = tmp_path / "input"
    pdf_factory(root / "manual.pdf")
    output = tmp_path / "output"
    existing = output / "manual.ru.pdf"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"keep")

    result = run_batch(
        _options(root, output, tmp_path / "cache", cyrillic_font_path),
        services=_services(FakeTranslator(), []),
    )

    assert result.exit_code == ExitCode.SUCCESS
    assert result.report.successful_files == ()
    assert result.report.skipped_files[0].output_path == str(existing.resolve())
    assert "output exists" in result.report.skipped_files[0].reason
    assert existing.read_bytes() == b"keep"


def test_shared_runtime_rejects_a_different_cache_root(tmp_path: Path) -> None:
    translator = FakeTranslator()
    factory_calls: list[Path] = []
    services = _services(translator, factory_calls)
    first = BatchOptions(
        input_dir=tmp_path,
        cache_dir=tmp_path / "cache-one",
        model="fake-nllb",
    ).pipeline_options(tmp_path / "one.pdf", tmp_path / "one.ru.pdf")
    second = BatchOptions(
        input_dir=tmp_path,
        cache_dir=tmp_path / "cache-two",
        model="fake-nllb",
    ).pipeline_options(tmp_path / "two.pdf", tmp_path / "two.ru.pdf")

    with (
        open_translation_runtime(first, services=services) as runtime,
        pytest.raises(ValueError, match="cache root"),
    ):
        runtime.translator_for(second)

    assert factory_calls == []
