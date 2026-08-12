"""Generated-PDF glossary validation with diagnostics and rendered searchable text."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pymupdf

from pdftranslate.diagnostics import DiagnosticCode
from pdftranslate.diagnostics.builder import build_success_report
from pdftranslate.glossary import load_glossary
from pdftranslate.pdf import PdfExtractor
from pdftranslate.rendering import PdfRenderer
from pdftranslate.translation import TranslationCache, TranslationOptions, translate_document


class _PdfTranslator:
    backend_name = "fake"
    model_name = "fake-model"
    device: Literal["cpu"] = "cpu"

    def count_tokens(self, text: str) -> int:
        return len(text.split()) + 2

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        return [f"RU {text}" for text in texts]


def test_generated_pdf_glossary_is_searchable_and_diagnostics_are_private(tmp_path: Path) -> None:
    source_path = tmp_path / "glossary-source.pdf"
    document = pymupdf.open()
    for number in range(1, 4):
        page = document.new_page(width=600, height=800)
        page.insert_text((50, 30), "Glossary Manual", fontsize=10)
        page.insert_text(
            (50, 160),
            f"The Secret Service uses identifier ZX-1900-1 on 2026-08-0{number}.",
            fontsize=10,
        )
        page.insert_text((295, 780), str(number), fontsize=10)
    document.save(source_path)
    document.close()

    glossary_path = tmp_path / "glossary.json"
    glossary_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "glossary_version": "1.0.0",
                "source_language": "en",
                "target_language": "ru",
                "entries": [
                    {
                        "id": "service",
                        "source": "Secret Service",
                        "target": "Секретная служба",
                        "mode": "translate",
                        "case_sensitive": True,
                        "match": "phrase",
                        "inflection": "fixed",
                        "priority": 100,
                    },
                    {
                        "id": "identifier",
                        "source": "ZX-1900-1",
                        "target": "ZX-1900-1",
                        "mode": "preserve",
                        "case_sensitive": True,
                        "match": "whole_word",
                        "inflection": "fixed",
                        "priority": 200,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    extracted = PdfExtractor().extract(source_path)
    with TranslationCache(tmp_path / "cache.sqlite3") as cache:
        translated = translate_document(
            extracted,
            translator=_PdfTranslator(),
            cache=cache,
            options=TranslationOptions(glossary=load_glossary(glossary_path)),
        )

    output = tmp_path / "glossary-output.pdf"
    render = PdfRenderer().render(source_path, translated, output)
    rendered = pymupdf.open(output)
    try:
        text = "\n".join(page.get_text("text") for page in rendered)
    finally:
        rendered.close()
    normalized_text = text.replace("‐", "-")
    assert normalized_text.count("Секретная служба") == 3
    assert normalized_text.count("ZX-1900-1") == 3
    assert "__PDFTR_" not in text
    assert "Secret Service" not in text

    now = datetime.now(UTC)
    report = build_success_report(
        run_id="pdftr13-generated",
        started_at=now,
        finished_at=now,
        input_path=source_path,
        output_path=output,
        translated=translated,
        render=render,
        ocr_pages=(),
        ocr_warnings=(),
        elapsed_seconds=0.1,
        stage_durations={},
        peak_ram_bytes=None,
        include_text=False,
        debug_layout_path=None,
        block_evidence={},
    )
    assert report.summary.glossary_enabled
    assert report.summary.glossary_matched_entries == 2
    assert report.summary.glossary_applied_occurrences == 6
    assert all(block.source_text is None for page in report.pages for block in page.blocks)
    assert all(block.translated_text is None for page in report.pages for block in page.blocks)
    assert DiagnosticCode.GLOSSARY_ENTRY_UNUSED not in {item.code for item in report.findings}
