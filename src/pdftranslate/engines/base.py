"""Engine-independent contract for translating book paragraphs."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class EngineRequest:
    """One paragraph to translate, with optional neighbouring context."""

    text: str
    previous_source: str | None = None
    previous_translation: str | None = None
    glossary: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class EngineResult:
    """A translation, or the reason this paragraph could not be translated."""

    text: str | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.text is not None


@dataclass(frozen=True)
class EngineCapabilities:
    """What the engine can use; callers skip work an engine would ignore."""

    uses_context: bool = False
    uses_glossary: bool = False
    parallel_requests: int = 1


class TranslationEngine(Protocol):
    """A loaded engine that translates English paragraphs into Russian."""

    @property
    def engine_id(self) -> str:
        """Stable identity of every setting that changes output; used as the cache namespace."""
        ...

    @property
    def capabilities(self) -> EngineCapabilities: ...

    def translate(self, requests: Sequence[EngineRequest]) -> list[EngineResult]: ...


@dataclass(frozen=True)
class EngineSettings:
    """Options shared by the CLI and the registry; each engine reads what it needs."""

    model: str | None = None
    endpoint: str | None = None
    api_key: str | None = None
    temperature: float = 0.2
    max_output_tokens: int = 4096
    timeout_seconds: float = 600.0
    parallel_requests: int = 1
    beams: int = 4
    device: str = "auto"
    cache_dir: str | None = None
    offline: bool = False
    extra: dict[str, str] = field(default_factory=dict)


EngineFactory = Callable[[EngineSettings], TranslationEngine]


class EngineError(RuntimeError):
    """An engine cannot be created or is misconfigured."""


_REGISTRY: dict[str, EngineFactory] = {}


def register_engine(name: str, factory: EngineFactory) -> None:
    """Make an engine available by name; adding a model means adding one adapter here."""
    _REGISTRY[name] = factory


def available_engines() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def create_engine(name: str, settings: EngineSettings) -> TranslationEngine:
    try:
        factory = _REGISTRY[name]
    except KeyError as error:
        known = ", ".join(available_engines()) or "none"
        raise EngineError(f"unknown engine {name!r}; available: {known}") from error
    return factory(settings)
