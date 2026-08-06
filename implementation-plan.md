# Implementation Plan — PDFTR-12

1. Add typed repeated-element kinds, policies, options, per-block/group evidence and metrics.
2. Implement conservative document-level normalization, position, bbox/font similarity,
   recurrence, parity, numeric sequence and first/last-page heuristics.
3. Classify before reconstruction, retain every source block, isolate confirmed repeated units
   from body and cross-page merges, and persist evidence in schema 1.2/1.3.
4. Apply translate/preserve/skip/remove policies without automatic removal; reuse translation/cache
   work for duplicate headers and legal text while maintaining page-specific paragraph anchors.
5. Update renderer and source revalidation so preserve/translate/skip semantics are deterministic
   and source watermark candidates remain untouched.
6. Add typed settings and `--repeated-elements auto|off` to root, extract and batch; include mode in
   pipeline identity and bump behavior revision.
7. Extend PDFTR-10 diagnostics with counts, confidence, group IDs, policy, ambiguity and a stable
   warning code without exposing report text by default.
8. Add generated fixtures for sequences, uniform/alternating/chapter headers, footers, legal text,
   legitimate repeated body, first-page exceptions, watermark, short documents, policy/cache,
   diagnostics and page-correct rendered PDF output.
9. Add a deterministic synthetic benchmark, update README/CHANGELOG/help, run focused and full
   checks, then refresh/query Graphify and CRG and source-verify their conclusions.
10. Create `implementation-report.md` and `reviews/review-PDFTR-12.md`, update YouTrack, commit,
    push and record CI status without beginning PDFTR-13.

---

# Implementation Plan — PDFTR-11

1. Add immutable raw-line, paragraph-fragment, source mapping, logical-paragraph, decision,
   metrics and reconstruction-result models plus validated typed reconstruction options.
2. Implement a pure conservative reconstructor using page/column geometry, gaps, alignment,
   indentation, typography, punctuation, lowercase continuation, list/heading/caption/footnote
   traits, repeated header/footer detection and bounded cross-page continuation.
3. Replace destructive extractor merging with raw line preservation and document-level
   reconstruction; add schema 1.2 while retaining legacy 1.0 parsing.
4. Update translation orchestration to select logical paragraphs for reconstructed documents,
   preserve checkpoints/resume mapping, write schema 1.3, and translate each paragraph once.
5. Update rendering validation/planning so every mapped source rectangle is redacted and each
   paragraph is inserted exactly once into its deterministic first-page anchor union.
6. Extend PDFTR-10 diagnostic models/builders/reports with reconstruction metrics, stable decision
   codes, source block IDs, fragment rectangles, merge reasons and ambiguity evidence.
7. Add `conservative|off` typed mode propagation to extract, root pipeline and batch CLI paths;
   add settings-backed tolerances and bump the pipeline behavior revision.
8. Add generated model/PDF fixtures and focused tests for split/separate paragraphs,
   heading/body, bullets, numbering, soft/real hyphens, CLI options, identifiers, two columns,
   captions, footnotes, page continuation, ambiguity, reversible mapping and no duplicate render.
9. Add deterministic before/after benchmark cases and assertions that reconstructed output improves
   the fragmented baseline without unexplained regression.
10. Update README, CHANGELOG, CLI help and schema/configuration documentation.
11. Run focused tests from narrowest to broadest, direct CLI help/smoke checks and full
    `.\scripts\check.ps1` with all temporary output under `./temp/`.
12. Update CRG, inspect changed symbols/reachability/blast radius, refresh/query Graphify because
    architecture changed, and source-verify both results.
13. Create `implementation-report.md` and `reviews/review-PDFTR-11.md`, attach the review to
    YouTrack when the available interface permits, move the ticket to In Review, commit, push and
    verify GitHub Actions before handoff.
