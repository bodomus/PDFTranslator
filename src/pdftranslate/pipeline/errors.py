"""User-facing end-to-end pipeline failures."""

from __future__ import annotations

from pathlib import Path

from pdftranslate.pipeline.exit_codes import ExitCode
from pdftranslate.pipeline.models import PipelineStage


class PipelineStateError(ValueError):
    """Workspace state is missing, corrupt, or incompatible with resume."""


class OcrRequiredError(RuntimeError):
    """Selected scanned pages require OCR, which is intentionally not implemented."""


class ModelUnavailableError(RuntimeError):
    """The configured local translation model could not be initialized."""


class OutputValidationError(RuntimeError):
    """The rendered candidate failed final validation or publication."""


class PipelineExecutionError(RuntimeError):
    """Concise categorized failure with retained diagnostic location."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: ExitCode,
        stage: PipelineStage | None = None,
        log_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.stage = stage
        self.log_path = log_path

    @property
    def user_message(self) -> str:
        """Include stage and diagnostics without exposing a traceback."""
        prefix = f"{self.stage.value} failed: " if self.stage is not None else ""
        suffix = f"; diagnostics: {self.log_path}" if self.log_path is not None else ""
        return f"{prefix}{self}{suffix}"
