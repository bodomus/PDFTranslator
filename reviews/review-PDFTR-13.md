# Review — PDFTR-13

## Verdict

Ready locally for review: focused tests, generated-PDF validation, full `scripts/check.ps1`, coverage, Ruff, and mypy pass. Remote CI is pending push.

## Scope reviewed

- New glossary package and strict schema/loading/conflict boundaries.
- Logical paragraph translation, protected tokens, deduplication, cache, resume, batch runtime, CLI propagation, serialization, diagnostics, rendering-facing output, docs, benchmark, and tests.
- No OCR implementation, NLLB backend implementation, paragraph reconstruction algorithm, repeated classifier algorithm, or renderer layout behavior was changed.

## Review findings and resolutions

- Stable text structure: glossary matches `LogicalParagraph.text`; paragraph IDs, fragments, source mappings, raw blocks, reading order, headings, columns, and cross-page decisions are not rewritten.
- Repeated precedence: `preserve`/`skip` returns before glossary/cache/model. Translated repeated headers use glossary once per unique source and copy validated output/evidence to each logical unit.
- Conflict behavior: duplicates and semantic conflicts fail during strict load before model construction or partial batch processing.
- Protected-token compatibility: explicit glossary spans own overlap; glossary sentinels are then protected by the generic layer. Generic restoration precedes glossary restoration due this nesting; leak/missing-target checks fail closed before cache/publication.
- Cache/resume correctness: semantic fingerprint and behavior revisions are in cache and workspace identity; path/mtime/order do not control compatibility; changed target/version misses cache and mismatches resume.
- Diagnostics privacy: reports contain fingerprint, versions, stable entry IDs, modes, counts, status, and codes, but no glossary source/target strings by default.
- Batch: one loaded glossary instance is shared by the runtime and per-file statistics are serialized.
- CLI: strict-only `--glossary` is present on root, batch, and direct translate help. No partially implemented warn/off mode was added.

## Validation evidence

- Focused matrix: 62 passed.
- Full gate: 189 passed, 1 skipped; coverage 87.78%.
- Generated PDF: three pages; Russian target searchable three times; original English term absent; placeholders absent; preserve identifier semantically retained.
- Benchmark: 64 paragraphs, 128 matches, 0 measured violations/false matches, 0 model calls.
- Graphify refreshed to 1,824 nodes/3,974 edges; CRG refreshed to 891 indexed rows and reviewed against source/tests.

## Limitations and all review remarks

- Real NLLB/CUDA/OCR and an external real-world PDF were not executed; no such success is claimed.
- Automated PDF text extraction shows U+2010 in place of ASCII hyphens for rendered identifiers/dates. Normalized search passes, but the distinction is explicitly a renderer-layer observation and not hidden as glossary success.
- Selection/copy behavior was not manually checked in PDF-XChange during this run.
- `allow_model` provides no automatic inflection guarantee.
- Strict success evidence is implemented; a future warning mode would need explicit semantics/tests before exposure.
- `GLOSSARY_MATCH_AMBIGUOUS` is stable/reserved but deterministic priority resolves non-conflicting overlaps, so current strict success paths do not emit it.
- CRG’s heuristic gap list includes constructors/CLI branches despite executable integration/full tests; it was treated as review guidance, not as proof of missing behavior.
- Initial Graphify update was blocked by sandbox access and succeeded on the elevated retry.
- Generated PDFs, SQLite cache, benchmark JSON, logs, model assets, and runtime directories remain under ignored `./temp/` and are not committed.
- Ticket attachment/state update depends on connector support; the ticket Markdown is preserved under `Tickets/` and review/report files are ready for attachment.

## Recommendation

Merge only after the pushed GitHub Actions workflow is green. Do not start PDFTR-14.
