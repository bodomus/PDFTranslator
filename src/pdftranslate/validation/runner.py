"""Typer-independent orchestration for reproducible real-PDF validation."""

# ruff: noqa: E501

from __future__ import annotations

import fnmatch
import hashlib
import shutil
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Literal

from pdftranslate.pipeline import (
    ExitCode,
    PipelineExecutionError,
    PipelineOptions,
    PipelineServices,
    PipelineStage,
    StageProgress,
    default_services,
    open_translation_runtime,
    plan_pipeline,
    run_pipeline,
)
from pdftranslate.serialization import read_document_json
from pdftranslate.validation.models import (
    MANUAL_CHECK_NAMES,
    CorpusDocument,
    CorpusManifest,
    DocumentValidationResult,
    ManualReview,
    ManualReviewEntry,
    ManualReviewManifest,
    StageStatus,
    StageValidationResult,
    ValidationDefect,
    ValidationFailure,
    ValidationOptions,
    ValidationSummary,
)
from pdftranslate.validation.reporting import write_json, write_markdown


@dataclass(frozen=True)
class ValidationRunResult:
    """Published validation evidence and its in-memory models."""

    summary: ValidationSummary
    documents: tuple[DocumentValidationResult, ...]
    summary_json_path: Path
    summary_markdown_path: Path
    manual_template_path: Path


@dataclass(frozen=True)
class _SelectedDocument:
    descriptor: CorpusDocument
    source: Path
    relative_path: Path


class _StageTimer:
    def __init__(self) -> None:
        self._current: PipelineStage | None = None
        self._current_started = 0.0
        self._records: dict[PipelineStage, StageValidationResult] = {}
        self._reused = False

    def transition(self, event: StageProgress) -> None:
        now = perf_counter()
        self._finish_current(now, "reused" if self._reused else "passed")
        self._current = event.stage
        self._current_started = now
        self._reused = event.reused

    def succeed(self) -> None:
        self._finish_current(perf_counter(), "reused" if self._reused else "passed")

    def fail(self, stage: PipelineStage | None) -> None:
        now = perf_counter()
        if self._current is not None and (stage is None or self._current == stage):
            self._finish_current(now, "failed")
        else:
            self._finish_current(now, "reused" if self._reused else "passed")
            if stage is not None:
                self._records[stage] = StageValidationResult(
                    stage=stage,
                    status="failed",
                    elapsed_seconds=0.0,
                )

    def results(self) -> tuple[StageValidationResult, ...]:
        return tuple(
            self._records.get(
                stage,
                StageValidationResult(stage=stage, status="not_run", elapsed_seconds=0.0),
            )
            for stage in PipelineStage
        )

    def _finish_current(self, now: float, status: StageStatus) -> None:
        if self._current is None:
            return
        self._records[self._current] = StageValidationResult(
            stage=self._current,
            status=status,
            elapsed_seconds=max(0.0, now - self._current_started),
        )
        self._current = None


def run_validation(
    options: ValidationOptions,
    *,
    services: PipelineServices | None = None,
) -> ValidationRunResult:
    """Validate a selected corpus without ever modifying a source PDF."""
    started_at = datetime.now(UTC)
    started = perf_counter()
    root = options.resolved_corpus_root
    output_root = options.resolved_output_root
    if not root.is_dir():
        raise ValueError(f"corpus root does not exist or is not a directory: {root}")
    if output_root == root:
        raise ValueError("validation output root cannot equal the corpus root")

    discovered = _discover_documents(options)
    selected = _select_documents(discovered, options.subsets)
    if not selected:
        raise ValueError("no PDFs matched the selected corpus/subsets")
    reviews = _load_manual_reviews(options.manual_results_path)
    selected_services = services or default_services()
    documents: list[DocumentValidationResult] = []
    stopped = False

    output_root.mkdir(parents=True, exist_ok=True)
    runtime_context = (
        nullcontext(None)
        if options.dry_run
        else open_translation_runtime(
            _pipeline_options(selected[0], options),
            services=selected_services,
        )
    )

    with runtime_context as runtime:
        for item in selected:
            if stopped:
                result = _not_run_result(item, options, reviews.get(item.descriptor.document_id))
            else:
                result = _validate_document(
                    item,
                    options,
                    selected_services,
                    runtime,
                    reviews.get(item.descriptor.document_id),
                )
                if result.status == "failed" and not options.continue_on_error:
                    stopped = True
            documents.append(result)
            write_json(
                result,
                output_root / "document-results" / f"{item.descriptor.document_id}.json",
            )

    document_tuple = tuple(documents)
    defects = tuple(defect for item in document_tuple for defect in item.defects)
    finished_at = datetime.now(UTC)
    passed = sum(item.status == "passed" for item in document_tuple)
    failed = sum(item.status == "failed" for item in document_tuple)
    planned = sum(item.status == "planned" for item in document_tuple)
    manual_statuses = [item.manual_review.status for item in document_tuple]
    status: Literal["planned", "passed", "failed"]
    if failed:
        status = "failed"
    elif options.dry_run:
        status = "planned"
    else:
        status = "passed"
    summary = ValidationSummary(
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=max(0.0, perf_counter() - started),
        dry_run=options.dry_run,
        corpus_fingerprint=_corpus_fingerprint(discovered),
        selected_subsets=options.subsets,
        discovered_documents=len(discovered),
        selected_documents=len(selected),
        passed_documents=passed,
        failed_documents=failed,
        planned_documents=planned,
        source_integrity_failures=sum(not item.source_unchanged for item in document_tuple),
        manual_reviews_passed=manual_statuses.count("passed"),
        manual_reviews_failed=manual_statuses.count("failed"),
        manual_reviews_pending=sum(
            status in {"partial", "not_checked"} for status in manual_statuses
        ),
        categories_covered=tuple(
            sorted({category for item in selected for category in item.descriptor.categories})
        ),
        document_result_files=tuple(
            f"document-results/{item.descriptor.document_id}.json" for item in selected
        ),
        defects=defects,
    )
    summary_json = write_json(summary, output_root / "validation-summary.json")
    summary_markdown = write_markdown(
        summary,
        document_tuple,
        output_root / "validation-summary.md",
    )
    manual_template = ManualReviewManifest(
        documents=tuple(
            ManualReviewEntry(
                document_id=item.descriptor.document_id,
                review=reviews.get(item.descriptor.document_id, ManualReview()),
            )
            for item in selected
        )
    )
    manual_template_path = write_json(
        manual_template,
        output_root / "manual-review-template.json",
    )
    (output_root / "logs").mkdir(exist_ok=True)
    return ValidationRunResult(
        summary=summary,
        documents=document_tuple,
        summary_json_path=summary_json,
        summary_markdown_path=summary_markdown,
        manual_template_path=manual_template_path,
    )


def _validate_document(
    item: _SelectedDocument,
    options: ValidationOptions,
    services: PipelineServices,
    runtime: object,
    manual_review: ManualReview | None,
) -> DocumentValidationResult:
    started_at = datetime.now(UTC)
    started = perf_counter()
    source_sha, source_size = _file_identity(item.source)
    pipeline_options = _pipeline_options(item, options)
    review = manual_review or ManualReview()
    timer = _StageTimer()
    plan = None
    pipeline_result = None
    failure: ValidationFailure | None = None
    defects: list[ValidationDefect] = []
    warnings: list[str] = []
    workspace: Path | None = None

    try:
        plan = plan_pipeline(pipeline_options, services=services)
        warnings.extend(plan.inspection.warnings)
        if not options.dry_run:
            pipeline_result = run_pipeline(
                pipeline_options,
                services=services,
                translation_runtime=runtime,  # type: ignore[arg-type]
                stage_progress=timer.transition,
            )
            timer.succeed()
            workspace = pipeline_result.workspace_path
            warnings.extend(pipeline_result.ocr_warnings)
    except PipelineExecutionError as error:
        timer.fail(error.stage)
        diagnostics = _copy_log(error.log_path, item.descriptor.document_id, options)
        failure = ValidationFailure(
            exit_code=int(error.exit_code),
            stage=error.stage,
            error=str(error),
            diagnostics_log=diagnostics,
        )
        defects.append(_failure_defect(item.descriptor.document_id, error))
        if error.log_path is not None:
            workspace = error.log_path.parent
    except Exception as error:
        timer.fail(None)
        failure = ValidationFailure(
            exit_code=1,
            error=f"{type(error).__name__}: {error}",
        )
        defects.append(
            ValidationDefect(
                document_id=item.descriptor.document_id,
                severity="major",
                stage="harness",
                reproducibility="deterministic",
                summary="Validation harness could not complete the document",
                root_cause=f"{type(error).__name__}: {error}",
                recommended_follow_up="Create a focused validation-harness defect after PDFTR-8",
            )
        )

    source_after_sha: str | None = None
    source_after_size: int | None = None
    if item.source.is_file():
        source_after_sha, source_after_size = _file_identity(item.source)
    source_unchanged = source_sha == source_after_sha and source_size == source_after_size
    if not source_unchanged:
        defects.append(
            ValidationDefect(
                document_id=item.descriptor.document_id,
                severity="critical",
                stage="source-integrity",
                reproducibility="deterministic",
                summary="Source PDF identity changed during validation",
                root_cause="The source size or SHA-256 differs from the pre-run identity",
                recommended_follow_up="Stop validation and create an immediate source-safety ticket",
            )
        )

    effective_device = None
    cache_hits = cache_misses = 0
    if workspace is not None:
        translated_path = workspace / "translated.json"
        if translated_path.is_file():
            try:
                translated = read_document_json(translated_path)
                if translated.translation is not None:
                    effective_device = translated.translation.effective_device
                    cache_hits = translated.translation.statistics.cache_hits
                    cache_misses = translated.translation.statistics.cache_misses
                    warnings.extend(translated.translation.warnings)
            except Exception as error:
                warnings.append(f"could not read translated metadata: {error}")

    if not options.dry_run:
        defects.extend(_manual_defects(item.descriptor.document_id, review))
    status: Literal["planned", "passed", "failed"]
    if (
        failure is not None
        or not source_unchanged
        or (not options.dry_run and review.status == "failed")
    ):
        status = "failed"
    elif options.dry_run:
        status = "planned"
    else:
        status = "passed"

    if options.dry_run:
        stage_results = tuple(
            StageValidationResult(stage=stage, status="planned", elapsed_seconds=0.0)
            for stage in PipelineStage
        )
    else:
        stage_results = timer.results()
    output_relative = _output_relative_path(item).as_posix()
    output_path = options.resolved_output_root / output_relative
    if plan is None:
        ocr_decision = "unknown"
        ocr_pages: tuple[int, ...] = ()
    elif options.dry_run:
        ocr_decision = "would_run" if plan.ocr_will_run else "would_skip"
        ocr_pages = plan.ocr_pages
    elif pipeline_result is not None:
        ocr_decision = pipeline_result.ocr_status
        ocr_pages = pipeline_result.ocr_pages
    else:
        if failure is not None and failure.stage == PipelineStage.OCR:
            ocr_decision = "failed"
        elif plan.ocr_will_run:
            ocr_decision = (
                "processed"
                if workspace is not None and (workspace / "ocr.pdf").is_file()
                else "failed"
            )
        else:
            ocr_decision = "skipped"
        ocr_pages = plan.ocr_pages

    copied_log = None
    if pipeline_result is not None:
        copied_log = _copy_log(
            pipeline_result.workspace_path / "pipeline.log",
            item.descriptor.document_id,
            options,
        )
    if copied_log is not None:
        warnings.append(f"pipeline log: {copied_log}")
    finished_at = datetime.now(UTC)
    return DocumentValidationResult(
        document_id=item.descriptor.document_id,
        relative_path=item.relative_path.as_posix(),
        categories=item.descriptor.categories,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=max(0.0, perf_counter() - started),
        source_sha256_before=source_sha,
        source_sha256_after=source_after_sha,
        source_size_before=source_size,
        source_size_after=source_after_size,
        source_unchanged=source_unchanged,
        page_count=plan.inspection.page_count if plan is not None else None,
        page_classifications=plan.selected_page_classifications if plan is not None else (),
        stage_results=stage_results,
        backend=options.backend,
        requested_device=options.device,
        effective_device=effective_device,
        ocr_decision=ocr_decision,
        ocr_pages=ocr_pages,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        resume_requested=options.resume,
        reused_stages=pipeline_result.reused_stages if pipeline_result is not None else (),
        output_relative_path=output_relative if output_path.is_file() else None,
        output_size=output_path.stat().st_size if output_path.is_file() else None,
        workspace_size=_directory_size(workspace) if workspace is not None else None,
        warnings=tuple(dict.fromkeys(warnings)),
        failure=failure,
        manual_review=review,
        defects=tuple(defects),
    )


def _not_run_result(
    item: _SelectedDocument,
    options: ValidationOptions,
    manual_review: ManualReview | None,
) -> DocumentValidationResult:
    now = datetime.now(UTC)
    sha256, size = _file_identity(item.source)
    defect = ValidationDefect(
        document_id=item.descriptor.document_id,
        severity="normal",
        stage="harness",
        reproducibility="deterministic",
        summary="Document was not run after an earlier fail-fast error",
        root_cause="continue_on_error was disabled",
        recommended_follow_up="Rerun this subset independently after the preceding defect is fixed",
    )
    return DocumentValidationResult(
        document_id=item.descriptor.document_id,
        relative_path=item.relative_path.as_posix(),
        categories=item.descriptor.categories,
        status="failed",
        started_at=now,
        finished_at=now,
        elapsed_seconds=0.0,
        source_sha256_before=sha256,
        source_sha256_after=sha256,
        source_size_before=size,
        source_size_after=size,
        source_unchanged=True,
        stage_results=tuple(
            StageValidationResult(stage=stage, status="not_run", elapsed_seconds=0.0)
            for stage in PipelineStage
        ),
        backend=options.backend,
        requested_device=options.device,
        ocr_decision="not_run",
        failure=ValidationFailure(exit_code=1, error=defect.summary),
        manual_review=manual_review or ManualReview(),
        defects=(defect,),
    )


def _discover_documents(options: ValidationOptions) -> tuple[_SelectedDocument, ...]:
    root = options.resolved_corpus_root
    output_root = options.resolved_output_root
    if options.manifest_path is not None:
        manifest_path = options.manifest_path.expanduser().resolve()
        manifest = CorpusManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        descriptors = manifest.documents
    else:
        descriptors = tuple(
            CorpusDocument(
                document_id=_generated_id(path.relative_to(root)),
                path=path.relative_to(root).as_posix(),
            )
            for path in sorted(
                (
                    candidate.resolve()
                    for candidate in root.rglob("*")
                    if candidate.is_file()
                    and candidate.suffix.casefold() == ".pdf"
                    and not candidate.name.casefold().endswith(".ru.pdf")
                    and not candidate.resolve().is_relative_to(output_root)
                ),
                key=lambda path: path.as_posix().casefold(),
            )
        )
    selected: list[_SelectedDocument] = []
    seen_paths: set[Path] = set()
    for descriptor in descriptors:
        relative = Path(descriptor.path)
        if relative.is_absolute():
            raise ValueError(f"manifest paths must be relative: {descriptor.path}")
        source = (root / relative).resolve()
        if not source.is_relative_to(root):
            raise ValueError(f"manifest path escapes the corpus root: {descriptor.path}")
        if source.suffix.casefold() != ".pdf" or not source.is_file():
            raise ValueError(f"manifest PDF does not exist: {descriptor.path}")
        if source in seen_paths:
            raise ValueError(f"manifest contains the same PDF more than once: {descriptor.path}")
        seen_paths.add(source)
        selected.append(
            _SelectedDocument(
                descriptor=descriptor,
                source=source,
                relative_path=source.relative_to(root),
            )
        )
    return tuple(selected)


def _select_documents(
    documents: tuple[_SelectedDocument, ...],
    subsets: tuple[str, ...],
) -> tuple[_SelectedDocument, ...]:
    if not subsets:
        return documents
    selected: list[_SelectedDocument] = []
    matched = {subset: False for subset in subsets}
    for item in documents:
        for subset in subsets:
            folded = subset.casefold()
            if (
                folded == item.descriptor.document_id.casefold()
                or any(folded == category.casefold() for category in item.descriptor.categories)
                or fnmatch.fnmatch(item.relative_path.as_posix().casefold(), folded)
            ):
                matched[subset] = True
                selected.append(item)
                break
    missing = [subset for subset, found in matched.items() if not found]
    if missing:
        raise ValueError("subset(s) matched no documents: " + ", ".join(missing))
    return tuple(selected)


def _pipeline_options(item: _SelectedDocument, options: ValidationOptions) -> PipelineOptions:
    return PipelineOptions(
        input_path=item.source,
        output_path=options.resolved_output_root / _output_relative_path(item),
        pages=options.pages,
        backend=options.backend,
        model=options.model,
        device=options.device,
        batch_size=options.batch_size,
        max_input_tokens=options.max_input_tokens,
        cache_dir=options.cache_dir,
        offline=options.offline,
        resume=options.resume,
        overwrite=options.overwrite,
        font_path=options.font_path,
        ocr=options.ocr,
    )


def _output_relative_path(item: _SelectedDocument) -> Path:
    relative = item.relative_path
    return (Path("outputs") / relative).with_name(f"{relative.stem}.ru.pdf")


def _load_manual_reviews(path: Path | None) -> dict[str, ManualReview]:
    if path is None:
        return {}
    manifest = ManualReviewManifest.model_validate_json(
        path.expanduser().resolve().read_text(encoding="utf-8")
    )
    return {item.document_id: item.review for item in manifest.documents}


def _file_identity(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _corpus_fingerprint(documents: tuple[_SelectedDocument, ...]) -> str:
    digest = hashlib.sha256()
    for item in documents:
        source_sha, source_size = _file_identity(item.source)
        digest.update(item.descriptor.document_id.encode("utf-8"))
        digest.update(item.relative_path.as_posix().encode("utf-8"))
        digest.update(source_sha.encode("ascii"))
        digest.update(str(source_size).encode("ascii"))
    return digest.hexdigest()


def _generated_id(relative_path: Path) -> str:
    digest = hashlib.sha256(relative_path.as_posix().casefold().encode("utf-8")).hexdigest()[:12]
    return f"document-{digest}"


def _copy_log(path: Path | None, document_id: str, options: ValidationOptions) -> str | None:
    if path is None or not path.is_file():
        return None
    relative = Path("logs") / f"{document_id}.log"
    destination = options.resolved_output_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)
    return relative.as_posix()


def _directory_size(path: Path) -> int:
    return sum(candidate.stat().st_size for candidate in path.rglob("*") if candidate.is_file())


def _failure_defect(document_id: str, error: PipelineExecutionError) -> ValidationDefect:
    stage = error.stage.value if error.stage is not None else "arguments"
    severity: Literal["critical", "major", "normal", "minor"] = "major"
    if error.exit_code in {ExitCode.INVALID_ARGUMENTS, ExitCode.OCR_REQUIRED}:
        severity = "normal"
    follow_up = (
        "PDFTR-9 — Translation quality benchmark"
        if stage == PipelineStage.TRANSLATE.value
        else f"Create a focused {stage} stabilization ticket after PDFTR-8"
    )
    return ValidationDefect(
        document_id=document_id,
        severity=severity,
        stage=stage,
        reproducibility="deterministic",
        summary=f"{stage} stage failed with exit code {int(error.exit_code)}",
        root_cause=str(error),
        recommended_follow_up=follow_up,
    )


def _manual_defects(document_id: str, review: ManualReview) -> list[ValidationDefect]:
    return [
        ValidationDefect(
            document_id=document_id,
            severity="normal",
            stage="manual-review",
            reproducibility="deterministic",
            summary=f"PDF-XChange check failed: {name}",
            root_cause=review.notes or "Manual observation reported a failed compatibility check",
            recommended_follow_up="Create a layout/compatibility stabilization ticket after PDFTR-8",
        )
        for name in MANUAL_CHECK_NAMES
        if getattr(review, name) == "failed"
    ]
