"""Command-line interface for PDFTranslate."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Annotated, Any, Never, Protocol, cast

import typer
from rich.console import Console
from rich.table import Table
from typer.core import TyperGroup

from pdftranslate import __version__
from pdftranslate.config import Settings
from pdftranslate.domain.document import ExtractedDocument, InspectionReport
from pdftranslate.logging_config import configure_logging
from pdftranslate.pdf import PdfAnalyzer, PdfExtractor, PdfInputError
from pdftranslate.pipeline import (
    DryRunResult,
    ExitCode,
    PipelineExecutionError,
    PipelineOptions,
    StageProgress,
    default_output_path,
    plan_pipeline,
    run_pipeline,
)
from pdftranslate.rendering import PdfRenderer, RenderingError, RenderOptions
from pdftranslate.serialization import (
    DocumentJsonError,
    OutputExistsError,
    read_document_json,
    write_document_json,
)
from pdftranslate.translation import (
    DEFAULT_NLLB_MODEL,
    NllbTranslator,
    TranslationCache,
    TranslationError,
    TranslationInterruptedError,
    TranslationOptions,
    TranslationProgress,
    translate_document,
)
from pdftranslate.translation.nllb import DeviceRequest

try:
    _usage_error_module = importlib.import_module("typer._click.exceptions")
except ImportError:  # Typer before its vendored Click runtime
    _usage_error_module = importlib.import_module("click")
UsageError = cast(type[Exception], _usage_error_module.UsageError)


class _RootCommandGroup(TyperGroup):
    """Dispatch a leading PDF path to the hidden pipeline command."""

    def resolve_command(
        self,
        ctx: Any,
        args: list[str],
    ) -> Any:
        try:
            return super().resolve_command(ctx, args)
        except UsageError:
            if args and Path(args[0]).suffix.lower() == ".pdf":
                command = self.get_command(ctx, "run")
                if command is not None:
                    return "run", command, args
            raise


app = typer.Typer(
    name="pdftranslate",
    help="Translate English PDF documents into Russian with local models.",
    no_args_is_help=True,
    add_completion=False,
    cls=_RootCommandGroup,
)
console = Console()


class _CudaModule(Protocol):
    def is_available(self) -> bool: ...


class _TorchModule(Protocol):
    cuda: _CudaModule


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"PDFTranslate {__version__}")
        raise typer.Exit()


def _cuda_status() -> str:
    """Return a defensive CUDA availability status without requiring PyTorch."""
    if importlib.util.find_spec("torch") is None:
        return "unavailable (PyTorch is not installed)"

    torch = cast(_TorchModule, importlib.import_module("torch"))
    return "available" if torch.cuda.is_available() else "unavailable"


def _nvidia_gpu_status() -> str:
    """Detect an NVIDIA GPU through nvidia-smi when the utility is available."""
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return "not detected (nvidia-smi is unavailable)"

    try:
        result = subprocess.run(
            [executable, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "not detected (nvidia-smi check failed)"

    gpu_names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return ", ".join(gpu_names) if gpu_names else "not detected"


def _exit_with_error(error: Exception) -> Never:
    typer.echo(f"Error: {error}", err=True)
    raise typer.Exit(code=2)


def _inspection_table(report: InspectionReport) -> Table:
    table = Table(title="PDF inspection", show_header=False)
    table.add_column("Property", style="bold")
    table.add_column("Value")
    rows = (
        ("File", report.source.path),
        ("File size", f"{report.source.file_size} bytes"),
        ("Pages", str(report.page_count)),
        ("Text pages", str(report.text_pages)),
        ("Scanned pages", str(report.scanned_pages)),
        ("Mixed pages", str(report.mixed_pages)),
        ("Empty pages", str(report.empty_pages)),
        ("Text blocks", str(report.text_block_count)),
        ("Images", str(report.image_count)),
        ("Encrypted", str(report.encrypted).lower()),
        ("Password required", str(report.password_required).lower()),
        ("Probable source language", report.probable_source_language or "unknown"),
        ("SHA-256", report.source.sha256),
        ("Warnings", "\n".join(report.warnings) if report.warnings else "none"),
    )
    for name, value in rows:
        table.add_row(name, value)
    return table


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            help="Show the application version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """PDFTranslate command-line application."""


def _print_pipeline_error(error: PipelineExecutionError) -> Never:
    typer.echo(f"Error: {error.user_message}", err=True)
    raise typer.Exit(code=int(error.exit_code))


def _dry_run_table(dry_run: DryRunResult) -> Table:
    classifications = (
        ", ".join(
            f"{page}:{classification}"
            for page, classification in zip(
                dry_run.selected_pages,
                dry_run.selected_page_classifications,
                strict=True,
            )
        )
        or "none"
    )
    table = Table(title="PDFTranslate dry run", show_header=False)
    table.add_column("Property", style="bold")
    table.add_column("Value")
    table.add_row("Source", dry_run.inspection.source.path)
    table.add_row("Pages", str(dry_run.inspection.page_count))
    table.add_row("Page classifications", classifications)
    table.add_row("Estimated text blocks", str(dry_run.estimated_text_blocks))
    table.add_row("OCR required", str(dry_run.ocr_required).lower())
    table.add_row("Translation backend", dry_run.backend)
    table.add_row("Selected device", dry_run.device)
    table.add_row("Output", str(dry_run.output_path))
    table.add_row(
        "Expected stages",
        " -> ".join(stage.value for stage in dry_run.expected_stages),
    )
    return table


@app.command("run", hidden=True)
def translate_pdf(
    input_path: Annotated[Path, typer.Argument(help="English PDF file to translate.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Destination PDF; defaults to <stem>.ru.pdf."),
    ] = None,
    pages: Annotated[
        str | None,
        typer.Option("--pages", help="One-based page range, for example 1,3-5."),
    ] = None,
    backend: Annotated[
        str,
        typer.Option("--backend", help="Local translation backend (currently nllb)."),
    ] = "nllb",
    model: Annotated[
        str,
        typer.Option("--model", help="Hugging Face model identifier or local directory."),
    ] = DEFAULT_NLLB_MODEL,
    device: Annotated[
        str,
        typer.Option("--device", help="Inference device: auto, cpu, or cuda."),
    ] = "auto",
    batch_size: Annotated[
        int,
        typer.Option("--batch-size", min=1, help="Maximum inference segments per batch."),
    ] = 8,
    max_input_tokens: Annotated[
        int,
        typer.Option("--max-input-tokens", min=8, help="Maximum tokens per input segment."),
    ] = 512,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Application cache and pipeline workspace root."),
    ] = None,
    font: Annotated[
        Path | None,
        typer.Option("--font", help="TrueType or OpenType Cyrillic font path."),
    ] = None,
    min_font_size: Annotated[
        float,
        typer.Option("--min-font-size", min=0.1, help="Smallest allowed font size."),
    ] = 6.0,
    font_size_step: Annotated[
        float,
        typer.Option("--font-size-step", min=0.1, help="Font reduction step."),
    ] = 0.5,
    line_height: Annotated[
        float,
        typer.Option("--line-height", min=0.1, help="Textbox line-height factor."),
    ] = 1.2,
    redaction_padding: Annotated[
        float,
        typer.Option("--redaction-padding", min=0.0, help="Source-text padding in points."),
    ] = 0.5,
    allow_expand: Annotated[
        bool,
        typer.Option("--allow-expand", help="Expand blocks downward within safe limits."),
    ] = False,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Use local model files only; never use network."),
    ] = False,
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Reuse compatible completed stages and checkpoints."),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Replace an existing final PDF after validation."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Inspect and report the plan without loading a model."),
    ] = False,
) -> None:
    """Translate one PDF from inspection through validated atomic publication."""
    try:
        options = PipelineOptions(
            input_path=input_path,
            output_path=output or default_output_path(input_path),
            pages=pages,
            backend=backend,
            model=model,
            device=cast(DeviceRequest, device),
            batch_size=batch_size,
            max_input_tokens=max_input_tokens,
            cache_dir=cache_dir,
            offline=offline,
            resume=resume,
            overwrite=overwrite,
            font_path=font,
            min_font_size=min_font_size,
            font_size_step=font_size_step,
            line_height=line_height,
            redaction_padding=redaction_padding,
            allow_expand=allow_expand,
        )
    except ValueError as error:
        _print_pipeline_error(
            PipelineExecutionError(str(error), exit_code=ExitCode.INVALID_ARGUMENTS)
        )

    if dry_run:
        try:
            console.print(_dry_run_table(plan_pipeline(options)))
        except PipelineExecutionError as error:
            _print_pipeline_error(error)
        return

    started = time.perf_counter()

    def report_stage(progress: StageProgress) -> None:
        reuse = " (reused)" if progress.reused else ""
        console.print(f"{progress.index}/{progress.total} {progress.stage.value.title()}{reuse}")

    def report_translation(event: TranslationProgress) -> None:
        console.print(
            f"Blocks {event.completed_blocks}/{event.total_blocks}; "
            f"cache {event.cache_hits} hit(s), {event.cache_misses} miss(es); "
            f"page {event.page_number}, block {event.block_id}"
        )

    try:
        result = run_pipeline(
            options,
            stage_progress=report_stage,
            translation_progress=report_translation,
        )
    except PipelineExecutionError as error:
        _print_pipeline_error(error)

    elapsed = time.perf_counter() - started
    statistics = result.statistics
    console.print(
        f"Translated {statistics.completed_blocks}/{statistics.total_blocks} block(s) to "
        f"[path]{result.output_path}[/path]; cache {statistics.cache_hits} hit(s), "
        f"{statistics.cache_misses} miss(es); reused {len(result.reused_stages)} stage(s); "
        f"size {result.file_size} bytes; elapsed {elapsed:.2f}s"
    )


@app.command()
def doctor() -> None:
    """Report lightweight environment diagnostics."""
    settings = Settings()
    configure_logging(settings.log_level)

    table = Table(title="PDFTranslate doctor", show_header=False)
    table.add_column("Check", style="bold")
    table.add_column("Result")
    table.add_row("Application", __version__)
    table.add_row("Python", platform.python_version())
    table.add_row("OS", platform.platform())
    table.add_row("Config directory", str(settings.config_dir))
    table.add_row("Cache directory", str(settings.cache_dir))
    table.add_row("CUDA", _cuda_status())
    table.add_row("NVIDIA GPU", _nvidia_gpu_status())
    table.add_row("Status", "OK" if sys.version_info[:2] == (3, 12) else "WARNING")
    console.print(table)


@app.command("inspect")
def inspect_pdf(
    input_path: Annotated[Path, typer.Argument(help="PDF file to inspect.")],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON without Rich markup."),
    ] = False,
) -> None:
    """Inspect page content and classify a PDF without running OCR."""
    try:
        report = PdfAnalyzer(Settings()).inspect(input_path)
    except (PdfInputError, OSError) as error:
        _exit_with_error(error)

    if json_output:
        typer.echo(report.model_dump_json())
    else:
        console.print(_inspection_table(report))


@app.command("extract")
def extract_pdf(
    input_path: Annotated[Path, typer.Argument(help="PDF file to extract.")],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Destination for versioned document JSON."),
    ],
    pages: Annotated[
        str | None,
        typer.Option("--pages", help="One-based page range, for example 1,3-5."),
    ] = None,
    pretty: Annotated[
        bool,
        typer.Option("--pretty/--compact", help="Select formatted or compact JSON."),
    ] = True,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Replace an existing JSON output."),
    ] = False,
) -> None:
    """Extract structured text blocks into a stable JSON representation."""
    try:
        document = PdfExtractor(Settings()).extract(input_path, pages)
        write_document_json(document, output, pretty=pretty, overwrite=overwrite)
    except (PdfInputError, OutputExistsError, OSError) as error:
        _exit_with_error(error)

    console.print(f"Extracted {len(document.pages)} page(s) to [path]{output.resolve()}[/path]")


@app.command("translate")
def translate_json(
    input_path: Annotated[Path, typer.Argument(help="Extracted document JSON to translate.")],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Destination for translated document JSON."),
    ],
    source_language: Annotated[
        str, typer.Option("--from", help="Source language (currently en).")
    ] = "en",
    target_language: Annotated[
        str, typer.Option("--to", help="Target language (currently ru).")
    ] = "ru",
    backend: Annotated[
        str, typer.Option("--backend", help="Local translation backend (currently nllb).")
    ] = "nllb",
    model: Annotated[
        str, typer.Option("--model", help="Hugging Face model identifier or local directory.")
    ] = DEFAULT_NLLB_MODEL,
    device: Annotated[
        str, typer.Option("--device", help="Inference device: auto, cpu, or cuda.")
    ] = "auto",
    batch_size: Annotated[
        int, typer.Option("--batch-size", min=1, help="Maximum inference segments per batch.")
    ] = 8,
    max_input_tokens: Annotated[
        int,
        typer.Option("--max-input-tokens", min=8, help="Maximum tokens per input segment."),
    ] = 512,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Root for model files and translation memory."),
    ] = None,
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Replace an existing output and start again.")
    ] = False,
    offline: Annotated[
        bool, typer.Option("--offline", help="Use local model files only; never use network.")
    ] = False,
    resume: Annotated[
        bool, typer.Option("--resume", help="Continue a compatible interrupted output.")
    ] = False,
) -> None:
    """Translate extracted text blocks with one reusable local NLLB model."""
    started = time.perf_counter()
    settings = Settings()
    configure_logging(settings.log_level)
    root_cache = (cache_dir or settings.cache_dir).expanduser().resolve()
    output_path = output.expanduser().resolve()

    try:
        if backend != "nllb":
            raise TranslationError(f"unsupported translation backend: {backend}")
        if device not in {"auto", "cpu", "cuda"}:
            raise TranslationError("--device must be one of: auto, cpu, cuda")
        if overwrite and resume:
            raise TranslationError("--overwrite and --resume cannot be used together")
        source_document = read_document_json(input_path)
        resume_document = None
        if resume:
            if not output_path.exists():
                raise TranslationError(f"resume output does not exist: {output_path}")
            resume_document = read_document_json(output_path)
        elif output_path.exists() and not overwrite:
            raise OutputExistsError(f"output already exists; use --overwrite: {output_path}")

        mode_message = "local files only" if offline else "download may be required if not cached"
        console.print(f"Loading model {model} ({mode_message})...")
        translator = NllbTranslator(
            model_name=model,
            source_language=source_language,
            target_language=target_language,
            device=cast(DeviceRequest, device),
            cache_dir=root_cache / "models",
            offline=offline,
            max_input_tokens=max_input_tokens,
        )
        console.print(f"Model loaded on {translator.device}; effective batch size {batch_size}")

        def checkpoint(document: ExtractedDocument) -> None:
            write_document_json(document, output_path, overwrite=True)

        def report(event: TranslationProgress) -> None:
            console.print(
                f"Blocks {event.completed_blocks}/{event.total_blocks}; "
                f"cache {event.cache_hits} hit(s), {event.cache_misses} miss(es); "
                f"page {event.page_number}, block {event.block_id}"
            )

        options = TranslationOptions(
            source_language=source_language,
            target_language=target_language,
            batch_size=batch_size,
            max_input_tokens=max_input_tokens,
        )
        with TranslationCache(root_cache / "translation-memory.sqlite3") as cache:
            result = translate_document(
                source_document,
                translator=translator,
                cache=cache,
                options=options,
                resume_document=resume_document,
                checkpoint=checkpoint,
                progress=report,
            )
    except TranslationInterruptedError as error:
        typer.echo(f"Interrupted: {error}", err=True)
        raise typer.Exit(code=130) from error
    except (DocumentJsonError, OutputExistsError, TranslationError, OSError, ValueError) as error:
        _exit_with_error(error)

    metadata = result.translation
    assert metadata is not None
    elapsed = time.perf_counter() - started
    stats = metadata.statistics
    console.print(
        f"Translated {stats.completed_blocks}/{stats.total_blocks} block(s) to "
        f"[path]{output_path}[/path]; cache {stats.cache_hits} hit(s), "
        f"{stats.cache_misses} miss(es); device {metadata.effective_device}; "
        f"elapsed {elapsed:.2f}s"
    )


@app.command("render")
def render_pdf(
    input_path: Annotated[Path, typer.Argument(help="Immutable source PDF file.")],
    document_json: Annotated[
        Path, typer.Argument(help="Completed translated document JSON (schema 1.1).")
    ],
    output: Annotated[Path, typer.Option("--output", "-o", help="Destination translated PDF.")],
    font: Annotated[
        Path | None, typer.Option("--font", help="TrueType or OpenType Cyrillic font path.")
    ] = None,
    min_font_size: Annotated[
        float, typer.Option("--min-font-size", min=0.1, help="Smallest allowed font size.")
    ] = 6.0,
    font_size_step: Annotated[
        float, typer.Option("--font-size-step", min=0.1, help="Font reduction step.")
    ] = 0.5,
    line_height: Annotated[
        float, typer.Option("--line-height", min=0.1, help="Textbox line-height factor.")
    ] = 1.2,
    redaction_padding: Annotated[
        float,
        typer.Option("--redaction-padding", min=0.0, help="Padding around source text in points."),
    ] = 0.5,
    allow_expand: Annotated[
        bool, typer.Option("--allow-expand", help="Expand blocks downward within safe limits.")
    ] = False,
    debug_layout: Annotated[
        bool, typer.Option("--debug-layout", help="Also write a separate annotated debug PDF.")
    ] = False,
    force_source_mismatch: Annotated[
        bool,
        typer.Option(
            "--force-source-mismatch",
            help="Ignore only source size/SHA mismatch; layout validation still applies.",
        ),
    ] = False,
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Replace existing output and debug PDFs.")
    ] = False,
) -> None:
    """Render completed Russian translations into a validated copy of the source PDF."""
    started = time.perf_counter()
    try:
        translated = read_document_json(document_json)
        result = PdfRenderer().render(
            input_path,
            translated,
            output,
            font_path=font,
            options=RenderOptions(
                min_font_size=min_font_size,
                font_size_step=font_size_step,
                line_height=line_height,
                redaction_padding=redaction_padding,
                allow_expand=allow_expand,
                overwrite=overwrite,
                force_source_mismatch=force_source_mismatch,
                debug_layout=debug_layout,
            ),
        )
    except (DocumentJsonError, RenderingError, OSError, ValueError) as error:
        _exit_with_error(error)

    elapsed = time.perf_counter() - started
    console.print(
        f"Rendered {result.blocks_rendered}/{len(result.blocks)} block(s) to "
        f"[path]{result.output_path}[/path]; font reductions {result.font_reductions}; "
        f"expanded {result.expanded_blocks}; overflow {result.overflow_blocks}; "
        f"size {result.file_size} bytes; elapsed {elapsed:.2f}s"
    )
    if result.debug_output_path is not None:
        console.print(f"Debug layout: [path]{result.debug_output_path}[/path]")
    for warning in result.warnings:
        console.print(f"Warning: {warning}")
