# Review — PDFTR-14

## Verdict

**Ready to merge.** The mandatory CUDA criterion is satisfied with real NLLB work on an RTX 4080,
CPU results were never substituted for CUDA, and both GitHub Actions platforms are green.

## Scope reviewed

- Official Windows-only uv source for `torch 2.13.0+cu130` and platform-split lockfile.
- Dedicated `pdftranslate.performance` package and standalone benchmark script.
- Deterministic 120-paragraph fixture and short/medium/long/forced-segmentation matrices.
- Cold model, warm model, warm cache, batch 1/4/8, and three-document reuse scenarios.
- Versioned JSON and Markdown reporting, RSS/VRAM collection, cache isolation, and integrity gates.
- README, CHANGELOG, benchmark documentation, plan, investigation, and tests.

## Evidence assessment

- Clean frozen sync installs CUDA-enabled Torch reproducibly on Windows; Linux remains on PyPI.
- Raw CUDA allocation/matmul/synchronize/result/counter gate and strict-offline production NLLB
  CUDA/CPU smokes passed. Explicit CUDA remained CUDA.
- CPU and CUDA benchmarks use the same commit, dataset hash, glossary, model, max-token setting,
  local model cache, and dependency environment.
- Cold load is separated from translation. Warm inference always uses a fresh SQLite cache. Full
  cache reuse is separate and reports zero translator calls.
- One excluded warmup precedes 3 CPU or 5 CUDA samples. Reports contain min/median/p95/max and use
  medians to select the observed best batch.
- Windows working set and PyTorch allocated/reserved CUDA counters are present for every scenario;
  missing required counters make a report incomplete.
- Batch reuse proves one translator construction, zero additional batch model loads, 3 documents,
  360 paragraphs, 258 hits / 42 misses, and only 47 model-facing segments.
- Equivalent real outputs are identical on CPU and CUDA with hash
  `16c9ea36e27866e2525209da09ca9514c9997c63ea3a58f0150edef522f12df8`.
- Protected-token, glossary, placeholder, output-count, repeated-policy, and cache-location checks
  all pass.

## Measured conclusions

- Model load: CPU **4.756 s**; CUDA load/device placement **5.977 s**.
- Best median batch: 8 on both devices.
- Batch-8 median: CPU **107.635 s / 271.391 characters/s**; CUDA
  **16.494 s / 1,770.985 characters/s**; CUDA speedup **6.526x**.
- CPU peak working set: **3.22 GiB** single document, **3.71 GiB** batch reuse.
- CUDA peak: **2.37 GiB allocated / 2.42 GiB reserved** single document and
  **2.76 / 3.08 GiB** batch reuse.
- Warm cache: CPU **0.0089 s**, CUDA **0.0077 s**, with 100 hits and no model work.

## Review findings and limitations

- An early run exposed a real instrumentation defect: untyped Windows `GetCurrentProcess` handling
  yielded null RSS. Explicit WinAPI signatures fixed it, and all final real runs were repeated.
- Input-length timing was initially absent; the incomplete run was stopped, four separate
  production-path scenarios were added, and all final runs were repeated from new output roots.
- Output roots now reject non-empty directories, preventing stale cold-cache evidence and silent
  artifact overwrite.
- A CPU batch=4 outlier is retained. Three CPU samples are the ticket's allowed expensive-run
  exception; CPU p95 therefore equals max and has low statistical resolution.
- RSS is sampled at 10 ms and can miss shorter peaks. CUDA peak counters are authoritative only for
  PyTorch-managed memory, not every driver allocation.
- Glossary and protected processing are included and validated, but no no-glossary timing control
  exists here; their isolated overhead cannot be inferred. PDFTR-13A remains the relevant behavior
  benchmark.
- Synthetic results validate accounting only. Real NLLB results remain workstation-specific and
  are not promises for other hardware.
- CRG's heuristic listed numerous model/script symbols as test gaps, but focused tests plus the
  synthetic and two real script executions cover the ticket's reachable behavior. No unexpected
  extraction/OCR/rendering/CLI blast radius was found.
- Initial validation failures were environmental permissions on temp/cache paths, not code
  failures. The same suite passed with all temporary state explicitly under repository `./temp/`.

## Validation reviewed

- PDFTR-14 focused: **9 passed**.
- Adjacent translation/glossary/repeated: **31 passed**.
- Full quality gate: **199 passed, 1 skipped**, coverage **88.21%**.
- Ruff, formatting, mypy, lock check, synthetic, CPU real, CUDA real, Graphify, and CRG: PASS.
- Initial CI: Windows passed; Ubuntu correctly rejected direct Windows-only ctypes attribute access
  during mypy. The narrow portable-access fix was locally revalidated.
- Final implementation CI [`31590250965`](https://github.com/bodomus/PDFTranslator/actions/runs/31590250965):
  **Windows PASS, Ubuntu PASS** through frozen sync, Ruff, mypy, tests, and coverage.

## Recommendation

Merge recommendation: **ready**. The branch has local CUDA evidence, full local validation, and
green Windows/Ubuntu CI. Do not start PDFTR-15 until this review is accepted.
