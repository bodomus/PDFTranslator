---
name: code-review-graph-analysis
description: Use code-review-graph in PDFTranslate for exact Python symbols, imports, callers, dependants, CLI reachability, backend implementations, tests, review context, and blast-radius analysis before and after implementation.
---

# Code Review Graph Analysis

## Repository workflow precedence

When `AGENTS.md` or `.codex/PRE_TICKET_WORKFLOW.md` requires this skill, that workflow
takes precedence.

- Level 1 and Level 2: mandatory scoped preflight and post-change update when CRG is available.
- Level 0: normally unnecessary.

## Purpose

Use CRG as a structural dependency and review aid for `PDFTranslate`.

It complements but does not replace source inspection, dependency validation, unit and
integration tests, CLI smoke tests, real-PDF checks, model checks, OCR checks, or output-PDF
validation.

## Project scope

Analyze relationships across:

- `src/pdftranslate` package modules;
- Typer CLI commands and entry points;
- settings and logging initialization;
- document, page, and text-block models;
- JSON schema and serialization code;
- PyMuPDF inspection, extraction, redaction, rendering, and validation paths;
- translator protocols and backend implementations;
- tokenizer, segmentation, batching, and protected-token handling;
- model lifecycle, device selection, CUDA fallback, and OOM handling;
- translation cache and resumable workspace logic;
- OCR subprocess integration;
- batch discovery and report generation;
- unit, integration, and fixture-generation tests;
- PowerShell scripts and packaging entry points where represented.

## Exclusions

Exclude:

- `.git`, `.idea`, `.vscode`, `.vs`;
- `.venv` and other virtual environments;
- `__pycache__` and compiled Python files;
- `.pytest_cache`, `.ruff_cache`, `.mypy_cache`;
- coverage, build, wheel, and distribution output;
- generated PDFs and extracted/translated JSON artifacts;
- local model weights and caches;
- OCR temporary files and logs;
- `.code-review-graph` and `graphify-out`;
- large binary fixtures unless directly required for the ticket.

Retain project-owned source, scripts, small deterministic test fixtures, schemas, and docs.

## Workflow

1. Resolve repository root.
2. Read `AGENTS.md`, `.codex/PRE_TICKET_WORKFLOW.md`, ticket, and relevant docs.
3. Inspect the working tree and diff first for reviews.
4. Discover the exact installed CRG command and configuration.
5. Verify graph usability with a confirmed update or query, not file existence alone.
6. Collect ticket-specific symbols and relationships.
7. Validate every important relationship in current Python source and tests.
8. After implementation, update CRG and inspect blast radius.
9. Report coverage, discrepancies, and limitations.

Do not invent CLI syntax.

Commands such as these are examples only:

```powershell
code-review-graph --help
code-review-graph build
code-review-graph update --brief
code-review-graph detect-changes --brief
```

Confirm locally before execution.

## Required analysis

Inspect as applicable:

- protocols, abstract interfaces, and concrete implementations;
- constructors, factories, and dependency creation;
- callers, callees, imports, and module-level coupling;
- Typer application and command registration;
- `__main__` and console-script reachability;
- settings loading and environment-variable binding;
- document schema models and serializers;
- PyMuPDF adapters and page/block transformations;
- translator backend registration and selection;
- model loading and model reuse;
- device-selection and CUDA fallback paths;
- tokenizer and segmentation helpers;
- translation-cache reads and writes;
- workspace, resume, and source-fingerprint paths;
- OCR command construction and subprocess handling;
- renderer font fitting, overflow, and output validation;
- batch discovery, exclusions, and report generation;
- tests asserting the behavior;
- cancellation, retries, cleanup, and error paths.

Answer:

1. Which symbols change?
2. Who calls or imports them?
3. What depends on them?
4. What construction or registration makes them reachable?
5. Which CLI commands expose the behavior?
6. Which tests assert the behavior?
7. Which schema, cache, configuration, model, filesystem, or subprocess contracts are adjacent?
8. What is the blast radius?
9. Are new paths disconnected or unreachable?
10. Are obsolete paths still active?
11. Does the change unexpectedly cross extraction, translation, rendering, OCR, or batch boundaries?
12. Could the change affect source-PDF safety or final-PDF integrity?

## Python and dynamic-runtime caveat

CRG may not fully represent:

- dynamic imports;
- Typer/Click registration performed at runtime;
- protocol conformance without explicit inheritance;
- Pydantic model behavior;
- environment-driven configuration;
- subprocess behavior;
- PyMuPDF runtime semantics;
- Hugging Face model and tokenizer behavior;
- CUDA availability and memory behavior;
- reflection, monkeypatching, or fixtures;
- serialized JSON compatibility;
- filesystem state and resume caches.

Verify these directly in:

- Python source;
- `pyproject.toml` and `uv.lock`;
- CLI help and smoke tests;
- pytest unit and integration tests;
- generated fixture PDFs;
- controlled real-model or OCR validation when explicitly available;
- reopening and inspecting generated output PDFs.

## Ticket-specific review lenses

### PDF extraction and schema

Check:

- one-based CLI pages versus zero-based library indexes;
- stable block IDs and ordering;
- page dimensions and rotation;
- schema-version compatibility;
- source fingerprint propagation;
- no silent text omission.

### Translation and model lifecycle

Check:

- model loads once per process or batch;
- no silent truncation;
- tokenizer limits are respected;
- segment recombination is ordered;
- protected tokens remain intact;
- cache keys include all behavior-affecting settings;
- CPU fallback does not mask explicit CUDA failures;
- OOM retries are bounded.

### Rendering

Check:

- source PDF is never overwritten;
- translated JSON belongs to the source PDF;
- original text removal does not erase adjacent content;
- Cyrillic font paths are reachable;
- overflow is reported rather than clipped;
- final output is written atomically and reopened for validation.

### OCR

Check:

- executable discovery and command escaping;
- timeout and cancellation;
- `auto`, `on`, and `off` semantics;
- no duplicate OCR text layer;
- subprocesses are mocked in unit tests;
- OCR artifacts participate correctly in resume invalidation.

## Graphify comparison

Classify findings as:

- both tools plus source;
- Graphify plus source;
- CRG plus source;
- tool disagreement resolved by source;
- unresolved due to incomplete coverage.

Do not force agreement.

## Post-change review

After code changes:

- update CRG using a confirmed command;
- inspect changed symbols;
- inspect dependants and tests;
- inspect CLI and backend reachability;
- inspect schema/cache/configuration adjacency;
- inspect cross-stage pipeline impact;
- identify model, CUDA, OCR, filesystem, or packaging risk;
- investigate unexpected blast radius.

If blast radius exceeds the implementation plan, stop and reassess before broadening scope.

## Failure handling

Record the confirmed command and concise error. Preserve existing graph data. Continue with
Graphify, `rg`, Python source, dependency files, tests, CLI smoke tests, and controlled PDF
validation. Report unavailable or partial structural analysis.

Never fabricate relationships or claim graph freshness without a successful check.

## Definition of done

- CRG availability and freshness assessed;
- confirmed invocation used or absence reported;
- scoped dependency analysis completed;
- important relationships source-verified;
- CLI, schema, model, cache, OCR, rendering, and test adjacencies examined as applicable;
- graph updated after implementation when available;
- blast radius, discrepancies, and limitations documented.
