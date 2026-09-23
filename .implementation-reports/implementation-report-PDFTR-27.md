# PDFTR-27 implementation report — typography evidence and style baseline

## Result

Implemented a typed, deterministic, source-backed typography evidence layer for every logical
paragraph occurrence. The baseline is suitable as PDFTR-28 input and is intentionally disconnected
from production rendering, so current body/footnote layout, pagination, and publication behavior do
not change.

## Delivered architecture

- Added `pdftranslate.typography` with typed models for property value, categorical confidence,
  provenance, fallback behavior, paragraph role, alignment, RGB color, mixed-style evidence,
  per-occurrence evidence, and a versioned document baseline.
- Added `extract_typography_evidence(document)`. It consumes the already extracted document in one
  in-memory pass and never reopens the PDF per paragraph.
- Kept occurrence index authoritative and retained paragraph ID as a secondary source mapping.
- Chose derived storage (ticket option C/D). Typography is not embedded in `ExtractedDocument`, so
  schema 1.3 and translation cache/resume compatibility remain unchanged.
- Added optional `TextSpan.font_flags` and `TextSpan.origin` and populated them during the existing
  PyMuPDF page pass. Old JSON without these fields still validates.
- Added `python -m scripts.typography_inspect` with page/occurrence filtering and compact JSON output.

## Evidence policy

- Font name, size, booleans, and color use meaningful-character weights rather than span count.
  This prevents isolated superscripts/footnote markers from defining the paragraph baseline.
- Font normalization removes only a canonical `^[A-Z]{6}\+` PDF subset prefix. Source font identity
  remains distinct from future render-font resolution.
- Bold/italic are source flag evidence; color is decoded from packed PDF color to 8-bit RGB.
- Mixed name, size, weight, italic, and color remain explicit even when a dominant value is reliable.
- Alignment is conservative geometry evidence. First-line indentation is excluded from the stable
  following-line left-edge test, allowing justified indented prose without flattening the indent.
- Line height is median positive baseline distance. Line-box top distance is only a low-confidence
  fallback; one-line paragraphs remain unknown.
- First-line indent is first line versus median following lines. Left/right indents use observed
  role-region edges.
- Only observed gap-before is represented; gap-after remains unknown to prevent double counting.
- Role comes from `ParagraphKind`; no heading level is invented.

## Robitzsch source verification

The extractor and raw PyMuPDF were compared on pages 1, 3, and 4. The source SHA-256 is
`739163d0cb4a7ec189e069ceed3b0c719db0a00c57bc5b5465139815e0d6b3de`.

| Page / occurrence | Source-backed result | Classification |
| --- | --- | --- |
| 1 / 4 | AGaramondPro-Regular 10.959 pt; regular; dominant black; 12.472 pt line height; about 11 pt first-line indent; justified | direct font/size/flags/color; inferred geometry; mixed italic/size/font/color |
| 1 / 8 | AGaramondPro-Regular 7.970 pt footnote; left | direct style/role; inferred alignment; one-line height unknown |
| 3 / 39 | AGaramondPro-Regular 10.959 pt; 12.472 pt / 1.138 ratio; justified | direct style; inferred geometry; mixed italic/font |
| 3 / 40 | AGaramondPro-Regular 10.959 pt; about 11 pt first-line indent; justified | isolated 7.749 pt marker and teal marker remain mixed evidence and do not replace the baseline |
| 3 / 42 | AGaramondPro-Regular 7.970 pt footnote | one-line alignment/line height unknown rather than guessed |
| 4 / 49 | AGaramondPro-Italic 10.959 pt; centered | source classifier says body; visually heading-like text is not promoted to heading |
| 4 / 56 | AGaramondPro-Regular 7.970 pt footnote; left | direct style/role; inferred alignment; mixed marker/color evidence |

The artifact contains 61 logical occurrences: 26 body and 35 footnote. It contains no classified
heading occurrence; synthetic deterministic tests cover heading evidence without falsifying the
real source result.

## Tests

Added 21 deterministic typography tests covering the 20 requested scenarios plus canonical
gap-before spacing. Coverage includes dominant size versus superscript, subset prefix handling,
bold/italic/conflict, RGB, left/center/justified/unknown alignment, baseline height, single-line
uncertainty, first-line/whole-paragraph indents, body/heading/footnote distinctions, all mixed-style
flags, duplicate paragraph IDs, typed serialization, immutable rendering input, and spacing.

Updated PDF extraction coverage to assert retained raw flags and origin. Existing extraction and
production reflow tests were included in the focused run:

```text
60 passed
```

The complete repository gate reported:

```text
ProjectWiki: 14 pages, 85 links, 0 errors, 0 warnings
Ruff format: 226 files formatted
Ruff lint: passed
Mypy: 93 source files, no issues
Pytest: 290 passed, 1 skipped
Coverage: 88.57% (required 80%)
```

## Rendering regression evidence

- No renderer, reflow model, planner, measurement, mutation, validation, translation, OCR, cache,
  or pipeline file changed.
- Existing `tests/test_reflow_production.py` passed in the focused and full runs.
- The saved PDFTR-24 Robitzsch artifact remains readable with 9 pages and 8,907 extracted text
  characters. Its established completeness metrics remain 61 required occurrences, zero overflow,
  zero unplaced text, and 9 final pages.
- The ticket does not regenerate or commit PDFs.

## Documentation

- Added `docs/typography-evidence.md` with model, algorithms, confidence/provenance, storage decision,
  developer command, representative raw-source comparison, and limitations.
- Added the ProjectWiki typography architecture page and updated the reflow boundary, index, and
  knowledge log. Wiki lint passes.
- Updated README and CHANGELOG for the developer inspection workflow and typed baseline.

## Structural review

- Graphify was refreshed successfully after the new production module boundary: 3,330 nodes,
  6,704 edges, 227 communities.
- CRG was rebuilt successfully on the ticket branch: 1,320 nodes and 11,773 edges during the full
  build; status records 1,316 normalized nodes, 11,627 edges, and 138 files.
- CRG's tracked-diff detector reported risk 0.35, no affected flows, and named `TextSpan` and
  `_span_from_dict` as test gaps. Source verification resolves that conservative graph result:
  `tests/test_pdf_extraction.py` directly asserts both new fields and the full suite passes. Because
  the new files are untracked until the user commits them, tracked-diff impact output cannot list
  the new typography package; the full graph build plus Graphify and source/tests cover it.
- Source-verified blast radius stays inside extraction evidence, the new standalone domain service,
  diagnostics script, tests, and documentation. No dynamic CLI registration or backend reachability
  is required.

## Required artifacts

- `Tickets/PDFTR-27.md`
- `.implementation-plans/investigation-PDFTR-27.md`
- `.implementation-plans/implementation-plan-PDFTR-27.md`
- `.implementation-reports/implementation-report-PDFTR-27.md`
- `reviews/review-PDFTR-27.md`

The unrelated pre-existing deletion `temp/.agents.zip` was not modified or restored.
