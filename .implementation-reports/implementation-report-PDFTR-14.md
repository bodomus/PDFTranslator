# Implementation Report — PDFTR-14

## Final status

**BLOCKED — implementation not started.**

CUDA validation is a mandatory PDFTR-14 acceptance criterion. The current project environment
cannot execute CUDA through PyTorch, so CPU benchmark results were not generated or presented as a
substitute.

## Git state

- Branch: `codex/PDFTR-14-performance-memory-cuda-benchmark`.
- Base commit: `368195f14c8728b366417f58508271c74b523edc` (`master`).
- Working tree before ticket files: clean.
- PDFTR-11, PDFTR-12, PDFTR-13, and PDFTR-13A are present in the selected master history.

## CUDA gate

Commands executed:

```powershell
nvidia-smi
uv run python -c "... torch.cuda.is_available(); CUDA allocation/matmul/synchronize ..."
uv run python -c "... torch/CUDA/cuDNN metadata ..."
uv pip show torch
uv tree --depth 1
```

Observed hardware/driver:

- GPU: NVIDIA GeForce RTX 4080.
- Reported GPU memory: 16,376 MiB.
- NVIDIA-SMI: 610.47.
- Driver-reported CUDA UMD: 13.3.
- GPU is visible to the operating system and NVIDIA driver.

Observed project Python environment:

- Python: 3.12.10.
- Torch: `2.13.0+cpu`.
- `torch.version.cuda`: `null`.
- `torch.cuda.is_available()`: `False`.
- `torch.cuda.device_count()`: `0`.
- `torch.backends.cudnn.is_available()`: `False`.
- cuDNN version: `null`.
- The required CUDA allocation/matrix/synchronization probe stopped at the availability assertion
  and did not run on the GPU.

## Root cause

The repository currently resolves Torch from the standard PyPI wheel recorded in `uv.lock`:

- dependency declaration: `torch>=2.7,<3`;
- locked Windows wheel: `torch-2.13.0-cp312-cp312-win_amd64.whl`;
- installed runtime identifies itself as `torch 2.13.0+cpu`.

Therefore the blocker is not missing NVIDIA hardware. The active project environment has a
CPU-only PyTorch build and exposes no CUDA runtime/device to the application.

## Work deliberately not performed

- No synthetic benchmark implementation.
- No real NLLB CPU benchmark.
- No real NLLB CUDA benchmark.
- No CPU/CUDA comparison or speedup claim.
- No batch-size recommendation.
- No RAM/VRAM benchmark claim.
- No production source, dependency declaration, or lockfile change.
- No Graphify/CRG implementation preflight beyond reading the mandatory workflow, because the
  explicit environment gate terminated the ticket before benchmark design.
- No `scripts/check.ps1`, since no implementation exists to validate.
- No PDFTR-15 work.

## Unblock decision required

Resuming requires changing the project environment to a CUDA-enabled PyTorch distribution and
locking an appropriate package source/build. That is a dependency and environment policy decision,
not a benchmark-only edit. After the CUDA build is installed, the real GPU operation gate must pass
before PDFTR-14 implementation continues.

## Recommendation

- Keep PDFTR-14 **On hold**.
- Do not merge this branch as a completed implementation.
- Do not accept CPU-only measurements for this ticket.
- Resume only after the CUDA gate succeeds in the same `uv` project environment.
