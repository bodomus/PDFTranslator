# PDFTR-32 Investigation

## ProjectWiki pre-source retrieval

### Pages consulted

- `knowledge/wiki/index.md`
- `knowledge/wiki/architecture/reflow-layout.md`
- `knowledge/wiki/architecture/typography-evidence.md`
- `knowledge/wiki/architecture/style-reconstruction.md`
- `knowledge/wiki/components/foreign-language-preservation.md`
- `knowledge/wiki/failure-modes/render-completeness.md`
- `knowledge/wiki/architecture/system-overview.md`

### Search queries used

- `inline style mixed typography`
- `reflow measurement insertion`
- `foreign language preservation`
- `paragraph style reconstruction`
- `render completeness`
- `How exactly should inline runs be clipped and rebased while _largest_fitting_prefix() probes candidate prefixes?`

### Architecture facts recovered from ProjectWiki

- A logical paragraph occurrence is the semantic flow unit; a `PlacementSegment`-like continuation
  is the physical unit, and ordered segment ranges must reproduce the exact translated paragraph.
- BODY, HEADING, and FOOTNOTE all use occurrence-indexed resolved paragraph typography in production.
  Paragraph IDs validate identity but are not authoritative lookup keys.
- Measurement and insertion share one PyMuPDF HTML/CSS representation and automatic downscaling is
  disabled.
- Typography evidence and resolved styles are derived in memory and are not persisted in schema 1.3,
  cache, or resume artifacts.
- Mixed source font, size, weight, italic, and color are retained as diagnostics, while inline style
  reproduction is currently deferred.
- Existing foreign-language preservation can leave exact source substrings in translated output,
  including whole preserved units and protected inline foreign spans.
- Rendering is fail-closed for required content: planning precedes PDF mutation, every required
  occurrence must be accounted for, and saved-PDF validation is a separate strict invariant.
- Bold/italic requests remain diagnostic and unapplied until a safe face resolver exists.

### Safety constraints recovered from ProjectWiki

- Source PDFs are immutable and partial or invalid output must not be published.
- Paragraph-level resolved style remains the authoritative base style.
- Inline fidelity must not weaken exact text accounting, capacity failure, collision checks, or
  segment-local saved validation.
- Unsafe layouts and unsupported geometry must continue to fail closed.
- Current source, tests, configuration, and runtime evidence are more authoritative than Wiki
  summaries.

### Open questions requiring canonical source inspection

- How source `TextSpan` ordering composes into each `LogicalParagraph.text`, especially across
  fragments and separators.
- Whether existing preservation metadata identifies exact target ranges or only proves that text was
  preserved somewhere in the translated paragraph.
- The exact immutable inline evidence, mapping, applied-run, and diagnostic contracts.
- How `_largest_fitting_prefix()` probes candidate text and where prefix-local run clipping belongs.
- How segment ranges are constructed and therefore where paragraph runs should be clipped/rebased.
- Which measurer APIs, test doubles, and insertion APIs must change compatibly.
- How PyMuPDF saved span extraction can validate local size/color without platform-dependent font
  assumptions.
- Whether any safely mappable natural mixed-style examples exist in available real artifacts.

### Potentially stale or ambiguous Wiki claims

- `knowledge/wiki/architecture/system-overview.md` says resolved style reconstruction is not yet
  connected to production rendering, while the newer reflow and reconstruction pages say PDFTR-29,
  PDFTR-30, and PDFTR-31 activated BODY, HEADING, and FOOTNOTE. Canonical source must resolve this
  contradiction; the overview likely needs correction.
- The Wiki establishes that measurement and insertion share a representation, but intentionally does
  not define exact private planner behavior for inline run clipping. The negative retrieval query
  surfaced broad architecture pages rather than an authoritative implementation answer, so source
  inspection remains required as intended.

## ProjectWiki source cross-check

### Material claim classification

- **CONFIRMED** — BODY, HEADING, and FOOTNOTE resolved styles are active. `PdfRenderer.render()`
  reconstructs styles once, and `discover_reflow_page()` / `discover_footnote_page()` map them by
  occurrence index through role-specific adapters.
- **CONFIRMED** — occurrence index is authoritative and paragraph ID is validation only. Both body
  and footnote discovery reject a resolved identity mismatch.
- **CONFIRMED** — mixed inline style is currently diagnostic/deferred. `ReflowStyle` and
  `BlockRenderResult` carry one `mixed_style` flag, while `_segment_html()` emits one uniformly
  styled paragraph.
- **CONFIRMED** — measurement and insertion use `_segment_html()` and `_segment_css()` with the same
  selected font and `scale_low=1`; saved validation remains segment-local.
- **CONFIRMED** — strict planning reconstructs every paragraph from contiguous `PlacementSegment`
  ranges before mutation, and saved output is reopened and checked in each segment clip.
- **CONFIRMED** — bold/italic are requested metadata only; all three role adapters report them as
  unapplied and no synthetic face CSS is emitted.
- **CONFIRMED** — foreign-language preservation restores exact source strings, but its serialized
  evidence stores counts/classification rather than target offsets. PDFTR-32 therefore must prove
  target offsets from the final translated string itself.
- **STALE** — `knowledge/wiki/architecture/system-overview.md` says reconstructed style is not
  connected to production rendering. Current source and the newer reflow/style pages prove the
  opposite. The overview requires a focused correction.

### Source ordering and mapping findings

1. `TextLine.text` is created as the ordered concatenation of its `TextSpan.text` values and then
   stripped. `ParagraphFragment` retains the same ordered span tuple.
2. `LogicalParagraph.text` is reconstructed in fragment order by stripping fragment edges, inserting
   one inter-fragment space, or removing a proven soft line-break hyphen. The paragraph also retains
   every fragment and flattened source span in order.
3. Exact source ranges can therefore be reconstructed conservatively only when span concatenation
   matches its fragment and replaying the fragment join rules reproduces the paragraph text. A
   mismatch, removed soft hyphen inside a candidate, or otherwise unprovable range must be deferred.
4. Existing preservation behavior proves that some exact source strings survive, but it does not
   expose renderer-ready offsets. A bounded exact matcher must compare source and translated
   occurrences and require a unique monotonic assignment.

### Required-question answers

1. Source spans are ordered inside each fragment; fragments are ordered in the logical paragraph.
   Exact offsets are reconstructable only by replaying the current fragment join contract and
   validating the result against `LogicalParagraph.text`.
2. Ranges are not unconditionally reconstructable. Fragment/span mismatches and soft-hyphen edits
   can invalidate a run; those candidates must be deferred as unsafe rather than guessed.
3. Whole-unit and protected foreign-language restoration preserve exact strings, while glossary
   preservation can also leave exact terms. Neither exposes final offsets, so the final translated
   text remains the authoritative matching surface.
4. Planner, measurer, and inserter should share immutable translated-offset `InlineStyleRun` values;
   source candidates and deferrals remain separate evidence.
5. `_largest_fitting_prefix()` must receive the remaining-text-local runs and clip them again for
   every binary-search prefix before calling the measurer.
6. A run crossing a segment boundary is intersected with the segment's full-paragraph range, then
   rebased to segment-local offsets. The run text is sliced from the segment, never reconstructed.
7. Saved style validation is reliable only when extracted PyMuPDF span text aligns exactly with the
   segment text. In that case size/color can be checked with tolerances; otherwise existing strict
   text validation remains authoritative and style inspection is skipped rather than guessed.
8. `TextMeasurer.measure(text, style)` is implemented by the production PyMuPDF measurer and two
   production-test fakes. A keyword-only `inline_runs=()` extension preserves simple callers while
   making production planner calls explicit.
9. The implementation can remain derived at render time. No schema, translation cache, resume, or
   backend contract change is required.
10. Repository tests contain mixed-script deterministic fixtures. Natural Robitzsch data has mixed
    evidence, but safe applied counts must be measured after implementation and may legitimately be
    zero.
11. ProjectWiki correctly recovered occurrence identity, active role typography, deferred mixed
    styles, shared measurement/insertion, disabled downscaling, and fail-closed completeness.
12. Canonical source was still required for exact fragment joining, measurer signatures, prefix
    probing, segment construction, and diagnostic wiring.
13. One stale overview claim was found; no other material contradiction was found.

### Graph preflight

- Graphify reused the existing graph and surfaced the production reflow planner, PyMuPDF adapter,
  typography evidence, renderer, translation preservation, and focused tests. Every material graph
  conclusion above was checked in source.
- CRG was stale at commit `e9fd949` on the PDFTR-31 branch. A full build on
  `c7a991e` refreshed 147 files and confirmed the principal symbols:
  `FlowParagraph`, `PlacementSegment`, `TextMeasurer.measure`, `_largest_fitting_prefix()`,
  `PyMuPdfMeasurer.measure`, `_segment_html()`, `_segment_css()`, `insert_reflow_segments()`,
  `LogicalParagraph`, `TextSpan`, and foreign-language restoration.
- The expected blast radius is rendering/reflow models, planner, PyMuPDF layout, body/heading and
  footnote discovery, renderer diagnostics, focused tests, and documentation. Translation backend,
  OCR, CUDA/model loading, and persisted document schema are not expected to change.

### Smallest coherent change

Add one derived inline-style mapping module that reconstructs auditable source candidates,
conservatively maps exact surviving strings to translated offsets, clips/rebases immutable applied
runs, and exposes privacy-safe decisions. Thread those runs through the existing reflow contracts,
measure every prefix with the same rich HTML/CSS builder used for insertion, retain strict text
accounting and saved validation, and extend diagnostics. Do not alter translation, schema 1.3,
font resolution, or fixed-layout rendering.

## Follow-up investigation (2026-09-26)

- Current repeated-token mapping equates matching source/target occurrence counts with identity and
  selects by ordinal. For `2 source / 2 target`, the translation supplies no occurrence-level
  evidence proving that either styled source token owns the corresponding target token.
- The existing contract has no independent alignment metadata. The smallest safe rule is therefore
  to apply an exact candidate only when it occurs once in the source and once in the target; every
  repeated source or target occurrence is `AMBIGUOUS_TARGET_OCCURRENCE`.
- `PyMuPdfMeasurer.line_count` currently divides used height by the base paragraph line height.
  Because inline font size legitimately raises used height, one physical rendered line can be
  reported as two or more logical lines.
- The scratch PyMuPDF page already contains the shared HTML measurement result and no other text.
  Counting its emitted text-line objects is direct production evidence and feeds the existing
  heading-orphan path without changing planner or measurer contracts.
- Blast radius remains local to inline mapping, PyMuPDF measurement, focused tests, and affected
  documentation; schema, translation, cache/resume, CLI, OCR, and model/device behavior are
  unchanged.
