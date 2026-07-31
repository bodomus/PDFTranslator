# PRE_TICKET_WORKFLOW.md

> Mandatory repository-intelligence workflow for Codex before every non-trivial
> PDFTranslate ticket, bugfix, feature, refactor, dependency change, model integration,
> PDF-processing change, OCR change, CLI change, packaging change, investigation,
> implementation-planning task, or code review.

## 0. Authority and purpose

This workflow defines how the `PDFTranslate` repository must be investigated, changed,
and validated.

The repository may use:

1. **Graphify** for architectural and semantic repository orientation.
2. **code-review-graph (CRG)** for concrete structural relationships and impact analysis.

Neither graph is authoritative.

**Current Python source, tests, lockfile, generated diagnostic artifacts, runtime behavior,
and maintained documentation remain authoritative.**

Explicit user instructions take precedence, followed by applicable `AGENTS.md`, followed by
this workflow.

## 1. Project context

`PDFTranslate` is a Windows-first Python CLI utility for translating PDF documents from
English to Russian.

Expected technical direction:

- Python 3.12;
- `uv` for environment and dependency management;
- `pyproject.toml` and committed `uv.lock`;
- `src/pdftranslate` package layout;
- Typer and Rich for the CLI;
- PyMuPDF for PDF inspection, extraction, and rendering;
- local translation backends such as NLLB;
- optional CUDA acceleration;
- OCRmyPDF and Tesseract for scanned PDFs;
- pytest, Ruff, mypy, and pre-commit for quality checks;
- GitHub Actions without model downloads or CUDA requirements;
- no GUI unless explicitly requested by a future ticket.

The user may initially provide only an empty project directory. Initialization tickets must
create all required project files and tooling without relying on machine-specific paths.

## 2. Workflow levels

### Level 0 — trivial

Examples:

- spelling;
- formatting;
- comment-only edits;
- metadata-only edits;
- documentation changes that cannot alter installation, CLI, model, PDF, or OCR behavior.

Required:

- read applicable instructions;
- inspect working-tree state;
- validate the edited file.

No graph preflight required.

### Level 1 — local change

Examples:

- isolated bugfix in one known module;
- narrow CLI validation correction;
- focused PDF extraction fix;
- local renderer fitting correction;
- focused test change;
- small configuration or logging correction.

Required:

- repository baseline;
- CRG scoped analysis when available;
- source validation;
- focused tests;
- Graphify reuse/query when architecture context is relevant;
- no blind Graphify rebuild.

### Level 2 — structural or operational change

Examples:

- feature spanning extraction, translation, and rendering;
- document schema change;
- translation backend addition;
- model lifecycle or cache change;
- CUDA/CPU device-selection change;
- OCR integration;
- batch-processing pipeline;
- resume/workspace architecture;
- CLI contract or exit-code change;
- dependency-management or packaging change;
- broad refactor or architecture review.

Required:

- full Graphify preflight when available;
- full CRG preflight when available;
- investigation;
- implementation plan;
- source and configuration validation;
- post-change CRG update;
- targeted plus broader validation;
- Graphify refresh when architecture changed.

When uncertain, choose Level 2.

## 3. Execution order

1. Read instructions.
2. Resolve repository root and record Git state.
3. Classify workflow level.
4. Identify affected modules and runtime boundaries.
5. Check Graphify when applicable.
6. Check CRG when applicable.
7. Gather scoped graph context.
8. Validate findings in Python source, tests, `pyproject.toml`, lockfile, scripts, and docs.
9. Assess PDF integrity, model, cache, OCR, device, and filesystem safety.
10. Produce `investigation.md` and `implementation-plan.md` for Level 2.
11. Implement the smallest coherent change.
12. Update CRG when available.
13. Inspect blast radius and review context.
14. Run checks from narrowest to broadest.
15. Perform controlled manual or integration validation when required and available.
16. Refresh Graphify only for structural changes.
17. Update documentation and changelog when required.
18. Produce an implementation report.

Do not skip directly to implementation.

## 4. Repository baseline

Run from the repository root:

```powershell
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short
uv --version
uv run python --version
```

If the repository has not yet been initialized, record that fact and follow the initialization
ticket rather than assuming files already exist.

Read when present:

- root `AGENTS.md`;
- `.codex/PRE_TICKET_WORKFLOW.md`;
- ticket and acceptance criteria;
- applicable nested `AGENTS.md`;
- `README.md`;
- `CHANGELOG.md`;
- `CONTRIBUTING.md`;
- `pyproject.toml`;
- `uv.lock`;
- relevant scripts, configuration, schemas, and docs.

Identify:

- affected package/module;
- CLI entry point;
- pipeline stage: inspect, extract, translate, render, OCR, batch, validation;
- runtime dependencies;
- cache/workspace behavior;
- model and device requirements;
- test commands;
- pre-existing user changes.

Never clean, reset, stash, revert, delete, or overwrite unrelated user changes.

Never introduce workstation-specific absolute paths.

## 5. Graphify preflight

Follow the installed Graphify repository-analysis workflow when Graphify is available.

For Level 2 tasks, determine:

- owning package and subsystem;
- CLI-to-domain orchestration flow;
- document-model and serialization boundaries;
- PDF backend boundaries;
- translation backend interfaces;
- model lifecycle and cache ownership;
- OCR subprocess boundary;
- rendering and validation flow;
- likely test areas.

Expected working output may be under `graphify-out/`.

Exclude:

- `.venv`;
- Python caches;
- `.pytest_cache`;
- `.ruff_cache`;
- `.mypy_cache`;
- coverage output;
- build and distribution output;
- generated PDFs;
- model caches and weights;
- `.code-review-graph`;
- `graphify-out`;
- temporary workspaces and logs.

Do not exclude project-owned source, test fixtures, scripts, or configuration.

Use only confirmed installed Graphify commands. Do not invent commands, backend options,
or update flags.

A local environment may use Ollama, but verify machine configuration before execution.
Do not commit or alter machine-specific model settings.

Validate every implementation-relevant graph conclusion in source.

## 6. CRG preflight

Follow the installed code-review-graph workflow when CRG is available.

Use only confirmed repository-supported CRG commands.

Expected local state may be under `.code-review-graph/`.

For the ticket scope, identify:

- concrete functions, classes, protocols, and data models;
- callers and callees;
- CLI entry points and command registration;
- configuration loading;
- serialization boundaries;
- translation backend implementations;
- cache access;
- PDF backend calls;
- subprocess calls;
- tests;
- expected blast radius.

Do not treat graph-file existence as freshness. Confirm with a successful update or query.

## 7. Mandatory investigation

Answer before implementation:

1. What is the current behavior?
2. What is the expected behavior?
3. What is the root cause or missing capability?
4. What is the smallest correct change?
5. Which modules, functions, classes, schemas, configuration keys, scripts, and tests are affected?
6. Which CLI, JSON schema, cache, or filesystem contracts must remain compatible?
7. What is the expected blast radius?
8. Does the change affect source PDF integrity or output PDF validity?
9. Does it affect translation quality, segmentation, batching, or protected tokens?
10. Does it affect model loading, memory use, CUDA fallback, or CPU execution?
11. Does it affect cache correctness, resume behavior, idempotency, retries, or cancellation?
12. Does it affect OCR dependency detection or subprocess handling?
13. Which validation commands are required?
14. Which documentation or changelog files require updates?
15. Is there graph/source/documentation disagreement?

For Level 2, write:

```text
investigation.md
implementation-plan.md
```

## 8. Dependency and environment gate

For changes touching dependencies, Python versions, build backend, `uv`, packaging, CUDA,
PyTorch, Transformers, PyMuPDF, OCRmyPDF, or Tesseract:

1. inspect `pyproject.toml` and `uv.lock`;
2. preserve Python compatibility declared by the project;
3. use `uv` rather than introducing another environment manager;
4. update and commit `uv.lock` when dependencies change;
5. separate runtime and development dependencies correctly;
6. avoid unnecessary heavy dependencies;
7. verify Windows compatibility;
8. keep CPU-only development and CI paths functional where required;
9. never download models during unit tests or standard CI;
10. never commit model weights, local caches, virtual environments, or generated binaries;
11. document external system requirements;
12. run installation or synchronization validation after dependency changes.

A dependency change is not complete merely because imports compile.

## 9. PDF inspection and extraction gate

For PDF inspection, page classification, extraction, document models, coordinates, or JSON
schema changes, inspect:

- source-file validation;
- encrypted and corrupt PDF handling;
- page count and page dimensions;
- page rotation;
- text, image, mixed, scanned, and empty page classification;
- block bounding boxes;
- reading order;
- font metadata;
- one-based CLI page ranges versus zero-based library indexes;
- schema versioning;
- UTF-8 serialization;
- source fingerprinting;
- paths containing spaces and Cyrillic characters.

Requirements:

- never modify the source PDF;
- never silently omit extracted text;
- do not assume every PDF has a simple single-column reading order;
- report unsupported or ambiguous layouts;
- preserve deterministic ordering;
- validate JSON round-trips.

## 10. Translation and model gate

For translation backends, tokenization, segmentation, batching, cache, model loading,
or device-selection changes, inspect:

- translator protocol and backend isolation;
- model identifier and language codes;
- model load count;
- CPU, CUDA, and automatic device selection;
- CUDA availability detection;
- batch sizing;
- tokenizer limits;
- long-block segmentation;
- recombination order;
- URLs, email addresses, file paths, code fragments, numbers, and identifiers;
- translation-cache key correctness;
- cache invalidation;
- offline mode;
- interruption and resume behavior;
- out-of-memory handling;
- deterministic test doubles.

Requirements:

- load the model once per process or batch;
- never silently truncate source text;
- never silently drop blocks;
- bound retries and OOM fallback;
- keep model-specific types inside the backend;
- unit tests must use fake or mocked backends;
- CI must not download ML models;
- report selected model, device, and effective settings.

## 11. Rendering and output-PDF gate

For rendering, redaction, font fitting, layout, output validation, or font discovery changes,
inspect:

- source and translated-document identity;
- page count and dimensions;
- block identifiers;
- schema compatibility;
- original-text removal;
- neighboring content;
- non-white backgrounds;
- Cyrillic font availability;
- font embedding;
- wrapping;
- font-size reduction;
- minimum font size;
- overflow handling;
- block expansion;
- images and vector graphics;
- temporary output and atomic publication;
- reopening and validating the generated PDF.

Requirements:

- never overwrite the source PDF;
- never publish a partial result under the final output filename;
- never silently clip or discard translated text;
- report unresolved overflow;
- do not commit proprietary font files;
- do not rasterize full pages unless explicitly required;
- preserve page geometry and non-text content where practical;
- validate the final PDF by reopening it.

## 12. OCR change gate

For scanned PDFs, mixed PDFs, OCRmyPDF, Tesseract, Ghostscript, or subprocess changes,
inspect:

- page classification before OCR;
- `auto`, `on`, and `off` semantics;
- executable discovery;
- dependency versions;
- language-pack availability;
- command construction;
- argument escaping;
- timeout;
- cancellation;
- exit-code handling;
- stdout and stderr capture;
- temporary files;
- output validation;
- duplicate text layers;
- resume invalidation;
- paths containing spaces and Cyrillic characters.

Requirements:

- never install system dependencies automatically;
- never overwrite the source;
- use a controlled subprocess boundary;
- do not run OCR on normal text PDFs in auto mode;
- mock subprocesses in unit tests;
- keep optional integration tests separate;
- report missing dependencies with actionable diagnostics.

## 13. CLI and batch-processing gate

For CLI commands, arguments, exit codes, progress output, directory processing, or batch mode:

- validate arguments before heavy initialization;
- preserve stable documented command names and options;
- keep Typer code thin;
- keep domain logic callable without the CLI;
- define exit codes centrally;
- preserve redirected-output behavior;
- avoid Rich markup in machine-readable JSON;
- verify Ctrl+C and cancellation;
- verify default output naming;
- prevent source overwrite;
- prevent output directories and `.ru.pdf` files from re-entering discovery;
- ensure deterministic discovery order;
- initialize the translation model once per batch;
- return non-zero status for partial batch failure;
- generate a complete batch report.

## 14. Implementation rules

- Follow package architecture and dependency direction.
- Preserve user changes.
- Keep scope ticket-focused.
- Avoid unrelated refactoring.
- Use explicit typed boundaries.
- Propagate cancellation where supported.
- Avoid hidden global state.
- Avoid broad exception swallowing.
- Keep filesystem writes outside the source tree unless generating intentional project files.
- Use temporary files and atomic replacement for final artifacts where practical.
- Add or update tests for every behavior change.
- Re-query CRG when unexpected dependencies appear.
- Re-query Graphify when an unexpected subsystem boundary appears.
- Keep source, schemas, configuration, docs, tests, and CLI help synchronized.
- Do not add a GUI unless explicitly required.
- Do not add cloud translation APIs unless explicitly required.

## 15. Post-change CRG validation

After non-trivial code changes, when CRG is available:

1. run the confirmed CRG update;
2. inspect changed symbols;
3. inspect callers and dependants;
4. inspect CLI reachability;
5. inspect backend registration and construction;
6. inspect related tests;
7. inspect blast radius;
8. investigate unexpected cross-module impact;
9. verify new code is reachable;
10. verify obsolete paths are not unintentionally active.

If impact exceeds the plan, stop and reassess before expanding the change.

## 16. Validation order

Use the narrowest applicable command first.

Examples:

```powershell
uv run pytest tests/test_cli.py -q
uv run pytest tests/test_extraction.py -q
uv run pytest tests/test_translation.py -q
uv run pytest tests/test_rendering.py -q
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
uv run mypy src
.\scripts\check.ps1
```

After dependency changes:

```powershell
uv sync --locked
uv run pdftranslate --version
uv run pdftranslate doctor
```

When relevant and available, perform controlled manual checks using small fixtures:

```powershell
uv run pdftranslate inspect .\tests\fixtures\sample-text.pdf
uv run pdftranslate extract .\tests\fixtures\sample-text.pdf --output .\tmp\sample.json
uv run pdftranslate .\tests\fixtures\sample-text.pdf --dry-run
```

For real-model integration, use an explicit opt-in command or marker. Do not make normal unit
tests or CI download a model.

For OCR integration, run only when OCRmyPDF, Tesseract, and required system tools are confirmed
available.

Never claim execution that did not occur.

## 17. Graphify post-change policy

Refresh Graphify only if the change affected:

- package or module boundaries;
- major pipeline orchestration;
- document schema architecture;
- translation backend architecture;
- model lifecycle or cache ownership;
- OCR integration boundary;
- public CLI entry points;
- substantial cross-module relationships;
- broad refactoring.

CRG should be updated after every non-trivial code change when available.

## 18. Documentation obligations

Evaluate:

- `CHANGELOG.md`;
- `README.md`;
- `AGENTS.md`;
- `docs/*`;
- CLI `--help`;
- configuration examples;
- JSON schema documentation;
- model and cache documentation;
- OCR installation documentation;
- Windows setup documentation;
- troubleshooting documentation.

User-visible, operational, dependency, schema, CLI, model, OCR, or packaging changes require
documentation updates.

## 19. Failure handling

If Graphify or CRG fails:

- record the exact confirmed command;
- capture the concise error;
- do not fabricate findings;
- continue with source, `rg`, tests, and runtime checks when safe;
- report degraded analysis.

If CUDA, a translation model, OCR dependencies, or representative PDFs are unavailable:

- state what was unavailable;
- state which substitute, fake, mock, or fixture validation ran;
- state the remaining risk;
- do not claim real-model, GPU, OCR, or real-document validation occurred.

If a PDF is corrupt, encrypted, unsupported, or unsafe to process:

- fail clearly;
- retain diagnostics;
- do not modify or replace the source;
- do not publish a partial output as successful.

## 20. Required implementation report

```markdown
# Implementation Report

## Ticket
<ticket id and summary>

## Workflow
- Level: 0 / 1 / 2
- Graphify: used / unavailable / not required
- CRG: used / unavailable / not required
- Working tree before changes: clean / dirty / repository not initialized

## Scope
- Modules:
- Pipeline stages:
- Dependency impact:
- Model/device impact:
- OCR impact:
- CLI/public contract impact:
- PDF/output integrity impact:

## Investigation
- Current behavior:
- Expected behavior:
- Root cause or implementation gap:
- Main symbols:
- Configuration/schema:
- Expected blast radius:

## Changes
- ...

## Graph and source validation
- Graphify findings:
- CRG findings:
- Source/configuration validations:
- Discrepancies:

## Post-change impact
- CRG updated:
- Blast radius:
- Unexpected dependants:
- Compatibility or migration concerns:

## Validation
- Focused tests:
- Full tests:
- Ruff format:
- Ruff lint:
- mypy:
- Bootstrap/check scripts:
- CLI smoke tests:
- Real-model validation:
- CUDA validation:
- PDF manual validation:
- OCR integration validation:

## Documentation
- Updated:
- Not required because:

## Remaining risks
- ...
```

## 21. Non-negotiable rules

1. Do not start non-trivial implementation before applicable preflight.
2. Do not invent Graphify or CRG commands.
3. Do not trust graphs without source validation.
4. Do not destroy unrelated user changes.
5. Do not introduce workstation-specific absolute paths.
6. Do not overwrite source PDFs.
7. Do not publish partial output under the final output name.
8. Do not silently truncate, omit, or clip text.
9. Do not download models during unit tests or standard CI.
10. Do not require CUDA for normal development checks or CI.
11. Do not commit model weights, caches, generated PDFs, virtual environments, or temporary files.
12. Do not claim model, GPU, OCR, PDF, tests, or checks passed unless they were actually executed.
13. Update CRG after implementation when available.
14. Keep source, schemas, configuration, lockfile, tests, CLI help, and docs aligned.
15. Source and executable evidence win over graph inference.
