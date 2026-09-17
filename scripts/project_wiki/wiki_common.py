"""Shared, dependency-free helpers for ProjectWiki tooling."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

FRONTMATTER_BOUNDARY = "---"
MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


class FrontmatterError(ValueError):
    """Raised when a Wiki page has malformed frontmatter."""


@dataclass(frozen=True)
class WikiPage:
    """A parsed Markdown Wiki page."""

    path: Path
    metadata: dict[str, str | list[str]]
    body: str
    headings: tuple[str, ...]

    def scalar(self, key: str) -> str | None:
        value = self.metadata.get(key)
        return value if isinstance(value, str) else None

    def items(self, key: str) -> tuple[str, ...] | None:
        value = self.metadata.get(key)
        return tuple(value) if isinstance(value, list) else None


def default_wiki_root() -> Path:
    """Return the Wiki root for this repository layout."""

    return Path(__file__).resolve().parents[2] / "knowledge" / "wiki"


def discover_pages(wiki_root: Path) -> list[Path]:
    """Return Markdown pages in deterministic path order."""

    return sorted(
        (path for path in wiki_root.rglob("*.md") if path.is_file()),
        key=lambda path: path.relative_to(wiki_root).as_posix().casefold(),
    )


def parse_page(path: Path) -> WikiPage:
    """Parse the deliberately small ProjectWiki frontmatter subset."""

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_BOUNDARY:
        raise FrontmatterError("frontmatter must start on the first line with '---'")

    try:
        closing_index = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == FRONTMATTER_BOUNDARY
        )
    except StopIteration as error:
        raise FrontmatterError("frontmatter is missing its closing '---'") from error

    metadata = _parse_frontmatter_lines(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1 :]).strip()
    headings = tuple(match.group(1).strip() for match in HEADING_PATTERN.finditer(body))
    return WikiPage(path=path, metadata=metadata, body=body, headings=headings)


def markdown_link_targets(body: str) -> tuple[str, ...]:
    """Extract link and image targets from Markdown body text."""

    return tuple(
        _clean_markdown_target(match.group(1)) for match in MARKDOWN_LINK_PATTERN.finditer(body)
    )


def resolve_local_target(page_path: Path, target: str) -> Path | None:
    """Resolve a local link target, or return None for URLs and anchors."""

    cleaned = target.strip()
    if not cleaned or cleaned.startswith("#"):
        return None

    parsed = urlsplit(cleaned)
    if parsed.scheme or parsed.netloc:
        return None

    decoded_path = unquote(parsed.path)
    if not decoded_path:
        return None
    return (page_path.parent / Path(decoded_path)).resolve()


def _parse_frontmatter_lines(lines: list[str]) -> dict[str, str | list[str]]:
    metadata: dict[str, str | list[str]] = {}
    active_list: list[str] | None = None

    for line_number, original_line in enumerate(lines, start=2):
        stripped = original_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- "):
            if active_list is None:
                raise FrontmatterError(f"line {line_number}: list item has no field")
            item = _parse_scalar(stripped[2:].strip())
            if not item:
                raise FrontmatterError(f"line {line_number}: list item is empty")
            active_list.append(item)
            continue

        if original_line[:1].isspace() or ":" not in original_line:
            raise FrontmatterError(f"line {line_number}: expected 'field: value'")

        key, raw_value = original_line.split(":", maxsplit=1)
        key = key.strip()
        if not key:
            raise FrontmatterError(f"line {line_number}: field name is empty")
        if key in metadata:
            raise FrontmatterError(f"line {line_number}: duplicate field '{key}'")

        raw_value = raw_value.strip()
        if not raw_value:
            value: str | list[str] = []
        elif raw_value == "[]":
            value = []
        elif raw_value.startswith("[") and raw_value.endswith("]"):
            value = [
                item
                for item in (_parse_scalar(part.strip()) for part in raw_value[1:-1].split(","))
                if item
            ]
        else:
            value = _parse_scalar(raw_value)

        metadata[key] = value
        active_list = value if isinstance(value, list) else None

    return metadata


def _parse_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _clean_markdown_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        return target[1 : target.index(">")]
    match = re.match(r"([^\s]+)(?:\s+[\"'].*[\"'])?$", target)
    return match.group(1) if match else target
