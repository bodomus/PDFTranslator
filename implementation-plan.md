# PDFTR-3 Implementation Plan

1. Add and lock compatible Transformers and PyTorch runtime dependencies.
2. Extend the intermediate schema compatibly with translated text, status, settings identity, timestamps, statistics, and warnings.
3. Add a backend-independent translator protocol and translation errors.
4. Implement pure skip/protection/segmentation/recombination helpers with exact protected-token restoration and no truncation.
5. Implement SQLite translation memory below the application cache root.
6. Implement an injectable NLLB adapter with direct loading, EN/RU mapping, offline/cache behavior, CPU/CUDA/auto selection, inference mode, and bounded CUDA OOM recovery.
7. Implement the document orchestrator with token-aware batches, cache reuse, progress events, atomic checkpoints, interruption metadata, and validated resume.
8. Add a thin `translate` Typer command with every required option and useful logs/statistics.
9. Add fake-backed tests for abstraction, batching, segmentation, skip/protection, cache, device selection, offline loading, JSON integrity, interruption/resume, CLI, and output safety.
10. Update README and CHANGELOG with usage, cache/model behavior, storage estimate, offline operation, and limitations.
11. Run formatting, lint, strict mypy, full tests/coverage, CLI smoke checks, CRG update/impact analysis, and Graphify refresh.
12. Create and attach `review-PDFTR-3.md`, move the ticket to review, and commit only PDFTR-3 files while preserving unrelated user files.
