"""Hugging Face NLLB adapter; third-party objects stay inside this module."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Literal, Protocol, cast

from pdftranslate.translation.errors import (
    TranslationBackendError,
    TranslationOutOfMemoryError,
)

DEFAULT_NLLB_MODEL = "facebook/nllb-200-distilled-600M"
LANGUAGE_CODES = {"en": "eng_Latn", "ru": "rus_Cyrl"}
DeviceRequest = Literal["auto", "cpu", "cuda"]


class _Tensor(Protocol):
    def to(self, device: str) -> _Tensor: ...


class _Tokenizer(Protocol):
    model_max_length: int

    def __call__(self, text: object, **kwargs: object) -> Mapping[str, object]: ...

    def batch_decode(self, values: object, **kwargs: object) -> list[str]: ...

    def convert_tokens_to_ids(self, token: str) -> int: ...


class _Model(Protocol):
    def to(self, device: str) -> _Model: ...

    def eval(self) -> _Model: ...

    def generate(self, **kwargs: object) -> object: ...


class _CudaRuntime(Protocol):
    def is_available(self) -> bool: ...

    def empty_cache(self) -> None: ...


class _TorchRuntime(Protocol):
    cuda: _CudaRuntime

    def zeros(self, size: int, *, device: str) -> object: ...

    def inference_mode(self) -> AbstractContextManager[object]: ...


class _PretrainedFactory(Protocol):
    @staticmethod
    def from_pretrained(model: str, **kwargs: object) -> object: ...


class _TransformersRuntime(Protocol):
    AutoTokenizer: _PretrainedFactory
    AutoModelForSeq2SeqLM: _PretrainedFactory


Loader = Callable[[str, str, Path, bool], tuple[_Tokenizer, _Model]]


def resolve_device(
    requested: DeviceRequest, torch_runtime: _TorchRuntime
) -> Literal["cpu", "cuda"]:
    """Resolve CPU/CUDA and probe that auto-selected CUDA can allocate."""
    if requested == "cpu":
        return "cpu"
    available = torch_runtime.cuda.is_available()
    if requested == "cuda":
        if not available:
            raise TranslationBackendError("CUDA was requested but is not available")
        return "cuda"
    if not available:
        return "cpu"
    try:
        torch_runtime.zeros(1, device="cuda")
        torch_runtime.cuda.empty_cache()
    except Exception:
        return "cpu"
    return "cuda"


class NllbTranslator:
    """Loaded-once NLLB implementation of the translator protocol."""

    backend_name = "nllb"

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_NLLB_MODEL,
        source_language: str = "en",
        target_language: str = "ru",
        device: DeviceRequest = "auto",
        cache_dir: Path,
        offline: bool = False,
        max_input_tokens: int = 512,
        loader: Loader | None = None,
        torch_runtime: _TorchRuntime | None = None,
    ) -> None:
        if (source_language, target_language) != ("en", "ru"):
            raise TranslationBackendError("NLLB backend currently supports only English to Russian")
        if max_input_tokens < 8:
            raise TranslationBackendError("max_input_tokens must be at least 8")

        self.model_name = model_name
        self._source_code = LANGUAGE_CODES[source_language]
        self._target_code = LANGUAGE_CODES[target_language]
        self._requested_device = device
        self._max_input_tokens = max_input_tokens
        self._torch = torch_runtime or _import_torch()
        self._device = resolve_device(device, self._torch)
        self._cpu_fallback_used = False
        actual_loader = loader or _load_components
        try:
            self._tokenizer, self._model = actual_loader(
                model_name,
                self._source_code,
                cache_dir.expanduser().resolve(),
                offline,
            )
        except OSError as error:
            mode = "offline mode; model files are absent" if offline else "model loading failed"
            raise TranslationBackendError(f"{mode}: {model_name}: {error}") from error
        except Exception as error:
            raise TranslationBackendError(
                f"cannot load NLLB model {model_name}: {error}"
            ) from error
        tokenizer_limit = getattr(self._tokenizer, "model_max_length", max_input_tokens)
        if (
            isinstance(tokenizer_limit, int)
            and 0 < tokenizer_limit < 1_000_000
            and max_input_tokens > tokenizer_limit
        ):
            raise TranslationBackendError(
                f"--max-input-tokens {max_input_tokens} exceeds tokenizer limit {tokenizer_limit}"
            )
        try:
            self._model.to(self._device).eval()
            self._target_token_id = self._tokenizer.convert_tokens_to_ids(self._target_code)
        except Exception as error:
            raise TranslationBackendError(
                f"cannot initialize NLLB on {self._device}: {error}"
            ) from error
        if self._target_token_id < 0:
            raise TranslationBackendError(
                f"target language token is unavailable: {self._target_code}"
            )

    @property
    def device(self) -> Literal["cpu", "cuda"]:
        return self._device

    def count_tokens(self, text: str) -> int:
        encoded = self._tokenizer(text, add_special_tokens=True, truncation=False)
        input_ids = cast(Sequence[int], encoded["input_ids"])
        return len(input_ids)

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        if not texts:
            return []
        try:
            return self._infer(texts)
        except Exception as error:
            if not _is_out_of_memory(error):
                raise TranslationBackendError(f"NLLB inference failed: {error}") from error

        if (
            self._device == "cuda"
            and self._requested_device == "auto"
            and not self._cpu_fallback_used
        ):
            self._cpu_fallback_used = True
            self._model.to("cpu")
            self._device = "cpu"
            self._torch.cuda.empty_cache()
            try:
                return self._infer(texts)
            except Exception as error:
                if _is_out_of_memory(error):
                    raise TranslationOutOfMemoryError(
                        "NLLB inference exhausted memory after one CPU fallback"
                    ) from error
                raise TranslationBackendError(
                    f"NLLB inference failed after CPU fallback: {error}"
                ) from error
        raise TranslationOutOfMemoryError(
            f"NLLB inference exhausted memory on {self._device}; reduce --batch-size"
        )

    def _infer(self, texts: Sequence[str]) -> list[str]:
        encoded = self._tokenizer(
            list(texts),
            return_tensors="pt",
            padding=True,
            truncation=False,
        )
        inputs = {name: cast(_Tensor, value).to(self._device) for name, value in encoded.items()}
        with self._torch.inference_mode():
            generated = self._model.generate(
                **inputs,
                forced_bos_token_id=self._target_token_id,
                max_new_tokens=max(32, self._max_input_tokens * 2),
            )
        translated = self._tokenizer.batch_decode(generated, skip_special_tokens=True)
        if len(translated) != len(texts):
            raise TranslationBackendError("NLLB returned a different number of translations")
        return translated


def _load_components(
    model_name: str,
    source_code: str,
    cache_dir: Path,
    offline: bool,
) -> tuple[_Tokenizer, _Model]:
    runtime = cast(_TransformersRuntime, importlib.import_module("transformers"))
    common: dict[str, object] = {
        "cache_dir": str(cache_dir),
        "local_files_only": offline,
    }
    tokenizer = cast(
        _Tokenizer,
        runtime.AutoTokenizer.from_pretrained(model_name, src_lang=source_code, **common),
    )
    model = cast(_Model, runtime.AutoModelForSeq2SeqLM.from_pretrained(model_name, **common))
    return tokenizer, model


def _import_torch() -> _TorchRuntime:
    try:
        return cast(_TorchRuntime, importlib.import_module("torch"))
    except ImportError as error:
        raise TranslationBackendError(
            "PyTorch is required for the NLLB backend; synchronize project dependencies"
        ) from error


def _is_out_of_memory(error: BaseException) -> bool:
    name = type(error).__name__.lower()
    message = str(error).lower()
    return "outofmemory" in name or "out of memory" in message
