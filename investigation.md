# PDFTR-9A Investigation

## Workflow and baseline

- Level 2: model lifecycle/offline contract plus benchmark cache correctness.
- Branch required by ticket: `codex/PDFTR-9-translation-quality-benchmark`.
- Base commit: `411bc72b51d19701d201f6440cf68688d39b79a4`.
- Working tree was clean before switching from merged `master` to the required branch.
- Python 3.12.10, uv 0.5.26; no dependency change is required.

## Graph and source findings

- Graphify BFS connected benchmark, `NllbTranslator`, `Translator`, CLI and translation tests.
  The result was source-verified and saved to Graphify work memory. The stored interpreter path was
  stale, so the first module invocation failed; the installed `graphify save-result` CLI succeeded.
- CRG refreshed to 648 FTS rows and reported no pre-existing working-tree changes.
- Source is authoritative: `run_benchmark()` owns the in-run benchmark cache;
  `NllbTranslator` owns third-party loading; Typer only propagates `offline` and cache paths.

## Issue 1 — Cache isolation

Current behavior: `_CachedResult` stores output, segment evidence, findings and status. A hit keyed by
`effective_source` copies `cached.findings` and `cached.status` into the next sample.

Root cause: inference artifacts and sample evaluation were combined in one cache value. Protected
token declarations, human review and stage trace are sample-specific even when source text is equal.

Smallest correct change: cache only translation execution artifacts (output, evidence, segment
counts, segmentation warning, restore error and runtime error). Analyze every sample after lookup and
derive its status independently. Translator execution remains deduplicated by effective source.

## Issue 2 — Strict offline loading

Current behavior: tokenizer and model receive `local_files_only=offline`, but the remote model ID is
still passed to Transformers. The PDFTR-9 real run showed Hugging Face API metadata requests.

Official Hugging Face documentation confirms that `local_files_only=True` restricts file loading,
while `HF_HUB_OFFLINE=1` explicitly prevents Hub HTTP calls. The current installed versions are
Transformers 5.14.1 and huggingface-hub 1.26.0.

Root cause: no scoped Hub offline environment is applied, and remote repository identity is resolved
inside third-party code. Environment flags are imported into Hub constants, so setting them after a
prior Hub import alone is not a complete process-wide guarantee.

Smallest robust change:

1. in offline mode, resolve the requested model to an existing local directory or a Hugging Face
   cache snapshot before importing Transformers;
2. set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` only around component loading, restoring the
   previous values in `finally`;
3. load `AutoConfig`, `AutoTokenizer` and `AutoModelForSeq2SeqLM` from the resolved local path with
   `local_files_only=True`; pass the loaded config to the model;
4. fail before any third-party network-capable loader when the local snapshot is absent, including
   model and checked cache path in the message;
5. preserve remote-ID online behavior when `offline=False`.

Resolving to a local filesystem path is the strict boundary even if Hugging Face was imported earlier;
the scoped environment is defense in depth and follows the documented offline mechanism.

## Boundaries and risks

- Affected: benchmark runner, NLLB loader, focused tests, CLI help/docs/reports.
- Unaffected: PDF extraction, rendering, OCR, schemas, persistent TranslationCache and CUDA logic.
- No model download in tests; mocks verify loader arguments and environment restoration.
- Real verification should use the existing local cache and inspect logs for absence of HTTP requests.
- Production token-protection behavior for command filenames/options is explicitly out of scope.
