# Review — PDFTR-28 Style model / style reconstruction

## Summary

PDFTR-28 is implemented on `codex/PDFTR-28-style-model-reconstruction` from merged `master`.

The change adds a typed, versioned renderer-facing paragraph style contract and pure reconstruction
policy over PDFTR-27 evidence. Every resolved property retains source evidence, confidence,
decision source, fallback status, and reason. Role baselines are stable only with deterministic
sample/support/tolerance thresholds; BODY, HEADING, FOOTNOTE, and OTHER fallbacks remain isolated.

## Key decisions

- Reliable direct evidence wins; low/unknown evidence cannot silently override a role baseline.
- Only color may use a document-wide fallback. Other typography is same-role or safe-default.
- Source font identity, normalized family group, generic role, and future local font resolution are
  separate. No font installation lookup or substitution occurs.
- One physical paragraph gap is represented as space-before; space-after is zero with an explicit
  invariant decision.
- Mixed inline flags and duplicate-ID occurrence identity survive reconstruction.
- The derived schema stays outside `ExtractedDocument`, cache, and resume state.
- Production rendering does not import or consume the new contract; activation belongs to PDFTR-29.

The branch also fixes four prerequisite PDFTR-27 issues: inspector source/output aliasing,
cross-column region aggregation, cross-column gap measurement, and non-adjacent line-baseline
pairing.

## Real evidence

Robitzsch reconstructs all 61 occurrences (26 BODY, 35 FOOTNOTE) with no fabricated HEADING
baseline. Stable results include Garamond family, 10.959 pt BODY size, 1.138 BODY line-height ratio,
and 7.970 pt FOOTNOTE size. Representative justified, centered, indented, one-line, and mixed-style
occurrences on pages 1, 3, and 4 were inspected side by side.

BODY alignment remains correctly marked unstable at role level because the source contains
comparable LEFT/JUSTIFIED groups; reliable paragraph values still win directly. This is preferable
to manufacturing a document-wide alignment.

The retained PDFTR-24 result still opens as 9 pages with 8,907 extracted characters. Production
renderer/reflow files are unchanged, and their regression suite passes.

## Verification

- Follow-up regression fix: low-confidence source font names no longer override stable same-role
  family or generic font-role baselines; literal `source_font_name` identity remains preserved.
- Follow-up focused style reconstruction suite: **28 passed**.
- Follow-up full `scripts/check.ps1`: **321 passed, 1 skipped**, **88.74% coverage**.
- Focused style/evidence/reflow/render/diagnostics: **86 passed**.
- Full `scripts/check.ps1`: **319 passed, 1 skipped**, **88.64% coverage**.
- Ruff format/lint and mypy: passed.
- ProjectWiki: **15 pages, 94 links, 0 errors, 0 warnings**.
- Graphify refreshed: **3,492 nodes, 7,075 edges, 244 communities**.
- CRG updated: **1,393 nodes, 12,166 edges**, risk **0.55**, zero affected application flows.
- `git diff --check`: passed.

## Assessment

The ticket acceptance criteria are met. The contract is deterministic, traceable, role-isolated,
serializable, source-safe, and ready for PDFTR-29 without changing current PDF output.

Generated JSON and PDFs remain under ignored `temp/` locations and are not part of the change.
