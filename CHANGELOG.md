# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

- Source PDFs are never rewritten; extraction rejects source/output aliases and protects existing
  JSON unless `--overwrite` is explicit.
- Password-required PDFs are reported by inspection and rejected by extraction with a useful error.

## [0.1.0] - 2026-07-31

- Bootstrap release foundation; PDF translation is not implemented yet.
