"""Backend-independent translation contract."""

from collections.abc import Sequence
from typing import Literal, Protocol


class Translator(Protocol):
    """A loaded, reusable local translation backend."""

    @property
    def backend_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def device(self) -> Literal["cpu", "cuda"]: ...

    def count_tokens(self, text: str) -> int: ...

    def translate_batch(self, texts: Sequence[str]) -> list[str]: ...
