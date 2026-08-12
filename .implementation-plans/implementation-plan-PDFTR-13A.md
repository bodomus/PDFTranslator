# Implementation Plan — PDFTR-13A

## Classification

- Workflow level: Level 1 narrow benchmark correction.
- Scope: benchmark, benchmark tests, changelog, implementation report, and review only.
- Production glossary, translation pipeline, cache implementation, renderer, OCR, and CLI behavior
  remain unchanged.

## Investigation

- Current benchmark builds 64 plain strings and calls only `prepare_glossary_text()`.
- It reports zero model calls and does not exercise `LogicalParagraph`, repeated-element policy,
  protected tokens, segmentation, translator batches, glossary restoration/validation, or SQLite
  cache behavior.
- Source verification shows `translate_document()` dispatches schema 1.2 documents to
  `translate_paragraphs()`, which owns the complete required path and records cache/segment and
  glossary evidence in translation metadata.
- Graphify connects `LogicalParagraph`, `translate_paragraphs()`, `TranslationCache`, repeated
  classification, glossary preparation, protected text, segmentation, and fake-backed tests.
- CRG was rebuilt for this branch: 941 nodes and 8,151 edges.

## Implementation

1. Replace the matcher-only benchmark with a deterministic schema 1.2 document containing 64
   logical paragraphs and repeated classifications.
2. Add a deterministic fake translator that records batch calls and translated segment counts.
3. Execute four scenarios:
   - no glossary with a dedicated empty SQLite cache;
   - glossary cold run with a second empty SQLite cache;
   - identical glossary warm run reusing the second cache;
   - changed glossary target run against that same cache to prove fingerprint-scoped misses.
4. Derive glossary matches, required targets, violations, false matches, translator calls,
   translated segments, cache hits/misses, and elapsed time from runtime output and explicit
   assertions.
5. Fail the benchmark if expected cache reuse, changed-target invalidation, placeholder safety,
   protected values, or repeated preserve/skip behavior is not demonstrated.
6. Add focused tests for the report schema and exact deterministic counters.
7. Record measured results in `.implementation-reports/implementation-report-PDFTR-13A.md` and
   `reviews/review-PDFTR-13A.md`, retaining the fake-backend/NLLB/CUDA/OCR/manual-review caveats.

## Validation

- Focused benchmark test.
- Direct benchmark execution writing under `./temp/`.
- Existing glossary/translation/repeated/cache focused tests.
- Post-change CRG update and blast-radius check.
- Full `.\scripts\check.ps1`.
- GitHub Actions after push.
