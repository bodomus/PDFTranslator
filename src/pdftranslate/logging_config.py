"""Centralized logging configuration."""

import logging

from rich.logging import RichHandler

SUPPORTED_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})


def configure_logging(level: str = "INFO") -> None:
    """Configure readable console logging for an explicit supported level."""
    normalized_level = level.upper()
    if normalized_level not in SUPPORTED_LOG_LEVELS:
        supported = ", ".join(sorted(SUPPORTED_LOG_LEVELS))
        raise ValueError(f"Unsupported log level {level!r}. Expected one of: {supported}")

    logging.basicConfig(
        level=normalized_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(markup=False, rich_tracebacks=True)],
        force=True,
    )
