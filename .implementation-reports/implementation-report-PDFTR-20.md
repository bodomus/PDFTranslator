# PDFTR-20 implementation report

## Summary

Implemented fail-closed schema 1.3 logical-paragraph render completeness. The renderer now plans
and accounts for every paragraph occurrence before mutating a PDF. A required translated unit that
cannot fit at the configured minimum font size aborts rendering with actionable occurrence-level
diagnostics, so an incomplete candidate cannot reach pipeline publication.

## Workflow and scope

- Workflow level: 2 (final-PDF content integrity and atomic publication).
- Branch: `codex/PDFTR-20-strict-render-completeness`, created from `master` at `77ea815`.
- Changed boundaries: rendering result model, renderer planning/publication order, diagnostic result
  correlation, CLI summary, deterministic tests, README/CHANGELOG, and ProjectWiki.
- Unchanged boundaries: extraction/reconstruction schema, translation policy, cache identity, OCR,
  model/CUDA lifecycle, PDFTR-17 marker handling, and PDFTR-18 post-save Cyrillic validation.
- Explicitly excluded: full reflow, cross-page flow, repagination, page creation, typography
  redesign, and foreign-language preservation policy.

## Investigation and root cause

Current schema 1.3 rendering redacted every translatable source fragment, planned each translated
unit, skipped insertion when `_fit` returned no font size, omitted that overflow unit from
`_validate_saved_pdf`, and still saved and published the resulting PDF. Overflow therefore appeared
only as warnings while required content vanished.

The completed Robitzsch artifact contains 61 logical paragraph occurrences. Replaying the current
planner against the source produced:

- 40 rendered occurrences;
- 21 overflow occurrences;
- no evidence that post-save Cyrillic validation caused the missing regions.

The missing regions reported on pages 1, 3, and 4 align with overflow occurrences. Examples include
ten occurrences of `p0001-b0007`, two `p0003-b0005`, three `p0003-b0006`, and two
`p0004-b0004`. Four additional occurrences of `p0002-b0006` overflow on page 2. Every overflow
had `font_size=None`, five fitting attempts down to the 6 pt minimum, `expanded=False`, no
insertion, and no PDFTR-18 post-save expectation.

Split-block reconstruction can emit multiple paragraph occurrences with the same paragraph ID.
Consequently, completeness and diagnostics now use a stable document-order `unit_index` in addition
to the paragraph ID; an ID-keyed set or dictionary is not authoritative.

## Implementation

- Added stable `RenderState` values: `rendered`, `preserved`, `excluded_by_policy`, `overflow`,
  and `failed`.
- Extended `BlockRenderResult` with unit index, repeated-element policy, terminal state, minimum
  font size, and translated character count while retaining fitting/geometry evidence.
- Extended `RenderResult` with programmatic expected, preserved, excluded, and failed-unit views.
- Changed `PdfRenderer.render` to plan every page first, assemble one result per document-order
  source unit, enforce completeness, and only then redact, insert, save, run PDFTR-18 validation,
  and atomically publish.
- Added a dedicated `RenderCompletenessError`. Its concise message includes paragraph ID,
  occurrence index, page, state, source/final bbox, selected/minimum font size, attempts, expansion,
  and translated character count for every unresolved required unit.
- Missing planner results are explicitly classified as `failed`; they cannot disappear from the
  accounting invariant.
- `PRESERVE` becomes `preserved`; `SKIP` and `REMOVE` become `excluded_by_policy`. Existing source
  retention/removal behavior is unchanged.
- Debug mode writes only a separate failed-layout PDF on completeness failure. No requested output
  or successful debug PDF is published.
- Success-report diagnostics correlate ordered units by `unit_index`, avoiding duplicate-ID
  collapse, and expose policy terminal states.
- The standalone render CLI now reports rendered, preserved, and policy-excluded counts.

## Atomic publication and compatibility

- Completeness is enforced before PDF mutation and before creation of a saved render candidate.
- A failed new output path remains absent.
- With explicit overwrite and a pre-existing output, completeness failure leaves the previous file
  byte-for-byte unchanged.
- PDFTR-18 local-region saved-PDF validation remains after successful planning and insertion.
- Marker-only/pass-through split paragraphs remain renderable and are independently accounted even
  when they share a paragraph ID.
- Legacy schema 1.1 units also receive render results and fail closed on overflow.

## Deterministic validation

- Focused rendering/repeated/diagnostics/pipeline/validation suite: `66 passed` before the final
  repository gate.
- Policy tests cover `PRESERVE`, `SKIP`, and `REMOVE` without false completeness failures.
- Overflow tests cover exact diagnostics, partial-document failure, no new final PDF, preservation
  of an existing final PDF under overwrite, and a separate failed-layout artifact in debug mode.
- Marker/pass-through and PDFTR-18 saved-PDF tests remain in the focused suite.
- `uv run python scripts/project_wiki/wiki_lint.py`: 11 pages, 49 links, 0 errors, 0 warnings.
- `uv run ruff format --check .`: passed.
- `uv run ruff check .`: passed.
- `uv run mypy src`: passed for 83 source files.
- `scripts/check.ps1`: 243 passed, 1 skipped, coverage 88.65%.

## Real CUDA regression

Command used a repository-local temporary destination to preserve the user's existing untracked
`test10textpages.ru.pdf`:

```powershell
uv run pdftranslate ".\tests\Robitzsch Jan Maximilian - Epicurean Justice. Nature, Agreement, and Virtue - 2024_50.pdf" `
  --device cuda `
  --output .\temp\pdftr20-robitzsch.ru.pdf `
  --debug-layout `
  --report `
  --report-dir .\temp\pdftr20-real-report
```

Result: accepted ticket Outcome B.

- CUDA model loaded and translation completed 61/61 units with 57 cache hits and 0 misses.
- Render failed explicitly with 21 required overflow occurrences across pages 1–4.
- Every failure included exact occurrence-level geometry and fitting evidence.
- `temp/pdftr20-robitzsch.ru.pdf` was not created.
- No successful debug PDF was created.
- The layout-only `rendered.failed-render.pdf` was retained in the pipeline workspace.
- The requested report directory contains failed JSON and HTML reports; the full failure message
  lists all 21 unresolved occurrences.

Counts for the real artifact:

```text
source logical paragraphs: 61
required translated paragraphs: 61
rendered: 40
policy-excluded: 0
overflow/failed: 21
```

## ProjectWiki pilot

- Wiki pages consulted before implementation: `index.md`, `architecture/system-overview.md`,
  `workflows/development-workflow.md`, and `testing/wiki-validation.md`.
- Canonical/raw sources additionally opened: renderer, render models/errors, reconstruction and
  repeated-element models, pipeline runner, diagnostics builder/models, rendering/repeated/pipeline
  tests, and PDFTR-17/PDFTR-18 implementation reports. No new raw Wiki evidence was needed.
- Missing/stale Wiki knowledge discovered: no content-completeness invariant, overflow failure-mode
  page, or warning that schema 1.3 paragraph IDs are not occurrence-unique.
- Wiki pages updated: system overview, index, pilot evaluation, log, and new
  `failure-modes/render-completeness.md`.
- The Wiki avoided rediscovery of the high-level six-stage flow, source-immutability/publication
  boundary, and required quality workflow.
- Review exposed the duplicate-ID/occurrence-accounting gap, which is now documented.
- No unmeasured time or token saving is claimed.

## Graph analysis

- Graphify preflight located the renderer, fitting, insertion, saved-PDF validation, pipeline
  publication, and diagnostic relationships; all important conclusions were verified in source.
- CRG was rebuilt before implementation because it was stale on PDFTR-19.
- Post-change CRG update completed on the PDFTR-20 branch: 124 files, 1111 nodes, 9771 edges.
- Reported risk score: 0.40. Static test-link gaps were source-checked against direct renderer,
  CLI, diagnostics, repeated-policy, and end-to-end tests.
- Blast radius is confined to rendering results, renderer execution order, render diagnostics, CLI
  presentation, tests, and documentation. No extraction, translation, OCR, cache, dependency, or
  packaging boundary was crossed.

## Remaining risk and follow-up

The fixed-layout renderer cannot fit the 21 identified Robitzsch occurrences under current bounded
rules. This is now an explicit safe failure rather than data loss. A later dedicated reflow ticket
must design cross-block/page flow; PDFTR-21 owns foreign-language preservation and is intentionally
not implemented here.
