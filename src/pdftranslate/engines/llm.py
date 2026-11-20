"""Local LLM engine over the OpenAI-compatible chat API (llama.cpp, Ollama, LM Studio)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pdftranslate.engines.base import (
    EngineCapabilities,
    EngineError,
    EngineRequest,
    EngineResult,
    EngineSettings,
)

PostJson = Callable[[str, dict[str, Any], dict[str, str], float], dict[str, Any]]

DEFAULT_ENDPOINT = "http://localhost:8080/v1"
PROMPT_REVISION = 2

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"^```[a-z]*\n?|\n?```$")
_LABEL = re.compile(r"^(?:перевод|translation)\s*:\s*", re.IGNORECASE)
_LATIN_WORD = re.compile(r"[A-Za-z]{3,}")
_CYRILLIC = re.compile(r"[А-Яа-яЁё]")

SYSTEM_PROMPT = """You are a professional literary translator from English into Russian.
Translate the paragraph the user gives you into natural, accurate Russian prose suitable for a
published book.

Rules:
- Output only the Russian translation of the paragraph. No comments, notes or quotes around it.
- Keep every fact, number, date and name. Do not summarize, add or omit anything.
- Russian people, places and institutions: use their established Russian spelling
  (Kryuchkov -> Крючков, Lubyanka -> Лубянка, Cheka -> ЧК), not a transliteration.
- Other foreign names: use the usual Russian transcription.
- Latin and other foreign expressions that a Russian edition would keep (agent provocateur,
  modus vivendi, persona non grata) stay in the original language.
- Keep abbreviations such as KGB, NKVD, FCD in their usual Russian form (КГБ, НКВД, ПГУ).
- Keep the paragraph as one paragraph."""


class LlmEngine:
    """Translate paragraphs with a chat model served by a local OpenAI-compatible server."""

    def __init__(self, settings: EngineSettings, *, post_json: PostJson | None = None) -> None:
        if not settings.model:
            raise EngineError("the llm engine requires --model (the name the server uses)")
        self._settings = settings
        self._endpoint = (settings.endpoint or DEFAULT_ENDPOINT).rstrip("/")
        self._post = post_json or _post_json
        self._domain = settings.extra.get("domain", "").strip()
        self._reasoning_off = True

    @property
    def engine_id(self) -> str:
        domain = f":{self._domain}" if self._domain else ""
        return (
            f"llm:{self._settings.model}:t{self._settings.temperature:g}:p{PROMPT_REVISION}{domain}"
        )

    @property
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            uses_context=True,
            uses_glossary=True,
            parallel_requests=max(1, self._settings.parallel_requests),
        )

    def translate(self, requests: Sequence[EngineRequest]) -> list[EngineResult]:
        workers = min(len(requests), self.capabilities.parallel_requests) or 1
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(self._translate_one, requests))

    def messages(self, request: EngineRequest) -> list[dict[str, str]]:
        system = SYSTEM_PROMPT
        if self._domain:
            system += f"\n\nThe book is about: {self._domain}."
        if request.glossary:
            terms = "\n".join(f"- {source} -> {target}" for source, target in request.glossary)
            system += (
                "\n\nUse these established translations, inflected as Russian grammar requires:\n"
                + terms
            )
        messages = [{"role": "system", "content": system}]
        if request.previous_source and request.previous_translation:
            messages.append({"role": "user", "content": request.previous_source})
            messages.append({"role": "assistant", "content": request.previous_translation})
        messages.append({"role": "user", "content": request.text})
        return messages

    def _translate_one(self, request: EngineRequest) -> EngineResult:
        last_error = "no attempt"
        for _attempt in range(2):
            try:
                raw = self._complete(self.messages(request))
            except EngineError as error:
                return EngineResult(None, str(error))
            text = clean_output(raw)
            problem = validate_translation(request.text, text)
            if problem is None:
                return EngineResult(text)
            last_error = problem
        return EngineResult(None, last_error)

    def _complete(self, messages: list[dict[str, str]]) -> str:
        payload: dict[str, Any] = {
            "model": self._settings.model,
            "messages": messages,
            "temperature": self._settings.temperature,
            "max_tokens": self._settings.max_output_tokens,
            "stream": False,
            # Answer directly instead of reasoning first: llama.cpp and LM Studio read the chat
            # template switch, Ollama reads reasoning_effort.
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if self._reasoning_off:
            payload["reasoning_effort"] = "none"
        headers = {"Content-Type": "application/json"}
        if self._settings.api_key:
            headers["Authorization"] = f"Bearer {self._settings.api_key}"
        url = f"{self._endpoint}/chat/completions"
        try:
            response = self._post(url, payload, headers, self._settings.timeout_seconds)
        except EngineError as error:
            # A server that rejects the field gets the request again without it, once for all.
            if not (self._reasoning_off and "reasoning_effort" in str(error)):
                raise
            self._reasoning_off = False
            payload.pop("reasoning_effort")
            response = self._post(url, payload, headers, self._settings.timeout_seconds)
        try:
            message = response["choices"][0]["message"]
            content = str(message.get("content") or "")
        except (KeyError, IndexError, TypeError, AttributeError) as error:
            raise EngineError(
                f"unexpected response from {self._endpoint}: {response!r:.200}"
            ) from error
        reasoning = message.get("reasoning") or message.get("reasoning_content")
        if not content.strip() and reasoning:
            raise EngineError(
                "the model spent its output on reasoning and gave no answer; "
                "turn thinking off for this model on the server"
            )
        return content


def clean_output(text: str) -> str:
    """Remove reasoning blocks, code fences and labels some models add around the answer."""
    cleaned = _THINK.sub("", text).strip()
    cleaned = _FENCE.sub("", cleaned).strip()
    cleaned = _LABEL.sub("", cleaned).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] == '"':
        cleaned = cleaned[1:-1].strip()
    return cleaned


def validate_translation(source: str, translation: str) -> str | None:
    """Reject empty, untranslated or wildly mis-sized output; return the reason or None."""
    if not translation:
        return "empty translation"
    if not _CYRILLIC.search(translation):
        if _LATIN_WORD.search(source):
            return "output contains no Russian text"
        if set(_LATIN_WORD.findall(translation)) - set(_LATIN_WORD.findall(source)):
            return "output is English text that is not in the source"
    ratio = len(translation) / max(1, len(source))
    if len(source) >= 80 and not 0.5 <= ratio <= 2.5:
        return f"suspicious length ratio {ratio:.2f}"
    return None


def _post_json(
    url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:200]
        raise EngineError(f"{url} returned HTTP {error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise EngineError(f"cannot reach {url}: {error}") from error
    except json.JSONDecodeError as error:
        raise EngineError(f"{url} returned invalid JSON") from error
    if not isinstance(data, dict):
        raise EngineError(f"{url} returned an unexpected JSON value")
    return data
