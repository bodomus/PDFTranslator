---
title: Paragraph style reconstruction architecture
type: architecture
status: active
created: 2026-09-23
updated: 2026-09-23
tags:
- typography
- styles
- rendering
- paragraphs
- diagnostics
sources:
- ../../../Tickets/PDFTR-28.md
- ../../../docs/style-reconstruction.md
- ../../../src/pdftranslate/typography/style_models.py
- ../../../src/pdftranslate/typography/reconstruction.py
- ../../../tests/test_style_reconstruction.py
related:
- typography-evidence.md
- reflow-layout.md
- system-overview.md
---

# Paragraph style reconstruction architecture

PDFTranslate has a pure style-policy boundary between source typography evidence and future
rendering. It derives a versioned `ResolvedStyleDocument` from `TypographyBaseline`, with one
immutable `ResolvedParagraphStyle` per authoritative occurrence. The derived contract is not
embedded in `ExtractedDocument`, cache, or resume artifacts.

Every property retains its original evidence value/confidence, resolved value, typed decision
source, fallback flag, and reason. Resolution accepts high/medium direct evidence, then a stable
same-role baseline, then a document baseline only for safe color reuse, then an explicit renderer
default. BODY, HEADING, FOOTNOTE, and OTHER size/alignment/spacing policies never borrow from each
other.

Role baselines require at least two samples and two-thirds support. Numeric properties use a median
plus property-specific tolerance so one anomaly cannot redefine a role. Missing roles remain
absent. Source font identity, conservative family grouping, generic font role, and future local
font resolution remain separate concepts.

One physical paragraph gap is represented once: space-before may resolve from evidence/baseline,
while space-after is zero with an explicit invariant decision. Mixed inline font/size/weight/
italic/color flags survive, but inline runs are not rendered yet.

The standalone inspection script can emit evidence and resolved decisions side by side with
`--resolved`; it rejects source/output aliases. The Robitzsch baseline confirms stable Garamond
family, 10.959 pt BODY size, 1.138 BODY line-height ratio, and 7.970 pt FOOTNOTE size, while leaving
the mixed BODY alignment aggregate and one-line FOOTNOTE geometry unstable. No HEADING occurrence
or baseline is fabricated.

Production rendering does not import or consume this contract. The current `ReflowStyle`, font
selection, completeness accounting, pagination, and nine-page Robitzsch behavior remain the
PDFTR-24 path until PDFTR-29 activates a tested adapter.
