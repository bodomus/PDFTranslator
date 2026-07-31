# PDFTR-4 Investigation

## Scope and baseline

PDFTR-4 is a Level 2 rendering and public-CLI change. It introduces source/JSON integrity validation, redaction, font discovery and glyph validation, deterministic fitting, atomic PDF publication, output reopening, and optional debug output.

- Repository: `J:/Projects/Python/PDFTranslator`
- Branch: `master`
- Baseline: `00e40f6ef55508ad1a2bf92e88d4a7cda4b8d895`
- Python: 3.12.10
- uv: 0.5.26
- PyMuPDF declared range: `>=1.26,<2`
- Installed smoke version: 1.28.0
- Existing translated contract: completed schema 1.1 with source fingerprint and per-block `translated_text`
- Pre-existing untracked files preserved: `Tasks/PDFTR-4-render-translated-pdf.md` and `Tasks/PDFTR-5-end-to-end-cli.md`

The ticket source is already attached to PDFTR-4 and is mirrored under `Tickets/`.

## Current and expected behavior

The CLI currently stops after translated JSON. There is no renderer, font policy, fitting, redaction, output validation, or `render` command. The required behavior is to create a new PDF from the immutable source plus completed schema 1.1 JSON while preserving page geometry, images, and vector objects where practical.

## Graph and source preflight

Graphify identified `cli.py` as composition root, the document/page/block models as renderer input, the extraction PyMuPDF adapter as source of fingerprint/effective coordinates, and serialization as the JSON boundary. Source verification confirmed stable block IDs, page dimensions, original span font sizes/colors, and SHA-256/file-size identity.

Code-review-graph was updated at baseline: 269 nodes, 1693 edges, 36 files, and 17 flows. Existing flows cover inspect, extract, translate, and JSON I/O; no render flow exists. The new path must be explicitly reachable from Typer and directly tested.

## External-library findings

Context7 current PyMuPDF documentation confirms:

- redaction uses `add_redact_annot()` then `apply_redactions()`;
- `apply_redactions(images=0, graphics=0, text=0)` removes text while retaining image/vector objects;
- `Shape.insert_textbox()` wraps text and returns a negative deficit without insertion when the rectangle is too small;
- a custom `fontfile` can be embedded;
- `Font.has_glyph()` validates required Unicode code points.

The installed runtime exposes these constants and a system Segoe UI font with Cyrillic glyphs. No font file will be copied into the repository.

## Decisions

1. Add a focused `rendering` package; keep PyMuPDF types in its adapter.
2. Reuse source fingerprint logic so identity rules cannot drift.
3. Require completed schema 1.1 and validate size/hash, page count, selected page dimensions, source indexes, block IDs/bounds, and translated text before publication. A deliberate override bypasses only size/hash mismatch.
4. Discover explicit, Windows, and common cross-platform fonts. Validate every required Cyrillic character with `Font.has_glyph()`.
5. Redact translated block rectangles, preserve image/vector objects, and sample a conservative background color rather than assuming white.
6. Fit with discarded shapes and deterministic font-size steps. Expansion is bounded by the page bottom and the next horizontally overlapping block.
7. Record overflow; never report silently clipped text as success. Debug mode writes a separate sibling `.debug.pdf`.
8. Save to a temporary sibling, reopen and validate, then atomically replace the output.

## Blast radius and limitations

Changes are limited to a new rendering package, a thin CLI command, PDF exports/errors, tests, README/CHANGELOG, and ticket documents. Translation, cache, model/CUDA, OCR, and schema layout do not change. Source PDFs remain immutable and generated PDFs stay temporary.

Arbitrary complex backgrounds and perfect typography cannot be guaranteed. Background sampling and rectangle redaction are conservative; warnings and debug output expose overflow/expansion. OCR and text inside images remain out of scope.
