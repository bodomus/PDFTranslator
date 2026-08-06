# Review — PDFTR-12

## Verdict

Ready for project review. Local checks and branch CI are green; the implementation satisfies the
ticket with conservative, typed, auditable behavior and does not start PDFTR-13.

## What was reviewed

- New `pdftranslate.repeated` domain/classifier boundary and its integration into extraction.
- Reconstruction isolation, translation/cache policies, renderer redaction/insertion behavior.
- Schema validation, pipeline behavior identity, batch/root/extract CLI propagation and settings.
- PDFTR-10 JSON/HTML diagnostic model inputs and privacy-default behavior.
- Generated fixtures, real generated-PDF round trip, benchmark, README and CHANGELOG.
- Graphify/CRG post-change impact plus direct source inspection of important relationships.

## Confirmed behavior

- Sequential page numbers are classified and preserved on their original pages.
- Uniform, alternating and first-page-exception headers are recognized when evidence is strong.
- Chapter-dependent and short-document repetition remains `unknown_repeated`, ambiguous and
  preserved; nothing uncertain is silently removed.
- Repeated legal text translates through the normal deduplication/cache path.
- Watermark candidates skip translation and remain visible in the source PDF; destructive removal
  is never selected automatically.
- Legitimately repeated body text with varying geometry remains body.
- Repeated units cannot merge into body paragraphs or across pages.
- Diagnostics contain counts, confidence, stable group IDs, policy and ambiguity without including
  source/translated text by default.
- Compatibility mode `--repeated-elements off` classifies every block as body and participates in
  cache/resume identity.

## Test evidence

- Focused and adjacent: **52 passed**.
- Full `scripts/check.ps1`: **174 passed, 1 skipped**, **87.47%** total coverage.
- GitHub Actions CI #30 on `5fd40d2`: completed successfully in 1m 20s
  (<https://github.com/bodomus/PDFTranslator/actions/runs/31087523817>).
- Formatting, Ruff and mypy: passed.
- Direct batch/extract help: passed and lists `--repeated-elements`.
- Generated-PDF rendering: page-specific translated body/header and original page numbers verified.
- Synthetic benchmark: body noise reduced from 32 blocks to 8; 24 service blocks separated
  (**75%**), with 4 groups and 0 ambiguous blocks in the benchmark fixture.

## Findings and limitations

1. No private publisher PDF corpus was supplied for this ticket. The checked PDF is generated but
   is a real PDF that is extracted, rendered, reopened and text-verified.
2. Real NLLB, CUDA and OCR were not executed; classifier tests deliberately use no model downloads,
   GPU or OCR system tools. Fake translation plus SQLite cache verifies policy and reuse behavior.
3. Exact normalized text is intentional. Fuzzy chapter-heading matching and OCR-corruption recovery
   are deferred to avoid false-positive removal or translation suppression.
4. Watermark detection remains an ambiguous candidate and never erases content. This matches the
   ticket's non-goal of watermark cleaning.
5. Preserve and skip policies leave source text/formatting untouched. Therefore uncertain English
   repeated content can remain English by design; diagnostics make this visible.
6. The first restricted Graphify refresh failed with Windows access denial; the approved elevated
   retry completed (1,665 nodes, 3,704 edges, 110 communities).
7. CRG reports 42 conservative possible gaps and risk 0.60. Its list includes indirect dataclass and
   Typer paths; focused CLI/integration/full-suite results cover acceptance behavior. Real-corpus
   calibration remains the meaningful next validation layer.

## Recommendation

Review this report and generated benchmark evidence before merging or starting the next ticket;
the branch is pushed, GitHub Actions is green, and measured coverage exceeds 80%.
