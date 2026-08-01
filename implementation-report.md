# Implementation Report — PDFTR-9A

## Git state

- Branch: `codex/PDFTR-9-translation-quality-benchmark` (required by the corrective ticket).
- Base commit: `411bc72b51d19701d201f6440cf68688d39b79a4`.
- Working tree before changes: clean; repository was on merged `master`, then switched to the
  explicitly required existing PDFTR-9 branch without rebase or merge.
- Workflow: Level 2 because model lifecycle/offline behavior changed.

## Issue 1 — Cache isolation

- Root cause: `_CachedResult` cached output/evidence together with sample-specific `findings` and
  `status`, keyed only by `effective_source`. A later sample with equal source inherited the first
  sample's protected-token/human-review evaluation.
- Design change: `_CachedTranslation` stores only output, segment evidence, input/output segment
  counts, segmentation warning, protected-placeholder restore error and runtime error. Every sample,
  including cache hits, independently runs `analyze_sample_output()`, `analyze_stage_trace()` and
  `_status()`.
- Tests added: equal source with different protected tokens, human-review scores and historical
  stage traces. Each scenario proves one cache hit/49 misses for the 50-sample fixture and no
  cross-sample finding/status leakage.
- Result: translator work remains deduplicated; sample evaluation is isolated. Benchmark focused
  suite: 14 passed, including sample-specific human findings after a reused runtime error.

## Issue 2 — Offline behavior

- Root cause: `local_files_only=True` was passed with a remote repository ID. Transformers/
  huggingface-hub could still perform metadata/revision requests because strict Hub offline state
  and local snapshot resolution were absent.
- Loader changes:
  - offline mode resolves an explicit local directory or Hugging Face cache `refs/main` snapshot
    before importing Transformers;
  - missing/ambiguous local files fail before a network-capable loader is imported;
  - `AutoConfig`, `AutoTokenizer` and `AutoModelForSeq2SeqLM` all receive the resolved local path,
    cache directory and `local_files_only=True`; the loaded config is passed into the model loader;
  - `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` are scoped to component loading and previous
    values are restored in `finally` after success or failure;
  - `offline=False` keeps the remote model identifier and does not force offline environment.
- Error behavior: the offline-specific error names the model, checked local/cache paths, and tells
  the user to populate the cache or rerun without `--offline`. No online fallback is attempted.
- Network-access verification: the real benchmark completed with `HTTP_PROXY`, `HTTPS_PROXY` and
  `ALL_PROXY` pointed at non-listening `127.0.0.1:9` and empty `NO_PROXY`. No HTTP request appeared in
  the output. This is controlled process-level blocking/log verification, not packet capture.
- Result: strict offline real-model run succeeded entirely from the existing local cache.

## Real benchmark

Command used the repository dataset, CPU, `--offline`, max input tokens 64, the existing local model
cache and output under `./temp`. Network proxies were deliberately invalid.

- Dataset/model: `1.0.0`, 61 samples, `facebook/nllb-200-distilled-600M`.
- Result: 60 passed, 1 failed, 0 execution errors.
- Cache: 0 hits, 61 misses.
- Model elapsed: 44.183 seconds; CLI elapsed: 48.47 seconds.
- Output: `temp/pdftr9-benchmark/nllb-offline.json` and sibling Markdown.
- No HTTP request lines occurred; the earlier Hugging Face metadata traffic did not recur.
- The existing `command-01` failure remains: `data.json`, `--device` and `--offline` are translated.
  Its production fix is explicitly outside PDFTR-9A.
- Transformers still warns that `max_new_tokens=128` takes priority over `max_length=200`.

## Files changed

- `src/pdftranslate/benchmark/runner.py`
- `src/pdftranslate/benchmark/checks.py`
- `src/pdftranslate/translation/nllb.py`
- `tests/test_translation_benchmark.py`
- `tests/test_nllb.py`
- `README.md`, `CHANGELOG.md`
- `Tickets/PDFTR-9A-fix-benchmark-cache-and-offline.md`
- `investigation.md`, `implementation-plan.md`
- `implementation-report.md`
- `reviews/review-PDFTR-9.md`, `reviews/review-PDFTR-9A.md`

No dependencies, schemas, persistent TranslationCache formats, PDF stages or CLI option names were
changed.

## Graph and source validation

- Graphify existing graph was queried with repository vocabulary and connected benchmark runner,
  `NllbTranslator`, CLI and tests. Conclusions were verified in source. The saved interpreter path
  was stale (`No module named graphify`), but the installed CLI successfully saved the result to
  Graphify memory. Required incremental refresh completed at 1339 nodes/2947 edges and reclustered
  to 92 communities. Ollama's 8192-token context caused several oversized semantic Markdown chunks
  to be dropped and three JSON inputs produced zero nodes; code AST extraction, source and CRG are
  used as authority. Community labeling remains partially stale (78 saved labels for 92 communities).
- CRG final post-commit audit: 705 FTS rows; 13 changed files, 26 symbols, risk 0.40, no affected flow.
  The audit completed before its decorative panel hit a Windows CP1251 console encoding error; the
  reported analysis counts were already emitted and remain valid.
  Its heuristic listed `_CachedTranslation`, `run_benchmark`, `_TransformersRuntime`,
  `_load_components` and `_resolve_model_source` as gaps, but direct source tests exercise their
  cache-hit, loader, missing-cache, environment restoration and online paths. Source/tests prevail.
- No full Graphify rebuild was performed; the required incremental refresh and cluster-only report
  regeneration completed.

## Validation

- Focused benchmark tests: 14 passed (`--no-cov`; focused-only runs otherwise trip the global
  repository coverage threshold).
- Translation tests: 9 passed.
- Combined benchmark/NLLB/translation tests: 32 passed.
- Full pytest: 152 passed, 1 skipped.
- Coverage: 87.70% (required 80%).
- Ruff format check: 95 files already formatted.
- Ruff lint: passed.
- mypy: no issues in 59 source files.
- `scripts/check.ps1`: passed with the same 152/1 result and 87.70% coverage.
- Skipped test: existing opt-in OCR integration dependency check.
- CLI propagation of `--offline`: covered by a mocked benchmark CLI assertion.

## Remaining risks and remarks

1. The scoped environment uses process-global variables during synchronous model construction.
   Local snapshot resolution remains the primary no-network boundary, but concurrent model loading
   in multiple threads is not a supported/tested scenario.
2. Online-capable loading is tested with mocked Transformers factories; no real online download was
   performed because that would violate the controlled test scope and is unnecessary for this fix.
3. The offline proof used blocked proxies and logs, not an OS-level packet capture.
4. CUDA, OCR, extraction, rendering and PDF output were not exercised because PDFTR-9A changes none
   of those boundaries.
5. The real benchmark metadata records base commit `411bc72` because the corrective work was not yet
   committed when the evidence was generated. Source diff and exact command are recorded here.
6. `command-01` token protection remains a separate follow-up; it was not silently broadened into
   this ticket.
7. The supplied PDFTR-9A Markdown did not identify a numeric YouTrack issue, so no separate issue
   fields or attachments could be updated. The ticket copy is committed under `Tickets/`.
8. All runtime artifacts and caches were kept under `./temp`; reviews are under `reviews/`.
9. PDFTR-10 was not started.

## Recommendation

Ready for PDFTR-9A check-in and merge after review. PDFTR-9 cache isolation and strict offline
contracts are now implemented, tested and verified with the real local model cache.
