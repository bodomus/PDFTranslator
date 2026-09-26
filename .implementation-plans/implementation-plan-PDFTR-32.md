# PDFTR-32 Implementation Plan

## Workflow

- Level 2: cross-cutting production reflow change.
- Preserve the unrelated pre-existing deletion of `temp/.agents.zip`.
- Keep the change derived and renderer-facing; do not change schema 1.3, translation backends,
  cache/resume identity, OCR, or model/device behavior.

## Implementation

1. Add immutable source-candidate, translated-run, deferral, and mapping-result contracts plus a
   conservative source reconstruction/exact mapping helper.
2. Build inline mapping during BODY, HEADING, and FOOTNOTE discovery from existing
   `LogicalParagraph`/`TextSpan` evidence and the authoritative resolved paragraph base style.
3. Extend `FlowParagraph`, `PlacementSegment`, and `TextMeasurer` so every measurement receives the
   exact clipped/rebased runs for its text slice, including binary-search prefixes and heading
   orphan probes.
4. Replace the separate paragraph-only HTML/CSS calls with one rich-text builder used by both
   PyMuPDF measurement and insertion. Emit only supported size/color overrides; keep font family,
   bold, and italic diagnostic/requested-only.
5. Preserve exact segment accounting and strengthen validation of inline contract invariants before
   PDF mutation. Validate saved size/color only when extracted span text aligns reliably.
6. Add per-occurrence and aggregate applied/deferred inline diagnostics without exposing source
   prose in normal output.
7. Add deterministic tests for exact color and size, shifted target offsets, repeated ambiguity,
   partial preservation, segment crossing, heading orphan measurement, footnote continuation,
   unsupported faces, invalid runs, diagnostics, and saved selectable output.
8. Update README, CHANGELOG, reflow/style docs, affected ProjectWiki pages/log, implementation
   report, and final review file.

## Validation

1. Focused inline mapping and reflow production tests.
2. Full `uv run pytest`.
3. `uv run python scripts/project_wiki/wiki_lint.py` after Wiki edits.
4. Post-change CRG update, changed-symbol/dependant/test/blast-radius inspection.
5. `./scripts/check.ps1` as the final local quality gate.
6. Controlled deterministic PDF inspection with the bundled Liberation Sans font; use natural
   cached evidence only if available and report zero safely mapped natural runs honestly.
