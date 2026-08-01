from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn
from unittest.mock import Mock, patch

import pymupdf
import pytest
from typer.testing import CliRunner

from pdftranslate.cli import app
from pdftranslate.pdf import PdfAnalyzer, PdfExtractor
from pdftranslate.pipeline import (
    ExitCode,
    PipelineExecutionError,
    PipelineOptions,
    PipelineServices,
    PipelineStage,
    default_output_path,
    plan_pipeline,
    run_pipeline,
)
from pdftranslate.pipeline.models import PIPELINE_BEHAVIOR_REVISION
from pdftranslate.rendering import OutputPdfError, PdfRenderer, validate_output_pdf
from pdftranslate.translation import TranslationBackendError
from tests.conftest import PdfFactory

runner = CliRunner()
RUSSIAN_TRANSLATION = (
    "\u0420\u0443\u0441\u0441\u043a\u0438\u0439 \u043f\u0435\u0440\u0435\u0432\u043e\u0434"
)
CYRILLIC_FOLDER = (
    "\u043f\u0430\u043f\u043a\u0430 \u0441 \u043f\u0440\u043e\u0431\u0435\u043b\u0430\u043c\u0438"
)
CYRILLIC_OUTPUT = (
    "\u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442 "
    "\u043f\u0435\u0440\u0435\u0432\u043e\u0434\u0430.pdf"
)


class FakeTranslator:
    backend_name = "nllb"
    model_name = "fake-nllb"
    device = "cpu"

    def __init__(self, *, interrupt: bool = False) -> None:
        self.calls = 0
        self.interrupt = interrupt

    def count_tokens(self, text: str) -> int:
        return len(text.split()) + 2

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        self.calls += 1
        if self.interrupt:
            raise KeyboardInterrupt
        return [f"{RUSSIAN_TRANSLATION}: {text}" for text in texts]


class FailingTranslator(FakeTranslator):
    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        raise TranslationBackendError("simulated inference failure")


class FailingRenderer(PdfRenderer):
    def render(self, *args: object, **kwargs: object) -> NoReturn:
        raise OutputPdfError("simulated rendering failure")


class InterruptingRenderer(PdfRenderer):
    def render(self, *args: object, **kwargs: object) -> NoReturn:
        raise KeyboardInterrupt


def _options(
    source: Path,
    output: Path,
    cache: Path,
    font: Path,
    **changes: object,
) -> PipelineOptions:
    values: dict[str, object] = {
        "input_path": source,
        "output_path": output,
        "cache_dir": cache,
        "font_path": font,
        "model": "fake-nllb",
    }
    values.update(changes)
    return PipelineOptions(**values)  # type: ignore[arg-type]


def _services(
    translator: FakeTranslator,
    *,
    renderer: PdfRenderer | None = None,
    validator: object = validate_output_pdf,
) -> PipelineServices:
    return PipelineServices(
        analyzer=PdfAnalyzer(),
        extractor=PdfExtractor(),
        renderer=renderer or PdfRenderer(),
        translator_factory=lambda _options, _cache: translator,
        validator=validator,  # type: ignore[arg-type]
    )


def test_default_output_name_is_documented_sibling() -> None:
    assert default_output_path(Path("manual.pdf")) == Path("manual.ru.pdf")
    assert default_output_path(Path("folder/report.final.PDF")) == Path(
        "folder/report.final.ru.pdf"
    )


def test_pipeline_identity_includes_behavior_revision(tmp_path: Path) -> None:
    options = PipelineOptions(
        input_path=tmp_path / "source.pdf",
        output_path=tmp_path / "output.pdf",
    )

    assert options.identity_values()["pipeline_behavior_revision"] == PIPELINE_BEHAVIOR_REVISION


def test_complete_pipeline_uses_cache_workspace_and_unicode_paths(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    root = tmp_path / CYRILLIC_FOLDER
    source = pdf_factory(
        root / "\u0440\u0443\u043a\u043e\u0432\u043e\u0434\u0441\u0442\u0432\u043e.pdf",
        page_specs=("text", "empty"),
    )
    output = root / CYRILLIC_OUTPUT
    cache = (
        tmp_path / "\u043a\u044d\u0448 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u044f"
    )
    events: list[tuple[PipelineStage, bool]] = []

    result = run_pipeline(
        _options(source, output, cache, cyrillic_font_path),
        services=_services(FakeTranslator()),
        stage_progress=lambda event: events.append((event.stage, event.reused)),
    )

    assert output.is_file()
    assert result.output_path == output.resolve()
    assert result.file_size > 0
    assert [stage for stage, _ in events] == list(PipelineStage)
    assert not any(reused for _, reused in events)
    assert result.workspace_path.parent == (cache / "workspaces").resolve()
    expected_artifacts = {
        "inspection.json",
        "extracted.json",
        "translated.json",
        "rendered.pdf",
        "manifest.json",
        "pipeline.log",
    }
    assert expected_artifacts <= {path.name for path in result.workspace_path.iterdir()}
    with pymupdf.open(output) as document:
        assert document.page_count == 2
        assert (
            "\u0420\u0443\u0441\u0441\u043a\u0438\u0439 \u043f\u0435\u0440\u0435\u0432\u043e\u0434"
            in document[0].get_text("text")
        )


def test_dry_run_never_constructs_model_or_creates_workspace(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "dry.pdf", page_specs=("text", "image"))
    output = tmp_path / "dry.ru.pdf"
    cache = tmp_path / "cache"
    factory = Mock(side_effect=AssertionError("model must not load"))
    services = PipelineServices(
        analyzer=PdfAnalyzer(),
        extractor=PdfExtractor(),
        renderer=PdfRenderer(),
        translator_factory=factory,
    )

    result = plan_pipeline(
        _options(source, output, cache, cyrillic_font_path),
        services=services,
    )

    assert result.estimated_text_blocks == 1
    assert result.ocr_required is True
    assert result.selected_page_classifications == ("text", "scanned")
    factory.assert_not_called()
    assert not output.exists()
    assert not cache.exists()


def test_resume_reuses_completed_translation_after_render_interruption(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "resume.pdf")
    output = tmp_path / "resume.ru.pdf"
    cache = tmp_path / "cache"
    original = _options(source, output, cache, cyrillic_font_path)
    translator = FakeTranslator()

    with pytest.raises(PipelineExecutionError) as interrupted:
        run_pipeline(
            original,
            services=_services(translator, renderer=InterruptingRenderer()),
        )

    assert interrupted.value.exit_code == ExitCode.INTERRUPTED
    assert interrupted.value.stage == PipelineStage.RENDER
    assert translator.calls == 1
    never_translate = Mock(side_effect=AssertionError("translation stage must be reused"))
    resumed_services = PipelineServices(
        analyzer=PdfAnalyzer(),
        extractor=PdfExtractor(),
        renderer=PdfRenderer(),
        translator_factory=never_translate,
    )
    resumed = run_pipeline(
        _options(source, output, cache, cyrillic_font_path, resume=True),
        services=resumed_services,
    )

    assert output.is_file()
    assert resumed.reused_stages == (
        PipelineStage.INSPECT,
        PipelineStage.OCR,
        PipelineStage.EXTRACT,
        PipelineStage.TRANSLATE,
    )
    never_translate.assert_not_called()


@pytest.mark.parametrize("change", ["options", "source"])
def test_resume_rejects_changed_identity(
    change: str,
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "identity.pdf")
    output = tmp_path / "identity.ru.pdf"
    cache = tmp_path / "cache"
    with pytest.raises(PipelineExecutionError):
        run_pipeline(
            _options(source, output, cache, cyrillic_font_path),
            services=_services(FakeTranslator(), renderer=InterruptingRenderer()),
        )

    changes: dict[str, object] = {"resume": True}
    if change == "options":
        changes["batch_size"] = 4
    else:
        source.write_bytes(source.read_bytes() + b"\n% source changed\n")

    with pytest.raises(PipelineExecutionError) as failure:
        run_pipeline(
            _options(source, output, cache, cyrillic_font_path, **changes),
            services=_services(FakeTranslator()),
        )

    assert failure.value.exit_code == ExitCode.INVALID_ARGUMENTS
    assert "no compatible pipeline state" in str(failure.value)
    assert not output.exists()


def test_validation_failure_retains_artifacts_without_publishing_final_name(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "validation.pdf")
    output = tmp_path / "validation.ru.pdf"
    cache = tmp_path / "cache"

    def fail_validation(_path: Path, _pages: int) -> NoReturn:
        raise OutputPdfError("simulated validation failure")

    with pytest.raises(PipelineExecutionError) as failure:
        run_pipeline(
            _options(source, output, cache, cyrillic_font_path),
            services=_services(FakeTranslator(), validator=fail_validation),
        )

    assert failure.value.exit_code == ExitCode.OUTPUT_VALIDATION_FAILED
    assert failure.value.stage == PipelineStage.VALIDATE
    assert not output.exists()
    assert failure.value.log_path is not None
    workspace = failure.value.log_path.parent
    assert (workspace / "rendered.pdf").is_file()
    assert (workspace / "failure.json").is_file()
    assert "simulated validation failure" in failure.value.log_path.read_text(encoding="utf-8")


def test_translation_keyboard_interrupt_is_checkpointed_and_categorized(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "interrupt.pdf")
    output = tmp_path / "interrupt.ru.pdf"

    with pytest.raises(PipelineExecutionError) as failure:
        run_pipeline(
            _options(source, output, tmp_path / "cache", cyrillic_font_path),
            services=_services(FakeTranslator(interrupt=True)),
        )

    assert failure.value.exit_code == ExitCode.INTERRUPTED
    assert failure.value.stage == PipelineStage.TRANSLATE
    assert failure.value.log_path is not None
    assert (failure.value.log_path.parent / "translated.json").is_file()
    assert not output.exists()


def test_scanned_pdf_uses_stable_ocr_required_exit_category(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "scan.pdf", page_specs=("image",))
    translator = FakeTranslator()

    with pytest.raises(PipelineExecutionError) as failure:
        run_pipeline(
            _options(
                source,
                tmp_path / "scan.ru.pdf",
                tmp_path / "cache",
                cyrillic_font_path,
                ocr="off",
            ),
            services=_services(translator),
        )

    assert failure.value.exit_code == ExitCode.OCR_REQUIRED
    assert translator.calls == 0


def test_corrupt_pdf_uses_stable_pdf_input_exit_category(
    tmp_path: Path,
    cyrillic_font_path: Path,
) -> None:
    source = tmp_path / "corrupt.pdf"
    source.write_bytes(b"not a pdf")

    with pytest.raises(PipelineExecutionError) as failure:
        run_pipeline(
            _options(
                source,
                tmp_path / "corrupt.ru.pdf",
                tmp_path / "cache",
                cyrillic_font_path,
            ),
            services=_services(FakeTranslator()),
        )

    assert failure.value.exit_code == ExitCode.PDF_INPUT_ERROR
    assert not (tmp_path / "corrupt.ru.pdf").exists()


def test_model_initialization_failure_has_dedicated_exit_category(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "model.pdf")

    def unavailable(_options: PipelineOptions, _cache: Path) -> NoReturn:
        raise TranslationBackendError("model is unavailable")

    services = PipelineServices(
        analyzer=PdfAnalyzer(),
        extractor=PdfExtractor(),
        renderer=PdfRenderer(),
        translator_factory=unavailable,
    )
    with pytest.raises(PipelineExecutionError) as failure:
        run_pipeline(
            _options(
                source,
                tmp_path / "model.ru.pdf",
                tmp_path / "cache",
                cyrillic_font_path,
            ),
            services=services,
        )

    assert failure.value.exit_code == ExitCode.MODEL_UNAVAILABLE


def test_inference_failure_has_translation_exit_category(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "translation.pdf")

    with pytest.raises(PipelineExecutionError) as failure:
        run_pipeline(
            _options(
                source,
                tmp_path / "translation.ru.pdf",
                tmp_path / "cache",
                cyrillic_font_path,
            ),
            services=_services(FailingTranslator()),
        )

    assert failure.value.exit_code == ExitCode.TRANSLATION_FAILED


def test_renderer_failure_has_rendering_exit_category(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "rendering.pdf")

    with pytest.raises(PipelineExecutionError) as failure:
        run_pipeline(
            _options(
                source,
                tmp_path / "rendering.ru.pdf",
                tmp_path / "cache",
                cyrillic_font_path,
            ),
            services=_services(FakeTranslator(), renderer=FailingRenderer()),
        )

    assert failure.value.exit_code == ExitCode.RENDERING_FAILED


def test_existing_final_output_is_never_replaced_without_overwrite(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "existing.pdf")
    output = tmp_path / "existing.ru.pdf"
    output.write_bytes(b"keep")

    with pytest.raises(PipelineExecutionError) as failure:
        run_pipeline(
            _options(source, output, tmp_path / "cache", cyrillic_font_path),
            services=_services(FakeTranslator()),
        )

    assert failure.value.exit_code == ExitCode.INVALID_ARGUMENTS
    assert output.read_bytes() == b"keep"


def test_exit_code_values_are_stable() -> None:
    assert {name: int(value) for name, value in ExitCode.__members__.items()} == {
        "SUCCESS": 0,
        "INVALID_ARGUMENTS": 2,
        "PDF_INPUT_ERROR": 3,
        "OCR_REQUIRED": 4,
        "MODEL_UNAVAILABLE": 5,
        "TRANSLATION_FAILED": 6,
        "RENDERING_FAILED": 7,
        "OUTPUT_VALIDATION_FAILED": 8,
        "OCR_FAILED": 9,
        "BATCH_FAILED": 10,
        "INTERRUPTED": 130,
    }


def test_root_cli_runs_complete_pipeline_with_fake_backend(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "CLI \u043f\u0443\u0442\u044c.pdf")
    output = default_output_path(source)
    translator = FakeTranslator()

    with patch("pdftranslate.pipeline.runner.NllbTranslator", return_value=translator) as loader:
        result = runner.invoke(
            app,
            [
                str(source),
                "--cache-dir",
                str(tmp_path / "cli-cache"),
                "--font",
                str(cyrillic_font_path),
                "--model",
                "fake-nllb",
                "--offline",
                "--report",
                "--report-format",
                "both",
                "--report-dir",
                str(tmp_path / "cli-report"),
                "--debug-layout",
            ],
        )

    assert result.exit_code == ExitCode.SUCCESS, result.output
    assert output.is_file()
    assert (tmp_path / "cli-report" / "translation-report.json").is_file()
    assert (tmp_path / "cli-report" / "translation-report.html").is_file()
    assert (tmp_path / "cli-report" / "debug-layout.pdf").is_file()
    assert "Report:" in result.stdout
    assert "Debug layout:" in result.stdout
    assert "1/6 Inspect" in result.stdout
    assert "6/6 Validate" in result.stdout
    assert "Translated 1/1 block(s)" in result.stdout
    loader.assert_called_once()


def test_root_cli_dry_run_does_not_load_model(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "dry-cli.pdf")

    with patch("pdftranslate.pipeline.runner.NllbTranslator") as loader:
        result = runner.invoke(app, [str(source), "--dry-run"])

    assert result.exit_code == ExitCode.SUCCESS, result.output
    assert "PDFTranslate dry run" in result.stdout
    assert "Expected stages" in result.stdout
    assert not default_output_path(source).exists()
    loader.assert_not_called()


def test_pipeline_writes_private_reports_and_annotated_debug_pdf(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "diagnostic-source.pdf", page_specs=("text",))
    output = tmp_path / "diagnostic-output.pdf"
    report_dir = tmp_path / "reports"

    result = run_pipeline(
        _options(
            source,
            output,
            tmp_path / "cache",
            cyrillic_font_path,
            report=True,
            report_dir=report_dir,
            report_format="both",
            debug_layout=True,
        ),
        services=_services(FakeTranslator()),
    )

    assert {path.name for path in result.report_paths} == {
        "translation-report.json",
        "translation-report.html",
    }
    assert result.debug_layout_path == report_dir / "debug-layout.pdf"
    assert result.debug_layout_path.is_file()
    payload = __import__("json").loads((report_dir / "translation-report.json").read_text("utf-8"))
    assert payload["status"] == "success"
    assert payload["text_included"] is False
    assert payload["pages"][0]["blocks"][0]["source_text"] is None
    assert payload["pages"][0]["blocks"][0]["translated_text"] is None
    assert payload["pages"][0]["blocks"][0]["cache_status"] == "miss"
    assert payload["pages"][0]["blocks"][0]["segmentation_count"] >= 1
    assert payload["pages"][0]["blocks"][0]["fitting_attempts"] >= 1
    assert payload["summary"]["selected_font"] == str(cyrillic_font_path)
    debug_document = pymupdf.open(result.debug_layout_path)
    try:
        assert payload["pages"][0]["blocks"][0]["block_id"] in debug_document[0].get_text("text")
    finally:
        debug_document.close()
    html = (report_dir / "translation-report.html").read_text("utf-8")
    assert "<script src=" not in html
    assert "<link rel=" not in html


def test_pipeline_writes_failure_report_without_hiding_primary_error(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "failure-source.pdf", page_specs=("text",))
    report_dir = tmp_path / "failure-report"
    options = _options(
        source,
        tmp_path / "failure-output.pdf",
        tmp_path / "failure-cache",
        cyrillic_font_path,
        report=True,
        report_dir=report_dir,
        report_format="json",
    )

    with pytest.raises(PipelineExecutionError) as caught:
        run_pipeline(
            options,
            services=_services(FakeTranslator(), renderer=FailingRenderer()),
        )

    assert caught.value.stage is PipelineStage.RENDER
    payload = __import__("json").loads((report_dir / "translation-report.json").read_text("utf-8"))
    assert payload["status"] == "failed"
    assert payload["failed_stage"] == "render"
    assert payload["findings"][0]["code"] == "PIPELINE_STAGE_FAILED"


def test_pipeline_report_text_is_explicit_opt_in_and_preserves_cyrillic(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "opt-in-source.pdf", page_specs=("text",))
    report_dir = tmp_path / "opt-in-report"
    run_pipeline(
        _options(
            source,
            tmp_path / "opt-in-output.pdf",
            tmp_path / "opt-in-cache",
            cyrillic_font_path,
            report=True,
            report_dir=report_dir,
            report_format="json",
            include_report_text=True,
        ),
        services=_services(FakeTranslator()),
    )

    payload = __import__("json").loads((report_dir / "translation-report.json").read_text("utf-8"))
    block = payload["pages"][0]["blocks"][0]
    assert payload["text_included"] is True
    assert "English" in block["source_text"]
    assert RUSSIAN_TRANSLATION in block["translated_text"]
