# PDFTR-9A Implementation Plan

1. Add failing regression tests for identical-source samples with different protected tokens, human
   reviews and historical traces; confirm current leakage while translator executes once.
2. Replace `_CachedResult` with an execution-only immutable cache value and centralize per-sample
   evaluation so cache hits and misses follow the same analysis/status path.
3. Add mocked NLLB tests covering AutoConfig/AutoTokenizer/model local-only arguments, local cache
   snapshot resolution, offline missing-file errors, no online fallback, environment restoration on
   success/failure, and unchanged online behavior.
4. Implement local offline model resolution and a small scoped environment context inside the NLLB
   adapter; keep Typer and other pipeline modules unchanged except help/documentation if needed.
5. Run focused benchmark/NLLB/translation tests, then full pytest, Ruff, mypy and `check.ps1` with all
   caches and runtime artifacts under `./temp`.
6. Run the real cached NLLB benchmark in strict offline mode and record logs/results. Update CRG and
   inspect blast radius; no Graphify rebuild unless module boundaries unexpectedly change.
7. Update README, CHANGELOG, `implementation-report.md`, `reviews/review-PDFTR-9.md`, and create
   `reviews/review-PDFTR-9A.md`. Commit/push only after all checks and check-in evidence are complete.
