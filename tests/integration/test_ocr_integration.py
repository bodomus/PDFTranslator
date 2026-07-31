from __future__ import annotations

import os
from pathlib import Path

import pytest
from tests.conftest import PdfFactory

from pdftranslate.ocr import OcrOptions, OcrProcessor, inspect_ocr_dependencies


@pytest.mark.ocr_integration
def test_real_ocrmypdf_process_is_opt_in(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    if os.environ.get("PDFTRANSLATE_RUN_OCR_INTEGRATION") != "1":
        pytest.skip("set PDFTRANSLATE_RUN_OCR_INTEGRATION=1 to run real OCR")
    dependencies = inspect_ocr_dependencies()
    try:
        dependencies.require("eng")
    except RuntimeError as error:
        pytest.skip(str(error))

    source = pdf_factory(tmp_path / "real-ocr-input.pdf", page_specs=("image",))
    output = tmp_path / "real-ocr-output.pdf"
    result = OcrProcessor().process(
        source,
        output,
        log_path=tmp_path / "real-ocr.log",
        sidecar_path=tmp_path / "real-ocr.txt",
        pages=(1,),
        options=OcrOptions(mode="on"),
    )

    assert result.output_path.is_file()
