# PDFTR-41 implementation plan

1. Complete source-verified investigation before production edits.
2. Add a pure source-list evidence/view helper; reject weak or contradictory geometry and semantic
   lookalikes. Reuse existing source spans without changing serialization.
3. Separate the proven marker before translation preprocessing; restore canonical structure per
   occurrence after provider/cache reuse under the clarified rule.
4. Adapt confirmed list evidence to ListLayoutContract in shared body reflow and preserve semantic
   inline offsets and source typography. Leave unsupported cases on existing paths.
5. Extend shared local saved-output occurrence validation for missing/duplicate/continuation markers.
6. Add deterministic source/provider regressions and actual saved-PDF geometry/pagination probes.
7. Update README, CHANGELOG and affected Wiki knowledge; update CRG/Graphify and assess blast radius.
8. Run focused tests and the required full PowerShell quality gate. Write report/review, commit only
   ticket implementation files, push, record implementer.json and validator handoff, then stop.

The earlier clarification commit contains only Tickets/PDFTR-41.md. No unrelated files belong in
the implementation commit. Independent exact-SHA review and merge remain outside implementer work.
