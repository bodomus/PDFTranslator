# Investigation — PDFTR-14 / PDFTR-14A

## Classification and baseline

- Workflow level: 2 (dependency management plus CUDA/CPU operational behavior).
- Branch: `codex/PDFTR-14-performance-memory-cuda-benchmark`.
- Starting commit: `121332369cccfe8a35c0f0851468a198d588f5af`.
- Starting working tree: clean.
- Python contract: `>=3.12,<3.13`; environment manager: uv.

## Current behavior and root cause

The Windows lock selected the standard PyPI `torch 2.13.0` wheel. That wheel installs as
`2.13.0+cpu`, so the RTX 4080 remains invisible to PyTorch even though NVIDIA-SMI sees the GPU and
driver. The failure is dependency-source selection, not production device resolution.

`NllbTranslator.resolve_device()` already fails when explicit CUDA is unavailable. Its one-time
CUDA-to-CPU OOM fallback applies only to `device=auto`, so the required explicit CUDA smoke test
cannot silently become a CPU run.

## Official-source verification

- The current official uv PyTorch integration guide documents accelerator-specific explicit
  indexes and platform-marked `tool.uv.sources` entries.
- The official PyTorch CUDA 13.0 package index contains
  `torch-2.13.0+cu130-cp312-cp312-win_amd64.whl`.
- The installed driver reports support beyond CUDA 13.0; no standalone CUDA Toolkit is required
  by the official PyTorch wheel installation model.

## Smallest correct change

Add a Windows-only `torch` source pointing at the official explicit `pytorch-cu130` index. Leave
Linux without a source override so existing Ubuntu CI resolution from PyPI remains intact. Update
the lockfile and developer documentation; do not add packages or change translator code.

## Graph and source findings

- Graphify was refreshed and identified `NllbTranslator`, `resolve_device`, CLI translation and
  benchmark commands, pipeline/batch construction, and `test_nllb.py` as the affected runtime
  neighborhood.
- CRG was rebuilt for the current branch: 109 files, 954 nodes, and 8,307 edges.
- Source verification confirms the dependency change reaches runtime through the lazy Torch import
  in `src/pdftranslate/translation/nllb.py`; no Typer/domain boundary changes are needed.
- Bootstrap and both CI jobs run `uv sync --frozen --all-groups`, making `pyproject.toml` and
  `uv.lock` the relevant reproducibility contract.

## Compatibility and blast radius

- Windows development and Windows CI install a larger CUDA-capable Torch wheel, but model-free
  tests remain GPU-independent and explicit CPU execution remains supported.
- Ubuntu CI continues resolving Torch from PyPI and requires no physical GPU.
- No extraction, segmentation, glossary, cache, OCR, rendering, schema, or PDF integrity contract
  changes.
- Clean synchronization, raw CUDA work, memory counters, offline NLLB CUDA/CPU smoke tests, full
  checks, and both CI platforms remain mandatory evidence.

## PDFTR-14A blocker resolution

After outbound package-index access was enabled, the intended source configuration was reapplied
and `uv --cache-dir .\temp\uv-cache lock` resolved the official Windows
`torch 2.13.0+cu130` wheel while retaining PyPI Torch for non-Windows platforms. A clean project
environment was created by moving the previous `.venv` below `./temp/` and running frozen
synchronization; no manual pip repair was used.

The clean environment reports CUDA 13.0, one RTX 4080 with capability 8.9, and successfully
performs CUDA allocation, matrix multiplication, synchronization, result transfer, and allocated/
reserved peak-memory queries. Production `NllbTranslator` strict-offline smoke tests return the
same non-empty Russian text for explicit CUDA and explicit CPU; explicit CUDA remains CUDA.

## Benchmark ownership and source verification

- `translate_document()` selects `translate_paragraphs()` for schema 1.2 documents.
- `translate_paragraphs()` owns repeated-element policy, glossary protection/validation,
  segmentation, translator calls, restoration, and cache accounting.
- `NllbTranslator` owns tokenizer/config/model construction and effective device selection, so
  timing its constructor externally captures model load and CUDA placement without modifying the
  production hot path.
- `TranslationRuntime.translator_for()` proves the production batch rule: one compatible translator
  instance is lazily reused. The benchmark mirrors that ownership by constructing one measured
  translator and passing it through every scenario and all three documents in the reuse scenario.
- Each benchmark scenario opens an explicitly named `TranslationCache` below its selected
  repository-local `./temp/` output. Only the intentional warm-cache scenario reopens cold cache.
- The new package is callable independently of Typer; the standalone script supplies either the
  deterministic fake or production NLLB factory.

The instrumentation does not cross PDF extraction, OCR, rendering, publication, or normal CLI
boundaries. It adds report contracts and a benchmark-only sampler around the existing translation
path; the lock/source change is the only normal environment behavior change.
