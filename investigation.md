# PDFTR-2 Investigation

## Scope and risk

PDFTR-2 is a Level 2 change. It adds a runtime dependency, a stable document schema,
PDF parsing and validation, two CLI commands, filesystem writes, and generated PDF
test scenarios.

## Baseline

- Repository: `J:/Projects/Python/PDFTranslator`
- Branch: `master`
- Baseline commit: `7a4cb4e`
- Python: 3.12.10
- uv: 0.5.26
- Existing CLI: Typer callback plus `doctor`
- Existing runtime boundaries: `Settings`, logging setup, and a thin package entry point
- Pre-existing untracked input: `Tasks/PDFTR-2-pdf-inspection-and-extraction.md`

## Ticket and dependency

- The complete ticket source is already attached to PDFTR-2 in YouTrack.
- The required PDFTR-1 code is present in the repository and committed.
- PDFTR-1 remains in review only because its review attachment could not be uploaded;
  the user explicitly instructed work on PDFTR-2 to proceed.

## Graph preflight

Graphify 0.9.8 found no existing `graphify-out` graph. No supported semantic LLM
backend is configured, so the local no-LLM update path was used. It produced an
AST/document graph with 161 nodes and 190 edges. Queries confirmed:

- `src/pdftranslate/cli.py` is the only CLI composition point;
- domain and PDF services can be added without importing Typer;
- the existing `doctor` command depends only on settings and logging;
- README, CHANGELOG, tests, and the ticket are the relevant downstream documentation.

`code-review-graph` was updated to commit `7a4cb4e` and contains 32 code nodes and
154 relationships across 11 source/test/script files. The current change starts with
a low blast radius but introduces new module boundaries that require a post-change
graph refresh.

## Current PyMuPDF API findings

Context7 was used against the current official PyMuPDF project documentation:

- `pymupdf.open(path)` raises dedicated missing, empty, and file-data errors;
- `Document.needs_pass` identifies a document that requires authentication;
- `Page.get_text("dict", sort=False)` exposes original blocks, lines, spans,
  bounding boxes, font name, font size, integer color, and font flags;
- image blocks use type `1` and include placement bounding boxes;
- `Page.rect` is the effective visible rectangle and accounts for rotation;
- `Page.rotation` is normalized to 0, 90, 180, or 270;
- italic and bold are derivable from the documented font flag bits.

## Decisions

1. Use Pydantic domain models because it is already a project dependency and gives
   strict validation plus deterministic JSON round-tripping.
2. Store page numbers as one-based values and retain `source_index` as the explicit
   zero-based PyMuPDF index.
3. Preserve PyMuPDF block order. Normalization removes empty blocks and normalizes
   line whitespace without geometrically reordering columns. Both original and
   normalized indexes remain visible.
4. Count actual image placements from `get_text("dict")`, not merely image resources.
5. Use a conservative built-in Latin/Cyrillic character heuristic for probable
   language; no new language-model dependency.
6. Inspection of an encrypted document returns a restricted inspection report with
   `encrypted=true`, `password_required=true`, and a warning. Extraction fails with
   a useful password-required error because this ticket exposes no password option.
7. Use a SHA-256 source fingerprint so later translation/rendering stages can verify
   that JSON belongs to the immutable source PDF.
8. Generate all PDF fixtures at test runtime with PyMuPDF; commit no binary fixtures.

## Classification heuristic

Configurable settings use the `PDFTRANSLATE_` environment prefix:

- minimum meaningful text characters;
- maximum incidental text block count;
- minimum mixed-page image-area ratio;
- minimum scanned-page image-area ratio.

Classification is deterministic:

- no text and no images: `empty`;
- no meaningful text plus an image: `scanned`;
- meaningful text plus sufficiently large image coverage: `mixed`;
- otherwise, any extractable text: `text`.

An image-only page remains `scanned` even when its image coverage is below the
configured scanned threshold, with a warning that the classification is low
coverage. This avoids misclassifying image-only content as empty.

## Validation and security boundaries

- Validate that input exists, is a regular `.pdf` file, opens as PDF, and has pages.
- Reject corrupt files and password-required extraction.
- Parse one-based page ranges and reject descending, duplicate, malformed, or
  out-of-bounds selections.
- Reject output equal to the source path.
- Refuse existing outputs unless `--overwrite` is explicit.
- Write UTF-8 JSON through a temporary sibling file followed by atomic replacement.
- Never mutate or rewrite the source PDF.

## Known limitation

PyMuPDF's native block order is deterministic but is not a semantic reading-order
solver. Multi-column PDFs are preserved as emitted; unrelated columns are not merged
or heuristically rearranged in this ticket.
