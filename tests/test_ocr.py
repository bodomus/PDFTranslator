from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pdftranslate.ocr import (
    OcrDependencies,
    OcrDependencyError,
    OcrOptions,
    OcrOutputError,
    OcrProcessError,
    OcrProcessor,
    OcrTimeoutError,
    validate_ocr_output,
)
from pdftranslate.ocr.diagnostics import ExecutableStatus, inspect_ocr_dependencies
from pdftranslate.pdf import PdfExtractor
from tests.conftest import PdfFactory


def _dependencies(*, language: bool = True) -> OcrDependencies:
    return OcrDependencies(
        ocrmypdf=ExecutableStatus("OCRmyPDF", "C:/Tools/ocrmypdf.exe", "16.10.0"),
        tesseract=ExecutableStatus("Tesseract", "C:/Tools/tesseract.exe", "5.5.0"),
        ghostscript=ExecutableStatus("Ghostscript", None, None),
        languages=("eng",) if language else (),
    )


def test_dependency_diagnostics_report_paths_versions_and_languages() -> None:
    paths = {
        "ocrmypdf": "C:/Tools/ocrmypdf.exe",
        "tesseract": "C:/Tools/tesseract.exe",
        "gswin64c": "C:/Tools/gswin64c.exe",
    }

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[-1] == "--list-langs":
            return subprocess.CompletedProcess(command, 0, "List of available languages\neng\n", "")
        return subprocess.CompletedProcess(command, 0, f"{Path(command[0]).stem} 1.2.3\n", "")

    result = inspect_ocr_dependencies(run_process=run, find_executable=paths.get)

    assert result.ocrmypdf.path == paths["ocrmypdf"]
    assert result.tesseract.version == "tesseract 1.2.3"
    assert result.ghostscript.path == paths["gswin64c"]
    assert result.languages == ("eng",)


@pytest.mark.parametrize("missing", ["ocrmypdf", "tesseract", "language"])
def test_missing_dependency_is_actionable(missing: str) -> None:
    dependencies = _dependencies(language=missing != "language")
    if missing == "ocrmypdf":
        dependencies = OcrDependencies(
            ExecutableStatus("OCRmyPDF", None, None),
            dependencies.tesseract,
            dependencies.ghostscript,
            dependencies.languages,
        )
    elif missing == "tesseract":
        dependencies = OcrDependencies(
            dependencies.ocrmypdf,
            ExecutableStatus("Tesseract", None, None),
            dependencies.ghostscript,
            dependencies.languages,
        )

    with pytest.raises(OcrDependencyError) as failure:
        dependencies.require("eng")

    assert "install" in str(failure.value).lower()


def test_processor_passes_unicode_paths_as_unquoted_arguments_and_retains_log(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "папка с пробелами" / "скан.pdf", page_specs=("image",))
    output = tmp_path / "рабочая папка" / "ocr.pdf"
    observed: list[str] = []

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        observed.extend(command)
        shutil.copy2(command[-2], command[-1])
        return subprocess.CompletedProcess(command, 0, "ok", "warning")

    result = OcrProcessor(
        run_process=run,
        dependency_probe=_dependencies,
    ).process(
        source,
        output,
        log_path=tmp_path / "ocr.log",
        sidecar_path=tmp_path / "ocr.txt",
        pages=(1,),
        options=OcrOptions(mode="on", deskew=True, rotate_pages=True),
    )

    assert result.output_path == output
    assert str(source) in observed
    assert "--mode" in observed and "skip" in observed
    assert "--deskew" in observed and "--rotate-pages" in observed
    assert (tmp_path / "ocr.log").read_text(encoding="utf-8").endswith("warning\n")


def test_processor_reports_subprocess_failure_and_timeout(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "scan.pdf", page_specs=("image",))

    def failed(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 6, "", "invalid PDF")

    processor = OcrProcessor(run_process=failed, dependency_probe=_dependencies)
    with pytest.raises(OcrProcessError, match="code 6"):
        processor.process(
            source,
            tmp_path / "failed.pdf",
            log_path=tmp_path / "failed.log",
            sidecar_path=tmp_path / "failed.txt",
            pages=(1,),
            options=OcrOptions(),
        )

    def timeout(_command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired("ocrmypdf", 1, output="partial", stderr="slow")

    processor = OcrProcessor(run_process=timeout, dependency_probe=_dependencies)
    with pytest.raises(OcrTimeoutError, match="timeout"):
        processor.process(
            source,
            tmp_path / "timeout.pdf",
            log_path=tmp_path / "timeout.log",
            sidecar_path=tmp_path / "timeout.txt",
            pages=(1,),
            options=OcrOptions(timeout_seconds=1),
        )
    assert "partial" in (tmp_path / "timeout.log").read_text(encoding="utf-8")


def test_output_validation_rejects_page_count_change_and_warns_on_no_text(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "source.pdf", page_specs=("image",))
    same = pdf_factory(tmp_path / "same.pdf", page_specs=("image",))
    extra = pdf_factory(tmp_path / "extra.pdf", page_specs=("image", "image"))
    extractor = PdfExtractor()
    before = extractor.extract(source)
    after = extractor.extract(same)

    warnings = validate_ocr_output(source, same, before, after, (1,))
    assert warnings == ("OCR produced little or no additional usable text on page 1",)

    with pytest.raises(OcrOutputError, match="page count"):
        validate_ocr_output(source, extra, before, extractor.extract(extra), (1,))


def test_processor_rejects_source_output_alias(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    source = pdf_factory(tmp_path / "same.pdf")
    with pytest.raises(OcrOutputError, match="must not replace"):
        OcrProcessor(dependency_probe=_dependencies).process(
            source,
            source,
            log_path=tmp_path / "ocr.log",
            sidecar_path=tmp_path / "ocr.txt",
            pages=(1,),
            options=OcrOptions(),
        )


def test_force_requires_explicit_on_mode() -> None:
    with pytest.raises(ValueError, match="requires --ocr on"):
        OcrOptions(mode="auto", force=True)

    with pytest.raises(ValueError, match="cannot be used"):
        OcrOptions(mode="off", deskew=True)
