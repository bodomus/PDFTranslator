from __future__ import annotations

import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import pytest
from typer.testing import CliRunner

from pdftranslate.book import BookDocument, book_translation_text, translate_book
from pdftranslate.book.models import BookOcrInfo, BookParagraph, BookStatistics
from pdftranslate.book.translate import _schedule, needs_translation
from pdftranslate.cli import app
from pdftranslate.domain.document import SourceDocument
from pdftranslate.engines import (
    EngineCapabilities,
    EngineError,
    EngineRequest,
    EngineResult,
    EngineSettings,
    LlmEngine,
    NllbEngine,
    available_engines,
    create_engine,
)
from pdftranslate.engines.llm import clean_output, validate_translation
from pdftranslate.engines.nllb import sentence_segments, split_sentences
from pdftranslate.translation.cache import TranslationCache
from pdftranslate.translation.errors import TranslationBackendError


def _book(texts: Sequence[str]) -> BookDocument:
    return BookDocument(
        source=SourceDocument(path="book.pdf", file_size=1, sha256="0" * 64),
        page_count=1,
        selected_pages=(1,),
        ocr=BookOcrInfo(),
        statistics=BookStatistics(
            pages=1,
            paragraphs=len(texts),
            headings=0,
            removed_headers=0,
            cross_page_merges=0,
            dehyphenated_words=0,
            note_markers=0,
            low_confidence_words=0,
        ),
        paragraphs=tuple(
            BookParagraph(id=f"b{index + 1:05d}", kind="body", text=text, pages=(1,))
            for index, text in enumerate(texts)
        ),
    )


class FakeEngine:
    """Upper-cases text; fails paragraphs listed in `fail`; records every request."""

    def __init__(
        self, *, uses_context: bool = True, parallel: int = 1, fail: frozenset[str] = frozenset()
    ) -> None:
        self.requests: list[EngineRequest] = []
        self.calls: list[list[str]] = []
        self.fail = set(fail)
        self._capabilities = EngineCapabilities(
            uses_context=uses_context, parallel_requests=parallel
        )

    @property
    def engine_id(self) -> str:
        return "fake:1"

    @property
    def capabilities(self) -> EngineCapabilities:
        return self._capabilities

    def translate(self, requests: Sequence[EngineRequest]) -> list[EngineResult]:
        self.requests.extend(requests)
        self.calls.append([request.text for request in requests])
        return [
            EngineResult(None, "boom")
            if request.text in self.fail
            else EngineResult(request.text.upper())
            for request in requests
        ]


def test_translate_book_passes_previous_paragraph_as_context() -> None:
    engine = FakeEngine()

    result = translate_book(_book(["one", "two", "three"]), engine, engine_name="fake")

    assert [item.translation for item in result.paragraphs] == ["ONE", "TWO", "THREE"]
    assert engine.requests[0].previous_source is None
    assert engine.requests[2].previous_source == "two"
    assert engine.requests[2].previous_translation == "TWO"
    assert result.translation is not None
    assert result.translation.engine_id == "fake:1"
    assert (result.translation.translated, result.translation.failed) == (3, 0)


def test_parallel_lanes_keep_context_from_the_same_lane() -> None:
    engine = FakeEngine(parallel=2)

    translate_book(_book(["a", "b", "c", "d", "e"]), engine, engine_name="fake")

    assert engine.calls == [["a", "d"], ["b", "e"], ["c"]]
    by_text = {request.text: request for request in engine.requests}
    assert by_text["e"].previous_translation == "D"
    # A lane start has no context even on a rerun, when "c" would already be cached.
    assert by_text["d"].previous_source is None


def test_schedule_without_context_uses_contiguous_batches() -> None:
    assert _schedule(20, False, 1) == [list(range(16)), list(range(16, 20))]
    assert _schedule(0, True, 4) == []
    assert _schedule(3, True, 8) == [[0, 1, 2]]


def test_failed_paragraph_is_recorded_and_retried_from_cache(tmp_path: Path) -> None:
    book = _book(["one", "two", "three"])
    progress: list[tuple[int, int, int]] = []

    with TranslationCache(tmp_path / "tm.sqlite3") as cache:
        first = translate_book(
            book,
            FakeEngine(fail=frozenset({"two"})),
            engine_name="fake",
            cache=cache,
            progress=lambda *event: progress.append(event),
        )
        retry = FakeEngine()
        second = translate_book(book, retry, engine_name="fake", cache=cache)

    assert first.paragraphs[1].translation is None
    assert first.paragraphs[1].translation_error == "boom"
    assert first.translation is not None and first.translation.failed == 1
    assert progress[-1] == (3, 3, 1)
    assert "[НЕ ПЕРЕВЕДЕНО] two" in book_translation_text(first)
    # "one" comes from the cache; "three" is retranslated because its context changed.
    assert retry.calls == [["two"], ["three"]]
    assert [item.translation for item in second.paragraphs] == ["ONE", "TWO", "THREE"]
    assert second.paragraphs[1].translation_error is None


def test_engine_returning_wrong_result_count_is_an_error() -> None:
    class Broken(FakeEngine):
        def translate(self, requests: Sequence[EngineRequest]) -> list[EngineResult]:
            return []

    with pytest.raises(RuntimeError, match="0 results"):
        translate_book(_book(["one"]), Broken(), engine_name="broken")


def test_registry_knows_builtin_engines() -> None:
    assert {"llm", "nllb"} <= set(available_engines())
    with pytest.raises(EngineError, match="unknown engine"):
        create_engine("nope", EngineSettings())
    with pytest.raises(EngineError, match="--model"):
        create_engine("llm", EngineSettings())


def _llm(
    replies: list[str], **settings: Any
) -> tuple[LlmEngine, list[tuple[str, dict[str, Any], dict[str, str]]]]:
    sent: list[tuple[str, dict[str, Any], dict[str, str]]] = []
    lock = threading.Lock()

    def post(
        url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float
    ) -> dict[str, Any]:
        with lock:
            sent.append((url, payload, headers))
            content = replies.pop(0)
        return {"choices": [{"message": {"content": content}}]}

    engine = LlmEngine(EngineSettings(model="qwen", **settings), post_json=post)
    return engine, sent


def test_llm_engine_builds_prompt_with_context_glossary_and_domain() -> None:
    engine, sent = _llm(
        ["<think>hmm</think>Перевод: Крючков вернулся."],
        endpoint="http://host:1234/v1/",
        api_key="secret",
        extra={"domain": "KGB history"},
    )
    request = EngineRequest(
        "Kryuchkov returned.",
        previous_source="He left.",
        previous_translation="Он ушёл.",
        glossary=(("Lubyanka", "Лубянка"),),
    )

    [result] = engine.translate([request])

    assert result.text == "Крючков вернулся."
    url, payload, headers = sent[0]
    assert url == "http://host:1234/v1/chat/completions"
    assert headers["Authorization"] == "Bearer secret"
    assert payload["model"] == "qwen"
    messages = payload["messages"]
    assert [item["role"] for item in messages] == ["system", "user", "assistant", "user"]
    assert "KGB history" in messages[0]["content"]
    assert "Lubyanka -> Лубянка" in messages[0]["content"]
    assert messages[-1]["content"] == "Kryuchkov returned."
    assert engine.engine_id == "llm:qwen:t0.2:p1:KGB history"
    assert engine.capabilities.uses_context


def test_llm_engine_retries_invalid_output_then_reports_failure() -> None:
    engine, sent = _llm(["Still English text", "```\nПривет мир\n```"])
    [ok] = engine.translate([EngineRequest("Hello world")])
    assert ok.text == "Привет мир"
    assert len(sent) == 2

    engine, _sent = _llm(["", ""])
    [failed] = engine.translate([EngineRequest("Hello world")])
    assert not failed.ok
    assert failed.error == "empty translation"


def test_llm_engine_reports_transport_and_shape_errors() -> None:
    def down(*_args: Any) -> dict[str, Any]:
        raise EngineError("cannot reach server")

    engine = LlmEngine(EngineSettings(model="qwen"), post_json=down)
    assert engine.translate([EngineRequest("Hi")])[0].error == "cannot reach server"

    engine = LlmEngine(EngineSettings(model="qwen"), post_json=lambda *_args: {"oops": 1})
    error = engine.translate([EngineRequest("Hi")])[0].error
    assert error is not None and "unexpected response" in error


def test_llm_engine_runs_requests_in_parallel_preserving_order() -> None:
    engine, _sent = _llm(["Один", "Два"], parallel_requests=2)
    texts = {"Один", "Два"}
    results = engine.translate([EngineRequest("one"), EngineRequest("two")])
    assert {result.text for result in results} == texts
    assert engine.capabilities.parallel_requests == 2


def test_clean_output_and_validation() -> None:
    assert clean_output('"Текст"') == "Текст"
    assert clean_output("Translation: Текст") == "Текст"
    assert validate_translation("Hello", "Привет") is None
    assert validate_translation("Hello", "Hello") == "output contains no Russian text"
    long_source = "word " * 40
    assert validate_translation(long_source, "Слово") is not None
    assert validate_translation("1945", "1945") is None
    assert validate_translation("1", "Could you clarify what you mean?") is not None


def test_split_sentences_keeps_abbreviations_and_initials() -> None:
    text = (
        "Dr. Smith met Gen. Ivanov in the U.S. embassy. They spoke. "
        'V. A. Kryuchkov agreed! "Why?" he asked.'
    )
    assert split_sentences(text) == [
        "Dr. Smith met Gen. Ivanov in the U.S. embassy.",
        "They spoke.",
        "V. A. Kryuchkov agreed!",
        '"Why?" he asked.',
    ]
    assert split_sentences("") == []


class FakeTranslator:
    backend_name = "fake"
    model_name = "nllb-test"
    device: Literal["cpu", "cuda"] = "cpu"

    def __init__(self, fail: bool = False) -> None:
        self.batches: list[list[str]] = []
        self.fail = fail

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        if self.fail:
            raise TranslationBackendError("out of memory")
        self.batches.append(list(texts))
        return [f"<{text}>" for text in texts]


def test_nllb_engine_translates_sentence_by_sentence() -> None:
    translator = FakeTranslator()
    engine = NllbEngine(translator, beams=4)

    [result] = engine.translate([EngineRequest("First one. Second one.")])

    assert result.text == "<First one.> <Second one.>"
    assert translator.batches == [["First one.", "Second one."]]
    assert engine.engine_id == "nllb:nllb-test:b4:s160"
    assert not engine.capabilities.uses_context

    failing = NllbEngine(FakeTranslator(fail=True), beams=1)
    assert failing.translate([EngineRequest("Text.")])[0].error == "out of memory"


def test_sentence_segments_split_overlong_sentences() -> None:
    long_sentence = " ".join(["word"] * 30) + "."
    segments = sentence_segments(long_sentence, lambda text: len(text.split()), max_tokens=10)
    assert len(segments) > 1
    assert segments[-1].separator_after == ""
    assert sentence_segments("   ", lambda text: 1) == (sentence_segments("   ", len)[0],)


def test_book_translate_cli_writes_json_and_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "book.json"
    source.write_text(_book(["Hello."]).model_dump_json(), encoding="utf-8")
    target = tmp_path / "ru.json"
    text = tmp_path / "ru.txt"
    engine = FakeEngine()
    monkeypatch.setattr("pdftranslate.cli.create_engine", lambda name, settings: engine)

    result = CliRunner().invoke(
        app,
        [
            "book-translate",
            str(source),
            "-o",
            str(target),
            "--text",
            str(text),
            "--cache-dir",
            str(tmp_path / "cache"),
        ],
    )

    assert result.exit_code == 0, result.output
    translated = BookDocument.model_validate_json(target.read_text(encoding="utf-8"))
    assert translated.paragraphs[0].translation == "HELLO."
    assert text.read_text(encoding="utf-8") == "HELLO.\n"
    assert "Translated 1/1" in result.output


def test_book_translate_cli_rejects_bad_input(tmp_path: Path) -> None:
    source = tmp_path / "book.json"
    source.write_text("{}", encoding="utf-8")
    runner = CliRunner()

    same = runner.invoke(app, ["book-translate", str(source), "-o", str(source)])
    assert same.exit_code == 2
    assert "must not replace" in same.output

    invalid = runner.invoke(app, ["book-translate", str(source), "-o", str(tmp_path / "o.json")])
    assert invalid.exit_code == 2
    assert "invalid book JSON" in invalid.output

    source.write_text(_book(["Hi."]).model_dump_json(), encoding="utf-8")
    no_model = runner.invoke(app, ["book-translate", str(source), "-o", str(tmp_path / "o.json")])
    assert no_model.exit_code == 2
    assert "--model" in no_model.output


def test_numbers_and_roman_numerals_are_not_sent_to_the_engine() -> None:
    engine = FakeEngine()

    result = translate_book(_book(["1", "XIV", "— 3 —", "One"]), engine, engine_name="fake")

    assert [item.translation for item in result.paragraphs] == ["1", "XIV", "— 3 —", "ONE"]
    assert engine.calls == [["One"]]
    assert not needs_translation("IV.")
    assert needs_translation("Vlad")
