# ProjectWiki tools

ProjectWiki is a dependency-free Markdown knowledge layer stored under `knowledge/`. The scripts
are intentionally generic so another repository can reuse them with the same frontmatter schema.

Validate the repository Wiki:

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

Search titles, tags, headings, and page bodies:

```powershell
uv run python scripts/project_wiki/wiki_search.py "PDF extraction"
```

Both commands accept `--wiki PATH`. Search also accepts `--limit N`. A no-match search exits with
code 1; invalid input or an unreadable Wiki exits with code 2. Lint exits with code 1 when it finds
an error and never uses the network to validate external URLs.

The directory model is:

- `knowledge/raw/`: immutable evidence or small stable external-research notes;
- `knowledge/wiki/`: curated, source-backed project knowledge;
- `knowledge/AGENTS.md`: maintenance and agent workflow rules.

See [`knowledge/wiki/index.md`](../../knowledge/wiki/index.md) for the curated entry point and
[`knowledge/AGENTS.md`](../../knowledge/AGENTS.md) before maintaining the Wiki.
