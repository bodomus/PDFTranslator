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

## PDFTR-14A execution blocker

The candidate `pytorch-cu130` source configuration was exercised but not retained because a
committed `pyproject.toml` with the old CPU-only lockfile would break every frozen synchronization.

- Online `uv lock` with repository-local `./temp/uv-cache`: PyPI connection refused.
- Online `uv lock` with the existing user cache: socket access forbidden (`os error 10013`).
- Offline `uv lock`: no compatible Windows Torch version is available in the cache.
- Cache inspection: only PyPI CPU Torch artifacts are present; no cu130 wheel/metadata.
- Browser verification: exact official link and SHA-256 were visible, but direct wheel download
  was blocked by the browser client.

No lockfile was manually edited and no CPU result was substituted. The next required environmental
change is outbound access for uv to PyPI and the official PyTorch index, or a correctly populated
repository-local uv cache.
