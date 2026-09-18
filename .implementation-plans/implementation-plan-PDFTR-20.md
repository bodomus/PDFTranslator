# PDFTR-20 implementation plan

1. Extend the existing rendering result contract with a small stable terminal-state enum and per-unit policy/index evidence. Keep one result for every schema 1.3 logical paragraph, including policy-excluded units, without using paragraph IDs as unique keys.
2. Refactor `PdfRenderer.render` into an explicit plan-first flow: build all page plans, assemble document-order completeness evidence, enforce the invariant, then redact/insert/save/validate/publish only when every required unit is renderable.
3. Raise a dedicated rendering error for unresolved required units. Include paragraph ID, page, state, source/final bbox, selected/minimum font size, attempt count, expansion flag, and translated character count. In debug mode, preserve a layout-only failure diagnostic without publishing a translated PDF.
4. Keep PDFTR-18 post-save validation unchanged for successfully planned Cyrillic units and retain legacy schema 1.1 behavior.
5. Make diagnostics consume ordered render evidence rather than an ID-keyed dictionary so split-block paragraphs remain distinct, and expose policy terminal states in reports.
6. Add deterministic tests for complete success, required overflow failure, partial-document failure, atomic output, policy exclusions, duplicate-ID marker/pass-through behavior, and PDFTR-18 validation regression.
7. Update README/CHANGELOG and the affected ProjectWiki pages, including a rendering completeness failure-mode page and pilot evaluation/log entries.
8. Run focused tests, formatting/lint/type checks, the full `scripts/check.ps1` gate, then the real Robitzsch CUDA regression. Expected fixed-layout outcome is explicit render failure listing the unresolved paragraph occurrences with no newly published partial PDF.
9. Update CRG and inspect the final blast radius; refresh Graphify only if module boundaries change.
