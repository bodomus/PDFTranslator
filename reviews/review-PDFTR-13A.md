# Review — PDFTR-13A

## Verdict

Ready locally for review. The benchmark defect is corrected without rewriting glossary or changing
production translation behavior.

## Scope reviewed

- `scripts/benchmark-glossary.py` end-to-end fixture, fake translator, scenario orchestration,
  assertions, metrics, SQLite ownership, and JSON output.
- `tests/test_glossary_benchmark.py` executable contract coverage.
- `translate_paragraphs()` source path and adjacent repeated/glossary/protection/segmentation/cache
  contracts were inspected but not modified.
- Ticket, plan, changelog, implementation report, and review paths follow the current repository
  rules.

## Findings and resolutions

- The original benchmark was matcher-only: it measured preparation latency and reported zero model
  calls. It did not prove the requested pipeline or cache behavior.
- The replacement creates 64 actual `LogicalParagraph` instances and calls
  `translate_paragraphs()` directly.
- Repeated policy is exercised: 48 units translate, 8 page numbers preserve, and 8 watermarks skip.
- Generic token protection and segmentation are exercised by dates, URLs, Windows paths,
  identifiers, and long sentences; protected values are asserted after restoration.
- Cold glossary evidence is real pipeline metadata: 56 matches, 32 required targets, 0 violations,
  and 0 false matches.
- Fake translator evidence is non-zero and internally consistent: 8 calls and 57 translated
  segments in each cold scenario.
- Cache reuse is proven: the same glossary produces 48 hits, 0 misses, 0 translator calls, and 0
  translated segments on the repeated run.
- Cache invalidation is proven: a changed target changes the glossary fingerprint and produces 41
  misses plus 8 translator calls against the already populated glossary cache.
- Baseline and glossary cold runs use distinct newly created SQLite databases; warm and
  changed-target runs intentionally reuse only the glossary database.
- No unresolved internal placeholder is present in final translated text.

## Validation evidence

- Focused benchmark test: 1 passed.
- Focused combined matrix: 32 passed.
- Full quality gate: 190 passed, 1 skipped; coverage 87.91%.
- Ruff format/lint and mypy passed.
- CRG post-change analysis found 0 affected production flows. Its 12 heuristic test gaps do not
  recognize subprocess execution of the benchmark; the executable test asserts the exact JSON
  contract and counters.
- GitHub Actions: pending push at review creation.

## All review remarks and limitations

- The 0.003691-second warm result is evidence from one local run, not a stable speed guarantee.
- The benchmark uses a deterministic fake backend by design. It proves pipeline mechanics and
  cache identity, not Russian translation quality.
- Real NLLB, CUDA, OCR, and an external real-world PDF were not executed.
- Manual selection/copy/search inspection in PDF-XChange was not executed.
- The existing generated-PDF validation is also fake-backed; this remains acceptable and is stated
  without inflating it into real-model evidence.
- Generated benchmark JSON, SQLite databases, and run directories stay under ignored `./temp/` and
  are not committed.
- YouTrack does not contain a separate `PDFTR-13A` key. Completion will be recorded as a follow-up
  comment on PDFTR-13 unless a separate issue is created by the user.

## Recommendation

Merge PDFTR-13A after the pushed GitHub Actions workflow is green.
