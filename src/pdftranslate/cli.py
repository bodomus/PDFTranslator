"""Command-line interface for PDFTranslate."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from typing import Annotated, Protocol, cast

import typer
from rich.console import Console
from rich.table import Table

from pdftranslate import __version__
from pdftranslate.config import Settings
from pdftranslate.logging_config import configure_logging

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
