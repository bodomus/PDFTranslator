"""Post-OCR PDF integrity and usefulness validation."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from pdftranslate.domain.document import ExtractedDocument
from pdftranslate.domain.page import PageClassification
from pdftranslate.ocr.errors import OcrOutputError


def validate_ocr_output(
    source_path: Path,
    output_path: Path,
    before: ExtractedDocument,
    after: ExtractedDocument,
    processed_pages: tuple[int, ...],
) -> tuple[str, ...]:
    """Require structural fidelity and report OCR pages that remain text-poor."""
    if source_path.resolve() == output_path.resolve():
        raise OcrOutputError("OCR output must not replace the source PDF")
    try:
        with (
            pymupdf.open(source_path) as source,  # type: ignore[no-untyped-call]
            pymupdf.open(output_path) as output,  # type: ignore[no-untyped-call]
        ):
            if output.page_count != source.page_count:
                raise OcrOutputError(
                    f"OCR output page count changed from {source.page_count} to {output.page_count}"
                )
            for index in range(source.page_count):
                source_rect = source[index].rect
                output_rect = output[index].rect
                if (
                    abs(source_rect.width - output_rect.width) > 0.01
                    or abs(source_rect.height - output_rect.height) > 0.01
                ):
                    raise OcrOutputError(f"OCR output changed page {index + 1} geometry")
    except OcrOutputError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise OcrOutputError(f"cannot reopen OCR output: {error}") from error

    before_by_page = {page.page_number: page for page in before.pages}
    after_by_page = {page.page_number: page for page in after.pages}
    warnings: list[str] = []
    for page_number in processed_pages:
        previous = before_by_page.get(page_number)
        current = after_by_page.get(page_number)
        if previous is None or current is None:
            continue
        old_chars = sum(len(block.text.strip()) for block in previous.text_blocks)
        new_chars = sum(len(block.text.strip()) for block in current.text_blocks)
        if current.classification is PageClassification.SCANNED or new_chars <= old_chars:
            warnings.append(
                f"OCR produced little or no additional usable text on page {page_number}"
            )
    return tuple(warnings)
