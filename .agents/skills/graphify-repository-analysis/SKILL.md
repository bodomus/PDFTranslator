---
name: graphify-repository-analysis
description: Use Graphify to orient within PDFTranslate architecture, discover relationships across CLI, document models, PDF extraction, translation backends, rendering, OCR, cache, batch processing, and tests, and produce source-verified context before structural implementation or review.
---

# Graphify Repository Analysis

## Repository workflow precedence

When `AGENTS.md` or `.codex/PRE_TICKET_WORKFLOW.md` requires this skill, the repository
workflow takes precedence.

- Level 2: full preflight when Graphify is available.
- Level 1: reuse or query when architectural context is relevant.
- Level 0: normally unnecessary.

## Purpose

Use Graphify for architectural orientation and candidate discovery across `PDFTranslate`.

Graphify is not authoritative. Validate important conclusions in current Python source,
`pyproject.toml`, `uv.lock`, tests, CLI behavior, generated fixture PDFs, and controlled runtime
evidence.

## Project scope model

Orient around the package and its major boundaries:

- CLI and application entry points;
- settings, paths, and logging;
- document/page/text-block domain models;
- PDF inspection and page classification;
- text extraction and reading-order normalization;
- JSON schema and serialization;
- translator protocol and local translation backends;
- tokenizer, segmentation, batching, and protected tokens;
- model loading, CUDA/CPU selection, and memory fallback;
- translation cache and resumable workspace;
- translated-PDF rendering and validation;
- OCRmyPDF/Tesseract subprocess integration;
- folder discovery, batch orchestration, and reports;
- tests, fixtures, scripts, and maintained documentation.

Likely source roots include:

```text
src/pdftranslate/
tests/
scripts/
```

Use the repository's actual structure when it differs.

## Use Graphify to find

- module and subsystem ownership;
- CLI-to-domain orchestration paths;
- pipeline-stage boundaries;
- document model and schema flow;
- PDF backend adapters;
- translator factories and implementations;
- model lifecycle ownership;
- cache and workspace ownership;
- OCR boundary and subprocess wrapper;
- rendering and output-validation flow;
- batch reuse of a single translator instance;
- test neighborhoods;
- cross-module relationships and likely blast radius.

## Exclusions

Exclude:

- `.git`, `.idea`, `.vscode`, `.vs`;
- `.venv` and other virtual environments;
- `__pycache__` and compiled Python files;
- `.pytest_cache`, `.ruff_cache`, `.mypy_cache`;
- build, wheel, distribution, coverage, and test-result output;
- `.code-review-graph` and `graphify-out`;
- generated PDFs and pipeline workspaces;
- extracted or translated runtime JSON artifacts;
- model weights, Hugging Face caches, Torch caches, and local databases;
- OCR temporary output, logs, and backups;
- large unrelated binary fixtures.

Retain:

- project-owned Python source;
- PowerShell scripts;
- `pyproject.toml` and relevant configuration;
- small deterministic fixtures and fixture generators;
- schema examples and maintained docs.

## Workflow

1. Resolve repository root.
2. Read `AGENTS.md`, `.codex/PRE_TICKET_WORKFLOW.md`, ticket, README, changelog, and relevant docs.
3. Confirm Graphify availability and exact installed commands.
4. Assess existing graph usability and freshness.
5. Reuse, build, or refresh only when justified.
6. Query with concrete ticket symbols, command names, and pipeline terms.
7. Build a compact candidate set.
8. Validate findings in source, tests, dependency files, and runtime evidence.
9. Record commands, findings, validation, disagreements, and limitations.

Do not invent `/graphify` commands, update flags, backend names, or configuration.

A previously successful local command in other repositories may have been:

```powershell
graphify label "." --backend ollama --batch-size 40
```

A local environment may use variables similar to:

```powershell
$env:OLLAMA_BASE_URL = "http://localhost:11434/v1"
$env:OLLAMA_API_KEY = "ollama"
$env:OLLAMA_MODEL = "qwen25coder14b:latest"
```

Confirm all syntax and local configuration before execution. Do not commit machine-specific
settings or silently switch backend/model.

## Query guidance

Prefer ticket-specific queries using actual repository symbols. Candidate terms include:

- `app`, `cli`, `main`, `doctor`;
- `Settings`, configuration, cache directory, workspace;
- `Document`, `Page`, `TextBlock`, schema version;
- `inspect`, `extract`, page classification, reading order;
- `Translator`, `NLLB`, backend factory, device selection;
- segmentation, tokenizer, batching, protected tokens;
- translation cache, source fingerprint, resume manifest;
- `render`, redaction, font fitting, overflow, validation;
- OCR, OCRmyPDF, Tesseract, subprocess;
- batch discovery, recursive processing, report;
- tests for the affected stage.

Use path queries only for navigation. A graph path is not proof of runtime execution order.

## Required architectural questions

For Level 2 work, determine:

1. Which module owns the behavior?
2. Which CLI command or orchestration path reaches it?
3. Which domain models and serialized schemas cross the boundary?
4. Which backend or adapter isolates third-party libraries?
5. Where are models, caches, workspaces, and temporary files owned?
6. Which stage is responsible for validation and failure reporting?
7. Which settings alter behavior?
8. Which tests cover the stage and its adjacent contracts?
9. Does the proposed change cross extraction, translation, rendering, OCR, or batch boundaries?
10. Could it invalidate cached or resumable artifacts?
11. Could it affect source-PDF safety or output-PDF integrity?
12. Could it cause repeated model loading or unexpected memory use?

## Source-validation rules

Verify:

- actual imports and package boundaries;
- console-script and `__main__` entry points;
- Typer command registration;
- protocol implementations and backend construction;
- Pydantic settings and environment prefix;
- JSON schema version and serializers;
- PyMuPDF calls and coordinate transformations;
- translation model and tokenizer invocation;
- model reuse and device selection;
- cache-key composition and storage paths;
- workspace/resume invalidation;
- subprocess argument construction;
- output file publication and validation;
- test assertions and fixture behavior;
- `pyproject.toml` and lockfile consistency.

When graph and source disagree, source wins.

## Domain-specific cautions

### PDF libraries

Graphify cannot prove that PyMuPDF operations preserve every PDF layout or that redaction is
safe for all page backgrounds. Validate with generated fixtures and representative PDFs.

### ML backends

Graphify cannot prove model availability, tokenizer limits, translation quality, CUDA support,
VRAM behavior, or deterministic output. Validate through isolated backend tests and explicit
opt-in runtime checks.

### OCR

Graphify cannot prove external executable availability, language packs, subprocess behavior,
or OCR quality. Validate dependency diagnostics, mocked tests, and optional integration tests.

### Serialization and resume

Graphify cannot prove old JSON, manifests, or cache entries remain compatible. Verify schema
versions, migration/rejection behavior, fingerprints, and round-trip tests.

## Expected working output

Graphify output may be stored under:

```text
graphify-out/
```

Do not commit generated graph output unless the repository explicitly requires it.

A useful investigation summary should include:

- queried terms and symbols;
- candidate modules;
- likely orchestration flow;
- adjacent contracts;
- test areas;
- source-verified findings;
- unresolved questions;
- graph limitations.

## Post-change policy

Refresh Graphify only when the change affects:

- package or module boundaries;
- major pipeline orchestration;
- document schema architecture;
- translation backend architecture;
- model lifecycle or cache ownership;
- OCR integration boundary;
- public CLI entry points;
- substantial cross-module relationships;
- broad refactoring.

For narrow local changes, reuse or query the current graph rather than rebuilding blindly.

## Failure handling

If unavailable or failing:

- record the exact confirmed command and concise error;
- preserve existing graph data;
- continue with CRG, `rg`, Python source, tests, CLI checks, and controlled PDF validation;
- report partial or unavailable Graphify analysis;
- do not fabricate architectural findings.

## Definition of done

- availability and freshness assessed;
- graph reused or refreshed only when justified;
- focused queries performed;
- relevant Python, configuration, schema, and test findings source-verified;
- exclusions avoided environment, model, binary, and generated-file noise;
- pipeline boundaries and likely blast radius documented;
- limitations reported accurately.
