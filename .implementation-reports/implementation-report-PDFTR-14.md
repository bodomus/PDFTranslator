# Implementation Report — PDFTR-14

## Final status

**Implementation and local acceptance: PASS. GitHub Actions: pending branch push.**

PDFTR-14A removed the CUDA dependency blocker reproducibly, and PDFTR-14 now has complete
synthetic, real CPU, and real CUDA benchmark evidence. No CPU result is presented as CUDA data.

## Git state

- Branch: `codex/PDFTR-14-performance-memory-cuda-benchmark`.
- Master base: `368195f14c8728b366417f58508271c74b523edc`.
- Benchmark implementation commit: `93f248c378367d901bfd94593d880fd97a4bb87e`.
- Working tree before PDFTR-14: clean; PDFTR-11/12/13/13A were present in master.
- PDFTR-15 was not started.

## PDFTR-14A — CUDA environment unblock

### Original blocker and selected dependency

- Original Torch: `2.13.0+cpu`; `torch.version.cuda=null`; CUDA unavailable to Python.
- Physical GPU was always visible to NVIDIA-SMI: NVIDIA GeForce RTX 4080.
- Selected official index: `https://download.pytorch.org/whl/cu130`.
- Selected Windows wheel: `torch 2.13.0+cu130`, CPython 3.12, win_amd64.
- Locked wheel SHA-256: `2efab1e83604ca628c6d85b9e188c153690980498d1297081a9dad704919303c`.
- `tool.uv.sources` applies the explicit CUDA index only for `sys_platform == 'win32'`;
  non-Windows resolution remains on PyPI and CI remains GPU-independent.
- No torchvision, torchaudio, system CUDA Toolkit, manual pip repair, or second environment was
  introduced.

### Reproducibility and gates

- `uv --cache-dir .\temp\uv-cache lock`: PASS.
- Previous `.venv` moved below `./temp/`; clean `uv sync --frozen --all-groups`: PASS.
- Installed Torch: `2.13.0+cu130`; Torch CUDA runtime: `13.0`.
- `torch.cuda.is_available()`: `true`; device count: `1`.
- Device: `NVIDIA GeForce RTX 4080`; compute capability: `8.9`.
- Real `2048 x 2048` CUDA allocation, matrix multiplication, synchronization, finite result
  transfer, and allocated/reserved peak-memory counters: PASS.
- Gate memory evidence: allocated `42,074,112` bytes; reserved `54,525,952` bytes.
- Production NLLB, strict offline, explicit CUDA: effective device `cuda`, output
  `Система готова к работе.`.
- Production NLLB, strict offline, explicit CPU in the same environment: effective device `cpu`,
  same output.
- Explicit CUDA never fell back to CPU.

## Investigation and architecture

- Production path is `ExtractedDocument(schema 1.2)` → `translate_document()` →
  `translate_paragraphs()` → repeated policy → glossary → protected tokens → segmentation →
  translator → restore/glossary validation → `TranslationCache`.
- External timing around `NllbTranslator` construction captures tokenizer/config/model load and
  device placement without adding benchmark branches to production inference.
- Production `TranslationRuntime.translator_for()` lazily owns one compatible translator for a
  batch. The benchmark likewise creates one measured translator and reuses it for all scenarios
  and all three documents in the batch scenario.
- Every scenario receives an explicit SQLite path below its run-specific `./temp/` root. Only the
  named warm-cache scenario intentionally reopens cold cache.
- A non-empty output root is rejected, preventing a stale cache from being reported as cold and
  preventing silent report replacement.
- Benchmark core is independent of Typer; the standalone script selects fake or production NLLB.
- No extraction, OCR, rendering, normal CLI, source PDF, or published PDF path changed.

Graph evidence was source-verified. Post-change Graphify contains 2,052 nodes / 4,381 edges / 136
communities. CRG contains 1,025 nodes / 8,916 edges across 118 files on commit `93f248c`; its
heuristic reported risk 0.60 and many test gaps for data models/script factories, but the reachable
behavior is directly covered by focused tests, full tests, synthetic runs, and real NLLB runs.

## Benchmark design

- Dataset: public-safe, deterministic 120 `LogicalParagraph` objects, 29,211 source characters,
  6,264 NLLB source-token count, document schema 1.2.
- Length classes: 60 short, 40 medium, 10 long, 10 forced-segmentation paragraphs.
- Content includes technical and ordinary prose, headings, list items, repeated headers and
  boilerplate, preserved page numbers, skipped watermarks, dates, numbers, URLs, Windows paths,
  protected IDs, glossary terms, and duplicates.
- Dataset SHA-256:
  `fa32d20f2d810356c805939522a7460693a2c15b6596e357b8702f4646e87f16`.
- Same dataset, glossary fingerprint, NLLB model, max input tokens (`256`), dependency environment,
  and implementation commit were used for CPU and CUDA.
- Synthetic mode uses a deterministic fake but traverses the same production paragraph pipeline.
- Real mode uses `facebook/nllb-200-distilled-600M` from the existing local cache in strict offline
  mode; no model was downloaded during tests.
- Timers use `time.perf_counter()`; CUDA synchronizes before stopping measured intervals.
- Cold model, warm model with fresh cache, full warm cache, input-length matrix, batch 1/4/8, and
  three-document batch reuse are distinct scenarios.
- One warmup is excluded. CUDA uses five measured iterations. CPU uses the ticket's documented
  expensive-run exception of three measured iterations.
- Distributions report count/min/median/p95/max; cold-start is never averaged into warm results.
- CPU memory is Windows process working set sampled every 10 ms. CUDA JSON values are PyTorch
  allocated/reserved bytes with peak stats reset before each scenario.
- Integrity requires correct output count, no placeholder leak, no protected-token violation, no
  glossary violation, and stable hashes for equivalent scenarios. Missing mandatory RAM/VRAM
  counters mark a report incomplete.

Generated local artifacts (ignored by Git):

- `temp/pdftr14-performance-synthetic-final/performance.json` and `performance.md`.
- `temp/pdftr14-performance-cpu-93f248c/performance.json` and `performance.md`.
- `temp/pdftr14-performance-cuda-93f248c/performance.json` and `performance.md`.

All three reports have `complete=true` and no warnings.

## Environment

- OS: Windows 11 (`10.0.26200`).
- Python: `3.12.10`.
- Application: `0.1.0`, commit `93f248c378367d901bfd94593d880fd97a4bb87e`.
- Torch: `2.13.0+cu130`; CUDA runtime: `13.0`.
- GPU: NVIDIA GeForce RTX 4080, capability 8.9, 17,170,956,288 bytes reported total memory.
- CPU: Intel64 Family 6 Model 183 Stepping 1, 32 logical CPUs.
- System RAM: 102,772,920,320 bytes.
- Model: `facebook/nllb-200-distilled-600M`, strict offline existing Hugging Face cache.

## Results — CPU

- Cold model/config/tokenizer load: **4.756 s**.
- Cold first translator call: **0.650 s**; cold translation **136.281 s**; total including load
  **141.037 s**.
- Batch 1 (n=3): min **130.689 s**, median **135.015 s**, p95/max **139.000 s**;
  median **0.889 paragraphs/s**, **0.348 segments/s**, **216.354 characters/s**.
- Batch 4 (n=3): min **100.316 s**, median **123.808 s**, p95/max **208.403 s**;
  median **0.969 paragraphs/s**, **0.380 segments/s**, **235.937 characters/s**.
- Batch 8 (n=3): min **103.523 s**, median **107.635 s**, p95/max **117.995 s**;
  median **1.115 paragraphs/s**, **0.437 segments/s**, **271.391 characters/s**.
- Working set before model: **66.60 MiB**; after load: **1,861.02 MiB**.
- Cold single-document peak working set: **3,297.61 MiB**; three-document batch peak:
  **3,795.18 MiB**.
- Full cache hit: **0.0089 s**, 100 hits / 0 misses / 0 translator calls / 0 model-facing
  segments. Relative to warm-model translation it is **14,625x** faster; this is cache speed, not
  inference throughput.
- A batch=4 outlier (208.403 s) is retained in p95/max; median is used for comparison.

## Results — CUDA

- Cold model load plus device placement: **5.977 s**.
- Cold first translator call: **0.385 s**; cold translation **36.406 s**; total including load
  **42.383 s**.
- Batch 1 (n=5): min **30.785 s**, median **31.604 s**, p95/max **36.384 s**;
  median **3.797 paragraphs/s**, **1.487 segments/s**, **924.285 characters/s**.
- Batch 4 (n=5): min **18.831 s**, median **19.136 s**, p95/max **19.581 s**;
  median **6.271 paragraphs/s**, **2.456 segments/s**, **1,526.515 characters/s**.
- Batch 8 (n=5): min **16.272 s**, median **16.494 s**, p95/max **16.786 s**;
  median **7.275 paragraphs/s**, **2.849 segments/s**, **1,770.985 characters/s**.
- Cold single-document peak VRAM: **2,430.35 MiB allocated**, **2,478 MiB reserved**.
- Three-document batch peak: **2,825.91 MiB allocated**, **3,158 MiB reserved**.
- Cold single-document peak host working set: **1,429.21 MiB**.
- Full cache hit: **0.0077 s**, 100 hits / 0 misses / 0 translator calls / 0 model-facing
  segments; **4,532x** faster than warm-model translation.

## Input-length matrix

Each class ran with a fresh cache through production NLLB. CPU / CUDA elapsed seconds:

- Short: 60 paragraphs, 12 translated segments, **4.786 / 1.494 s**.
- Medium: 40 paragraphs, 20 translated segments, **20.798 / 5.723 s**.
- Long: 10 paragraphs, 5 translated segments, **15.421 / 4.322 s**.
- Forced segmentation: 10 paragraphs, 10 translated paragraph units and more than ten actual
  model-facing segments after tokenizer splitting, **88.527 / 23.548 s**.

The raw reports retain paragraph, character, source-token, translated-segment, translator-call,
cache, timing, throughput, RAM, and VRAM fields for every class.

## Results — batch reuse

- Documents / logical paragraphs: **3 / 360**.
- Translator construction for whole benchmark: **1**; additional model loads in batch scenario:
  **0**.
- CPU: 6 translator calls, 47 model-facing segments, 258 cache hits / 42 misses,
  **101.128 s total**, **33.709 s/document**.
- CUDA: 6 translator calls, 47 model-facing segments, 258 hits / 42 misses,
  **15.891 s total**, **5.297 s/document**.
- Repeated content in documents two and three is served by the shared cache; no model reload occurs.

## CPU vs CUDA and required interpretation

1. CPU NLLB load: **4.756 s**.
2. NLLB load/move to CUDA: **5.977 s**.
3. Best measured warm CPU throughput: batch 8, **271.391 characters/s**.
4. Best measured warm CUDA throughput: batch 8, **1,770.985 characters/s**.
5. Same-data batch-8 median CUDA speedup: **6.526x**.
6. Batch 8 was fastest on this RTX 4080. This is a workstation finding, not an automatic default
   change.
7. Host memory: CPU model load reached **1.82 GiB**, single translation peaked **3.22 GiB**, and
   three-document reuse peaked **3.71 GiB** working set.
8. Peak CUDA memory: **2.37 GiB allocated / 2.42 GiB reserved** for a single document; batch reuse
   reached **2.76 / 3.08 GiB**.
9. Full-cache hits were **14,625x CPU** and **4,532x CUDA** faster than warm-model inference, with
   zero translator calls.
10. Multi-file reuse avoids model reload: one construction total, zero additional loads in batch.
11. Glossary/protected-token processing is included in every number and passed integrity checks,
    but this ticket did not run an otherwise-identical no-glossary control. Its isolated material
    cost therefore cannot be claimed from these data; PDFTR-13A is the dedicated deterministic
    glossary/cache behavior benchmark.
12. CPU and CUDA outputs were byte-identical for deterministic settings. Equivalent single-
    document hash on both devices:
    `16c9ea36e27866e2525209da09ca9514c9997c63ea3a58f0150edef522f12df8`.
13. Values depend on hardware, driver, thermals, background work, OS scheduling, local model state,
    dataset, and a 10 ms RSS sampler. CPU has only three samples. They are not portable performance
    promises.

## Correctness

- All synthetic/CPU/CUDA reports: `complete=true`, zero warnings.
- Protected-token violations: 0; glossary violations: 0; placeholder leaks: 0.
- Repeated `TRANSLATE`, `PRESERVE`, and `SKIP` policies stayed in the production path.
- Equivalent scenarios have identical hashes within each device and across CPU/CUDA.
- Output count equals logical paragraph count in every scenario.
- Caches and generated reports are isolated below `./temp/`; non-empty output roots fail closed.
- Instrumentation did not change normal translation or rendering behavior.

## Validation

- Focused PDFTR-14 tests: **9 passed**.
- Adjacent translation/glossary/repeated tests: **31 passed**.
- Full `scripts/check.ps1`: **199 passed, 1 skipped**.
- Coverage: **88.21%** (required ≥80%).
- Ruff format/check: PASS.
- mypy `src`: PASS.
- Synthetic benchmark: PASS, `complete=true`.
- Real CPU NLLB benchmark: PASS, `complete=true`, 20 scenarios.
- Real CUDA NLLB benchmark: PASS, `complete=true`, 26 scenarios, effective device CUDA.
- `uv lock --check`: PASS.
- Graphify/CRG post-change refresh: PASS after rerun with UTF-8 and normal filesystem access.
- GitHub Actions Windows/Ubuntu: **pending push**.

The first local check attempts failed before meaningful assertions because sandboxed processes
could not access the configured `A:\Temp`, the default user uv cache, or even their newly created
pytest directories. The unchanged checks passed outside that filesystem restriction with `TMP`,
`TEMP`, pytest basetemp/cache, and uv cache explicitly below `./temp/`.

## Findings and recommendation

- Main inference bottleneck is forced segmentation/sequence generation, not glossary/cache policy.
- Batch 8 is the best tested choice on this RTX 4080, but PDFTR-14 does not alter the production
  default.
- Cache reuse dominates inference when exact translations repeat; it must remain reported
  separately from model throughput.
- A future optimization ticket may investigate CPU batch variance, model compilation/quantization,
  or larger GPU batches. None was implemented here.
- **Ready for branch push and CI verification; merge readiness requires both CI jobs green.**
