# Implementation Plan — PDFTR-14

## Status

Blocked during PDFTR-14A dependency locking. The official CUDA dependency design and compatible
wheel are verified, but this execution environment cannot reach PyPI or the PyTorch package index,
and its offline uv cache does not contain the CUDA wheel/metadata required to produce and validate
`uv.lock`.

## Intended workflow

1. Verify a clean branch based on current `master`.
2. Verify that the project Python environment can execute a real PyTorch CUDA operation.
3. Complete Graphify/CRG Level 2 preflight and source verification.
4. Configure an official Windows CUDA PyTorch source in project metadata and regenerate the lock.
5. Prove clean frozen synchronization and the raw CUDA/NLLB CUDA/NLLB CPU gates.
6. Design and implement synthetic and real-model performance instrumentation.
7. Run real NLLB CPU and CUDA benchmarks on the same dataset.
8. Run focused and full validation, produce reports, push, and verify Windows and Ubuntu CI.

## Blocking condition

Step 2 failed on 2026-08-12. The workstation exposes an NVIDIA GeForce RTX 4080 through the
driver, but the project environment contains `torch 2.13.0+cpu`, has no Torch CUDA runtime, and
reports no CUDA devices. Per the ticket acceptance criterion, CPU-only work must not substitute for
CUDA evidence, so steps 3–6 have not started.

## PDFTR-14A — CUDA environment unblock

### Dependency decision

- Keep the declared Python range and Torch dependency range unchanged.
- On Windows only, resolve `torch` from the official
  `https://download.pytorch.org/whl/cu130` index.
- Keep the index explicit so unrelated packages continue to resolve from PyPI.
- Let Linux CI retain its existing PyPI Torch source and GPU-independent test behavior.
- Do not add torchvision, torchaudio, the system CUDA Toolkit, or developer-only install commands.

The official index was checked before editing and contains
`torch-2.13.0+cu130-cp312-cp312-win_amd64.whl`. CUDA 13.0 is an official current PyTorch target,
supports the project's selected Torch/Python/Windows combination, and is within the runtime
capability exposed by the installed NVIDIA driver. The driver-reported maximum is not treated as
the wheel version requirement.

### Required gates

- Regenerate `uv.lock` and verify its Windows source/wheel is CUDA-enabled.
- Synchronize a clean uv-managed environment exclusively from the frozen lock.
- Re-run the gate and require all of the following:
  - `torch.cuda.is_available()` is `True`;
  - at least one CUDA device is visible;
  - allocation, matrix multiplication, result transfer, peak-memory counters, and
    `torch.cuda.synchronize()` succeed;
  - the effective device is the RTX 4080 and is not silently changed to CPU.
- Run strict-offline production NLLB smoke tests on explicit CUDA and explicit CPU.
- Run focused dependency/device tests and the complete `scripts/check.ps1` quality gate.
- Push and require both Windows and Ubuntu GitHub Actions jobs to pass.
- Only then continue the original PDFTR-14 benchmark implementation on this branch.

### Current blocker

- `uv lock` cannot connect to PyPI from either the repository-local cache configuration or the
  existing user cache (`os error 10013`, socket access forbidden).
- `uv lock --offline` confirms the CUDA-index split is recognized but cannot resolve any matching
  Windows Torch build because the CUDA index metadata is absent locally.
- The connected browser verified the official wheel link and SHA-256 but its client blocks direct
  wheel navigation/download.
- No partial `pyproject.toml`/`uv.lock` mismatch is retained in the branch.

Resume requires network access for `uv` to `https://pypi.org` and
`https://download.pytorch.org`, or an approved repository-local uv cache populated with the exact
official indexes/wheel. Then apply the documented source entry, run `uv lock`, clean frozen sync,
and all mandatory gates.
