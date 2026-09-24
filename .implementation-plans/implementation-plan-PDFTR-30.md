# PDFTR-30 implementation plan

1. Refactor the BODY-only typography adapter into a shared resolved-style mapper with thin,
   role-validating BODY and HEADING entry points; preserve normalized RGB and explicit deferred
   bold/italic behavior.
2. Update production region discovery so HEADING uses its authoritative resolved style by
   occurrence index with paragraph-id validation and fail-closed handling for missing, mismatched,
   or wrong-role styles.
3. Remove the obsolete uniform-heading-size gate because planning, geometry validation,
   measurement, insertion, and saved validation are already per occurrence.
4. Expose applied typography diagnostics for both BODY and HEADING within the production body-flow
   plan while leaving FOOTNOTE diagnostics unchanged.
5. Add deterministic regression tests for duplicate paragraph ids, role isolation, resolved
   HEADING properties, heterogeneous headings, orphan movement, continuation semantics, unsafe
   heading geometry, requested/applied face state, mixed-style/fallback state, selectable
   Cyrillic/Latin/Greek saved output, and unchanged BODY/FOOTNOTE behavior.
6. Run focused adapter, discovery, planner, renderer, diagnostics, and saved-segment tests; inspect
   a real repository PDF for naturally classified HEADING evidence without manufacturing labels.
7. Update `docs/reflow-architecture.md`, `docs/style-reconstruction.md`, the affected ProjectWiki
   architecture pages and log, and `CHANGELOG.md`; run ProjectWiki lint.
8. Rebuild/update code-review-graph, inspect the final blast radius, run `uv run pytest`, then run
   `scripts/check.ps1` with the repository-local temporary/cache configuration.
9. Create `.implementation-reports/implementation-report-PDFTR-30.md` and
   `reviews/review-PDFTR-30.md`. Attach the review and move the YouTrack ticket to its appropriate
   review state only after local acceptance criteria and available CI evidence are satisfied.
