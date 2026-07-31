from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn
from unittest.mock import Mock

import pymupdf
import pytest

from pdftranslate.ocr import OcrDependencyError, OcrExecution, OcrOptions, OcrProcessor
from pdftranslate.pdf import PdfAnalyzer, PdfExtractor
from pdftranslate.pipeline import (
    ExitCode,
    PipelineExecutionError,
    PipelineOptions,
    PipelineServices,
    PipelineStage,
    run_pipeline,
)
from pdftranslate.rendering import PdfRenderer
from tests.conftest import PdfFactory


class FakeTranslator:
    backend_name = "nllb"
    model_name = "fake-nllb"
    device = "cpu"

    def count_tokens(self, text: str) -> int:
        return len(text.split()) + 2

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        return [f"Русский перевод: {text}" for text in texts]


class FakeOcrProcessor(OcrProcessor):
    def __init__(self, *, extra_page: bool = False) -> None:
        self.calls = 0
        self.extra_page = extra_page

    def process(
        self,
        input_path: Path,
        output_path: Path,
        *,
        log_path: Path,
        sidecar_path: Path,
        pages: tuple[int, ...],
        options: OcrOptions,
    ) -> OcrExecution:
        self.calls += 1
        with pymupdf.open(input_path) as document:
            for page_number in pages:
                document[page_number - 1].insert_text(
                    (40, 60),
                    "Recognized English source text with enough characters.",
                )
            if self.extra_page:
                document.new_page()
            document.save(output_path)
        log_path.write_text("fake OCR completed\n", encoding="utf-8")
        sidecar_path.write_text("recognized text\n", encoding="utf-8")
        return OcrExecution(output_path, pages, ("fake-ocr",), "", "")


class InterruptingRenderer(PdfRenderer):
    def render(self, *args: object, **kwargs: object) -> NoReturn:
        raise KeyboardInterrupt


def _options(
    source: Path,
    tmp_path: Path,
    font: Path,
    **changes: object,
) -> PipelineOptions:
    values: dict[str, object] = {
        "input_path": source,
        "output_path": tmp_path / "translated.pdf",
        "cache_dir": tmp_path / "cache",
        "font_path": font,
        "model": "fake-nllb",
    }
    values.update(changes)
    return PipelineOptions(**values)  # type: ignore[arg-type]


def _services(
    processor: OcrProcessor,
    *,
    renderer: PdfRenderer | None = None,
) -> PipelineServices:
    return PipelineServices(
        analyzer=PdfAnalyzer(),
        extractor=PdfExtractor(),
        renderer=renderer or PdfRenderer(),
        translator_factory=lambda _options, _cache: FakeTranslator(),
        ocr_processor=processor,
    )


def test_auto_skips_text_pdf_without_invoking_external_process(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "text.pdf")
    processor = FakeOcrProcessor()

    result = run_pipeline(
        _options(source, tmp_path, cyrillic_font_path),
        services=_services(processor),
    )

    assert processor.calls == 0
    assert result.ocr_status == "skipped"
    assert result.ocr_pages == ()
    assert PipelineStage.OCR not in result.reused_stages


def test_auto_processes_scanned_page_and_preserves_source(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "scan.pdf", page_specs=("image",))
    original = source.read_bytes()
    processor = FakeOcrProcessor()

    result = run_pipeline(
        _options(source, tmp_path, cyrillic_font_path),
        services=_services(processor),
    )

    assert processor.calls == 1
    assert result.ocr_status == "processed"
    assert result.ocr_pages == (1,)
    assert (result.workspace_path / "ocr.pdf").is_file()
    assert (result.workspace_path / "ocr.log").is_file()
    assert source.read_bytes() == original


def test_off_uses_dedicated_ocr_required_category(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "scan.pdf", page_specs=("image",))
    with pytest.raises(PipelineExecutionError) as failure:
        run_pipeline(
            _options(source, tmp_path, cyrillic_font_path, ocr="off"),
            services=_services(FakeOcrProcessor()),
        )
    assert failure.value.exit_code == ExitCode.OCR_REQUIRED


def test_missing_dependency_uses_ocr_failure_category(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "scan.pdf", page_specs=("image",))
    processor = Mock(spec=OcrProcessor)
    processor.process.side_effect = OcrDependencyError("install OCRmyPDF")
    with pytest.raises(PipelineExecutionError) as failure:
        run_pipeline(
            _options(source, tmp_path, cyrillic_font_path),
            services=_services(processor),  # type: ignore[arg-type]
        )
    assert failure.value.exit_code == ExitCode.OCR_FAILED
    assert "install OCRmyPDF" in str(failure.value)


def test_resume_reuses_valid_ocr_output(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "scan.pdf", page_specs=("image",))
    processor = FakeOcrProcessor()
    with pytest.raises(PipelineExecutionError):
        run_pipeline(
            _options(source, tmp_path, cyrillic_font_path),
            services=_services(processor, renderer=InterruptingRenderer()),
        )
    assert processor.calls == 1

    never_run = Mock(spec=OcrProcessor)
    result = run_pipeline(
        _options(source, tmp_path, cyrillic_font_path, resume=True),
        services=_services(never_run),  # type: ignore[arg-type]
    )

    never_run.process.assert_not_called()
    assert PipelineStage.OCR in result.reused_stages
    assert result.ocr_status == "reused"


def test_invalid_ocr_output_is_not_accepted(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    source = pdf_factory(tmp_path / "scan.pdf", page_specs=("image",))
    with pytest.raises(PipelineExecutionError) as failure:
        run_pipeline(
            _options(source, tmp_path, cyrillic_font_path),
            services=_services(FakeOcrProcessor(extra_page=True)),
        )
    assert failure.value.exit_code == ExitCode.OCR_FAILED
    assert "page count" in str(failure.value)
