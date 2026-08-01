# Implementation Plan — PDFTR-9

1. Add versioned benchmark dataset/result/review/finding models with strict uniqueness and stage
   trace validation.
2. Add pure deterministic checks that classify extraction, segmentation, protected-token, model,
   terminology and rendering findings.
3. Add a reusable runner that protects, segments, batches, restores and records model outputs,
   while loading no model itself.
4. Add atomic JSON/Markdown reporting and baseline comparison.
5. Add the thin `benchmark-translation` Typer command and expose only necessary package symbols.
6. Add a 61-sample synthetic dataset including both PDFTR-8 regression cases and all required text
   categories.
7. Add fake-backed tests for validation, malformed data, checks, stage attribution, reports,
   comparison, CLI behavior and no model download.
8. Update README and CHANGELOG with schemas, scoring scale, command examples and interpretation.
9. Run focused tests, CLI smoke/dataset validation, full `scripts/check.ps1`, post-change CRG and an
   explicit offline real-NLLB benchmark when the existing local model cache is available.
10. Write `implementation-report.md` and `reviews/review-PDFTR-9.md`, attach them and benchmark
    results to YouTrack, commit and push the branch. Do not start the next ticket.
