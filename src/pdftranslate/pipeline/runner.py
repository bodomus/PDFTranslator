"""Typer-independent inspect-to-validation orchestration."""

from __future__ import annotations

import os
import shutil
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from pdftranslate.config import Settings
from pdftranslate.domain.document import ExtractedDocument, InspectionReport
from pdftranslate.pdf import PdfAnalyzer, PdfExtractor, PdfInputError
from pdftranslate.pdf.pymupdf_backend import source_identity
from pdftranslate.pipeline.errors import (
    ModelUnavailableError,
    OcrRequiredError,
    OutputValidationError,
    PipelineExecutionError,
    PipelineStateError,
)
from pdftranslate.pipeline.exit_codes import ExitCode
from pdftranslate.pipeline.models import (
    DryRunResult,
    PipelineOptions,
    PipelineResult,
    PipelineStage,
    StageProgress,
)
from pdftranslate.pipeline.workspace import PipelineWorkspace
from pdftranslate.rendering import (
    OutputPdfError,
    PdfRenderer,
    RenderingError,
    RenderOptions,
    validate_output_pdf,
)
from pdftranslate.serialization import OutputExistsError
from pdftranslate.translation import (
    NllbTranslator,
    TranslationCache,
    TranslationError,
    TranslationInterruptedError,
    TranslationOptions,
    TranslationProgress,
    Translator,
    translate_document,
)

TranslatorFactory = Callable[[PipelineOptions, Path], Translator]
OutputValidator = Callable[[Path, int], int]
StageCallback = Callable[[StageProgress], None]
TranslationCallback = Callable[[TranslationProgress], None]


@dataclass(frozen=True)
class PipelineServices:
    """Injectable adapters; deterministic tests never construct a real model."""

    analyzer: PdfAnalyzer
    extractor: PdfExtractor
    renderer: PdfRenderer
    translator_factory: TranslatorFactory
    validator: OutputValidator = validate_output_pdf


def default_services(settings: Settings | None = None) -> PipelineServices:
    """Build production adapters without loading the heavyweight model yet."""
    selected_settings = settings or Settings()

    def create_translator(options: PipelineOptions, model_cache: Path) -> Translator:
        return NllbTranslator(
            model_name=options.model,
            source_language="en",
            target_language="ru",
            device=options.device,
            cache_dir=model_cache,
            offline=options.offline,
            max_input_tokens=options.max_input_tokens,
        )

    return PipelineServices(
        analyzer=PdfAnalyzer(selected_settings),
        extractor=PdfExtractor(selected_settings),
        renderer=PdfRenderer(),
        translator_factory=create_translator,
    )


def plan_pipeline(
    options: PipelineOptions,
    *,
    services: PipelineServices | None = None,
) -> DryRunResult:
    """Inspect and estimate selected pages without model construction or persistent artifacts."""
    selected_services = services or default_services()
    try:
        _validate_paths(options, allow_existing_output=True)
        inspection = selected_services.analyzer.inspect(options.input_path)
        extracted = selected_services.extractor.extract(options.input_path, options.pages)
    except (PdfInputError, OSError) as error:
        raise PipelineExecutionError(
            str(error),
            exit_code=ExitCode.PDF_INPUT_ERROR,
            stage=PipelineStage.INSPECT,
        ) from error
    except ValueError as error:
        raise PipelineExecutionError(
            str(error),
            exit_code=ExitCode.INVALID_ARGUMENTS,
        ) from error
    classifications = tuple(page.classification.value for page in extracted.pages)
    return DryRunResult(
        inspection=inspection,
        selected_pages=extracted.selected_pages,
        selected_page_classifications=classifications,
        estimated_text_blocks=sum(len(page.text_blocks) for page in extracted.pages),
        ocr_required=any(value == "scanned" for value in classifications),
        backend=options.backend,
        device=options.device,
        output_path=options.output_path.expanduser().resolve(),
    )


def run_pipeline(
    options: PipelineOptions,
    *,
    services: PipelineServices | None = None,
    stage_progress: StageCallback | None = None,
    translation_progress: TranslationCallback | None = None,
) -> PipelineResult:
    """Run or resume all stages and publish only a separately validated final PDF."""
    selected_services = services or default_services()
    try:
        _validate_paths(options, allow_existing_output=options.resume or options.overwrite)
        source = source_identity(options.input_path.expanduser().resolve())
        settings = Settings()
        cache_root = (options.cache_dir or settings.cache_dir).expanduser().resolve()
        workspace = PipelineWorkspace.prepare(cache_root, source, options)
    except (PdfInputError, OSError) as error:
        raise PipelineExecutionError(
            str(error),
            exit_code=ExitCode.PDF_INPUT_ERROR,
            stage=PipelineStage.INSPECT,
        ) from error
    except (PipelineStateError, ValueError) as error:
        raise PipelineExecutionError(
            str(error),
            exit_code=ExitCode.INVALID_ARGUMENTS,
        ) from error

    current_stage = PipelineStage.INSPECT
    reused: list[PipelineStage] = []
    try:
        _inspect(
            options,
            workspace,
            selected_services,
            reused,
            stage_progress,
        )
        current_stage = PipelineStage.EXTRACT
        extracted = _extract(
            options,
            workspace,
            selected_services,
            reused,
            stage_progress,
        )
        scanned_pages = tuple(
            page.page_number for page in extracted.pages if page.classification.value == "scanned"
        )
        if scanned_pages:
            pages = ", ".join(str(number) for number in scanned_pages)
            raise OcrRequiredError(
                f"OCR is required for selected scanned page(s): {pages}; OCR is not implemented"
            )

        current_stage = PipelineStage.TRANSLATE
        translated = _translate(
            options,
            workspace,
            extracted,
            selected_services,
            reused,
            stage_progress,
            translation_progress,
        )
        current_stage = PipelineStage.RENDER
        _render(
            options,
            workspace,
            translated,
            selected_services,
            reused,
            stage_progress,
        )
        current_stage = PipelineStage.VALIDATE
        file_size = _validate_and_publish(
            options,
            workspace,
            translated,
            selected_services,
            reused,
            stage_progress,
        )
    except (KeyboardInterrupt, TranslationInterruptedError) as error:
        _record_and_raise(
            workspace,
            current_stage,
            error,
            ExitCode.INTERRUPTED,
            interrupted=True,
        )
    except Exception as error:
        _record_and_raise(
            workspace,
            current_stage,
            error,
            _exit_code_for(error, current_stage),
            interrupted=False,
        )

    metadata = translated.translation
    assert metadata is not None
    workspace.log(f"pipeline completed: {options.output_path.expanduser().resolve()}")
    return PipelineResult(
        output_path=options.output_path.expanduser().resolve(),
        workspace_path=workspace.path,
        run_id=workspace.run_id,
        reused_stages=tuple(reused),
        statistics=metadata.statistics,
        file_size=file_size,
    )


def _inspect(
    options: PipelineOptions,
    workspace: PipelineWorkspace,
    services: PipelineServices,
    reused: list[PipelineStage],
    callback: StageCallback | None,
) -> InspectionReport:
    stage = PipelineStage.INSPECT
    if options.resume and workspace.can_reuse(stage):
        report = workspace.read_inspection()
        if report.source != workspace.manifest.source:
            raise PipelineStateError("inspection artifact belongs to a different source")
        _announce(stage, True, reused, callback, workspace)
        return report
    _announce(stage, False, reused, callback, workspace)
    report = services.analyzer.inspect(options.input_path)
    workspace.write_inspection(report)
    workspace.mark_completed(stage, workspace.inspection_path)
    return report


def _extract(
    options: PipelineOptions,
    workspace: PipelineWorkspace,
    services: PipelineServices,
    reused: list[PipelineStage],
    callback: StageCallback | None,
) -> ExtractedDocument:
    stage = PipelineStage.EXTRACT
    if options.resume and workspace.can_reuse(stage):
        document = workspace.read_document(workspace.extracted_path)
        if document.source != workspace.manifest.source or document.translation is not None:
            raise PipelineStateError("extracted artifact is incompatible with this run")
        _announce(stage, True, reused, callback, workspace)
        return document
    _announce(stage, False, reused, callback, workspace)
    document = services.extractor.extract(options.input_path, options.pages)
    workspace.write_document(document, workspace.extracted_path)
    workspace.mark_completed(stage, workspace.extracted_path)
    return document


def _translate(
    options: PipelineOptions,
    workspace: PipelineWorkspace,
    extracted: ExtractedDocument,
    services: PipelineServices,
    reused: list[PipelineStage],
    stage_callback: StageCallback | None,
    translation_callback: TranslationCallback | None,
) -> ExtractedDocument:
    stage = PipelineStage.TRANSLATE
    if options.resume and workspace.can_reuse(stage):
        document = workspace.read_document(workspace.translated_path)
        _validate_completed_translation(document, extracted, options)
        _announce(stage, True, reused, stage_callback, workspace)
        return document

    _announce(stage, False, reused, stage_callback, workspace)
    resume_document = None
    if options.resume and workspace.translated_path.is_file():
        resume_document = workspace.read_document(workspace.translated_path)
    try:
        translator = services.translator_factory(options, workspace.path.parent.parent / "models")
    except TranslationError as error:
        raise ModelUnavailableError(str(error)) from error

    def checkpoint(document: ExtractedDocument) -> None:
        workspace.write_document(document, workspace.translated_path)

    with TranslationCache(workspace.path.parent.parent / "translation-memory.sqlite3") as cache:
        translated = translate_document(
            extracted,
            translator=translator,
            cache=cache,
            options=TranslationOptions(
                source_language="en",
                target_language="ru",
                batch_size=options.batch_size,
                max_input_tokens=options.max_input_tokens,
            ),
            resume_document=resume_document,
            checkpoint=checkpoint,
            progress=translation_callback,
        )
    workspace.mark_completed(stage, workspace.translated_path)
    return translated


def _render(
    options: PipelineOptions,
    workspace: PipelineWorkspace,
    translated: ExtractedDocument,
    services: PipelineServices,
    reused: list[PipelineStage],
    callback: StageCallback | None,
) -> None:
    stage = PipelineStage.RENDER
    if options.resume and workspace.can_reuse(stage):
        services.validator(workspace.rendered_path, translated.page_count)
        _announce(stage, True, reused, callback, workspace)
        return
    _announce(stage, False, reused, callback, workspace)
    services.renderer.render(
        options.input_path,
        translated,
        workspace.rendered_path,
        font_path=options.font_path,
        options=RenderOptions(
            min_font_size=options.min_font_size,
            font_size_step=options.font_size_step,
            line_height=options.line_height,
            redaction_padding=options.redaction_padding,
            allow_expand=options.allow_expand,
            overwrite=True,
        ),
    )
    workspace.mark_completed(stage, workspace.rendered_path)


def _validate_and_publish(
    options: PipelineOptions,
    workspace: PipelineWorkspace,
    translated: ExtractedDocument,
    services: PipelineServices,
    reused: list[PipelineStage],
    callback: StageCallback | None,
) -> int:
    stage = PipelineStage.VALIDATE
    output = options.output_path.expanduser().resolve()
    if options.resume and workspace.can_reuse(stage):
        size = services.validator(output, translated.page_count)
        _announce(stage, True, reused, callback, workspace)
        return size
    if output.exists() and not options.overwrite:
        raise OutputValidationError(f"output already exists; use --overwrite: {output}")
    _announce(stage, False, reused, callback, workspace)
    services.validator(workspace.rendered_path, translated.page_count)
    size = _publish_atomically(
        workspace.rendered_path,
        output,
        translated.page_count,
        services.validator,
    )
    workspace.mark_completed(stage, output)
    return size


def _publish_atomically(
    candidate: Path,
    output: Path,
    page_count: int,
    validator: OutputValidator,
) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            prefix=f".{output.stem}.",
            suffix=".tmp.pdf",
            dir=output.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            with candidate.open("rb") as source_file:
                shutil.copyfileobj(source_file, temporary)
            temporary.flush()
            os.fsync(temporary.fileno())
        size = validator(temporary_path, page_count)
        temporary_path.replace(output)
        return size
    except (OSError, OutputPdfError) as error:
        raise OutputValidationError(str(error)) from error
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _validate_completed_translation(
    translated: ExtractedDocument,
    extracted: ExtractedDocument,
    options: PipelineOptions,
) -> None:
    metadata = translated.translation
    if (
        translated.source != extracted.source
        or translated.selected_pages != extracted.selected_pages
        or metadata is None
        or metadata.status != "completed"
        or metadata.backend != options.backend
        or metadata.model != options.model
        or metadata.batch_size != options.batch_size
        or metadata.max_input_tokens != options.max_input_tokens
    ):
        raise PipelineStateError("translated artifact is incompatible or incomplete")


def _validate_paths(options: PipelineOptions, *, allow_existing_output: bool) -> None:
    source = options.input_path.expanduser().resolve()
    output = options.output_path.expanduser().resolve()
    if not source.is_file():
        raise PdfInputError(f"PDF input file does not exist: {source}")
    if source.suffix.lower() != ".pdf":
        raise PdfInputError(f"input must have a .pdf extension: {source}")
    if output.suffix.lower() != ".pdf":
        raise ValueError(f"output must have a .pdf extension: {output}")
    if output == source:
        raise ValueError("output path must not be the source PDF")
    if output.exists() and not output.is_file():
        raise ValueError(f"output path is not a file: {output}")
    if output.exists() and not allow_existing_output:
        raise OutputExistsError(f"output already exists; use --overwrite: {output}")


def _announce(
    stage: PipelineStage,
    was_reused: bool,
    reused: list[PipelineStage],
    callback: StageCallback | None,
    workspace: PipelineWorkspace,
) -> None:
    if was_reused:
        reused.append(stage)
    progress = StageProgress(
        index=list(PipelineStage).index(stage) + 1,
        total=len(PipelineStage),
        stage=stage,
        reused=was_reused,
    )
    workspace.log(f"stage {stage.value} {'reused' if was_reused else 'started'}")
    if callback is not None:
        callback(progress)


def _exit_code_for(error: Exception, stage: PipelineStage) -> ExitCode:
    if isinstance(error, OcrRequiredError):
        return ExitCode.OCR_REQUIRED
    if isinstance(error, ModelUnavailableError):
        return ExitCode.MODEL_UNAVAILABLE
    if isinstance(error, OutputValidationError) or stage == PipelineStage.VALIDATE:
        return ExitCode.OUTPUT_VALIDATION_FAILED
    if isinstance(error, RenderingError) or stage == PipelineStage.RENDER:
        return ExitCode.RENDERING_FAILED
    if isinstance(error, TranslationError) or stage == PipelineStage.TRANSLATE:
        return ExitCode.TRANSLATION_FAILED
    if isinstance(error, PdfInputError):
        return ExitCode.PDF_INPUT_ERROR
    if isinstance(error, PipelineStateError | OutputExistsError | ValueError):
        return ExitCode.INVALID_ARGUMENTS
    if stage in {PipelineStage.INSPECT, PipelineStage.EXTRACT}:
        return ExitCode.PDF_INPUT_ERROR
    return ExitCode.INVALID_ARGUMENTS


def _record_and_raise(
    workspace: PipelineWorkspace,
    stage: PipelineStage,
    error: BaseException,
    exit_code: ExitCode,
    *,
    interrupted: bool,
) -> None:
    workspace.record_failure(
        stage,
        str(error) or type(error).__name__,
        interrupted=interrupted,
        details=traceback.format_exc(),
    )
    raise PipelineExecutionError(
        str(error) or type(error).__name__,
        exit_code=exit_code,
        stage=stage,
        log_path=workspace.log_path,
    ) from error
