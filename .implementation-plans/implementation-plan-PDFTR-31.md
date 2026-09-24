# PDFTR-31 implementation plan

1. Add a thin `footnote_reflow_style()` role validator over the existing common resolved-style
   mapper, preserving `heading=False`, normalized RGB, mixed/fallback metadata, and explicit
   requested-but-unapplied bold/italic state.
2. Pass the renderer's existing occurrence-index style map into production footnote discovery.
   Validate map presence, embedded occurrence index, paragraph id, FOOTNOTE role, and physical
   alignment; fail closed without synthesized fallback when the authoritative map is supplied.
3. Preserve the current local footnote style only when discovery is intentionally called without a
   reconstructed-style map. Keep region geometry, separator discovery/ownership, continuation
   ordering, and capacity limits unchanged.
4. Extend role/content-kind-aware diagnostics so `REFLOW_FOOTNOTE` exposes the same applied
   typography and metadata fields as BODY/HEADING without cross-role leakage.
5. Add deterministic regressions for the FOOTNOTE adapter, duplicate-id occurrence mapping,
   missing/mismatched/wrong-role styles, resolved properties, BODY/HEADING isolation, continuation
   semantics, pagination, separator preservation, unsafe geometry, face-request diagnostics, and
   selectable mixed-script saved output.
6. Run focused tests with repository-local temporary/cache paths, then validate the cached
   Robitzsch artifact and record occurrence/segment/font-size/continuation/unplaced/overflow/page
   statistics plus representative visual evidence where the artifact is available.
7. Update README, CHANGELOG, reflow/style docs, affected ProjectWiki architecture pages and log;
   run ProjectWiki lint.
8. Update code-review-graph, inspect post-change blast radius, run the full pytest suite and
   `scripts/check.ps1` with repository-local temporary/cache configuration.
9. Create `.implementation-reports/implementation-report-PDFTR-31.md` and
   `reviews/review-PDFTR-31.md`; attach the review and update YouTrack only after the local quality
   gate and available CI evidence establish the appropriate state.
