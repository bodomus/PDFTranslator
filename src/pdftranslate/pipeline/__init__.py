"""One-command PDF translation orchestration."""

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
    default_output_path,
)
from pdftranslate.pipeline.runner import (
    PipelineServices,
    default_services,
    plan_pipeline,
    run_pipeline,
)

__all__ = [
    "DryRunResult",
    "ExitCode",
    "ModelUnavailableError",
    "OcrRequiredError",
    "OutputValidationError",
    "PipelineExecutionError",
    "PipelineOptions",
    "PipelineResult",
    "PipelineServices",
    "PipelineStage",
    "PipelineStateError",
    "StageProgress",
    "default_services",
    "default_output_path",
    "plan_pipeline",
    "run_pipeline",
]
