---
title: Typography evidence architecture
type: architecture
status: active
created: 2026-09-23
updated: 2026-09-23
tags:
- typography
- extraction
- paragraphs
- diagnostics
- rendering
sources:
- ../../../Tickets/PDFTR-27.md
- ../../../docs/typography-evidence.md
- ../../../src/pdftranslate/typography/models.py
- ../../../src/pdftranslate/typography/extractor.py
- ../../../tests/test_typography.py
related:
- reflow-layout.md
- system-overview.md
---

# Typography evidence architecture

PDFTranslate derives a versioned typography baseline from retained source spans and reconstructed
logical paragraph occurrences. Occurrence index is authoritative because paragraph IDs may repeat.
The service is independent of Typer and rendering and consumes an already extracted document in one
in-memory pass; it does not reopen the PDF per paragraph.

Direct evidence covers source font identity, character-weighted dominant size, span-flag
bold/italic, packed color converted to RGB, and `ParagraphKind` role. Extraction also retains raw
font flags and span baseline origin. Only canonical six-uppercase-letter subset prefixes are
normalized; source names do not imply local availability.

Geometry inference covers conservative alignment, baseline distance and ratio, first-line versus
whole-paragraph indents, and a low-confidence observed gap before. The same physical gap is not
also stored as space after. One-line or conflicting geometry remains unknown. Every value carries a
categorical confidence, typed provenance, and explicit fallback behavior.

Mixed font name, size, weight, italic, and color are reported separately from the dominant
paragraph baseline. Inline style reproduction is deferred. Typography is not persisted inside
schema 1.3 and is not consumed by `ReflowStyle`, so translation resume/cache behavior, pagination,
and rendered appearance remain unchanged.

The Robitzsch source confirms 10.959 pt Garamond body evidence, 7.970 pt footnotes, approximately
12.472 pt body baseline spacing, first-line indents near 11 pt, and mixed italic/marker/color runs.
The four-page excerpt has no classified heading occurrence; the system preserves that fact instead
of inventing a heading level. See the canonical architecture document for algorithms,
representative occurrences, inspection commands, and limitations.
