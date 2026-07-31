# Implementation Report

## Ticket

PDFTR-5 - Add one-command end-to-end PDF translation

## Workflow

- Level: 2
- Graphify: refreshed and queried before and after implementation
- CRG: updated and queried before and after implementation
- Working tree before changes: dirty only because of the user-owned untracked
  `Tasks/PDFTR-5-end-to-end-cli.md`; it was preserved unchanged
- Baseline commit: `5604511591672c3af47c260acbfc5408897c0a62`

## Scope

- Modules: new `pdftranslate.pipeline` package, root CLI dispatch, final PDF validation export
- Pipeline stages: inspect, extract, translate, render, validate
- Dependency impact: none; `pyproject.toml` and `uv.lock` are unchanged
- Model/device impact: existing NLLB and CPU/CUDA behavior reused; model construction remains lazy
- OCR impact: no OCR implementation; selected scanned pages return the stable OCR-required code
- CLI/public contract impact: new `pdftranslate INPUT.pdf` workflow and centralized exit codes
- PDF/output integrity impact: source remains immutable; only validated temporary output is published

## Investigation

- Current behavior: four independent commands required user-managed intermediate JSON.
- Expected behavior: one root command completes all five stages, supports dry-run and stage resume,
  retains diagnostics, and never publishes a partial final PDF.
- Implementation gap: no orchestration owner, run identity, workspace/manifest, final validation
  stage, stable exit codes, or root PDF-path dispatch.
- Main symbols: `PipelineOptions`, `PipelineWorkspace`, `run_pipeline`, `plan_pipeline`,
  `PipelineServices`, `ExitCode`, `_RootCommandGroup`, `translate_pdf`, `validate_output_pdf`.
- Configuration/schema: application cache reused; new manifest schema 1.0; document JSON 1.0/1.1
  remains unchanged.
- Expected blast radius: CLI composition, all existing pipeline adapters, cache/filesystem safety,
  and tests; no changes to extraction schema, NLLB inference, or renderer layout algorithms.

## Changes

- Added typed stage/options/progress/result/dry-run models and centralized numeric exit categories.
- Added deterministic SHA-256 run identity from immutable source identity and relevant options.
- Added cache workspaces with atomic manifest/JSON writes, render candidate, UTF-8 logs, and
  structured failure state.
- Added strict `--resume` compatibility and artifact validation, completed-stage reuse, and partial
  translation checkpoint continuation.
- Added model-free dry-run with selected page classifications, block estimate, OCR requirement,
  backend/device, output, and expected stages.
- Added five-stage orchestration with fake-injectable services and lazy NLLB construction.
- Added separate candidate and temporary-sibling validation before atomic final publication.
- Added root PDF-path dispatch while retaining all existing Typer subcommands and compatibility
  with both pre-vendored and vendored Click Typer releases.
- Added 17 generated-PDF/fake-backend tests covering every ticket scenario and exit category.
- Updated README, CHANGELOG, investigation, implementation plan, and ticket mirror.

## Graph and source validation

- Graphify baseline: 760 nodes, 1358 edges, 45 communities.
- Graphify post-change: 905 nodes, 1845 edges, 48 communities.
- Graphify confirms reachability from `translate_pdf()` to `run_pipeline()`, workspace stage
  functions, translation, rendering, final validation, and the end-to-end tests.
- CRG baseline: 331 nodes, 2256 edges, 43 files at the baseline commit.
- CRG post-change update parsed 13 files and added 49 nodes / 551 edges; risk score 0.40.
- CRG reported dynamic Typer functions as test gaps, but source and coverage verify those paths are
  executed by root success and dry-run CliRunner tests. This is a graph limitation, not a missing
  test.
- CRG `status` has a Windows CP1251 output defect after printing statistics; updates and MCP
  queries still succeeded.
- No source/graph architecture disagreement remains. Source and executable tests were treated as
  authoritative.

## Post-change impact

- CRG updated: yes
- Graphify refreshed: yes, justified by new package boundaries, orchestration, and public CLI
- Blast radius: expected CLI imports plus PDF, serialization, translation, cache, rendering, and
  generated-PDF test neighborhoods
- Unexpected dependants: none; the broad two-hop CRG result is driven by the CLI composition root
- Compatibility concerns: no schema/dependency migration; incompatible workspace manifests are
  rejected; old subcommands remain available

## Validation

- Focused end-to-end tests: 17 passed
- Focused CLI plus end-to-end tests after Typer compatibility review: 26 passed
- Full tests: 88 passed
- Coverage: 84.42% (required minimum 80%)
- Ruff format: 58 files already formatted
- Ruff lint: passed
- mypy: strict check passed for 37 source files
- Bootstrap/check scripts: `scripts/check.ps1` passed
- CLI smoke tests: help, doctor, root missing-PDF dispatch, root fake-backend success, and dry-run
- Generated PDF validation: passed with page count, extracted Cyrillic text, spaces, and Unicode
- Real-model validation: not run; normal tests must not download model weights
- CUDA validation: not run; GPU is not required for CI and fake backend tests
- OCR integration validation: not run; OCR is explicitly a non-goal

## Documentation

- Updated `README.md` with one-command examples, stage progress, workspace files, resume, dry-run,
  atomic publication, and exit-code table.
- Updated `CHANGELOG.md` and roadmap.
- Updated `investigation.md` and `implementation-plan.md` for PDFTR-5.

## Remaining risks

- Real NLLB download/inference quality and actual CUDA execution require explicit opt-in validation.
- Renderer limitations for complex layouts/backgrounds remain those documented by PDFTR-4.
- Resume is intentionally strict: source or behavior-option changes require a fresh normal run.
- Typer command discovery is dynamic, so CRG cannot prove CliRunner reachability; executable tests
  provide that evidence.
