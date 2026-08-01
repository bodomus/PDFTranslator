from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn
from unittest.mock import Mock

import pytest

from pdftranslate.ocr import OcrDependencyError, OcrProcessor
from pdftranslate.pdf import PdfAnalyzer, PdfExtractor
from pdftranslate.pipeline import PipelineServices, PipelineStage
from pdftranslate.rendering import OutputPdfError, PdfRenderer, validate_output_pdf
from pdftranslate.translation import TranslationBackendError
from pdftranslate.validation import (
    CorpusDocument,
    CorpusManifest,
    ManualReview,
    ManualReviewManifest,
    ValidationOptions,
    run_validation,
)
from pdftranslate.validation.cli import main as validation_main
from pdftranslate.validation.models import ManualReviewEntry
from tests.conftest import PdfFactory

RUSSIAN = "Русский перевод"


class FakeTranslator:
    backend_name = "nllb"
    model_name = "fake-nllb"
    device = "cpu"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def count_tokens(self, text: str) -> int:
        return len(text.split()) + 2

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        self.calls += 1
        if self.fail:
            raise TranslationBackendError("simulated validation translation failure")
        return [f"{RUSSIAN}: {text}" for text in texts]


class FailingRenderer(PdfRenderer):
    def render(self, *args: object, **kwargs: object) -> NoReturn:
        raise OutputPdfError("simulated validation rendering failure")


class FailingOcrProcessor:
    def process(self, *args: object, **kwargs: object) -> NoReturn:
        raise OcrDependencyError("simulated missing OCR dependency")


def _services(
    translator: FakeTranslator,
    *,
    renderer: PdfRenderer | None = None,
    validator: object = validate_output_pdf,
    ocr_processor: object | None = None,
    loader: Mock | None = None,
) -> PipelineServices:
    def create_translator(_options: object, _cache: Path) -> FakeTranslator:
        if loader is not None:
            loader()
        return translator

    return PipelineServices(
        analyzer=PdfAnalyzer(),
        extractor=PdfExtractor(),
        renderer=renderer or PdfRenderer(),
        translator_factory=create_translator,
        validator=validator,  # type: ignore[arg-type]
        ocr_processor=ocr_processor or OcrProcessor(),  # type: ignore[arg-type]
    )


def _options(
    corpus: Path,
    results: Path,
    cache: Path,
    font: Path,
    **changes: object,
) -> ValidationOptions:
    values: dict[str, object] = {
        "corpus_root": corpus,
        "output_root": results,
        "cache_dir": cache,
        "font_path": font,
        "model": "fake-nllb",
    }
    values.update(changes)
    return ValidationOptions(**values)  # type: ignore[arg-type]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_dry_run_manifest_subset_generates_all_reports_without_model(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    corpus = tmp_path / "корпус с пробелами"
    pdf_factory(corpus / "text.pdf", page_specs=("text",))
    pdf_factory(corpus / "image.pdf", page_specs=("mixed",))
    manifest = CorpusManifest(
        documents=(
            CorpusDocument(document_id="text", path="text.pdf", categories=("text-heavy",)),
            CorpusDocument(
                document_id="image",
                path="image.pdf",
                categories=("images-and-captions",),
            ),
        )
    )
    manifest_path = corpus / "validation-corpus.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    loader = Mock(side_effect=AssertionError("dry-run must not load a model"))
    result = run_validation(
        _options(
            corpus,
            tmp_path / "results",
            tmp_path / "cache",
            cyrillic_font_path,
            manifest_path=manifest_path,
            subsets=("images-and-captions",),
            dry_run=True,
        ),
        services=_services(FakeTranslator(), loader=loader),
    )

    assert result.summary.status == "planned"
    assert result.summary.selected_documents == 1
    assert result.documents[0].page_classifications == ("mixed",)
    assert all(stage.status == "planned" for stage in result.documents[0].stage_results)
    assert result.summary_json_path.is_file()
    assert result.summary_markdown_path.is_file()
    assert result.manual_template_path.is_file()
    assert (tmp_path / "results" / "document-results" / "image.json").is_file()
    loader.assert_not_called()


def test_successful_text_and_image_validation_reuses_one_model_and_preserves_sources(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    corpus = tmp_path / "corpus"
    text = pdf_factory(corpus / "text.pdf", page_specs=("text",))
    image = pdf_factory(corpus / "image.pdf", page_specs=("mixed",))
    before = {path: _sha256(path) for path in (text, image)}
    translator = FakeTranslator()
    loader = Mock()

    result = run_validation(
        _options(corpus, tmp_path / "results", tmp_path / "cache", cyrillic_font_path),
        services=_services(translator, loader=loader),
    )

    assert result.summary.status == "passed"
    assert result.summary.passed_documents == 2
    assert result.summary.manual_reviews_pending == 2
    assert {item.page_classifications for item in result.documents} == {("text",), ("mixed",)}
    assert all(item.source_unchanged for item in result.documents)
    assert all(_sha256(path) == before[path] for path in before)
    assert all(item.output_size and item.output_size > 0 for item in result.documents)
    assert all(item.effective_device == "cpu" for item in result.documents)
    assert (tmp_path / "results" / "logs").is_dir()
    loader.assert_called_once_with()
    assert translator.calls == 1
    assert sum(item.cache_hits for item in result.documents) == 1


def test_corrupt_pdf_failure_does_not_stop_remaining_documents(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a-corrupt.pdf").write_bytes(b"not a PDF")
    good = pdf_factory(corpus / "b-good.pdf")
    good_sha = _sha256(good)

    result = run_validation(
        _options(corpus, tmp_path / "results", tmp_path / "cache", cyrillic_font_path),
        services=_services(FakeTranslator()),
    )

    assert [item.status for item in result.documents] == ["failed", "passed"]
    assert result.documents[0].failure is not None
    assert result.documents[0].failure.exit_code == 3
    assert result.documents[1].source_unchanged
    assert _sha256(good) == good_sha
    assert result.summary.failed_documents == 1
    assert result.summary.passed_documents == 1


@pytest.mark.parametrize("failure_kind", ["translation", "render", "ocr", "validation"])
def test_stage_failures_are_categorized_and_never_publish_partial_output(
    failure_kind: str,
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    corpus = tmp_path / "corpus"
    page_specs = ("image",) if failure_kind == "ocr" else ("text",)
    source = pdf_factory(corpus / f"{failure_kind}.pdf", page_specs=page_specs)
    translator = FakeTranslator(fail=failure_kind == "translation")
    renderer = FailingRenderer() if failure_kind == "render" else None
    ocr_processor = FailingOcrProcessor() if failure_kind == "ocr" else None

    def validator(_path: Path, _pages: int) -> NoReturn:
        raise OutputPdfError("simulated final validation failure")

    result = run_validation(
        _options(
            corpus,
            tmp_path / "results",
            tmp_path / "cache",
            cyrillic_font_path,
            ocr="on" if failure_kind == "ocr" else "auto",
        ),
        services=_services(
            translator,
            renderer=renderer,
            validator=validator if failure_kind == "validation" else validate_output_pdf,
            ocr_processor=ocr_processor,
        ),
    )

    document = result.documents[0]
    assert document.status == "failed"
    assert document.failure is not None
    expected_stage = {
        "translation": PipelineStage.TRANSLATE,
        "render": PipelineStage.RENDER,
        "ocr": PipelineStage.OCR,
        "validation": PipelineStage.VALIDATE,
    }[failure_kind]
    assert document.failure.stage == expected_stage
    if failure_kind == "ocr":
        assert document.ocr_decision == "failed"
    else:
        assert document.ocr_decision == "skipped"
    assert not (tmp_path / "results" / "outputs" / f"{failure_kind}.ru.pdf").exists()
    assert document.source_unchanged
    assert _sha256(source) == document.source_sha256_before
    assert document.defects[0].recommended_follow_up
    if failure_kind == "translation":
        assert document.defects[0].recommended_follow_up.startswith("PDFTR-9")


def test_resume_records_reused_stages_without_loading_model_again(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    corpus = tmp_path / "corpus"
    pdf_factory(corpus / "resume.pdf")
    results = tmp_path / "results"
    cache = tmp_path / "cache"
    first = run_validation(
        _options(corpus, results, cache, cyrillic_font_path),
        services=_services(FakeTranslator()),
    )
    assert first.summary.status == "passed"

    loader = Mock(side_effect=AssertionError("resumed translation must not load the model"))
    resumed = run_validation(
        _options(corpus, results, cache, cyrillic_font_path, resume=True),
        services=_services(FakeTranslator(), loader=loader),
    )

    assert resumed.summary.status == "passed"
    assert PipelineStage.TRANSLATE in resumed.documents[0].reused_stages
    assert resumed.documents[0].resume_requested
    assert resumed.documents[0].source_unchanged
    loader.assert_not_called()


def test_failed_manual_observation_becomes_a_mapped_defect(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    cyrillic_font_path: Path,
) -> None:
    corpus = tmp_path / "corpus"
    pdf_factory(corpus / "manual.pdf")
    discovered_id = "document-" + hashlib.sha256(b"manual.pdf").hexdigest()[:12]
    reviews = ManualReviewManifest(
        documents=(
            ManualReviewEntry(
                document_id=discovered_id,
                review=ManualReview(
                    reviewer="tester",
                    output_opens="failed",
                    notes="PDF-XChange could not open the output",
                ),
            ),
        )
    )
    review_path = tmp_path / "manual-results.json"
    review_path.write_text(reviews.model_dump_json(indent=2), encoding="utf-8")

    result = run_validation(
        _options(
            corpus,
            tmp_path / "results",
            tmp_path / "cache",
            cyrillic_font_path,
            manual_results_path=review_path,
        ),
        services=_services(FakeTranslator()),
    )

    assert result.summary.status == "failed"
    assert result.summary.manual_reviews_failed == 1
    assert any(defect.stage == "manual-review" for defect in result.summary.defects)


def test_validation_cli_dry_run_prints_published_paths(
    tmp_path: Path,
    pdf_factory: PdfFactory,
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus = tmp_path / "CLI корпус"
    pdf_factory(corpus / "sample.pdf")
    output = tmp_path / "CLI results"

    exit_code = validation_main(
        [
            "--corpus-root",
            str(corpus),
            "--output-root",
            str(output),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Validation status: planned" in captured.out
    assert (output / "validation-summary.json").is_file()


def test_validation_cli_rejects_incompatible_dry_run_resume(
    tmp_path: Path,
    pdf_factory: PdfFactory,
) -> None:
    corpus = tmp_path / "corpus"
    pdf_factory(corpus / "sample.pdf")

    with pytest.raises(SystemExit) as failure:
        validation_main(["--corpus-root", str(corpus), "--dry-run", "--resume"])

    assert failure.value.code == 2
