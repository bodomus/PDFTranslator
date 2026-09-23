# Review — PDFTR-27 Typography evidence extraction & style baseline

## Summary

PDFTR-27 is implemented on `codex/PDFTR-27-typography-evidence-style-baseline` from `master`.

The change adds a typed paragraph-occurrence typography baseline with explicit confidence,
provenance, and fallback for role, source font, size, bold, italic, RGB color, alignment, line
height, indents, and spacing. Mixed inline font/size/weight/italic/color evidence is retained.
Occurrence index remains authoritative when paragraph IDs repeat.

## Key decisions

- Typography is derived from the existing extracted document and not persisted inside schema 1.3.
- The existing PyMuPDF page pass now retains optional raw span flags and baseline origin.
- Source font names are identities only; no local-font availability is claimed.
- Dominant values are weighted by meaningful source characters, protecting font size from isolated
  superscripts and markers.
- Geometry inference is conservative; ambiguous and one-line properties remain unknown.
- Only observed gap-before is stored, preventing spacing double counting.
- Current renderer and reflow contracts do not consume the baseline.

## Verification

- Focused extraction/typography/reflow: **60 passed**.
- Full `scripts/check.ps1`: **290 passed, 1 skipped**, **88.57% coverage**.
- Ruff format/lint, mypy, and ProjectWiki lint all pass.
- Robitzsch pages 1, 3, and 4 were compared across raw PyMuPDF, reconstructed paragraphs, and typed
  evidence. Body resolves to dominant 10.959 pt Garamond; footnotes to 7.970 pt; representative body
  baseline spacing is 12.472 pt and first-line indent about 11 pt.
- The real excerpt has no classified heading occurrence; no heading role was invented.
- Existing nine-page PDFTR-24 Robitzsch output remains readable; no rendering code changed.
- Graphify and CRG were refreshed; source inspection resolves CRG's conservative false test-gap
  warning for the two newly retained `TextSpan` fields.

## Review assessment

Acceptance criteria are met. The result is a bounded, source-backed input contract for PDFTR-28,
with unknown/ambiguous evidence preserved and no production rendering regression.

Generated diagnostic JSON and PDFs remain under ignored `temp/` paths and are not part of the
change. The unrelated pre-existing deletion `temp/.agents.zip` remains untouched.
