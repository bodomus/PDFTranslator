# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Opt-in `scripts/validate-real-pdfs.ps1` corpus harness with dry-run, manifest/category/path
  subset selection, continue-on-error/fail-fast policies, one shared model/cache runtime, and
  explicit real-model, device, OCR, offline, resume, and overwrite controls.
- Versioned real-PDF evidence: atomic JSON and Markdown summaries, per-document results, copied
  logs, anonymized relative paths, stage timing, page classifications, source checksums, OCR and
  cache/resume metrics, manual PDF-XChange observations, and mapped deterministic defects.
- Generated-PDF/fake-backed validation tests covering text/image success, scanned OCR dependency,
  translation/render/output-validation failures, continuation, Unicode paths, source preservation,
  report generation, cache reuse, resume, and manual compatibility failures without model downloads.
- Recursive and non-recursive `pdftranslate batch INPUT_DIR` processing with deterministic
  case-insensitive PDF discovery, glob/exclude filters, `.ru.pdf` and output-tree protection,
  preserved relative output structure, and Unicode/spaced-path support.
- Lazy single-model and shared SQLite translation-cache lifetime across sequential batch files,
  while retaining source-specific workspaces, OCR settings, atomic output publication, and resume.
- Atomic versioned JSON batch reports, human-readable summaries, fail-fast and
  `--continue-on-error` policies, explicit skipped-file reasons, and exit code 10 for partial or
  complete batch failure.

- OCRmyPDF/Tesseract preprocessing stage with `auto`, `on`, and `off` modes, English language
  selection, deskew/clean/rotation controls, explicit force mode, bounded subprocess execution,
  retained logs/sidecars, actionable dependency failures, and a dedicated OCR failure exit code.
- Conservative mixed-PDF handling via OCRmyPDF skip mode, immutable source files, post-OCR
  page-count/geometry/classification validation, low-text warnings, and resumable `ocr.pdf`
  workspace artifacts invalidated by source or OCR-setting changes.
- `pdftranslate doctor` OCRmyPDF, Tesseract, Ghostscript, executable-path, version, and English
  language-data diagnostics without automatic system installation.
- Mocked OCR unit and pipeline tests plus an explicitly enabled optional real-OCR integration test.
- Root `pdftranslate INPUT.pdf` workflow for inspection, extraction, local translation, rendering,
  final validation, and atomic publication with `<stem>.ru.pdf` default naming.
- Deterministic application-cache workspaces containing inspection/extraction/translation
  artifacts, render candidates, versioned stage manifests, detailed logs, and failure state.
- Stage-aware `--resume` with strict source/options/artifact compatibility, completed-stage reuse,
  translation checkpoint continuation, and visible reused-stage reporting.
- Model-free `--dry-run` planning with page classifications, block estimates, OCR requirement,
  selected backend/device, output path, and expected stages.
- Centralized stable exit-code categories for arguments, PDF input, OCR, model loading,
  translation, rendering, output validation, and interruption.
- Generated-PDF/fake-backend end-to-end tests including option/source invalidation, publication
  safety, Ctrl+C, spaces, and Cyrillic paths.
- `pdftranslate render` for validated Russian text reconstruction in a new PDF.
- Cyrillic system-font discovery and glyph validation, embedded custom fonts, deterministic
  wrapping/font reduction, bounded block expansion, and explicit overflow warnings.
- Text-only redaction that retains image/vector objects, sampled non-white backgrounds, atomic PDF
  publication, reopening validation, and separate debug-layout output.
- Runtime-generated rendering tests for geometry, images/vectors, fitting, overflow, mismatch,
  Unicode paths, font validation, and CLI behavior.
- Local `pdftranslate translate` English-to-Russian pipeline using the
  `facebook/nllb-200-distilled-600M` backend.
- Backend-independent translator protocol, CPU/CUDA/auto selection, offline model loading, bounded
  OOM recovery, token-aware batching, protected tokens, and deterministic segmentation.
- Schema 1.1 translated JSON with original/translated text, settings identity, timestamps,
  warnings, progress statistics, atomic checkpoints, and validated resume.
- SQLite translation memory under the configured application cache root.
- Fake-backed translation/NLLB/CLI tests that never download model weights.
- PyMuPDF-backed PDF validation, inspection, and structured text-block extraction.
- `pdftranslate inspect` with readable table and clean `--json` output.
- `pdftranslate extract` with one-based page ranges, pretty/compact version 1.0 UTF-8 JSON,
  overwrite protection, and atomic writes.
- Strict domain models for source fingerprints, metadata, page geometry and classification,
  image placement counts, text-block order, bounding boxes, and span typography.
- Configurable deterministic `text`, `scanned`, `mixed`, and `empty` page heuristics.
- Runtime-generated PDF tests including encrypted and Unicode-path scenarios.
- Initial Python 3.12 project foundation.
- `pdftranslate --version` and `pdftranslate doctor` commands.
- Typed environment-based settings and centralized Rich logging.
- Tests, Ruff, mypy, pre-commit, PowerShell helpers, and cross-platform CI.

### Security

- The one-command workflow renders only to its cache workspace, validates a temporary destination
  sibling, and publishes the final name atomically; failed runs retain diagnostics without leaving
  a partial final PDF.
- Rendering validates source identity and block/page layout, refuses source/output aliases, and
  publishes only a reopened valid PDF; mismatch override never skips structural validation.
- Translation preserves original source text and fails rather than silently dropping protected
  URLs, email addresses, paths, measurements, or identifiers.
- Offline mode prevents remote model acquisition; default cache paths remain outside the repository.
- Source PDFs are never rewritten; extraction rejects source/output aliases and protects existing
  JSON unless `--overwrite` is explicit.
- Password-required PDFs are reported by inspection and rejected by extraction with a useful error.

## [0.1.0] - 2026-07-31

- Bootstrap release foundation; PDF translation is not implemented yet.
