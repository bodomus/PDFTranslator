"""Typer-independent inspect-to-validation orchestration."""

from __future__ import annotations

import os
import shutil
import time
import traceback
import tracemalloc
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from pdftranslate.config import Settings
from pdftranslate.diagnostics.builder import build_failure_report, build_success_report
from pdftranslate.diagnostics.reporting import write_report
from pdftranslate.domain.document import ExtractedDocument, InspectionReport
from pdftranslate.ocr import OcrError, OcrOptions, OcrProcessor, validate_ocr_output
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
    RenderResult,
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
    ocr_processor: OcrProcessor = field(default_factory=OcrProcessor)


@dataclass
class TranslationRuntime:
    """One lazily initialized translator and open cache shared across documents."""

    translator_factory: TranslatorFactory
    cache_root: Path
    model_cache: Path
    cache: TranslationCache
    _translator: Translator | None = None
    _identity: tuple[str, str, str, int, bool, str] | None = None

    def translator_for(self, options: PipelineOptions) -> Translator:
        """Create the model once and reject incompatible reuse."""
        requested_cache_root = (options.cache_dir or Settings().cache_dir).expanduser().resolve()
        if requested_cache_root != self.cache_root:
            raise ValueError("shared translation runtime cache root does not match this document")
        identity = (
            options.backend,
            options.model,
            options.device,
            options.max_input_tokens,
            options.offline,
            str(requested_cache_root),
        )
        if self._identity is not None and self._identity != identity:
            raise ValueError("shared translation runtime settings do not match this document")
        if self._translator is None:
            self._translator = self.translator_factory(options, self.model_cache)
            self._identity = identity
        return self._translator


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
        ocr_processor=OcrProcessor(),
    )


@contextmanager
def open_translation_runtime(
    options: PipelineOptions,
    *,
    services: PipelineServices | None = None,
) -> Iterator[TranslationRuntime]:
    """Open one cache and lazily construct one translator for repeated pipeline runs."""
    selected_services = services or default_services()
    settings = Settings()
    cache_root = (options.cache_dir or settings.cache_dir).expanduser().resolve()
    with TranslationCache(cache_root / "translation-memory.sqlite3") as cache:
        yield TranslationRuntime(
            translator_factory=selected_services.translator_factory,
            cache_root=cache_root,
            model_cache=cache_root / "models",
            cache=cache,
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
    scanned_pages = _scanned_pages(extracted)
    ocr_pages = _reported_ocr_pages(extracted, options)
    return DryRunResult(
        inspection=inspection,
        selected_pages=extracted.selected_pages,
        selected_page_classifications=classifications,
        estimated_text_blocks=sum(len(page.text_blocks) for page in extracted.pages),
        ocr_required=bool(scanned_pages),
        ocr_will_run=options.ocr == "on" or (options.ocr == "auto" and bool(scanned_pages)),
        ocr_pages=ocr_pages,
        backend=options.backend,
        device=options.device,
        output_path=options.output_path.expanduser().resolve(),
    )


def run_pipeline(
    options: PipelineOptions,
    *,
    services: PipelineServices | None = None,
    translation_runtime: TranslationRuntime | None = None,
    stage_progress: StageCallback | None = None,
    translation_progress: TranslationCallback | None = None,
) -> PipelineResult:
    """Run or resume all stages and publish only a separately validated final PDF."""
    started_at = datetime.now(UTC)
    started_perf = time.perf_counter()
    owns_memory_trace = options.report and not tracemalloc.is_tracing()
    if owns_memory_trace:
        tracemalloc.start()
    selected_services = services or default_services()
    try:
        _validate_paths(options, allow_existing_output=options.resume or options.overwrite)
        source = source_identity(options.input_path.expanduser().resolve())
        settings = Settings()
        cache_root = (options.cache_dir or settings.cache_dir).expanduser().resolve()
        workspace = PipelineWorkspace.prepare(cache_root, source, options)
    except (PdfInputError, OSError) as error:
        if owns_memory_trace and tracemalloc.is_tracing():
            tracemalloc.stop()
        raise PipelineExecutionError(
            str(error),
            exit_code=ExitCode.PDF_INPUT_ERROR,
            stage=PipelineStage.INSPECT,
        ) from error
    except (PipelineStateError, ValueError) as error:
        if owns_memory_trace and tracemalloc.is_tracing():
            tracemalloc.stop()
        raise PipelineExecutionError(
            str(error),
            exit_code=ExitCode.INVALID_ARGUMENTS,
        ) from error

    current_stage = PipelineStage.INSPECT
    stage_durations: dict[str, float] = {}
    block_evidence: dict[str, tuple[int | None, str]] = {}

    def capture_translation_progress(event: TranslationProgress) -> None:
        block_evidence[event.block_id] = (event.segmentation_count, event.cache_status)
        if translation_progress is not None:
            translation_progress(event)

    stage_started = time.perf_counter()
    reused: list[PipelineStage] = []
    try:
        _inspect(
            options,
            workspace,
            selected_services,
            reused,
            stage_progress,
        )
        stage_durations[PipelineStage.INSPECT.value] = time.perf_counter() - stage_started
        current_stage = PipelineStage.OCR
        stage_started = time.perf_counter()
        working_pdf, pre_extracted, ocr_status, ocr_pages, ocr_warnings = _ocr(
            options,
            workspace,
            selected_services,
            reused,
            stage_progress,
        )
        stage_durations[PipelineStage.OCR.value] = time.perf_counter() - stage_started
        current_stage = PipelineStage.EXTRACT
        stage_started = time.perf_counter()
        extracted = _extract(
            options,
            working_pdf,
            pre_extracted,
            workspace,
            selected_services,
            reused,
            stage_progress,
        )

        stage_durations[PipelineStage.EXTRACT.value] = time.perf_counter() - stage_started
        current_stage = PipelineStage.TRANSLATE
        stage_started = time.perf_counter()
        translated = _translate(
            options,
            workspace,
            extracted,
            selected_services,
            translation_runtime,
            reused,
            stage_progress,
            capture_translation_progress,
        )
        stage_durations[PipelineStage.TRANSLATE.value] = time.perf_counter() - stage_started
        current_stage = PipelineStage.RENDER
        stage_started = time.perf_counter()
        render_result = _render(
            options,
            workspace,
            translated,
            working_pdf,
            selected_services,
            reused,
            stage_progress,
        )
        stage_durations[PipelineStage.RENDER.value] = time.perf_counter() - stage_started
        current_stage = PipelineStage.VALIDATE
        stage_started = time.perf_counter()
        file_size = _validate_and_publish(
            options,
            workspace,
            translated,
            selected_services,
            reused,
            stage_progress,
        )
        stage_durations[PipelineStage.VALIDATE.value] = time.perf_counter() - stage_started
    except (KeyboardInterrupt, TranslationInterruptedError) as error:
        stage_durations.setdefault(current_stage.value, time.perf_counter() - stage_started)
        _write_failure_diagnostics(
            options,
            workspace,
            current_stage,
            error,
            started_at,
            started_perf,
            owns_memory_trace,
            stage_durations,
            interrupted=True,
        )
        _record_and_raise(
            workspace,
            current_stage,
            error,
            ExitCode.INTERRUPTED,
            interrupted=True,
        )
    except Exception as error:
        stage_durations.setdefault(current_stage.value, time.perf_counter() - stage_started)
        _write_failure_diagnostics(
            options,
            workspace,
            current_stage,
            error,
            started_at,
            started_perf,
            owns_memory_trace,
            stage_durations,
            interrupted=False,
        )
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
    report_paths: tuple[Path, ...] = ()
    debug_layout_path: Path | None = None
    try:
        report_directory = _report_directory(options)
        if options.debug_layout:
            debug_layout_path = _publish_debug_layout(render_result, report_directory)
        if options.report:
            report = build_success_report(
                run_id=workspace.run_id,
                started_at=started_at,
                finished_at=datetime.now(UTC),
                input_path=options.input_path.expanduser().resolve(),
                output_path=options.output_path.expanduser().resolve(),
                translated=translated,
                render=render_result,
                ocr_pages=ocr_pages,
                ocr_warnings=ocr_warnings,
                elapsed_seconds=time.perf_counter() - started_perf,
                stage_durations=stage_durations,
                peak_ram_bytes=_memory_peak(owns_memory_trace),
                include_text=options.include_report_text,
                debug_layout_path=debug_layout_path,
                block_evidence=block_evidence,
            )
            report_paths = write_report(
                report, report_directory, report_format=options.report_format
            )
    finally:
        if owns_memory_trace and tracemalloc.is_tracing():
            tracemalloc.stop()
    return PipelineResult(
        output_path=options.output_path.expanduser().resolve(),
        workspace_path=workspace.path,
        run_id=workspace.run_id,
        reused_stages=tuple(reused),
        statistics=metadata.statistics,
        file_size=file_size,
        ocr_status=ocr_status,
        ocr_pages=ocr_pages,
        ocr_warnings=ocr_warnings,
        pages_processed=len(translated.selected_pages),
        report_paths=report_paths,
        debug_layout_path=debug_layout_path,
    )


def _report_directory(options: PipelineOptions) -> Path:
    selected = options.report_dir or options.output_path.expanduser().resolve().parent
    return selected.expanduser().resolve()


def _memory_peak(owns_trace: bool) -> int | None:
    if not owns_trace or not tracemalloc.is_tracing():
        return None
    return tracemalloc.get_traced_memory()[1]


def _publish_debug_layout(render: RenderResult | None, directory: Path) -> Path | None:
    if render is None or render.debug_output_path is None:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "debug-layout.pdf"
    temporary = directory / ".debug-layout.tmp.pdf"
    try:
        shutil.copy2(render.debug_output_path, temporary)
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def _write_failure_diagnostics(
    options: PipelineOptions,
    workspace: PipelineWorkspace,
    stage: PipelineStage,
    error: BaseException,
    started_at: datetime,
    started_perf: float,
    owns_memory_trace: bool,
    stage_durations: dict[str, float],
    *,
    interrupted: bool,
) -> None:
    if not options.report:
        if owns_memory_trace and tracemalloc.is_tracing():
            tracemalloc.stop()
        return
    try:
        source_size = options.input_path.expanduser().resolve().stat().st_size
        report = build_failure_report(
            run_id=workspace.run_id,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            input_path=options.input_path.expanduser().resolve(),
            output_path=options.output_path.expanduser().resolve(),
            failed_stage=stage.value,
            message=str(error),
            input_size=source_size,
            elapsed_seconds=time.perf_counter() - started_perf,
            stage_durations=stage_durations,
            peak_ram_bytes=_memory_peak(owns_memory_trace),
            interrupted=interrupted,
        )
        write_report(report, _report_directory(options), report_format=options.report_format)
    except Exception as report_error:
        workspace.log(f"diagnostic report publication failed: {report_error}")
    finally:
        if owns_memory_trace and tracemalloc.is_tracing():
            tracemalloc.stop()


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


def _ocr(
    options: PipelineOptions,
    workspace: PipelineWorkspace,
    services: PipelineServices,
    reused: list[PipelineStage],
    callback: StageCallback | None,
) -> tuple[
    Path,
    ExtractedDocument,
    Literal["skipped", "processed", "reused"],
    tuple[int, ...],
    tuple[str, ...],
]:
    stage = PipelineStage.OCR
    source_path = options.input_path.expanduser().resolve()
    before = services.extractor.extract(source_path, options.pages)
    scanned_pages = _scanned_pages(before)
    target_pages = before.selected_pages if options.ocr == "on" else scanned_pages
    reported_pages = _reported_ocr_pages(before, options)

    if options.ocr == "off" and scanned_pages:
        pages = ", ".join(str(number) for number in scanned_pages)
        raise OcrRequiredError(
            f"OCR is required for selected scanned page(s): {pages}; rerun with --ocr auto or on"
        )

    if options.resume and workspace.can_reuse(stage):
        artifact = workspace.completed_artifact(stage).resolve()
        after = before
        warnings: tuple[str, ...] = ()
        if artifact != source_path:
            after = services.extractor.extract(artifact, options.pages)
            warnings = validate_ocr_output(
                source_path,
                artifact,
                before,
                after,
                reported_pages,
            )
        _announce(stage, True, reused, callback, workspace)
        return (
            artifact,
            after,
            "reused",
            reported_pages if artifact != source_path else (),
            warnings,
        )

    should_run = options.ocr == "on" or (options.ocr == "auto" and bool(scanned_pages))
    _announce(stage, False, reused, callback, workspace)
    if not should_run:
        workspace.log(
            "OCR skipped: selected pages contain no scanned pages; mixed/text layers preserved"
        )
        workspace.mark_completed(stage, source_path)
        return source_path, before, "skipped", (), ()

    execution = services.ocr_processor.process(
        source_path,
        workspace.ocr_path,
        log_path=workspace.ocr_log_path,
        sidecar_path=workspace.ocr_sidecar_path,
        pages=target_pages,
        options=OcrOptions(
            mode=options.ocr,
            language=options.ocr_language,
            deskew=options.ocr_deskew,
            clean=options.ocr_clean,
            rotate_pages=options.ocr_rotate_pages,
            force=options.ocr_force,
        ),
    )
    after = services.extractor.extract(execution.output_path, options.pages)
    warnings = validate_ocr_output(
        source_path,
        execution.output_path,
        before,
        after,
        reported_pages,
    )
    workspace.mark_completed(stage, execution.output_path)
    workspace.log(
        f"OCR processed {len(reported_pages)} page(s): "
        + ", ".join(str(page) for page in reported_pages)
    )
    for warning in warnings:
        workspace.log(f"OCR warning: {warning}")
    return (
        execution.output_path,
        after,
        "processed",
        reported_pages,
        warnings,
    )


def _reported_ocr_pages(
    document: ExtractedDocument,
    options: PipelineOptions,
) -> tuple[int, ...]:
    if options.ocr == "auto":
        return _scanned_pages(document)
    if options.ocr == "on" and options.ocr_force:
        return document.selected_pages
    if options.ocr == "on":
        return tuple(
            page.page_number
            for page in document.pages
            if page.classification.value in {"scanned", "empty"}
        )
    return ()


def _scanned_pages(document: ExtractedDocument) -> tuple[int, ...]:
    return tuple(
        page.page_number for page in document.pages if page.classification.value == "scanned"
    )


def _extract(
    options: PipelineOptions,
    working_pdf: Path,
    pre_extracted: ExtractedDocument,
    workspace: PipelineWorkspace,
    services: PipelineServices,
    reused: list[PipelineStage],
    callback: StageCallback | None,
) -> ExtractedDocument:
    stage = PipelineStage.EXTRACT
    if options.resume and workspace.can_reuse(stage):
        document = workspace.read_document(workspace.extracted_path)
        if document.source != source_identity(working_pdf) or document.translation is not None:
            raise PipelineStateError("extracted artifact is incompatible with this run")
        _announce(stage, True, reused, callback, workspace)
        return document
    _announce(stage, False, reused, callback, workspace)
    document = pre_extracted
    workspace.write_document(document, workspace.extracted_path)
    workspace.mark_completed(stage, workspace.extracted_path)
    return document


def _translate(
    options: PipelineOptions,
    workspace: PipelineWorkspace,
    extracted: ExtractedDocument,
    services: PipelineServices,
    translation_runtime: TranslationRuntime | None,
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
    if translation_runtime is None:
        with open_translation_runtime(options, services=services) as owned_runtime:
            return _translate_with_runtime(
                options,
                workspace,
                extracted,
                resume_document,
                owned_runtime,
                translation_callback,
            )
    return _translate_with_runtime(
        options,
        workspace,
        extracted,
        resume_document,
        translation_runtime,
        translation_callback,
    )


def _translate_with_runtime(
    options: PipelineOptions,
    workspace: PipelineWorkspace,
    extracted: ExtractedDocument,
    resume_document: ExtractedDocument | None,
    runtime: TranslationRuntime,
    translation_callback: TranslationCallback | None,
) -> ExtractedDocument:
    try:
        translator = runtime.translator_for(options)
    except TranslationError as error:
        raise ModelUnavailableError(str(error)) from error

    def checkpoint(document: ExtractedDocument) -> None:
        workspace.write_document(document, workspace.translated_path)

    translated = translate_document(
        extracted,
        translator=translator,
        cache=runtime.cache,
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
    workspace.mark_completed(PipelineStage.TRANSLATE, workspace.translated_path)
    return translated


def _render(
    options: PipelineOptions,
    workspace: PipelineWorkspace,
    translated: ExtractedDocument,
    working_pdf: Path,
    services: PipelineServices,
    reused: list[PipelineStage],
    callback: StageCallback | None,
) -> RenderResult | None:
    stage = PipelineStage.RENDER
    if (
        options.resume
        and workspace.can_reuse(stage)
        and not (options.debug_layout or options.report)
    ):
        services.validator(workspace.rendered_path, translated.page_count)
        _announce(stage, True, reused, callback, workspace)
        return None
    _announce(stage, False, reused, callback, workspace)
    result = services.renderer.render(
        working_pdf,
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
            debug_layout=options.debug_layout,
        ),
    )
    workspace.mark_completed(stage, workspace.rendered_path)
    return result


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
    if isinstance(error, OcrError) or stage == PipelineStage.OCR:
        return ExitCode.OCR_FAILED
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
