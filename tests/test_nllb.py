from __future__ import annotations

import os
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

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


class RecordingFactory:
    def __init__(self, value: object, *, failure: OSError | None = None) -> None:
        self.value = value
        self.failure = failure
        self.calls: list[tuple[str, dict[str, object], str | None, str | None]] = []

    def from_pretrained(self, model: str, **kwargs: object) -> object:
        self.calls.append(
            (
                model,
                kwargs,
                os.environ.get("HF_HUB_OFFLINE"),
                os.environ.get("TRANSFORMERS_OFFLINE"),
            )
        )
        if self.failure is not None:
            raise self.failure
        return self.value


class FakeTransformers:
    def __init__(
        self,
        *,
        config: RecordingFactory,
        tokenizer: RecordingFactory,
        model: RecordingFactory,
    ) -> None:
        self.AutoConfig = config
        self.AutoTokenizer = tokenizer
        self.AutoModelForSeq2SeqLM = model


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


def test_offline_loads_config_tokenizer_and_model_from_local_snapshot(tmp_path: Path) -> None:
    cache = tmp_path / "models"
    repository = cache / "models--example--model"
    revision = "abc123"
    snapshot = repository / "snapshots" / revision
    snapshot.mkdir(parents=True)
    (repository / "refs").mkdir()
    (repository / "refs" / "main").write_text(revision, encoding="utf-8")
    config_value = object()
    config = RecordingFactory(config_value)
    tokenizer = RecordingFactory(FakeTokenizer())
    model = RecordingFactory(FakeModel())
    runtime = FakeTransformers(config=config, tokenizer=tokenizer, model=model)

    with (
        patch.dict(
            os.environ,
            {"HF_HUB_OFFLINE": "previous-hf", "TRANSFORMERS_OFFLINE": "previous-transformers"},
        ),
        patch("pdftranslate.translation.nllb.importlib.import_module", return_value=runtime),
    ):
        NllbTranslator(
            model_name="example/model",
            cache_dir=cache,
            device="cpu",
            offline=True,
            torch_runtime=FakeTorch(False),
        )
        assert os.environ["HF_HUB_OFFLINE"] == "previous-hf"
        assert os.environ["TRANSFORMERS_OFFLINE"] == "previous-transformers"

    expected = str(snapshot.resolve())
    for factory in (config, tokenizer, model):
        assert factory.calls[0][0] == expected
        assert factory.calls[0][1]["local_files_only"] is True
        assert factory.calls[0][2:] == ("1", "1")
    assert tokenizer.calls[0][1]["src_lang"] == "eng_Latn"
    assert model.calls[0][1]["config"] is config_value


def test_offline_missing_cache_fails_before_transformers_import(tmp_path: Path) -> None:
    with (
        patch("pdftranslate.translation.nllb.importlib.import_module") as importer,
        pytest.raises(TranslationBackendError) as caught,
    ):
        NllbTranslator(
            model_name="missing/model",
            cache_dir=tmp_path / "empty-cache",
            device="cpu",
            offline=True,
            torch_runtime=FakeTorch(False),
        )

    importer.assert_not_called()
    message = str(caught.value)
    assert "offline mode" in message
    assert "missing/model" in message
    assert str((tmp_path / "empty-cache").resolve()) in message
    assert "rerun without --offline" in message


def test_offline_environment_is_restored_when_loader_fails(tmp_path: Path) -> None:
    local_model = tmp_path / "local-model"
    local_model.mkdir()
    runtime = FakeTransformers(
        config=RecordingFactory(object()),
        tokenizer=RecordingFactory(FakeTokenizer(), failure=OSError("broken tokenizer")),
        model=RecordingFactory(FakeModel()),
    )

    with (
        patch.dict(os.environ, {}, clear=False),
        patch("pdftranslate.translation.nllb.importlib.import_module", return_value=runtime),
    ):
        os.environ.pop("HF_HUB_OFFLINE", None)
        os.environ.pop("TRANSFORMERS_OFFLINE", None)
        with pytest.raises(TranslationBackendError, match="offline mode"):
            NllbTranslator(
                model_name=str(local_model),
                cache_dir=tmp_path / "cache",
                device="cpu",
                offline=True,
                torch_runtime=FakeTorch(False),
            )
        assert "HF_HUB_OFFLINE" not in os.environ
        assert "TRANSFORMERS_OFFLINE" not in os.environ


def test_online_loading_keeps_remote_model_and_does_not_force_offline_environment(
    tmp_path: Path,
) -> None:
    config_value = object()
    config = RecordingFactory(config_value)
    tokenizer = RecordingFactory(FakeTokenizer())
    model = RecordingFactory(FakeModel())
    runtime = FakeTransformers(config=config, tokenizer=tokenizer, model=model)

    with (
        patch.dict(os.environ, {}, clear=False),
        patch("pdftranslate.translation.nllb.importlib.import_module", return_value=runtime),
    ):
        os.environ.pop("HF_HUB_OFFLINE", None)
        os.environ.pop("TRANSFORMERS_OFFLINE", None)
        NllbTranslator(
            model_name="example/model",
            cache_dir=tmp_path / "cache",
            device="cpu",
            offline=False,
            torch_runtime=FakeTorch(False),
        )

    for factory in (config, tokenizer, model):
        assert factory.calls[0][0] == "example/model"
        assert factory.calls[0][1]["local_files_only"] is False
        assert factory.calls[0][2:] == (None, None)


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
