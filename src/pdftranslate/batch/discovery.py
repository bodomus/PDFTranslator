"""Deterministic, feedback-safe PDF discovery for directory batches."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from pdftranslate.batch.models import BatchDiscovery, BatchOptions, BatchSkippedFile


def discover_pdfs(options: BatchOptions) -> BatchDiscovery:
    """Discover case-insensitive PDFs and retain every exclusion reason."""
    input_root = options.resolved_input_dir
    output_root = options.resolved_output_dir
    if not input_root.exists():
        raise ValueError(f"input directory does not exist: {input_root}")
    if not input_root.is_dir():
        raise ValueError(f"batch input must be a directory: {input_root}")
    if output_root.exists() and not output_root.is_dir():
        raise ValueError(f"output directory path is not a directory: {output_root}")

    iterator = input_root.rglob("*") if options.recursive else input_root.iterdir()
    pdfs = tuple(
        sorted(
            (path.resolve() for path in iterator if path.is_file() and _is_pdf(path)),
            key=lambda path: (path.relative_to(input_root).as_posix().casefold(), path.as_posix()),
        )
    )
    selected: list[Path] = []
    skipped: list[BatchSkippedFile] = []
    output_is_nested = output_root != input_root and output_root.is_relative_to(input_root)

    for source in pdfs:
        relative = source.relative_to(input_root)
        if output_is_nested and source.is_relative_to(output_root):
            skipped.append(_skip(source, "inside output directory"))
        elif source.name.casefold().endswith(".ru.pdf"):
            skipped.append(_skip(source, "translated .ru.pdf output"))
        elif not _matches(relative, options.include_pattern):
            skipped.append(_skip(source, f"does not match --glob {options.include_pattern}"))
        elif excluded := _excluded_by(relative, options.exclude_patterns):
            skipped.append(_skip(source, f"matched --exclude {excluded}"))
        else:
            selected.append(source)

    return BatchDiscovery(
        discovered_files=pdfs,
        selected_files=tuple(selected),
        skipped_files=tuple(skipped),
    )


def _is_pdf(path: Path) -> bool:
    return path.suffix.casefold() == ".pdf"


def _matches(relative: Path, pattern: str) -> bool:
    normalized = relative.as_posix().casefold()
    candidate = relative.name.casefold()
    selected = pattern.replace("\\", "/").casefold()
    variants = (selected, selected[3:]) if selected.startswith("**/") else (selected,)
    return any(
        fnmatch.fnmatchcase(normalized, variant) or fnmatch.fnmatchcase(candidate, variant)
        for variant in variants
    )


def _excluded_by(relative: Path, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        if _matches(relative, pattern):
            return pattern
    return None


def _skip(source: Path, reason: str) -> BatchSkippedFile:
    return BatchSkippedFile(input_path=str(source), reason=reason)
