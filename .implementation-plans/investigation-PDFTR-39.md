# PDFTR-39 investigation (complete before implementation)

Level 2; baseline inspected: expected task branch, no pre-existing working-tree changes.
Ticket already saved as `Tickets/PDFTR-39.md`; ticket-service attachment tools are unavailable.

## Source-verified answers
1. `FlowParagraph` owns source geometry and `ReflowStyle`; `PlacementSegment` owns target geometry.
2. `_paragraph_geometry` combines region bounds with left/right indents; style first-line indent applies only on the first segment. Continuations use the same left edge without first-line indent.
3. An optional immutable source-backed metadata type on `FlowParagraph` is cleaner than booleans or embedding marker text. Source marker/content rectangles supply explicit physical x origins.
4. `plan_flow` passes `_paragraph_geometry` width to `TextMeasurer`; prefix fitting uses the same width/style. PyMuPDF measures `build_rich_text` in that box.
5. `insert_reflow_segments` obtains target rectangle and first-line indent from the segment; it uses the same HTML/CSS builder with scale disabled.
6. The shared forward-only planner splits exact text offsets, advances ordered regions, and increments continuation index. No alternate paginator is needed.
7. Occurrence index, paragraph id, source page, continuation index, text offsets and target rectangle survive to `validate_saved_segments`.
8. Minimum contract: marker text and mandatory source marker/content rectangles, with `marker_x`/`content_x` derived directly from their x0 coordinates; optional paragraph field. A structural placement fragment is independent of semantic text.
9. Only the segment whose text_start and continuation_index are zero receives a structural fragment; subsequent segments retain semantic geometry, not copies of marker ownership.
10. Derive output occurrences from segments: kind plus logical occurrence index and continuation index identifies semantic versus structural marker. Plan metadata remains available while validating the reopened saved PDF.
11. Existing typography discovery/reconstruction, role mappings, inline mapping/clipping and rich-text construction stay intact. Only explicit contracts suppress first-line indent so both semantic first and continuation lines use content_x; semantic alignment stays intact, structural alignment is LEFT.
12. `tests/test_reflow_production.py` covers BODY/HEADING/FOOTNOTE typography, orphan decisions, indents, continuation, saved validation and production rendering. `tests/test_inline_styles.py` covers exact runs, prefix clipping, styles and regressions. Full rendering/serialization tests protect old artifacts.
13. Production changes confined to reflow `models.py`, `planner.py`, `pymupdf_layout.py`; tests and architecture documentation accompany them.
14. Future detection can supply verified source evidence, separately translate semantic text and request structural placement without a second planner/renderer. Future validation can count marker identities and continuation ownership.
15. Out of scope: detection, translated-prefix handling, provider changes, product list reconstruction, marker font/style fidelity, duplicate-marker product validation and artifact schema changes.

## Safety and compatibility
Invalid/missing/non-finite/unsupported evidence rejects construction; out-of-region or unmeasurable marker geometry rejects planning before mutation. No guessing or clamping. Marker fit uses the same text measurer independently over marker_x to content_x; no font advance placement heuristic. Marker source rectangle joins existing redaction evidence. Layout metadata is internal/optional: schema 1.3, translation revision, caches, providers, models, OCR and CLI unchanged. Source files never modified; saved output reopened.

## Intelligence and external documentation
ProjectWiki search `reflow` and architecture page read, implementation claims verified in production source and tests. `graphify --help` and scoped query `FlowParagraph plan_flow insert_reflow_segments validate_saved_segments` identified shared production and historical PoC symbols; source inspection disambiguated them. CRG `update --brief` refreshed data but reporting hit cp1251 UnicodeEncodeError; retry with PYTHONIOENCODING=utf-8 planned. Existing graphs are advisory, not freshness proof. Respect `.graphifyignore`; refresh after structural model changes. Context7 tools are not exposed in this session; no dependency/API change is planned (existing PyMuPDF APIs reused and exercised by saved-PDF tests).

## Gate
Focused list-contract, production reflow and inline tests; full pytest; Wiki lint; PowerShell check script. Remote Windows/Ubuntu CI and exact-SHA review are external gates, not claims of this implementation process.
