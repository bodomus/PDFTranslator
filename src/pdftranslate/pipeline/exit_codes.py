"""Stable process exit-code categories for the public pipeline command."""

from enum import IntEnum


class ExitCode(IntEnum):
    """Documented process results; numeric values are part of the CLI contract."""

    SUCCESS = 0
    INVALID_ARGUMENTS = 2
    PDF_INPUT_ERROR = 3
    OCR_REQUIRED = 4
    MODEL_UNAVAILABLE = 5
    TRANSLATION_FAILED = 6
    RENDERING_FAILED = 7
    OUTPUT_VALIDATION_FAILED = 8
    OCR_FAILED = 9
    BATCH_FAILED = 10
    INTERRUPTED = 130
