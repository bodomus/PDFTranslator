from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from scripts.project_wiki.wiki_lint import validate_wiki
from scripts.project_wiki.wiki_search import search_wiki

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LINT_SCRIPT = REPOSITORY_ROOT / "scripts" / "project_wiki" / "wiki_lint.py"
SEARCH_SCRIPT = REPOSITORY_ROOT / "scripts" / "project_wiki" / "wiki_search.py"


@pytest.fixture
def wiki_root() -> Iterator[Path]:
    test_root = REPOSITORY_ROOT / "temp" / "project-wiki-tests" / str(uuid4())
    root = test_root / "knowledge" / "wiki"
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


def _write_source(wiki_root: Path) -> None:
    source = wiki_root.parent / "raw" / "source.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# Evidence\n", encoding="utf-8")


def _write_page(
    wiki_root: Path,
    relative_path: str,
    *,
    title: str,
    page_type: str = "component",
    status: str = "active",
    created: str = "2026-09-17",
    updated: str = "2026-09-17",
    tags: tuple[str, ...] = ("testing",),
    sources: tuple[str, ...] = ("../raw/source.md",),
    body: str = "# Example\n\nVerified body text.",
) -> Path:
    page = wiki_root / relative_path
    page.parent.mkdir(parents=True, exist_ok=True)
    tag_lines = "\n".join(f"- {tag}" for tag in tags)
    source_lines = "\n".join(f"- {source}" for source in sources)
    page.write_text(
        "\n".join(
            (
                "---",
                f"title: {title}",
                f"type: {page_type}",
                f"status: {status}",
                f"created: {created}",
                f"updated: {updated}",
                "tags:",
                tag_lines,
                "sources:",
                source_lines,
                "---",
                "",
                body,
                "",
            )
        ),
        encoding="utf-8",
    )
    return page


def _run_tool(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_valid_wiki_passes_lint(wiki_root: Path) -> None:
    _write_source(wiki_root)
    _write_page(
        wiki_root,
        "index.md",
        title="Test knowledge index",
        page_type="index",
        body="# Test knowledge index\n\n- [Details](details.md)",
    )
    _write_page(wiki_root, "details.md", title="Details")

    result = _run_tool(LINT_SCRIPT, "--wiki", str(wiki_root))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Pages: 2" in result.stdout
    assert "Errors: 0" in result.stdout
    assert result.stdout.rstrip().endswith("OK")

    report = validate_wiki(wiki_root)
    assert report.errors == []
    assert report.pages == 2

    matches = search_wiki(wiki_root, "verified body")
    assert matches
    assert matches[0].page.scalar("title") == "Details"


def test_broken_relative_link_fails_lint(wiki_root: Path) -> None:
    _write_source(wiki_root)
    _write_page(
        wiki_root,
        "page.md",
        title="Broken links",
        body="# Broken links\n\n[Missing](missing.md)",
    )

    result = _run_tool(LINT_SCRIPT, "--wiki", str(wiki_root))

    assert result.returncode == 1
    assert "missing link target: missing.md" in result.stdout


def test_invalid_type_fails_lint(wiki_root: Path) -> None:
    _write_source(wiki_root)
    _write_page(wiki_root, "page.md", title="Invalid type", page_type="ticket-dump")

    result = _run_tool(LINT_SCRIPT, "--wiki", str(wiki_root))

    assert result.returncode == 1
    assert "invalid type 'ticket-dump'" in result.stdout


def test_duplicate_title_fails_lint(wiki_root: Path) -> None:
    _write_source(wiki_root)
    _write_page(wiki_root, "one.md", title="Same durable topic")
    _write_page(wiki_root, "two.md", title="  same   durable topic  ")

    result = _run_tool(LINT_SCRIPT, "--wiki", str(wiki_root))

    assert result.returncode == 1
    assert "duplicate title" in result.stdout


def test_missing_source_and_invalid_date_order_fail_lint(wiki_root: Path) -> None:
    _write_page(
        wiki_root,
        "page.md",
        title="Invalid provenance",
        created="2026-09-18",
        updated="2026-09-17",
        sources=("../raw/missing.md",),
    )

    result = _run_tool(LINT_SCRIPT, "--wiki", str(wiki_root))

    assert result.returncode == 1
    assert "updated date is earlier than created date" in result.stdout
    assert "missing source target: ../raw/missing.md" in result.stdout


@pytest.mark.parametrize(
    ("title", "created", "expected_error"),
    (
        ("", "2026-09-17", "title must be a non-empty scalar"),
        ("Invalid calendar date", "2026-02-30", "invalid created date '2026-02-30'"),
    ),
)
def test_invalid_title_or_date_fails_lint(
    wiki_root: Path,
    title: str,
    created: str,
    expected_error: str,
) -> None:
    _write_source(wiki_root)
    _write_page(wiki_root, "page.md", title=title, created=created)

    result = _run_tool(LINT_SCRIPT, "--wiki", str(wiki_root))

    assert result.returncode == 1
    assert expected_error in result.stdout


def test_search_finds_and_prioritizes_title(wiki_root: Path) -> None:
    _write_source(wiki_root)
    _write_page(wiki_root, "title.md", title="PDF extraction architecture")
    _write_page(
        wiki_root,
        "body.md",
        title="Secondary topic",
        body="# Secondary topic\n\nThis paragraph mentions PDF extraction architecture.",
    )

    result = _run_tool(SEARCH_SCRIPT, "PDF extraction", "--wiki", str(wiki_root))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Matches: 2" in result.stdout
    assert result.stdout.index("1. PDF extraction architecture") < result.stdout.index(
        "2. Secondary topic"
    )


def test_search_finds_body_text(wiki_root: Path) -> None:
    _write_source(wiki_root)
    _write_page(
        wiki_root,
        "rendering.md",
        title="Output safety",
        body="# Rendering\n\nAtomic publication prevents partial output from becoming final.",
    )

    result = _run_tool(SEARCH_SCRIPT, "atomic publication", "--wiki", str(wiki_root))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Output safety" in result.stdout
    assert "matched: body" in result.stdout
