# PDFTR-12 — Repeated headers, footers and boilerplate detection

## Summary

Detect recurring non-body elements and stop them polluting paragraph reconstruction and translation.

## Dependencies

Requires completion of PDFTR-1 through PDFTR-11 unless this ticket explicitly refers to findings that can be gathered in parallel.

## Required workflow

Treat this as a Level 2 task under `.codex/PRE_TICKET_WORKFLOW.md`.

Before implementation:

1. inspect the current repository, Git state, `AGENTS.md`, workflow instructions, tests, CLI, schemas and relevant pipeline stages;
2. run confirmed Graphify and CRG preflight when available;
3. validate graph findings in Python source;
4. create `investigation.md` and `implementation-plan.md`;
5. preserve unrelated user changes;
6. implement the smallest coherent solution.

## Goal

Classify page numbers, running headers/footers, repeated legal text, document identifiers and watermark candidates conservatively.

## Scope and requirements

- Use document-level heuristics based on normalized text, page position, bounding-box/font similarity, recurrence ratio, page parity, numeric sequence and first/last-page exceptions.
- Classify at least: body, page number, running header, running footer, repeated boilerplate, watermark candidate and unknown repeated.
- Retain every original block and metadata.
- Define policies `translate`, `preserve`, `skip`, and `remove` with conservative defaults: preserve page numbers, translate reusable headers once, reuse repeated legal text, and preserve/warn on uncertainty.
- Exclude confirmed headers/footers/page numbers from body paragraph reconstruction and cross-page merging.
- Ensure page-specific rendering remains correct and repeated translations use cache.
- Add counts, confidence, group IDs, policy and ambiguity to PDFTR-10 diagnostics.
- Provide typed configuration and only minimal CLI controls such as `--repeated-elements auto|off` when justified.

## Tests and validation

Cover sequential page numbers, uniform and alternating headers, chapter-dependent headers, footer, copyright, legitimately repeated body sentence, first-page exception, watermark candidate, short document and policy behavior.

Normal unit tests and CI must not download translation models, require CUDA, or require OCR system tools. Use generated fixtures, fakes and mocks. Real-model, GPU, OCR and real-PDF tests must be explicit opt-in checks.

## Acceptance criteria

- [ ] Page numbers are detected in fixtures.
- [ ] Headers/footers are conservative.
- [ ] Confirmed elements are excluded from body merging.
- [ ] Uncertain content is never silently removed.
- [ ] Translation reuse works.
- [ ] Rendering remains page-correct.
- [ ] Diagnostics show confidence and policy.
- [ ] Real/benchmark evidence shows reduced noise.
- [ ] All checks pass.

## Non-goals

No watermark erasure, document cleaning, OCR image editing, broad chapter detection, or GUI rules editor.

## Documentation

Update the applicable files:

- `README.md`;
- `CHANGELOG.md`;
- CLI `--help`;
- configuration/schema documentation;
- troubleshooting or Windows instructions where relevant.

## Required completion report

Provide:

1. repository state before changes;
2. workflow level and Graphify/CRG status;
3. investigation findings and root cause or capability gap;
4. files and symbols changed;
5. commands actually executed;
6. focused and full test results;
7. Ruff, mypy and script results;
8. real-model, CUDA, OCR and real-PDF validation status;
9. remaining risks and deferred work.
