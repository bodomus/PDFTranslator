# PDFTR-9 — Translation quality benchmark

## Summary

Create a repeatable English-to-Russian benchmark and separate model-quality problems from
extraction, segmentation, terminology, protected-token, and rendering problems.

## Required PDFTR-8 regression inputs

1. NLLB damaged the protected token `1900-1`.
2. On page 7, numbers and dates were damaged and junk characters such as `F￾` appeared.

These observations must be retained as benchmark inputs even when the current pipeline contains
mitigations. The benchmark must identify which stage introduced a finding instead of treating all
output defects as model-quality failures.

## Goal

Measure current translation quality on representative PDF text and create a baseline for future
changes. The ticket does not improve PDF appearance. It must distinguish:

- model errors;
- segmentation errors;
- protected-token damage;
- extracted-text errors;
- rendering-stage problems.

## Scope and requirements

- Create a versioned, repository-safe dataset of approximately 50–100 synthetic, public-domain,
  or user-provided samples.
- Include prose, technical text, headings, captions, lists, warnings, labels, long sentences,
  abbreviations, units, URLs, paths, commands, code, product names, repeated terms, hyphenated line
  breaks, and multi-sentence paragraphs.
- Each sample contains an ID, category, English source, approved/reference Russian text, optional
  context, protected tokens, notes, and provenance.
- Add a runner such as
  `pdftranslate benchmark-translation benchmark.json --backend nllb --device auto`.
- Record application version, commit, backend, model, tokenizer, device, settings, timing, cache
  statistics, and dataset version. Produce JSON and Markdown.
- Implement deterministic checks for lost numbers, units, URLs, paths and options; missing or
  duplicated segments; untranslated output; suspicious length ratios; and protected-token damage.
- Provide human-review fields for adequacy, fluency, terminology, token preservation,
  segmentation, and overall acceptability using a documented scale.
- Support baseline comparison and clearly separate model, extraction, segmentation,
  protected-token, terminology, and rendering issues.
- Do not recommend model replacement without evidence.

## Tests and validation

Test dataset validation, fake-backend execution, token checks, baseline comparison, malformed
samples, and report generation. CI must not download NLLB. Real-model checks are explicit opt-in
runs and normal tests must not require CUDA or OCR system tools.

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

No PDF appearance changes, fine-tuning, cloud APIs, automatic production-model replacement, web
review UI, or BLEU-only acceptance.
