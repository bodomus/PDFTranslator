# Implementation Plan — PDFTR-14

## Status

Blocked at the mandatory CUDA environment gate before implementation.

## Intended workflow

1. Verify a clean branch based on current `master`.
2. Verify that the project Python environment can execute a real PyTorch CUDA operation.
3. Complete Graphify/CRG Level 2 preflight and source verification.
4. Design and implement synthetic and real-model performance instrumentation.
5. Run real NLLB CPU and CUDA benchmarks on the same dataset.
6. Run focused and full validation, produce reports, push, and verify CI.

## Blocking condition

Step 2 failed on 2026-08-12. The workstation exposes an NVIDIA GeForce RTX 4080 through the
driver, but the project environment contains `torch 2.13.0+cpu`, has no Torch CUDA runtime, and
reports no CUDA devices. Per the ticket acceptance criterion, CPU-only work must not substitute for
CUDA evidence, so steps 3–6 have not started.

## Resume criteria

- Install and lock a Python 3.12-compatible CUDA-enabled PyTorch distribution for the project.
- Confirm that the selected PyTorch/CUDA build is compatible with the installed NVIDIA driver.
- Re-run the gate and require all of the following:
  - `torch.cuda.is_available()` is `True`;
  - at least one CUDA device is visible;
  - allocation, matrix multiplication, result transfer, peak-memory counters, and
    `torch.cuda.synchronize()` succeed;
  - the effective device is the RTX 4080 and is not silently changed to CPU.
- Only then continue the Level 2 preflight and implementation.
