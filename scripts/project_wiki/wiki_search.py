"""Search ProjectWiki pages with deterministic local lexical ranking."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

try:
    from .wiki_common import (
        FrontmatterError,
        WikiPage,
        default_wiki_root,
        discover_pages,
        parse_page,
    )
except ImportError:  # Direct script execution.
    from wiki_common import (  # type: ignore[no-redef]
        FrontmatterError,
        WikiPage,
        default_wiki_root,
        discover_pages,
        parse_page,
    )

TOKEN_PATTERN = re.compile(r"[\w-]+", re.UNICODE)


@dataclass(frozen=True)
class SearchResult:
    """One ranked Wiki search result."""

    page: WikiPage
    score: int
    matched_fields: tuple[str, ...]
    snippet: str


def search_wiki(wiki_root: Path, query: str, *, limit: int = 10) -> list[SearchResult]:
    """Return deterministic weighted matches for *query*."""

    phrase = " ".join(query.casefold().split())
    tokens = tuple(dict.fromkeys(TOKEN_PATTERN.findall(phrase)))
    if not tokens:
        raise ValueError("query must contain at least one word or number")
    if limit < 1:
        raise ValueError("limit must be at least 1")

    results: list[SearchResult] = []
    for path in discover_pages(wiki_root.resolve()):
        page = parse_page(path)
        title = page.scalar("title") or ""
        tags = " ".join(page.items("tags") or ())
        headings = "\n".join(page.headings)
        fields = (
            ("title", title, 8),
            ("tags", tags, 6),
            ("headings", headings, 4),
            ("body", page.body, 1),
        )
        score = 0
        matched: list[str] = []
        for name, value, weight in fields:
            normalized = value.casefold()
            token_hits = sum(normalized.count(token) for token in tokens)
            phrase_hit = bool(phrase and phrase in normalized)
            if token_hits or phrase_hit:
                matched.append(name)
                score += token_hits * weight
                if phrase_hit:
                    score += weight * 4
        if score:
            results.append(
                SearchResult(
                    page=page,
                    score=score,
                    matched_fields=tuple(matched),
                    snippet=_make_snippet(page.body, phrase, tokens),
                )
            )

    results.sort(
        key=lambda result: (
            -result.score,
            (result.page.scalar("title") or "").casefold(),
            result.page.path.as_posix().casefold(),
        )
    )
    return results[:limit]


def _make_snippet(body: str, phrase: str, tokens: tuple[str, ...]) -> str:
    compact = " ".join(body.split())
    lowered = compact.casefold()
    positions = [
        position
        for term in (phrase, *tokens)
        if term
        for position in [lowered.find(term)]
        if position >= 0
    ]
    if not positions:
        return compact[:180]
    position = min(positions)
    start = max(0, position - 60)
    end = min(len(compact), position + 120)
    prefix = "..." if start else ""
    suffix = "..." if end < len(compact) else ""
    return f"{prefix}{compact[start:end].strip()}{suffix}"


def _print_results(wiki_root: Path, query: str, results: list[SearchResult]) -> None:
    print("ProjectWiki search")
    print(f"Query: {query}")
    print(f"Matches: {len(results)}")
    for index, result in enumerate(results, start=1):
        title = result.page.scalar("title") or result.page.path.stem
        relative_path = result.page.path.resolve().relative_to(wiki_root.resolve()).as_posix()
        print(f"{index}. {title} [score={result.score}]")
        print(f"   path: {relative_path}")
        print(f"   matched: {', '.join(result.matched_fields)}")
        if result.snippet:
            print(f"   snippet: {result.snippet}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Text to find in Wiki titles, tags, headings, and bodies")
    parser.add_argument(
        "--wiki",
        type=Path,
        default=default_wiki_root(),
        help="Wiki directory (default: repository knowledge/wiki)",
    )
    parser.add_argument("--limit", type=int, default=10, help="Maximum results (default: 10)")
    arguments = parser.parse_args(argv)

    try:
        if not arguments.wiki.is_dir():
            raise ValueError(f"wiki directory does not exist: {arguments.wiki}")
        results = search_wiki(arguments.wiki, arguments.query, limit=arguments.limit)
    except (OSError, UnicodeError, FrontmatterError, ValueError) as error:
        print(f"ProjectWiki search failed: {error}")
        return 2

    _print_results(arguments.wiki, arguments.query, results)
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
