# Review — PDFTR-22

## Outcome

PDFTR-22 is implemented as an isolated, executable architecture proof rather than a production
renderer rewrite. The PoC flows reviewed schema 1.3 body occurrences through typed regions and
continuation segments, preserves exact input character ranges, carries overflow onto an added page,
emits JSON evidence, and produces selectable normal/debug PDFs.

## Evidence reviewed

- Robitzsch pages 1, 3, and 4 were source-inspected for dimensions, paragraph order/kind/geometry,
  fragment counts, repeated-element policy, translated lengths, fixed-layout states, candidate
  body regions, anchored content, images, and drawings.
- The production planner replay confirmed 40 rendered / 21 overflow and corrected the earlier
  architectural assumption: every current overflow is a footnote, while all body occurrences fit.
- The page-3 PoC placed 4 body paragraphs / 2,153 characters with one continuation, one added page,
  and zero unplaced characters.
- Reopened output exposed selectable text and every planned segment in its target body region.
- Poppler PNG review caught an initial baseline collision not detected by extraction; the planner
  now reserves one line of baseline safety, and regenerated pages have no overlap or clipping.

## Architecture review

- Flow unit: logical paragraph occurrence.
- Placement unit: typed continuation segment with exact offsets.
- Region source: explicit content/geometry/anchor evidence, never whitespace or body kind alone.
- Page policy: hybrid existing safe regions, then bounded inserted pages.
- Anchors: headers, page numbers, figures, drawings, captions, and footnotes stay outside body flow.
- Unsupported/ambiguous layouts: fail closed.
- Post-save validation: segment-local padded-rectangle presence plus exact pre-save reconstruction
  and visual inspection. Region-wide extraction is diagnostics only.

The PoC uses composition through a small measurement protocol: pure planning is deterministic and
fake-testable, while PyMuPDF-specific behavior remains in one adapter. No production CLI or
renderer coupling was introduced.

## Compatibility and invariants

- PDFTR-17 marker/pass-through handling unchanged.
- PDFTR-18 saved-output validation principle retained and extended in the proposed split-segment
  design.
- PDFTR-20 completeness remains non-negotiable; no warning-only escape was added.
- PDFTR-21 preserved foreign units/spans are used exactly as stored and never retransformed.
- Source PDF, schema/cache/resume, OCR, translation, model loading, and CUDA paths are unchanged.

## Validation summary

- Full repository gate: 257 passed, 1 skipped, coverage 88.70%.
- Focused reflow/rendering suite: 27 passed.
- Wiki lint: 13 pages, 69 links, no errors/warnings.
- Ruff and production/PoC mypy checks: passed.
- CRG rebuilt; Graphify refreshed and queried; important conclusions source-verified.
- Controlled real-artifact and visual PDF validation: passed after the overlap correction.

## Review findings

1. A follow-up regression found that region-wide substring validation could falsely accept a
   missing segment when another segment in the same region had identical text. Validation now
   requires each segment in its own padded target rectangle; a duplicate-text regression proves
   that a physically missing second segment fails closed.
2. The ticket hypothesis was refined rather than assumed: current Robitzsch overflow is a footnote
   problem, not a body-prose overflow problem.
3. Short-document repeated-element evidence misclassifies running matter as body; PDFTR-23 must not
   auto-flow by `ParagraphKind.BODY` alone.
4. Extraction success is necessary but insufficient for layout quality; visual rendering remains a
   required gate.
5. PDFTR-23 body reflow should not claim that it will make the present Robitzsch artifact
   publishable while footnote pagination remains deferred.

## Recommended PDFTR-23 scope

Production single-column body prose and one basic heading style, explicit safe regions, anchored
object preservation, ordered cross-page continuation, bounded inserted pages, typed diagnostics,
zero-unplaced completeness, selectable output, and split-segment validation. Tables, arbitrary
columns, floating figures, verse, complex math, and footnote pagination remain explicit fail-closed
follow-ups.

## ProjectWiki decision

Phase 1 decision: **keep as-is**. The Wiki consistently preserved high-level constraints and made
new gaps visible; exact claims still required canonical evidence by design. No measured evidence
supports adding semantic search, embeddings, MCP, QMD, automated ingestion, or graph generation to
the Wiki workflow.
