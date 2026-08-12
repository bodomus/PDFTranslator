# Implementation Plan — PDFTR-14

## Status

Completed. Implementation, real CPU/CUDA benchmarks, local validation, push, report/review, and
Windows/Ubuntu CI verification all passed.

## Scope and sequence

1. Confirm the branch is based on the PDFTR-11/12/13/13A master baseline and preserve unrelated
   files.
2. Apply the Level 2 pre-ticket workflow: Graphify orientation, CRG preflight, and direct source
   verification of translation, cache, glossary, repeated-element, NLLB, and batch lifecycles.
3. Unblock the mandatory CUDA gate reproducibly with an official Windows PyTorch wheel selected by
   project-level uv metadata, an updated lock, and a clean frozen synchronization.
4. Prove raw CUDA allocation/computation/synchronization/memory counters and strict-offline NLLB on
   explicit CUDA and explicit CPU without fallback.
5. Add a Typer-independent performance package, public-safe deterministic dataset, standalone
   script, versioned JSON/Markdown contracts, timing/RSS/VRAM samplers, and integrity checks.
6. Exercise the production logical-paragraph path in synthetic, real CPU, and real CUDA modes with
   cold model, warm model, warm cache, batch reuse, batch sizes 1/4/8, and forced segmentation.
7. Use one excluded warmup and five CUDA samples; use three CPU samples as the ticket's documented
   expensive-run exception. Aggregate count/min/median/p95/max without mixing cold-start timing.
8. Run focused tests, full `scripts/check.ps1`, Graphify/CRG post-change validation, and inspect the
   generated reports for identical within-device and cross-device outputs.
9. Update the implementation report and independent review with measured values and limitations,
   commit/push the existing branch, and verify Windows and Ubuntu GitHub Actions.

## Constraints

- No PDFTR-15 work and no new PDFTR-14A branch.
- No production translation optimization or normal CLI behavior change.
- No model/GPU requirement in CI and no model download in tests.
- Every runtime cache and report remains below repository-local `./temp/` and uncommitted.
- Explicit CUDA must fail if the effective translator device is not CUDA.
