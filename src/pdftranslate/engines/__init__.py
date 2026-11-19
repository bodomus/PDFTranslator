"""Pluggable translation engines; each one is an adapter registered by name."""

from pdftranslate.engines.base import (
    EngineCapabilities,
    EngineError,
    EngineRequest,
    EngineResult,
    EngineSettings,
    TranslationEngine,
    available_engines,
    create_engine,
    register_engine,
)
from pdftranslate.engines.llm import LlmEngine
from pdftranslate.engines.nllb import NllbEngine, create_nllb_engine

register_engine("nllb", create_nllb_engine)
register_engine("llm", LlmEngine)

__all__ = [
    "EngineCapabilities",
    "EngineError",
    "EngineRequest",
    "EngineResult",
    "EngineSettings",
    "LlmEngine",
    "NllbEngine",
    "TranslationEngine",
    "available_engines",
    "create_engine",
    "register_engine",
]
