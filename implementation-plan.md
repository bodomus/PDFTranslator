# Implementation plan — PDFTR-7

1. Add typed batch options, discovery results, per-file outcomes, and report models.
2. Implement deterministic case-insensitive PDF discovery with glob/exclude/output-tree and
   `.ru.pdf` filtering.
3. Add a shared translator/cache runtime and allow `run_pipeline()` to consume it without changing
   the default single-document lifecycle.
4. Implement sequential batch orchestration, relative output mapping, resume/overwrite behavior,
   fail-fast and continue-on-error policies, totals, and atomic JSON reporting.
5. Add the thin `pdftranslate batch` CLI command, progress/summary output, and partial-failure exit
   code.
6. Add focused unit/end-to-end/CLI tests using generated PDFs and fake translators.
7. Update README and CHANGELOG, create `reviews/review-PDFTR-7.md`, run all checks, refresh graphs,
   attach the review, commit, and move YouTrack to `In Review`.
