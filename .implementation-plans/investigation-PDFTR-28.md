# PDFTR-28 investigation — style model and reconstruction

## Workflow and baseline

- Workflow level: 2 (new typed domain contract, aggregation policy, serialization, and developer
  inspection surface).
- Branch: `codex/PDFTR-28-style-model-reconstruction`, created from merged `master` commit
  `161b941219efe484459bf7c41e7fba98efba0ba7`.
- Initial worktree state: clean apart from the required saved ticket Markdown.
- Python 3.12 and the locked `uv` environment are available. The new worktree initially exposed
  broken archive entries in the shared uv cache; `uv sync --locked --refresh` restored the exact
  locked environment without changing dependencies or `uv.lock`.
- The focused PDFTR-27 typography/reflow tests execute successfully; their narrow invocation only
  fails the repository-wide coverage threshold, as expected for a subset run.

## Repository intelligence

Graphify was reused from the PDFTR-27 graph generated on 2026-09-23 because merged `master`
contains that exact typography implementation. Its candidate graph places typography extraction
beside `LogicalParagraph`, `ExtractedDocument`, reflow region discovery, footnote discovery, the
renderer, and typography/reflow tests. Source inspection confirms that relationship and also
confirms there is currently no runtime edge from typography evidence to rendering.

CRG was rebuilt for this worktree: 143 files, 1,390 nodes, and 12,250 edges. Source and `rg`
verification identify these adjacent contracts:

- `pdftranslate.typography.models` owns immutable Pydantic evidence values;
- `pdftranslate.typography.extractor.extract_typography_evidence` derives one item per occurrence;
- `pdftranslate.rendering.reflow.regions` and `.footnotes` independently construct `ReflowStyle`;
- `RenderOptions` supplies current renderer defaults;
- `scripts.typography_inspect` is a developer-only argparse boundary;
- `tests/test_typography.py`, `tests/test_reflow_production.py`, and `tests/test_rendering.py` protect
  evidence and unchanged rendering behavior.

Graphs are navigation aids only; all implementation decisions below were checked against current
source, tests, ProjectWiki, and the PDFTR-27/PDFTR-24 implementation evidence.

## Current behavior

`TypographyBaseline` is a versioned, derived, immutable diagnostic model. It contains direct and
geometry-inferred evidence, confidence, provenance, downstream fallback categories, role, mixed
inline flags, and authoritative occurrence indexes. It is not embedded in schema 1.3 and is not
consumed by `ReflowStyle`.

Production reflow still creates a small dataclass containing only font size, line-height ratio,
paragraph spacing, and a heading flag. Body and footnote paths derive those values separately from
paragraph spans and `RenderOptions`. Font discovery resolves a Cyrillic-capable local file only at
render time; source font names are not local font paths.

The PDFTR-27 developer script can emit evidence but cannot emit renderer-facing decisions. Its
`--output` path is not checked against the source PDF path.

## Implementation gap

There is no stable contract answering which value rendering should use when evidence is absent,
weak, mixed, or anomalous. There is also no role-aware aggregate, deterministic stability policy,
per-property decision source, explicit fallback trace, conservative font-family grouping/font-role
inference, or versioned resolved-style serialization.

Four source defects found during the merged PDFTR-27 review are relevant prerequisites:

1. the inspection script can overwrite its source PDF when `--output` aliases the input;
2. role regions combine different paragraph columns when inferring indents;
3. spacing can be measured across different columns;
4. filtering missing line baselines can join non-adjacent lines and report a doubled line height.

These defects will be fixed with focused regression tests because they directly affect the safety
and correctness of PDFTR-28 input evidence.

## Proposed boundary

Keep evidence contracts unchanged and add two focused modules:

- `pdftranslate.typography.style_models` — immutable JSON-safe style, baseline, threshold, and
  decision contracts;
- `pdftranslate.typography.reconstruction` — pure aggregation, normalization, and resolution.

This keeps policy independent of Typer, argparse, PyMuPDF, OS font discovery, and production
rendering. No new protocol, service class, inheritance hierarchy, dependency, or cache schema is
needed. The existing developer script may call the pure API, but production rendering will not.

## Resolution policy

- Accept direct `HIGH` and `MEDIUM` paragraph evidence; reject `LOW` and `UNKNOWN` as authoritative.
- Then use a stable same-role baseline.
- Use the document-wide baseline only for color, where cross-role fallback is renderer-safe.
- Otherwise use explicit renderer-safe defaults.
- Never use BODY size, weight, alignment, line-height, indentation, or spacing as HEADING or
  FOOTNOTE fallback.
- Preserve source font identity separately from a conservative normalized family group and generic
  font role. Do not resolve or scan local fonts.
- Keep `space_before` as the only evidence-derived physical gap; always resolve `space_after` to
  zero unless a future source-backed policy changes the invariant.

Role baselines require at least two acceptable samples. Categorical values require a dominant
share of at least two thirds. Numeric values use a median, property-specific tolerance, and require
both at least two inliers and at least two-thirds inlier support. One anomalous paragraph therefore cannot
redefine a stable role baseline. A role with no occurrences is represented as absent; the real
Robitzsch input must consequently have no HEADING baseline.

## Compatibility and blast radius

- `ExtractedDocument`, schema 1.3, translation cache/resume identity, OCR, model loading, and CLI
  commands remain unchanged.
- The new derived schema is version `1.0` and is not embedded in extraction artifacts.
- No PDF is reopened by reconstruction and no source/output PDF is written by the domain API.
- Production renderer imports and call paths remain unchanged, so pagination and visual output are
  no-op by construction.
- The developer script gains opt-in `--resolved` output and source/output alias protection.
- Tests, documentation, CHANGELOG, and the typography/reflow ProjectWiki boundary are affected.

## Validation requirements

- Focused evidence, reconstruction, script, reflow, rendering, and serialization tests.
- Real Robitzsch style reconstruction on pages 1, 3, and 4, with BODY/FOOTNOTE/mixed occurrences,
  no fabricated HEADING baseline, and a compact role stability report.
- Confirm the established nine-page Robitzsch result remains readable and/or rerun the cached
  deterministic rendering regression when the required local artifact is available.
- Ruff format/lint, mypy, Wiki lint, CRG update/blast-radius inspection, full pytest through
  `scripts/check.ps1`.
- Graphify refresh only if the implemented boundary materially differs from this two-module plan.
