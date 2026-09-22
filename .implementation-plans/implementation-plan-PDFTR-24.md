# PDFTR-24 Implementation Plan

1. Extend typed reflow contracts with content kind and a document-level layout/page-map plan.
2. Add conservative footnote-group discovery from `ParagraphKind.FOOTNOTE`, source mappings,
   grouped x-range evidence, body boundary, margins, anchors, images, drawings, and optional
   separator evidence.
3. Reuse the forward-only planner for ordered footnote occurrences, source capacity, and bounded
   dedicated continuation regions while retaining exact occurrence identity and offsets.
4. Replace independent body planning with one per-source-page orchestration that plans body first,
   footnotes second, and produces one final source-to-output page map before mutation.
5. Validate body/footnote and footnote/anchor collisions before redaction; keep source graphics and
   redact only selected source fragments.
6. Distinguish `REFLOW_FOOTNOTE` results and add footnote-specific document aggregates while
   preserving existing generic reflow compatibility.
7. Add deterministic tests for ordering, continuation, duplicate IDs, exact reconstruction,
   collision/unsafe-object rejection, anchor/separator preservation, page-map ordering,
   segment-local validation, atomic failure, foreign text, body regression, and fixed-layout pages.
8. Run focused tests, controlled Robitzsch render and PNG inspection, full quality gates, Wiki
   lint, post-change CRG, and Graphify refresh if module relationships materially change.
9. Update `docs/reflow-architecture.md`, `CHANGELOG.md`, affected ProjectWiki pages/log, the
   implementation report, and `reviews/review-PDFTR-24.md`.
