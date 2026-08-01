# PDFTR-9 — Translation quality benchmark

## Summary

Create a repeatable English-to-Russian benchmark and separate model-quality problems from extraction, segmentation and terminology problems.

## Dependencies

Requires completion of PDFTR-1 through PDFTR-8 unless this ticket explicitly refers to findings that can be gathered in parallel.

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

Measure current translation quality on representative PDF text and create a baseline for future changes.

## Scope and requirements

Create a versioned, repository-safe dataset of approximately 50–100 synthetic, public-domain or user-provided samples.

Include: prose, technical text, headings, captions, lists, warnings, labels, long sentences, abbreviations, units, URLs, paths, commands, code, product names, repeated terms, hyphenated line breaks and multi-sentence paragraphs.

Each sample must contain an ID, category, English source, approved/reference Russian text, optional context, protected tokens, notes and provenance.

Add a benchmark runner such as:

```bash
pdftranslate benchmark-translation benchmark.json --backend nllb --device auto
```

Record application version, commit, backend, model, tokenizer, device, settings, timing, cache statistics and dataset version. Produce JSON and Markdown.

Implement deterministic checks for lost numbers/units/URLs/paths/options, missing or duplicated segments, untranslated output, suspicious length ratios and protected-token damage.

Provide human review fields for adequacy, fluency, terminology, token preservation, segmentation and overall acceptability using a documented scale.

Support baseline comparison and clearly separate model, extraction, segmentation, protected-token, terminology and rendering issues. Do not recommend model replacement without evidence.

## Tests and validation

Test dataset validation, fake backend execution, token checks, baseline comparison, malformed samples and report generation. CI must not download NLLB.

Normal unit tests and CI must not download translation models, require CUDA, or require OCR system tools. Use generated fixtures, fakes and mocks. Real-model, GPU, OCR and real-PDF tests must be explicit opt-in checks.

## Acceptance criteria

- [ ] Versioned safe benchmark dataset exists.
- [ ] Runner produces JSON and Markdown.
- [ ] Model/settings/commit metadata is recorded.
- [ ] Protected tokens are checked.
- [ ] Human review can be recorded.
- [ ] Baseline comparison works.
- [ ] Findings distinguish model and pipeline issues.
- [ ] No model download occurs in tests/CI.
- [ ] All checks pass.

## Non-goals

No fine-tuning, cloud APIs, automatic production-model replacement, web review UI, or BLEU-only acceptance.

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
