---
title: ProjectWiki validation
type: testing
status: active
created: 2026-09-17
updated: 2026-09-17
tags:
- project-wiki
- lint
- search
- ci
sources:
- ../../../Tickets/PDFTR-19.md
- ../../../scripts/project_wiki/wiki_lint.py
- ../../../scripts/project_wiki/wiki_search.py
- ../../../scripts/check.ps1
related:
- ../index.md
- ../workflows/wiki-maintenance.md
---

# ProjectWiki validation

ProjectWiki validation is dependency-free and network-free. It is part of the local quality gate
and the existing GitHub Actions quality job.

## Frontmatter schema

Every Markdown file under `knowledge/wiki/` requires:

- `title`: non-empty scalar, unique case-insensitively after whitespace normalization;
- `type`: `architecture`, `component`, `workflow`, `decision`, `constraint`, `failure-mode`,
  `testing`, `integration`, `index`, or `log`;
- `status`: `active`, `deprecated`, or `to-be-documented`;
- `created` and `updated`: ISO calendar dates with `updated` not earlier than `created`;
- `tags` and `sources`: lists, which may be empty only when no truthful value exists;
- optional `related`: a list.

Only files named `index.md` may use `type: index`; only `log.md` may use `type: log`.

## Lint

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

Lint validates schema, duplicate titles, dates, local Markdown links, and local frontmatter source
targets. It ignores the reachability of external URLs rather than making CI depend on the network.

## Search

```powershell
uv run python scripts/project_wiki/wiki_search.py "PDF extraction"
```

Search ranks exact and token matches deterministically, weighting title, tags, headings, then body.
It does not use embeddings or persist an index. Exit code 1 means no match; invalid input or an
unreadable Wiki returns code 2.
