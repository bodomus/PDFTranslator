"""Versioned UTF-8 JSON serialization and protected output writes."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from pdftranslate.domain.document import ExtractedDocument


class OutputExistsError(ValueError):
    """The requested output exists or aliases the immutable source PDF."""


def document_to_json(document: ExtractedDocument, *, pretty: bool = True) -> str:
    """Serialize a document with stable field names and Unicode text."""
    return document.model_dump_json(indent=2 if pretty else None, by_alias=True)


def document_from_json(value: str) -> ExtractedDocument:
    """Validate and deserialize an intermediate document."""
    return ExtractedDocument.model_validate_json(value)


def write_document_json(
    document: ExtractedDocument,
    output_path: Path,
    *,
    pretty: bool = True,
    overwrite: bool = False,
) -> None:
    """Atomically write UTF-8 JSON without ever replacing the source PDF."""
    output = output_path.expanduser().resolve()
    source = Path(document.source.path).resolve()
    if output == source:
        raise OutputExistsError("output path must not be the source PDF")
    if output.exists() and not overwrite:
        raise OutputExistsError(f"output already exists; use --overwrite: {output}")
    if output.exists() and not output.is_file():
        raise OutputExistsError(f"output path is not a file: {output}")

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = document_to_json(document, pretty=pretty)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
            delete=False,
        ) as temporary:
            temporary.write(payload)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        temporary_path.replace(output)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
