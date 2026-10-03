# PDFTR-38 investigation — current architecture capability boundary

## Scope and preflight

Level 2: extraction → reconstruction → translation → shared reflow → saved validation.
The supplied ticket and current source were used; no stopped experiment reports or review findings
were consulted. Initial working tree was clean on the runner-provided ticket branch. Python 3.12.10,
uv 0.5.26, installed PyMuPDF 1.28.0. No dependency changes or model downloads are proposed.

Graphify `query "reconstruct_paragraphs discover_reflow_page PyMuPdfMeasurer" --budget 1300`
identified the expected reconstruction, document, renderer and planner neighborhood; source inspection
confirmed the relevant boundaries. CRG `update --brief` initially failed to print Unicode under the
Windows cp1251 console; `PYTHONIOENCODING=utf-8 code-review-graph update --brief` succeeded.
No Context7 tool is exposed in this agent context. Library capability conclusions below come from
controlled execution with the installed dependency, not assumed browser CSS support.

## Required investigation answers

1. **Identification:** `_kind` in `reconstruction/reconstructor.py` applies `_LIST_MARKER` to source
   line text and assigns `LIST_ITEM`. This is a candidate label, not structural proof. `_kind_boundary`
   separates every list-marked fragment; it does not merge hanging continuations into that list item.
2. **Source geometry:** `TextLine`, `TextSpan`, `ParagraphFragment` retain bounding boxes and spans
   retain origins. A separately emitted marker and content span can supply both x positions.
   One combined span supplies only its whole bounding box, not the semantic-content character edge.
   A separate marker block may also be reconstructed as a separate occurrence. No per-character
   coordinates are retained in the domain model. Guessing glyph widths from a combined span is unsafe.
3. **Current indentation model:** `ReflowStyle` has left/right and first-line indents. The planner
   insets the target rectangle by left/right indent; `build_rich_text` emits one `<p>` with CSS
   `text-indent`. Only the first segment receives that indent. There is no independently placed
   structural marker slot or first-line content-edge constraint. Typography `_indent_properties`
   compares whole fragment left edges, not the content edge after a marker.
4. **Ownership:** a source-backed immutable marker/content geometry contract belongs below both
   translation and rendering, alongside reconstruction/domain evidence. It must record exact source
   marker, semantic range, confidence/provenance, and marker/content edges. A renderer-owned type
   imported by translation would invert the dependency direction.
5. **Provider input:** confidently identified semantic content only. Structural marker identity must
   never depend on model output. This requires coordinated cache/resume and glossary/foreign-span
   offsets; current `translate_paragraphs` prepares and caches the entire paragraph text.
6. **Lookalikes:** `A. Smith` currently matches the candidate list regex, while `1.5 mm` and `3.14`
   do not. Do not strip any candidate prefix merely because of this label. Require independent source
   layout/group evidence; uncertain isolated letters/numbers retain their full semantic text.
   No destructive stripping is introduced by this investigation.
7. **Shared measurement:** any future structural extension must pass one immutable representation
   through `TextMeasurer.measure`, prefix fitting, insertion, and validation. Merely prepending text
   in insertion would invalidate measurement and exact offset accounting.
8. **First/continuation geometry:** plain `<p>` can move the first marker but cannot independently
   set the content edge after it. Its content edge depends on actual marker and separator advances.
   Native `<li>` provides hanging continuation but uses renderer-owned marker geometry. Controlled
   installed-library probes showed a decimal marker with `<ol start="2">`, but custom string
   `list-style-type: "2) "` and `li::marker {content:"2)"}` did not emit `2)`. Inline span padding
   did not create a source-backed content gap. These are capability probes, not production layouts.
9. **Pagination:** semantic offsets must remain contiguous across existing `plan_flow` segments.
   Structural marker appears once on the first segment, never on continuation pages. First segments
   need room for marker AND non-empty semantic text; existing character fallback could otherwise
   produce a marker-only first segment. Continuations use the content edge, not the marker edge.
10. **Saved validation:** existing `validate_saved_segments` checks normalized semantic substring
    presence in a padded segment-local clip and applied inline styles. It does not check structural
    marker cardinality, source identity or marker/content x edges. A future extension must inspect
    actual saved marker/content geometry and marker absence on later segments, and reject clipping.
11. **Fallback cases:** isolated lookalikes; marker/content in one undifferentiated span; disconnected
    marker blocks without reliable association; unstable continuation edges; nested/multi-column
    lists; ambiguous reconstruction; marker outside safe flow region; unsupported marker glyphs.
    Existing `discover_reflow_page` excludes `LIST_ITEM` and rejects intersecting unselected text.
    Do not bypass its all/partial ambiguity protections by relabeling list items BODY.
12. **Regression surface:** `test_paragraph_reconstruction.py`, `test_translation.py`,
    `test_serialization.py`, `test_typography.py`, `test_style_reconstruction.py`,
    `test_inline_styles.py`, `test_reflow_production.py`, `test_rendering.py`. BODY/HEADING/FOOTNOTE
    style roles, exact preserved inline offsets, cache/resume, heading orphan guard and segment-local
    validation all require preservation.
13. **Production files for a future implementation:** reconstruction models/reconstructor and exports;
    paragraph translation and behavior/cache/resume revision; shared reflow models/planner/regions/
    typography/pymupdf_layout; serialization if evidence is persisted; rendering diagnostics and
    completeness accounting. No production files change in this blocker-only outcome.
14. **Smallest safe outcome now:** document the renderer capability blocker and retain existing
    fixed-layout fallback, as explicitly permitted by the ticket. Do not add marker stripping without
    the corresponding geometry/completeness support, or activate lists as ordinary paragraphs.

## Blocker decision

The present shared representation cannot encode three independent source constraints (marker edge,
first semantic edge, continuation edge) for arbitrary source-owned markers. Native list generation
supports some conventional numbering but neither the tested custom marker forms nor independent
source marker placement. Changing only text-indent, using spaces/tabs, or post-rendering marker
patches would not satisfy the ticket. Tables and inline-block workaround layouts are explicitly
forbidden. This is a boundary of the **current** representation, not proof that PyMuPDF can never
support an appropriate future architecture.

Therefore this attempt takes the ticket's explicit **document the blocker** path. Product list-marker
fidelity is NOT implemented and the ticket must not be marked product-complete. The follow-on decision
is human-owned: approve a source-owned structural extension of the shared layout representation with
an experimentally verified renderer primitive, or change the supported-layout requirements.

## Safety and adjacent contracts

No source PDF mutation, schema migration, cache invalidation, translation-quality change, model/device
change, OCR change, CLI change or dependencies. Added tests characterize existing behavior and renderer
limitations without real providers. All generated fixtures and pytest temporary output are repository
local under `temp/`. CI, local gates and exact-SHA review must be reported separately, never inferred.
Ticket already exists at `Tickets/PDFTR-38.md`; no YouTrack/attachment tool is available in this context.
