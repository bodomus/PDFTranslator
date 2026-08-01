# PDFTR-9A — Fix benchmark cache isolation and strict offline behavior

## Summary

Correct two issues found during check-in of PDFTR-9:

1. benchmark cache entries are reused too broadly and may carry findings/status from one sample
   into another sample with the same source text;
2. `--offline` still allows Hugging Face metadata network requests.

This is a corrective follow-up for PDFTR-9. Do not start PDFTR-10 until this ticket is complete and
reviewed.

## Issue 1 — Benchmark cache leaks sample-specific findings

`run_benchmark()` currently caches output, segment evidence, findings and status by
`effective_source`. Findings and status depend on sample-specific protected tokens, human review
and historical stage trace. Cache only reusable model-execution artifacts. On every sample rerun
`analyze_sample_output()` and `analyze_stage_trace()`, apply that sample's human review and compute
status independently. A cache hit means only model execution was reused.

Required focused tests use identical source text with different protected tokens, human review and
historical stage traces. The translator must execute once, while findings/status remain independent.

## Issue 2 — Strict offline behavior

When `offline=True`, model, tokenizer and configuration loading must use local files only and no
Hugging Face metadata request or online fallback may occur. Missing files must fail immediately with
an offline-specific message containing the model/cache location where available. Scoped environment
changes must be restored after success and failure. Unit tests must mock external APIs and never use
the network. Normal `offline=False` behavior must remain unchanged, and benchmark CLI must propagate
the flag.

Supported mechanisms include `local_files_only=True` and scoped Hugging Face/Transformers offline
environment behavior. Do not permanently mutate process environment or swallow network failures.

## Documentation and validation

Update README, CHANGELOG, CLI help where necessary, `implementation-report.md` and
`reviews/review-PDFTR-9.md`. Run benchmark and translation focused tests, full pytest, Ruff, mypy,
`scripts/check.ps1`, and the real benchmark when the local model cache is available. Record sample
counts, pass/fail/errors, cache statistics, elapsed time, offline verification and warnings.

## Acceptance criteria

- Cache stores only reusable execution artifacts; findings and status are recomputed per sample.
- Identical sources with distinct protected tokens, human reviews and stage traces behave correctly
  while the translator executes once.
- Offline model, tokenizer and configuration loading is local-only with no online fallback.
- Missing local files produce a clear offline-specific error.
- Environment is restored on success and failure; online-capable behavior is unchanged.
- Tests do not access the network and the full quality gate passes.
- Reports are updated honestly; PDFTR-10 is not started.

## Non-goals

No production fix for translating `data.json`, `--device` or `--offline`; no glossary, paragraph
reconstruction, rendering, OCR, CUDA optimization or PDFTR-10 work.
