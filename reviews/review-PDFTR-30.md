# Review PDFTR-30 — Heading typography fidelity

## Completed

- Activated reconstructed HEADING typography in production reflow by authoritative occurrence
  index, with paragraph id used only as validation.
- Shared the resolved-style conversion with BODY while retaining explicit role validation and
  `heading=True` only for HEADING.
- Applied resolved size, line height, RGB color, physical alignment, indents, and one-time spacing
  to measurement, pagination, orphan protection, continuations, insertion, and diagnostics.
- Removed the obsolete uniform-heading-size gate; safe heterogeneous headings now render from their
  own authoritative styles.
- Preserved fail-closed identity/role/geometry handling, exact accounting, disabled downscaling,
  saved-segment validation, source immutability, and atomic publication.
- Kept BODY behavior compatible and FOOTNOTE rendering/diagnostics unchanged.
- Preserved requested/unapplied bold and italic state, mixed-style state, and fallback counts
  without synthetic faces or inline-run rendering.
- Updated README, CHANGELOG, reflow/style documentation, ProjectWiki, investigation, and plan.

## Validation

- Focused suites: 78 passed.
- Full quality gate: 335 passed, 1 skipped, 89.14% coverage.
- ProjectWiki lint, Ruff format/check, and strict mypy: clean.
- Deterministic production PDF test verifies selectable Cyrillic/Latin/Greek heading text,
  occurrence diagnostics, zero unplaced characters, and strict saved-segment validation.
- The available real artifact contains natural HEADING evidence but has no page eligible for the
  existing production single-column reflow boundary, so no false real-PDF rendering claim is made.

## Review status

LOCAL IMPLEMENTATION COMPLETE — CI PENDING

`READY FOR REVIEW` is intentionally withheld until GitHub Windows and Ubuntu jobs pass.
