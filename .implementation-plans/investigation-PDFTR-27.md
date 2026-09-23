# PDFTR-27 investigation — typography evidence and style baseline

## Scope and preflight

- Change level: **Level 2**. The ticket adds a typed domain/service boundary and retains two
  additional optional source-span attributes, but deliberately does not change rendering policy.
- Branch point: `master` at `42afc5e`; working branch
  `codex/PDFTR-27-typography-evidence-style-baseline`.
- Unrelated working-tree deletion `temp/.agents.zip` is user-owned and remains untouched.
- Required ProjectWiki search matched the reflow architecture, rendering-completeness boundary,
  and system overview.
- Graphify (`graphify-out/graph.json`, generated 2026-09-22) located the extraction →
  reconstruction → reflow path. Source inspection confirmed the relevant relationships.
- CRG was rebuilt successfully on this branch: 138 files, 1,320 nodes, 11,763 edges.

## Current source path

`PyMuPdfBackend._extract_page()` performs one `page.get_text("dict", sort=False)` call per selected
page. `_span_from_dict()` currently retains text, bbox, font name, font size, packed color, and
bold/italic booleans derived from PyMuPDF font flags. `_text_block_from_dict()` retains line bbox and
span membership. Paragraph reconstruction turns source lines into `ParagraphFragment` values and
preserves their spans in occurrence-ordered `LogicalParagraph` objects.

Production reflow currently derives a median span size and the first available color in
`rendering/reflow/regions.py`, then constructs the intentionally small `ReflowStyle` contract. It
does not consume a general typography model. That separation is the no-rendering-regression seam
for this ticket.

## Evidence matrix

| Property | Current evidence | Recoverable | Confidence basis | Decision |
| --- | --- | --- | --- | --- |
| source font name | `TextSpan.font_name` | yes | dominant meaningful source characters | normalize only six-uppercase-letter PDF subset prefixes |
| font size | `TextSpan.font_size` | yes | character-weighted dominant size | resistant to isolated superscripts/markers |
| bold | `TextSpan.bold` | yes | PyMuPDF flags | retain raw flags too; mixed evidence remains explicit |
| italic | `TextSpan.italic` | yes | PyMuPDF flags | retain raw flags too; mixed evidence remains explicit |
| color | `TextSpan.text_color` | yes | character-weighted packed RGB | emit normalized 8-bit RGB and mixed-color flag |
| alignment | fragment/line bboxes plus page geometry | inferred | stable line edges/centres | conservative enum; ambiguity yields unknown |
| line height | line bboxes only; span `origin` discarded | partially | successive baselines | retain optional span origin and use median baseline distance |
| first-line indent | ordered fragment bboxes | inferred | first line versus following lines | unknown for one-line paragraphs |
| left/right indent | fragment bboxes plus role-region bounds | inferred | source-page geometry | geometry only; no semantic guessing |
| spacing before | occurrence-neighbour bboxes | inferred | one reliable same-page predecessor | low confidence |
| spacing after | same physical gap | available but duplicative | n/a | keep unknown; canonical observed gap is `space_before` |
| role | `ParagraphKind` | yes | reconstruction classification | map body/heading/footnote; otherwise other |
| mixed inline styles | paragraph spans | yes | distinct normalized source values | explicit flags for name, size, weight, italic, and color |

## Lost raw evidence and compatibility

PyMuPDF's span dictionary includes integer `flags` and `origin=(x, baseline_y)`. Both are useful and
currently discarded. The smallest safe retention change is to add optional `font_flags` and
`origin` fields to `TextSpan` and populate them during the existing page pass. Old schema 1.2/1.3
JSON remains readable because both fields default to `None`; no source PDF is reopened and no new
pass is introduced. The document schema version is not bumped because typography is a derived,
optional diagnostic contract rather than a persisted document requirement.

## Real Robitzsch baseline before implementation

Direct PyMuPDF and production extraction were compared for pages 1, 3, and 4.

- The artifact has 4 pages and 61 logical occurrences: 26 body and 35 footnote. The current
  classifier exposes no `HEADING` occurrence in this four-page excerpt.
- Body text on pages 3 and 4 is predominantly `AGaramondPro-Regular` at about 10.959 pt; footnotes
  are predominantly 7.970 pt with isolated 5.635 pt markers.
- Page 3 occurrences 38–41 preserve line fragments and font metadata; occurrences 39 and 40 contain
  explicit italic runs. Occurrence 40 contains an isolated 7.749 pt marker among 10.959 pt body
  spans, demonstrating why an unweighted first/median choice is insufficient.
- Page 1 occurrence 4 contains regular and italic source spans plus the isolated marker size.
- Packed colors are mostly `0x000000`; isolated `0x008080` spans exist and must trigger mixed-color
  evidence rather than silently becoming uniform black.
- Raw span flags are `4` for regular and include PyMuPDF's italic bit for italic spans. Raw origins
  expose stable baseline distances that are absent from the current model.
- Font names such as `AGaramondPro-Regular+f6` are encoding/subfont suffixes, not the standard
  six-uppercase-letter subset-prefix form. They must not be stripped by the conservative normalizer.

## Storage and API decision

Use a derived production service (ticket option C/D):

```text
extract_typography_evidence(document) -> TypographyBaseline
```

The service consumes the already extracted schema 1.2/1.3 document in one deterministic in-memory
pass and is independent of Typer and rendering. `TypographyBaseline` is a compact diagnostic JSON
contract keyed by authoritative occurrence index plus paragraph ID. It is not embedded in
`ExtractedDocument`, so translation cache/resume compatibility and schema 1.3 rendering remain
unchanged.

## Blast radius and risks

- Direct changes: `TextSpan`, the PyMuPDF span adapter, a new `pdftranslate.typography` package, a
  standalone inspection script, tests, documentation, and Wiki.
- Adjacent but intentionally unchanged: `LogicalParagraph`, translation, cache/resume,
  `ReflowStyle`, body/footnote planning, PDF mutation, OCR, and public Typer CLI.
- Optional `TextSpan` fields flow through existing Pydantic serialization and reconstruction; tests
  must cover both populated and absent values.
- Geometry heuristics can overclaim. Every inference therefore has a small categorical confidence,
  typed provenance, and an explicit unknown outcome.
- No source-PDF safety or final-PDF integrity path is modified. Existing production reflow tests and
  the repository quality gate are required regression evidence.
