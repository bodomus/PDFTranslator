"""Versioned UTF-8 JSON serialization and protected output writes."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import ValidationError

from pdftranslate.domain.document import ExtractedDocument


class OutputExistsError(ValueError):
    """The requested output exists or aliases the immutable source PDF."""


class DocumentJsonError(ValueError):
    """The input is unreadable or not a supported document JSON file."""


def document_to_json(document: ExtractedDocument, *, pretty: bool = True) -> str:
    """Serialize a document with stable field names and Unicode text."""
    excluded = (
        {"paragraphs", "reconstruction"} if document.schema_version in {"1.0", "1.1"} else None
    )
    return document.model_dump_json(
        indent=2 if pretty else None,
        by_alias=True,
        exclude=excluded,
    )


def document_from_json(value: str) -> ExtractedDocument:
    """Validate and deserialize an intermediate document."""
    try:
        return ExtractedDocument.model_validate_json(value)
    except ValidationError as error:
        raise DocumentJsonError(f"invalid document JSON: {error}") from error


def read_document_json(input_path: Path) -> ExtractedDocument:
    """Read and validate an extracted or translated UTF-8 document."""
    path = input_path.expanduser().resolve()
    if not path.exists():
        raise DocumentJsonError(f"document JSON does not exist: {path}")
    if not path.is_file():
        raise DocumentJsonError(f"document JSON is not a file: {path}")
    try:
        return document_from_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        raise DocumentJsonError(f"cannot read document JSON: {path}: {error}") from error


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
