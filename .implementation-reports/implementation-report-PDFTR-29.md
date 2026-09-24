# PDFTR-29 implementation report

## Outcome

Production single-column BODY reflow now reconstructs typography once per schema 1.3 document and
maps styles to logical paragraphs by authoritative occurrence index. The renderer applies the
resolved BODY size, line-height ratio, RGB color, physical alignment, left/right indent,
first-line indent, and before/after spacing during planning and insertion.

## Implementation

- Added a BODY-only adapter from `ResolvedParagraphStyle` to the compact reflow contract.
- Expanded `ReflowStyle` and `PlacementSegment` with alignment, indents, spacing, mixed-style,
  fallback, and requested/applied bold/italic state.
- Reconstructed styles once in `PdfRenderer.render()` and passed an occurrence-index map to body
  discovery. Paragraph id is validated but is not the lookup key.
- Kept heading and footnote style selection outside the typography adapter.
- Made left/right indents reduce usable region width, first-line indent and space-before apply only
  to the first segment, and space-after apply only after the completing segment.
- Unified PyMuPDF fitting and insertion on the same HTML/CSS textbox representation with automatic
  scaling disabled and numeric HTML character references for safe Cyrillic/Greek embedding.
- Retained strict pre-mutation exact accounting, capacity failure, saved segment-local validation,
  reopen validation, and atomic destination replacement.
- Extended render/report diagnostics with physically applied BODY typography and explicit
  requested-versus-applied bold/italic state. Bold/italic variants remain safely deferred.

## Verification

- Focused reflow/rendering/diagnostics tests: 40 passed.
- Full `scripts/check.ps1`: ProjectWiki lint clean, Ruff format/check clean, mypy clean,
  325 passed, 1 skipped, total coverage 89.15%.
- Real cached Robitzsch validation: 61/61 render units, 7 BODY occurrences, 7 BODY segments,
  35 footnotes, 4 inserted pages, overflow 0, BODY unplaced 0, footnote unplaced 0.
- Compared Poppler PNGs for source pages 1, 3, and 4 with corresponding output pages 1, 5, and 7.
  Text remained selectable and legible, paragraph indentation/alignment were visible, and no
  clipping, overlap, or missing BODY text was observed.
- Machine-readable representative metrics are stored under ignored
  `temp/pdftr29-real/visual-fidelity-metrics.json`.

## Deferred behavior

The selected Cyrillic-capable font remains authoritative. Exact source font identity is preserved
in typography evidence but is not used as a local font lookup. Bold and italic requests are exposed
with `applied=false`; no synthetic styling or unsafe variant substitution was introduced.

## Follow-up planner safety fix

- Replaced the heading orphan vertical estimate with the normal style-aware `TextMeasurer` and
  fitting-prefix path, including BODY spacing, effective width, and true first-line indentation.
- Added one physical geometry check shared by ordinary planning and orphan evaluation. Safe
  hanging indents remain supported; first-line starts outside the flow region fail closed with
  `UnsupportedLayoutError` before PDF mutation.
- Added deterministic regressions for geometry-driven heading movement, safe negative indentation,
  and unsafe hanging-indent rejection. Existing continuation semantics remain covered.

### Follow-up files changed

- `src/pdftranslate/rendering/reflow/planner.py`
- `tests/test_reflow_production.py`
- `CHANGELOG.md`
- `docs/reflow-architecture.md`
- `knowledge/wiki/architecture/reflow-layout.md`
- `knowledge/wiki/log.md`
- this implementation report and `reviews/review-PDFTR-29.md`

### Follow-up validation

- Focused planner/rendering/diagnostics tests: 43 passed.
- Full `scripts/check.ps1`: ProjectWiki lint clean, Ruff format/check clean, mypy clean,
  328 passed, 1 skipped, total coverage 89.15%.
- Cached Robitzsch rerun: 61 units, 7 BODY occurrences in 7 segments, 4 inserted pages,
  overflow 0, BODY unplaced 0, footnote unplaced 0. Pagination remained unchanged.

## CI determinism fix

- Bundled the unmodified Liberation Sans Regular 2.1.5 font under `tests/resources/fonts/` with its
  SIL Open Font License 1.1 and source/checksum metadata.
- Changed only the shared test fixture so production reflow tests use identical font bytes and
  metrics on Windows and Ubuntu instead of selecting Segoe UI or DejaVu Sans by operating system.
- Production font discovery, renderer behavior, pagination limits, completeness enforcement, and
  planner/reflow logic remain unchanged.

### CI determinism validation

- Focused production reflow suite: 19 passed with the bundled font, including the pinned-path/hash
  regression and both tests that had failed under Ubuntu font metrics.
- Full `uv run pytest`: 329 passed, 1 skipped, total coverage 89.15%.
- Full `scripts/check.ps1`: ProjectWiki lint clean, Ruff format/check clean, mypy clean, and the
  same 329 passed / 1 skipped test result.
