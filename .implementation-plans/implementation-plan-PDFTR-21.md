# Implementation Plan — PDFTR-21

1. Add explicit typed foreign-language preservation classification and privacy-safe evidence.
2. Implement deterministic conservative classification:
   - whole Greek units by Unicode-script evidence;
   - whole Latin units by multiple Latin function-word signals and minimum length;
   - Greek spans plus narrowly scoped academic Latin/French terms in mixed prose.
3. Keep foreign spans outside model inference, then compose their exact reinsertion with glossary
   and generic protected-token processing.
4. Integrate decisions into `translate_paragraphs`: bypass NLLB for preserved units, restore spans
   exactly for mixed units, aggregate counters/evidence, and retain repeated/marker precedence.
5. Persist the current translation behavior revision, bump cache/workspace identity, and reject
   stale direct-resume/completed artifacts.
6. Extend diagnostics and add deterministic unit/integration/round-trip/cache/resume regressions.
7. Update README, CHANGELOG, affected ProjectWiki pages, pilot evaluation, report, and review.
8. Run focused tests, Wiki lint, Ruff, mypy, full `scripts/check.ps1`, then the real CUDA Robitzsch
   regression and inspect the persisted translation artifact before the expected PDFTR-20 boundary.
9. Update CRG and inspect the final blast radius; refresh Graphify only if module boundaries change
   materially.
