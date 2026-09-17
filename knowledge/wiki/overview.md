---
title: ProjectWiki overview
type: architecture
status: active
created: 2026-09-17
updated: 2026-09-17
tags:
- project-wiki
- knowledge
- onboarding
sources:
- ../../README.md
- ../../Tickets/PDFTR-19.md
related:
- index.md
- architecture/system-overview.md
- workflows/wiki-maintenance.md
---

# ProjectWiki overview

PDFTranslate is a Windows-first Python 3.12 command-line application that translates English PDF
content into Russian. Its verified pipeline can inspect, optionally OCR, extract, translate, render,
and validate documents, with batch and diagnostic workflows described in the repository README.

ProjectWiki is a small project-local knowledge layer for future coding agents. It consolidates
durable architectural context, decisions, constraints, failure modes, integrations, and testing
rules so later tickets do not have to rediscover them from scratch.

## Three layers

1. Canonical and raw sources provide evidence. Existing repository source, tests, tickets, reports,
   reviews, and docs stay in their canonical locations; `knowledge/raw/` holds only evidence that
   genuinely needs to live there.
2. `knowledge/wiki/` contains curated synthesis organized by durable topic rather than ticket.
3. `knowledge/AGENTS.md` and the validation scripts define how agents read, update, and verify it.

## What does not belong here

ProjectWiki does not replace source code, tests, Git history, YouTrack, implementation reports,
Graphify, CRG, schemas, generated artifacts, or runtime validation. It is not a dump of every
Markdown file and does not store model weights, PDFs, logs, caches, or full conversation history.

## How agents use it

For a non-trivial ticket, start at the [index](index.md), search for the affected subsystem, and
open relevant evidence before relying on an important claim. After implementation and tests reveal
what changed, update only the affected pages and run the Wiki linter.
