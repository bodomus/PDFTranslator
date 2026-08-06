"""Sequential directory orchestration with one shared model and translation cache."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pdftranslate.batch.discovery import discover_pdfs
from pdftranslate.batch.models import (
    BatchFileFailure,
    BatchFileSuccess,
    BatchOptions,
    BatchProgress,
    BatchReport,
    BatchResult,
    BatchSkippedFile,
)
from pdftranslate.batch.reporting import write_batch_report
from pdftranslate.pipeline import (
    ExitCode,
    PipelineExecutionError,
    PipelineServices,
    default_services,
    open_translation_runtime,
    run_pipeline,
)
from pdftranslate.translation import TranslationError

BatchProgressCallback = Callable[[BatchProgress], None]


def run_batch(
    options: BatchOptions,
    *,
    services: PipelineServices | None = None,
    progress: BatchProgressCallback | None = None,
) -> BatchResult:
    """Discover and translate PDFs sequentially with shared heavyweight resources."""
    started_at = datetime.now(UTC)
    started_clock = time.perf_counter()
    discovery = discover_pdfs(options)
    input_root = options.resolved_input_dir
    output_root = options.resolved_output_dir
    report_path = options.resolved_report_path
    selected_services = services or default_services()
    if any(report_path == source for source in discovery.discovered_files):
        raise ValueError("batch report path must not replace a source PDF")
    skipped = list(discovery.skipped_files)
    tasks: list[tuple[Path, Path]] = []

    for source in discovery.selected_files:
        output = _output_path(source, input_root, output_root)
        if output == report_path:
            raise ValueError("batch report path must not replace an output PDF")
        if output.resolve() == source.resolve():
            skipped.append(_skip(source, output, "output path aliases source PDF"))
        elif output.exists() and not options.overwrite and not options.resume:
            skipped.append(_skip(source, output, "output exists; use --overwrite or --resume"))
        else:
            tasks.append((source, output))

    successful: list[BatchFileSuccess] = []
    failed: list[BatchFileFailure] = []
    interrupted = False
    if tasks:
        template = options.pipeline_options(*tasks[0])
        try:
            with open_translation_runtime(template, services=selected_services) as runtime:
                for index, (source, output) in enumerate(tasks, start=1):
                    if progress is not None:
                        progress(
                            BatchProgress(
                                index=index,
                                total=len(tasks),
                                input_path=source,
                                output_path=output,
                            )
                        )
                    file_started = time.perf_counter()
                    try:
                        result = run_pipeline(
                            options.pipeline_options(source, output),
                            services=selected_services,
                            translation_runtime=runtime,
                        )
                    except PipelineExecutionError as error:
                        failed.append(
                            BatchFileFailure(
                                input_path=str(source),
                                output_path=str(output),
                                exit_code=int(error.exit_code),
                                error=error.user_message,
                                diagnostics_path=(
                                    str(error.log_path) if error.log_path is not None else None
                                ),
                                elapsed_seconds=time.perf_counter() - file_started,
                            )
                        )
                        interrupted = error.exit_code == ExitCode.INTERRUPTED
                        must_stop = (
                            not options.continue_on_error
                            or interrupted
                            or error.exit_code == ExitCode.MODEL_UNAVAILABLE
                        )
                        if must_stop:
                            skipped.extend(
                                _remaining_skips(tasks[index:], "not processed after batch failure")
                            )
                            break
                    else:
                        statistics = result.statistics
                        successful.append(
                            BatchFileSuccess(
                                input_path=str(source),
                                output_path=str(result.output_path),
                                pages_processed=result.pages_processed,
                                ocr_pages=len(result.ocr_pages),
                                translated_blocks=(
                                    statistics.completed_blocks - statistics.skipped_blocks
                                ),
                                cache_hits=statistics.cache_hits,
                                elapsed_seconds=time.perf_counter() - file_started,
                                reused_stages=tuple(stage.value for stage in result.reused_stages),
                                glossary_fingerprint=(
                                    result.glossary.fingerprint
                                    if result.glossary is not None
                                    else None
                                ),
                                glossary_matched_entries=(
                                    result.glossary.statistics.matched_entries
                                    if result.glossary is not None
                                    else 0
                                ),
                                glossary_unmatched_entries=(
                                    result.glossary.statistics.unmatched_entries
                                    if result.glossary is not None
                                    else 0
                                ),
                                glossary_applied_occurrences=(
                                    result.glossary.statistics.applied_occurrences
                                    if result.glossary is not None
                                    else 0
                                ),
                                glossary_preserved_occurrences=(
                                    result.glossary.statistics.preserved_occurrences
                                    if result.glossary is not None
                                    else 0
                                ),
                                glossary_violations=(
                                    result.glossary.statistics.violations
                                    if result.glossary is not None
                                    else 0
                                ),
                            )
                        )
        except TranslationError as error:
            source, output = tasks[0]
            failed.append(
                BatchFileFailure(
                    input_path=str(source),
                    output_path=str(output),
                    exit_code=int(ExitCode.TRANSLATION_FAILED),
                    error=str(error),
                    elapsed_seconds=0.0,
                )
            )
            skipped.extend(_remaining_skips(tasks[1:], "translation cache unavailable"))

    finished_at = datetime.now(UTC)
    exit_code = _final_exit_code(failed, interrupted)
    report = BatchReport(
        status=_status(successful, failed, interrupted),
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=time.perf_counter() - started_clock,
        input_root=str(input_root),
        output_root=str(output_root),
        report_path=str(report_path),
        recursive=options.recursive,
        include_pattern=options.include_pattern,
        exclude_patterns=options.exclude_patterns,
        continue_on_error=options.continue_on_error,
        discovered_files=tuple(str(path) for path in discovery.discovered_files),
        successful_files=tuple(successful),
        failed_files=tuple(failed),
        skipped_files=tuple(skipped),
        pages_processed=sum(item.pages_processed for item in successful),
        ocr_pages=sum(item.ocr_pages for item in successful),
        translated_blocks=sum(item.translated_blocks for item in successful),
        cache_hits=sum(item.cache_hits for item in successful),
        final_exit_code=int(exit_code),
    )
    published = write_batch_report(report, report_path)
    return BatchResult(report=report, report_path=published, exit_code=exit_code)


def _output_path(source: Path, input_root: Path, output_root: Path) -> Path:
    relative = source.relative_to(input_root)
    return (output_root / relative).with_name(f"{relative.stem}.ru.pdf").resolve()


def _skip(source: Path, output: Path, reason: str) -> BatchSkippedFile:
    return BatchSkippedFile(input_path=str(source), output_path=str(output), reason=reason)


def _remaining_skips(
    tasks: list[tuple[Path, Path]],
    reason: str,
) -> list[BatchSkippedFile]:
    return [_skip(source, output, reason) for source, output in tasks]


def _final_exit_code(failed: list[BatchFileFailure], interrupted: bool) -> ExitCode:
    if interrupted:
        return ExitCode.INTERRUPTED
    return ExitCode.BATCH_FAILED if failed else ExitCode.SUCCESS


def _status(
    successful: list[BatchFileSuccess],
    failed: list[BatchFileFailure],
    interrupted: bool,
) -> Literal["completed", "partial", "failed", "interrupted"]:
    if interrupted:
        return "interrupted"
    if failed and successful:
        return "partial"
    if failed:
        return "failed"
    return "completed"
