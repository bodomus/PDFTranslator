# Implementation Report

## Ticket

PDFTR-4 — Render translated Russian text into a copy of the source PDF

## Workflow

- Level: 2
- Graphify: used before and after implementation
- CRG: used before and after implementation
- Context7: current PyMuPDF redaction, textbox, custom-font, and glyph APIs checked
- Working tree before changes: user-owned untracked PDFTR-4/PDFTR-5 ticket sources preserved
- Baseline: `00e40f6ef55508ad1a2bf92e88d4a7cda4b8d895`

## Scope

- Modules: new `pdftranslate.rendering` package, thin `render` CLI command, shared source identity helper
- Pipeline stage: translated JSON → validated translated PDF
- Dependency impact: none; existing PyMuPDF dependency is sufficient
- Model/device impact: none
- OCR impact: none
- Public contract: `pdftranslate render SOURCE TRANSLATED_JSON --output OUTPUT`
- PDF integrity: source remains immutable; final files are temporary-written, reopened, validated, and atomically published

## Investigation

The application previously stopped at completed schema 1.1 JSON. The missing capability was a safe PyMuPDF reconstruction stage. Existing source fingerprint, page geometry, stable block IDs, span typography, and original/translated text provide the required renderer input without a schema change.

Graphify located CLI, document models, extraction/fingerprint ownership, serialization, and test neighborhoods. CRG baseline contained 269 nodes / 1693 edges across 36 files and 17 flows; there was no render path. Source and current PyMuPDF documentation resolved the design.

## Changes

- Added `PdfRenderer`, typed `RenderOptions`, block/result records, and user-facing rendering errors.
- Added explicit and Windows/Linux/macOS font discovery without bundling fonts.
- Added required-Cyrillic glyph validation through `Font.has_glyph()`.
- Added completed schema 1.1, SHA-256/file-size, page count/dimensions/index, block ID/text/bbox, and translated-text validation.
- Added deliberate fingerprint override that still performs full structural validation.
- Added median background sampling and text-only redaction with image/vector preservation modes.
- Added deterministic textbox probing, font reduction, bounded downward expansion, and explicit overflow results/warnings.
- Added temporary sibling saving, exact inserted-Cyrillic verification after reopening, and atomic output publication.
- Added separate `.debug.pdf` output with source/final/expanded/overflow rectangles.
- Added all required CLI options, including configurable redaction padding and source mismatch override.
- Added runtime-generated tests and updated README/CHANGELOG.

## Graph and source validation

- Graphify post-change: 745 nodes / 1584 edges. Query found `render_pdf`, `PdfRenderer.render`, validation, font, fitting, redaction, publication, debug, and rendering tests. Result saved as useful.
- CRG post-change full build: 331 nodes / 2256 edges across 43 files.
- The final CRG incremental parse completed; its console risk-panel rendering hit a Windows cp1251 Unicode limitation, while MCP statistics and queries remained available.
- CRG found 25 symbols in `renderer.py`, the `render_pdf` entry flow, and seven direct callers/tests for `PdfRenderer.render` (CLI plus six direct renderer tests). The CLI invocation test additionally verifies Typer registration dynamically.
- Source/runtime evidence confirmed PyMuPDF 1.28.0, redaction constants, system Segoe UI Cyrillic glyph support, and the documented negative textbox deficit behavior.
- No unexpected extraction, translation, cache, model, CUDA, or OCR dependencies were introduced.

## Validation

- Focused rendering tests: 8 passed (`--no-cov`)
- Full suite: 71 passed
- Coverage: 83.99% (required 80%)
- Ruff format: passed
- Ruff lint: passed
- strict mypy: passed for 30 source files
- Required `scripts/check.ps1`: passed
- CLI smoke: `pdftranslate render --help` passed and exposed every required option
- PDF validation: generated outputs reopened with PyMuPDF; page geometry, images, drawings, inserted Russian text, original-text removal, source hash, debug PDF, and Unicode paths verified
- Real-model/CUDA/OCR: not applicable and not run
- Representative external PDF: not used; deterministic generated PDFs were used to avoid committing binaries

## Documentation

- `README.md`: render usage, font policy, integrity checks, fitting, debug output, background limitations, and updated roadmap/tests
- `CHANGELOG.md`: renderer, safety, fitting, fonts, validation, and tests
- `Tickets/PDFTR-4-render-translated-pdf.md`: local ticket mirror

## Remaining risks

- Arbitrary gradients, patterns, transparency, and text intersecting complex line art cannot be reconstructed perfectly by median background sampling.
- Dense or highly irregular layouts may report overflow; the translated text is not silently clipped.
- Font discovery depends on system-installed fonts; explicit `--font` is the deterministic operational choice.
- OCR and text inside images remain intentionally out of scope.
