# PDFTR-5 Investigation

## Scope and baseline

PDFTR-5 is a Level 2 orchestration, workspace, resume, error-contract, and public-CLI change.

- Repository: `J:/Projects/Python/PDFTranslator`
- Branch: `master`
- Baseline: `5604511591672c3af47c260acbfc5408897c0a62`
- Python: 3.12.10
- uv: 0.5.26
- Existing stages: inspection, extraction, local NLLB translation, translated-PDF rendering
- Existing safe boundaries: source SHA-256 identity, atomic JSON checkpoints, translation memory,
  renderer temporary output and reopen validation
- Pre-existing unrelated file preserved: `Tasks/PDFTR-5-end-to-end-cli.md`

The ticket Markdown was already attached to YouTrack and is mirrored under `Tickets/`.

## Current and expected behavior

Users currently invoke four separate commands and manage intermediate JSON themselves. Translation
resume applies only to an explicitly managed translated JSON file. There is no run identity, stage
manifest, pipeline log, failure record, centralized exit-code contract, dry-run summary, or safe
one-command publication boundary.

The required root workflow is `pdftranslate INPUT.pdf [options]`. It must run inspect, extract,
translate, render, and validate; keep resumable artifacts under the application cache; report stage
and block progress; reject incompatible resume state; and publish only a validated final PDF.

## Graph and source preflight

Graphify was refreshed without LLM extraction and contains 760 nodes, 1358 edges, and 45
communities. It identifies `cli.py` as the composition root, `PdfAnalyzer` / `PdfExtractor` as PDF
services, `translate_document()` as Typer-independent translation orchestration,
`TranslationCache` as normal cross-run text reuse, and `PdfRenderer.render()` as the safe rendering
boundary.

Code-review-graph was updated at the baseline commit: 331 nodes, 2256 edges, and 43 files. It
confirms no existing one-command entry point. The CRG `status` renderer hits a Windows CP1251
display defect after printing valid statistics; graph queries remain usable.

Source verification confirms that translation already supports injected translator, cache,
checkpoint, and progress dependencies. The renderer protects the source, saves temporarily,
reopens the candidate, and atomically publishes its requested destination. Rendering into the
workspace and publishing to the user destination only after a separate validation stage provides
the required five-stage safety boundary.

## Context7 findings

Current Typer documentation supports Path arguments, callback applications with subcommands,
explicit exit codes, and CliRunner tests. Platformdirs recommends the user cache for regenerable
application data. PyMuPDF supports separate-path save and reopen validation.

## Decisions

1. Add a Typer-independent `pdftranslate.pipeline` package and keep CLI code thin.
2. Centralize stable numeric exit codes in one `IntEnum`.
3. Derive a deterministic run ID from source identity and every behavior-affecting option.
4. Store inspection, extracted/translated JSON, rendered candidate, manifest, log, and failure
   state under `<cache>/workspaces/<run-id>/`.
5. Require an exact compatible manifest for `--resume` and validate each reused artifact.
6. Keep normal translation-memory reuse independent from stage resume.
7. Validate a workspace render candidate, validate a temporary output sibling, then atomically
   publish the final name.
8. Treat selected scanned pages as OCR-required; dry-run reports this without model loading.
9. Persist detailed tracebacks but show concise categorized CLI errors.
10. Inject services in tests so unit/CI runs never download a model or require CUDA.

## Expected blast radius and limitations

Changes affect new pipeline modules, root CLI dispatch, rendering validation exports, generated-PDF
tests, README, CHANGELOG, and ticket reports. Existing subcommands, document schemas, cache keys,
NLLB internals, and renderer layout behavior remain compatible. OCR, batch mode, GUI, cloud
translation, and image-text translation remain out of scope.
