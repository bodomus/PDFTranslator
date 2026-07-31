"""SQLite translation memory with explicit corruption errors."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from pdftranslate.translation.errors import TranslationCacheError
from pdftranslate.translation.text import normalize_source_text

_SCHEMA = """
CREATE TABLE IF NOT EXISTS translations (
    cache_key TEXT PRIMARY KEY,
    translated_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


class TranslationCache:
    """Robust process-local access to translation memory."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> TranslationCache:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self.path)
            self._connection.execute(_SCHEMA)
            self._connection.commit()
        except (OSError, sqlite3.DatabaseError) as error:
            self.close()
            raise TranslationCacheError(
                f"cannot open translation cache {self.path}: {error}"
            ) from error
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def get(
        self,
        *,
        backend: str,
        model: str,
        source_language: str,
        target_language: str,
        source_text: str,
    ) -> str | None:
        key = cache_key(backend, model, source_language, target_language, source_text)
        try:
            row = (
                self._require_connection()
                .execute(
                    "SELECT translated_text FROM translations WHERE cache_key = ?",
                    (key,),
                )
                .fetchone()
            )
        except sqlite3.DatabaseError as error:
            raise TranslationCacheError(
                f"cannot read translation cache {self.path}: {error}"
            ) from error
        return None if row is None else str(row[0])

    def put(
        self,
        *,
        backend: str,
        model: str,
        source_language: str,
        target_language: str,
        source_text: str,
        translated_text: str,
    ) -> None:
        key = cache_key(backend, model, source_language, target_language, source_text)
        try:
            connection = self._require_connection()
            connection.execute(
                "INSERT OR REPLACE INTO translations(cache_key, translated_text) VALUES (?, ?)",
                (key, translated_text),
            )
            connection.commit()
        except sqlite3.DatabaseError as error:
            raise TranslationCacheError(
                f"cannot write translation cache {self.path}: {error}"
            ) from error

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise TranslationCacheError("translation cache is not open")
        return self._connection


def cache_key(
    backend: str,
    model: str,
    source_language: str,
    target_language: str,
    source_text: str,
) -> str:
    """Create a stable key from every behavior-defining identity field."""
    parts = (
        backend,
        model,
        source_language,
        target_language,
        normalize_source_text(source_text),
    )
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()
