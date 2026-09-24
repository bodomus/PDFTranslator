# PDFTR-30 investigation

## Scope and evidence

PDFTR-30 is a Level 2 rendering change. The investigation followed the repository pre-ticket
workflow, ProjectWiki, Graphify, and a freshly rebuilt code-review-graph. Graph conclusions were
verified against the production renderer, reflow region discovery, planner, PyMuPDF HTML/CSS
adapter, typography reconstruction contracts, diagnostics, and deterministic production tests.

## Current behavior and root cause

- `PdfRenderer.render()` already reconstructs one `ResolvedParagraphStyle` per schema-1.3
  paragraph occurrence and passes an occurrence-index map to production reflow discovery.
- `discover_reflow_page()` consumes that map only for BODY. HEADING still synthesizes font size,
  spacing, alignment, and color from local defaults/source spans.
- `body_reflow_style()` contains the complete resolved-style conversion, but it rejects every
  non-BODY role and has no shared role-aware mapping layer.
- Planner measurement, heading-orphan protection, continuation splitting, PyMuPDF insertion, and
  saved-segment validation already consume the compact `ReflowStyle`/`PlacementSegment` contract.
  Once a resolved HEADING style reaches that contract, these stages need no alternate layout path.
- Render diagnostics deliberately expose applied typography only for FLOWABLE_BODY. This suppresses
  the same fields for HEADING even though both dispositions share the production BODY layout plan.

## Required architecture answers

1. **Where should HEADING activation occur?**
   In `discover_reflow_page()`, at the same occurrence-index boundary as BODY. Typography remains
   reconstructed once per document by `PdfRenderer`; no schema, cache, or resume change is needed.
2. **How is identity validated?**
   Occurrence index remains the only lookup key. The resolved value must repeat that index and match
   the paragraph id; paragraph id is validation only and duplicate ids remain safe.
3. **How should the adapter be structured?**
   A private common resolved-style conversion owns alignment, normalized RGB, geometry, spacing,
   mixed-style/fallback state, and requested/applied face state. Thin BODY and HEADING adapters
   validate their expected roles and differ only in the `heading` flag.
4. **How does a bad HEADING style fail?**
   Missing/wrong occurrence, paragraph-id mismatch, wrong role, or unusable resolved geometry makes
   page discovery return ineligible before planning or PDF mutation. Planner geometry errors remain
   hard fail-closed errors if a validly mapped style escapes or exhausts the region.
5. **Do planner or PyMuPDF contracts need a new path?**
   No. Both measurement and insertion already share `_segment_html()`/`_segment_css()`, disable
   downscaling, preserve exact offsets, and carry indent/spacing/style diagnostics on every segment.
6. **Does heading orphan protection remain correct?**
   Yes. `_would_orphan_heading()` receives the actual heading measurement and subtracts the actual
   heading `space_after`, then measures the following BODY with its own style and first-line
   geometry. Activating resolved HEADING values feeds the existing style-aware path directly.
7. **What happens on continuation?**
   The planner already applies first-line indent and space-before only when `text_offset == 0`,
   preserves left/right indent and alignment on every segment, and emits space-after only on the
   completing segment. This contract is role-independent and therefore applies to HEADING.
8. **What happens to BODY and FOOTNOTE?**
   BODY continues through its named adapter backed by the same common conversion. FOOTNOTE
   discovery and diagnostics remain outside the resolved-style adapter.

## `_single_heading_style()` decision

The legacy gate compares source-derived heading font sizes and rejects a page when their spread is
greater than one point. Current source shows no remaining safety dependency on that uniformity:

- every heading becomes a separate `FlowParagraph` with its own immutable `ReflowStyle`;
- planning measures each occurrence independently;
- orphan protection uses the true current heading measurement;
- geometry validation is per occurrence and fails before mutation;
- insertion reconstructs the exact segment style and refuses automatic scaling;
- saved-PDF validation is segment-local and occurrence-indexed.

Consequently, the gate is obsolete rather than a layout-safety check. It will be removed. Safe
heterogeneous headings will be covered by deterministic per-occurrence tests; missing, mismatched,
wrong-role, and unsafe styles will remain fail-closed.

## Blast radius and validation

Expected code changes are limited to the reflow typography adapter, region discovery, renderer
diagnostic gating, and production reflow tests. Adjacent contracts are `ResolvedParagraphStyle`,
`ReflowStyle`, `FlowParagraph`, `PlacementSegment`, `BlockRenderResult`, and `BlockDiagnostic`.
Translation, reconstruction, evidence extraction, font discovery, FOOTNOTE flow, continuation-page
allocation, exact accounting, saved-PDF validation, and atomic publication are unchanged.

The repository contains real PDFs, including the cached Robitzsch baseline and a book artifact.
Robitzsch has no classified HEADING and must not be relabelled. A real artifact may be used only if
inspection finds a naturally classified confident HEADING; otherwise the report will document the
limitation and rely on deterministic production fixtures.
