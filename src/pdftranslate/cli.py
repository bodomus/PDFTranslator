"""Command-line interface for PDFTranslate."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Never, Protocol, cast

import typer
from rich.console import Console
from rich.table import Table

from pdftranslate import __version__
from pdftranslate.config import Settings
from pdftranslate.domain.document import InspectionReport
from pdftranslate.logging_config import configure_logging
from pdftranslate.pdf import PdfAnalyzer, PdfExtractor, PdfInputError
from pdftranslate.serialization import OutputExistsError, write_document_json

app = typer.Typer(
    name="pdftranslate",
    help="Translate English PDF documents into Russian (translation is not implemented yet).",
    no_args_is_help=True,
    add_completion=False,
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
