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

## PDFTR-14A — CUDA environment unblock

### Status

**BLOCKED — official dependency identified, reproducible lock/sync unavailable.**

### Original blocker

- Torch: `2.13.0+cpu`.
- `torch.version.cuda`: `null`.
- CUDA available: `False`.
- GPU visibility: RTX 4080 visible to NVIDIA-SMI, invisible to PyTorch.

### Selected dependency design

- Official index checked: `https://download.pytorch.org/whl/cu130`.
- Intended Torch build: `2.13.0+cu130`.
- Verified wheel: `torch-2.13.0+cu130-cp312-cp312-win_amd64.whl`.
- Verified official SHA-256:
  `2efab1e83604ca628c6d85b9e188c153690980498d1297081a9dad704919303c`.
- Intended platform marker: `sys_platform == 'win32'`.
- Intended uv policy: explicit `pytorch-cu130` source only for Torch; Linux remains on PyPI.
- Selection basis: current official uv PyTorch integration guidance and the official PyTorch
  wheel index; the installed NVIDIA driver supports a CUDA 13.0 runtime.

### Reproducibility attempts

Commands attempted:

```powershell
uv --cache-dir .\temp\uv-cache lock
uv lock
uv lock --offline
```

Results:

- Repository-local cache attempt could not connect to PyPI.
- Existing-cache online attempt failed with `os error 10013`: socket access forbidden.
- Offline resolution recognized the Windows source split but reported no Torch version in the
  required `>=2.7,<3` range because cu130 metadata/wheels are absent from the cache.
- Local cache inspection found only PyPI CPU Torch artifacts.
- Browser inspection verified the exact official cu130 wheel URL, but direct wheel download was
  blocked by the browser client.
- `uv.lock` was not edited manually.
- The candidate `pyproject.toml` change was removed so the committed branch does not contain
  mismatched project metadata and a stale CPU-only lockfile.

### Gates not executed

- Clean `uv sync --frozen --all-groups`: not possible without a valid updated lock and wheel.
- Raw CUDA allocation/matmul/synchronize/result/memory counters: not rerun.
- Production NLLB CUDA smoke: not run.
- Production NLLB CPU smoke under the CUDA-capable wheel: not run.
- Original PDFTR-14 benchmark: not resumed.
- `scripts/check.ps1`: not presented as completion evidence because dependency correction is not
  present and CUDA acceptance remains blocked.
- GitHub Actions: not run for an incomplete dependency change.

### Next required environmental action

Allow uv outbound access to both `https://pypi.org` and `https://download.pytorch.org`, or provide
an approved repository-local uv cache populated from those official sources. Then the documented
Windows-only explicit cu130 source can be applied, locked, cleanly synchronized, and subjected to
the mandatory CUDA/NLLB/CPU/CI gates before PDFTR-14 resumes.
