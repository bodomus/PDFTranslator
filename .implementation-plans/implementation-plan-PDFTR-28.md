# PDFTR-28 implementation plan — style model and reconstruction

1. Preserve the exact updated YouTrack text as `Tickets/PDFTR-28.md` and work only on the required
   branch created from merged `master`.
2. Correct the four adjacent PDFTR-27 evidence/inspection defects: source/output aliasing,
   cross-column role regions, cross-column spacing, and non-adjacent baseline pairing. Add focused
   regression tests for each behavior.
3. Add immutable typed contracts for stability thresholds, aggregate property evidence,
   role-specific document baselines, decision sources, generic font roles, resolved paragraph
   styles, typed per-property decisions, and a versioned resolved-style document.
4. Implement conservative font-family grouping and generic font-role inference without filesystem
   or registry access.
5. Implement deterministic role baseline aggregation with a minimum sample count, categorical
   dominant-share threshold, numeric median/tolerance inliers, confidence floor, and absent-role
   semantics.
6. Implement direct → same-role → safe document-wide color → renderer-default resolution. Preserve
   original evidence values/confidence, explicit fallback reasons, mixed-style flags, paragraph ID,
   and authoritative occurrence index. Keep the single-gap spacing invariant.
7. Export pure `build_document_style_baseline`, `resolve_paragraph_style`, and
   `reconstruct_styles` APIs from `pdftranslate.typography`; do not connect them to production
   rendering.
8. Extend `scripts.typography_inspect` with opt-in `--resolved` side-by-side console/JSON output,
   filters, fallback counts, and safe source/output validation.
9. Add deterministic tests for all ticket scenarios: confidence precedence, role isolation,
   absent headings, robust aggregation/outliers, font identity/group/role, booleans, color,
   alignment, line height, indents, one-sided spacing, mixed flags, duplicate IDs, round-trip,
   immutability, and unchanged reflow/rendering behavior.
10. Run the reconstruction over the local Robitzsch source, retain JSON/stability evidence under
    repository-local `temp/`, and document representative page 1/3/4 BODY and FOOTNOTE decisions.
11. Add `docs/style-reconstruction.md`; update README only for the visible developer flag,
    CHANGELOG, the typography/reflow/system ProjectWiki boundary, and Wiki log. Run Wiki lint.
12. Run focused tests, Ruff format/lint, mypy, full `scripts/check.ps1`, update CRG and inspect the
    final blast radius. Refresh Graphify because the new production module boundary is structural.
13. Write `.implementation-reports/implementation-report-PDFTR-28.md` and
    `reviews/review-PDFTR-28.md`, then present the completed branch and validation evidence before
    any external YouTrack comment, attachment, or state transition.
