from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pytest

from pdftranslate.translation import TranslationBackendError
from pdftranslate.translation.nllb import NllbTranslator, resolve_device


class FakeCuda:
    def __init__(self, available: bool) -> None:
        self.available = available
        self.emptied = 0

    def is_available(self) -> bool:
        return self.available

    def empty_cache(self) -> None:
        self.emptied += 1


class FakeTorch:
    def __init__(self, available: bool, *, probe_fails: bool = False) -> None:
        self.cuda = FakeCuda(available)
        self.probe_fails = probe_fails

    def zeros(self, size: int, *, device: str) -> object:
        if self.probe_fails:
            raise RuntimeError("driver failed")
        return (size, device)

    def inference_mode(self) -> nullcontext[None]:
        return nullcontext()


class FakeTensor:
    def __init__(self) -> None:
        self.devices: list[str] = []

    def to(self, device: str) -> FakeTensor:
        self.devices.append(device)
        return self


class FakeTokenizer:
    model_max_length = 1024

    def __call__(self, text: object, **kwargs: object) -> dict[str, object]:
        if isinstance(text, str):
            return {"input_ids": list(range(len(text.split()) + 2))}
        return {"input_ids": FakeTensor(), "attention_mask": FakeTensor()}

    def batch_decode(self, values: object, **kwargs: object) -> list[str]:
        return list(values)  # type: ignore[arg-type]

    def convert_tokens_to_ids(self, token: str) -> int:
        return 256 if token == "rus_Cyrl" else -1


class FakeModel:
    def __init__(self, *, oom_once: bool = False) -> None:
        self.devices: list[str] = []
        self.eval_calls = 0
        self.oom_once = oom_once

    def to(self, device: str) -> FakeModel:
        self.devices.append(device)
        return self

    def eval(self) -> FakeModel:
        self.eval_calls += 1
        return self

    def generate(self, **kwargs: object) -> object:
        if self.oom_once:
            self.oom_once = False
            raise RuntimeError("CUDA out of memory")
        input_ids = kwargs["input_ids"]
        assert isinstance(input_ids, FakeTensor)
        return ["перевод"]


def test_device_selection_supports_cpu_cuda_and_auto() -> None:
    unavailable = FakeTorch(False)
    assert resolve_device("cpu", unavailable) == "cpu"
    assert resolve_device("auto", unavailable) == "cpu"
    with pytest.raises(TranslationBackendError, match="not available"):
        resolve_device("cuda", unavailable)
    assert resolve_device("auto", FakeTorch(True)) == "cuda"
    assert resolve_device("auto", FakeTorch(True, probe_fails=True)) == "cpu"


def test_nllb_loads_once_and_passes_offline_cache_settings(tmp_path: Path) -> None:
    calls: list[tuple[str, str, Path, bool]] = []
    tokenizer = FakeTokenizer()
    model = FakeModel()

    def loader(
        model_name: str, source_code: str, cache_dir: Path, offline: bool
    ) -> tuple[FakeTokenizer, FakeModel]:
        calls.append((model_name, source_code, cache_dir, offline))
        return tokenizer, model

    translator = NllbTranslator(
        cache_dir=tmp_path,
        device="cpu",
        offline=True,
        loader=loader,
        torch_runtime=FakeTorch(False),
    )

    assert translator.translate_batch(["hello"]) == ["перевод"]
    assert translator.translate_batch(["again"]) == ["перевод"]
    assert calls == [("facebook/nllb-200-distilled-600M", "eng_Latn", tmp_path.resolve(), True)]
    assert model.eval_calls == 1
    assert model.devices == ["cpu"]
    assert translator.count_tokens("one two") == 4


def test_offline_missing_model_has_clear_error(tmp_path: Path) -> None:
    def missing(*_args: object) -> tuple[FakeTokenizer, FakeModel]:
        raise OSError("files unavailable")

    with pytest.raises(TranslationBackendError, match="offline mode; model files are absent"):
        NllbTranslator(
            cache_dir=tmp_path,
            offline=True,
            loader=missing,
            torch_runtime=FakeTorch(False),
        )


def test_requested_input_limit_cannot_exceed_tokenizer_limit(tmp_path: Path) -> None:
    def loader(
        _model: str, _source: str, _cache: Path, _offline: bool
    ) -> tuple[FakeTokenizer, FakeModel]:
        return FakeTokenizer(), FakeModel()

    with pytest.raises(TranslationBackendError, match="exceeds tokenizer limit"):
        NllbTranslator(
            cache_dir=tmp_path,
            max_input_tokens=2048,
            loader=loader,
            torch_runtime=FakeTorch(False),
        )


def test_auto_cuda_oom_falls_back_to_cpu_once(tmp_path: Path) -> None:
    model = FakeModel(oom_once=True)

    def loader(
        _model: str, _source: str, _cache: Path, _offline: bool
    ) -> tuple[FakeTokenizer, FakeModel]:
        return FakeTokenizer(), model

    translator = NllbTranslator(
        cache_dir=tmp_path,
        device="auto",
        loader=loader,
        torch_runtime=FakeTorch(True),
    )

    assert translator.translate_batch(["hello"]) == ["перевод"]
    assert translator.device == "cpu"
    assert model.devices == ["cuda", "cpu"]
