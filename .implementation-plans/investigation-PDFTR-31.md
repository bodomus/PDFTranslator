# PDFTR-31 investigation

## Scope and evidence

PDFTR-31 is a Level 2 production-rendering change. The investigation followed the repository
pre-ticket workflow, ProjectWiki search, Graphify orientation, a freshly rebuilt code-review-graph,
and source inspection of the renderer, reflow discovery, planner, PyMuPDF adapter, style
reconstruction contract, diagnostics, and production tests.

## Current behavior and root cause

- `PdfRenderer.render()` already reconstructs exactly one `ResolvedParagraphStyle` per schema-1.3
  paragraph occurrence and builds the authoritative occurrence-index map once per document.
- `_plan_reflow_document()` passes that map to BODY/HEADING discovery but not to
  `discover_footnote_page()`.
- Footnote discovery therefore creates a local `ReflowStyle` from source size, configured line
  height, and synthetic `font_size * 0.25` trailing spacing, even when authoritative reconstructed
  FOOTNOTE typography exists.
- `typography.py` already has one common resolved-style mapper behind thin BODY and HEADING role
  validators. The missing capability is a thin FOOTNOTE adapter with `heading=False`.
- The shared planner already applies first-line indent and space-before only to the true first
  segment, left/right indent and alignment to every segment, and space-after only to completion.
  Measurement, insertion, and saved-segment validation already consume the same style-bearing
  placement contract, so no alternate footnote layout path is required.
- `_render_results()` intentionally limits applied typography diagnostics to BODY/HEADING plans;
  consequently `REFLOW_FOOTNOTE` currently reports the rendered font size but suppresses line
  height, alignment, indents, spacing, color, face-request state, mixed style, and fallback count.

## Required architecture answers

1. **Where should FOOTNOTE activation occur?**
   In `discover_footnote_page()`, using the style map already created by `PdfRenderer` and passed
   through `_plan_reflow_document()`. Typography must not be reconstructed in the footnote module.
2. **What is authoritative identity?**
   Occurrence index is the lookup key. The embedded occurrence index and paragraph id validate the
   selected style; duplicate paragraph ids remain safe.
3. **How should invalid authoritative styles fail?**
   When a map is supplied, missing, index-mismatched, paragraph-id-mismatched, wrong-role, or
   nonphysical-alignment styles make footnote discovery return ineligible before planning and PDF
   mutation. There is no fallback to synthesized style in that mode.
4. **What legacy behavior remains?**
   Calls that intentionally omit the style map retain the existing synthesized local style for
   isolated tests/legacy callers.
5. **How is geometry protected?**
   Existing region/separator eligibility remains unchanged. Resolved left/right/first-line indents
   reach the planner's fail-closed `_paragraph_geometry()` checks before mutation; no clamping,
   leading-space emulation, font shrinking, or page-limit increase is needed.
6. **How is spacing protected?**
   Reconstructed spacing replaces the synthetic `font_size * 0.25` path. The planner's existing
   segment semantics preserve the one-gap invariant.
7. **How are diagnostics exposed without role leakage?**
   Gate applied typography by explicit content kind/disposition: BODY plans accept BODY/HEADING;
   FOOTNOTE plans accept only `FLOWABLE_FOOTNOTE`.
8. **What remains unchanged?**
   Translation, paragraph reconstruction, typography evidence/resolution, BODY/HEADING style
   activation, separator ownership, region discovery, continuation ordering, capacity bounds,
   exact accounting, saved validation, source immutability, and atomic publication.

## Graph and source verification

Graphify identifies `_plan_reflow_document()` as the production caller of
`discover_footnote_page()` and the renderer plus production tests as its reverse blast radius.
The freshly rebuilt code-review-graph contains 1,484 nodes and 13,239 edges. Source inspection
confirms the exact path: `PdfRenderer.render()` → `_plan_reflow_document()` →
`discover_footnote_page()` → `plan_flow()` → shared PyMuPDF HTML/CSS measurement/insertion →
`validate_saved_segments()` → `_render_results()`.

## Blast radius and validation

Expected production changes are limited to `rendering/reflow/typography.py`,
`rendering/reflow/footnotes.py`, `rendering/renderer.py`, reflow exports, and deterministic
production tests. Documentation and affected ProjectWiki pages must describe the activated
FOOTNOTE boundary. No dependency, schema, cache, model/device, OCR, CLI, or translation change is
required.

The baseline focused test command initially hit the machine's inaccessible system pytest temp
directory. Subsequent focused commands must use repository-local `temp/pytest` and disable the
global full-suite coverage threshold where appropriate. The required real Robitzsch artifact must
be located and validated without manufacturing roles.
