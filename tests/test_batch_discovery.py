from __future__ import annotations

from pathlib import Path

import pytest

from pdftranslate.batch import BatchOptions, default_batch_output_dir, discover_pdfs


def _pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-test")
    return path


def test_default_output_directory_is_a_sibling() -> None:
    assert default_batch_output_dir(Path("books")) == Path("books_ru")
    assert default_batch_output_dir(Path("library/books")) == Path("library/books_ru")


def test_non_recursive_discovery_is_case_insensitive(tmp_path: Path) -> None:
    root = tmp_path / "Books"
    selected = _pdf(root / "Manual.PDF")
    translated = _pdf(root / "already.RU.PDF")
    _pdf(root / "nested" / "ignored.pdf")

    discovery = discover_pdfs(BatchOptions(input_dir=root))

    assert discovery.discovered_files == (translated.resolve(), selected.resolve())
    assert discovery.selected_files == (selected.resolve(),)
    assert discovery.skipped_files[0].input_path == str(translated.resolve())
    assert ".ru.pdf" in discovery.skipped_files[0].reason


def test_recursive_discovery_excludes_output_tree_and_patterns(tmp_path: Path) -> None:
    root = tmp_path / "Книги с пробелами"
    output = root / "translated"
    first = _pdf(root / "A.pdf")
    second = _pdf(root / "nested" / "Б.pdf")
    excluded = _pdf(root / "nested" / "draft.pdf")
    output_pdf = _pdf(output / "old.pdf")

    discovery = discover_pdfs(
        BatchOptions(
            input_dir=root,
            output_dir=output,
            recursive=True,
            exclude_patterns=("**/draft.pdf",),
        )
    )

    assert discovery.selected_files == (first.resolve(), second.resolve())
    skipped = {Path(item.input_path).name: item.reason for item in discovery.skipped_files}
    assert "--exclude" in skipped[excluded.name]
    assert skipped[output_pdf.name] == "inside output directory"


def test_glob_and_order_use_relative_paths_deterministically(tmp_path: Path) -> None:
    root = tmp_path / "input"
    selected_root = _pdf(root / "root-final.pdf")
    selected_b = _pdf(root / "two" / "B-final.PDF")
    selected_a = _pdf(root / "one" / "a-final.pdf")
    ignored = _pdf(root / "one" / "notes.pdf")

    discovery = discover_pdfs(
        BatchOptions(input_dir=root, recursive=True, include_pattern="**/*-final.pdf")
    )

    assert discovery.selected_files == (
        selected_a.resolve(),
        selected_root.resolve(),
        selected_b.resolve(),
    )
    assert discovery.skipped_files[0].input_path == str(ignored.resolve())
    assert "--glob" in discovery.skipped_files[0].reason


def test_discovery_rejects_invalid_roots(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    try:
        discover_pdfs(BatchOptions(input_dir=missing))
    except ValueError as error:
        assert "does not exist" in str(error)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("missing input directory was accepted")


def test_batch_options_reject_non_json_report_and_conflicting_modes(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"\.json extension"):
        BatchOptions(input_dir=tmp_path, report_path=tmp_path / "report.pdf")

    with pytest.raises(ValueError, match="cannot be used together"):
        BatchOptions(input_dir=tmp_path, resume=True, overwrite=True)
