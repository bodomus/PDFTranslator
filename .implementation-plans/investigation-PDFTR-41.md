# PDFTR-41 investigation

## Baseline and evidence

- Workflow level 2: source reconstruction, translation boundary and shared reflow adapter.
- Branch: `pdftr-41-list-marker-fidelity`; implementation phase starts after the separate
  clarification commit `c6b114c`. Unrelated `.gitignore` and tracked archive edits were restored
  by explicit user instruction. The inactive stopped cycle was preserved under `temp/`.
- Read PRE_TICKET_WORKFLOW, Wiki index, reflow-layout, all three repository intelligence skills,
  Python design patterns, and implementer/handoff contracts.
- Graphify query: `list contract paragraph reflow translation`, BFS, 1700-token budget. Candidates
  include ListLayoutContract, LogicalParagraph, translate_paragraphs, discover_reflow_page,
  plan_flow and PyMuPdfMeasurer; graph conclusions were verified below in current source.
- CRG was stale at PDFTR-40; incremental update completed successfully. Exact-symbol callers:
  translate_document -> translate_paragraphs; PdfRenderer._plan_reflow_document ->
  discover_reflow_page. Test call edges include unresolved bare names and are not runtime proof.
- Context7 PyMuPDF documentation confirms `get_text('dict')` spans retain real source rectangles;
  `get_text('words')` returns word rectangles and local clipping for saved-output validation.

## Findings and smallest implementation

1. Earliest sufficient existing representation is ParagraphFragment.spans (TextSpan.bbox), retained
   from the source PDF by the backend, through JSON and reconstruction. MuPDF also exposes marker
   and content as separate line fragments in the same source block; only independently bounded,
   horizontally separated rectangles on the same physical line authorize joining those fragments.
   Header/footnote/repeated-element roles do not enter this joining rule. No glyph width calculation
   is necessary when a marker has its own span.
2. Regex-only ParagraphKind.LIST_ITEM currently partitions paragraphs but does not prove structural
   marker geometry. This classification alone must never authorize prefix removal.
3. A new pure reconstruction helper will require an exact supported marker token in a separate
   first span, nonempty semantic spans on the same line, finite positive contained rectangles,
   ordered/nonoverlapping geometry, consistent text and immutable source mappings. Ambiguous
   paragraphs and unsupported source evidence retain existing behavior.
4. Supported forms: bullet, hyphen, en dash, asterisk, decimal `n.` / `n)` and ASCII letter
   `a)` / `A.`. Letter-dot prefixes require a neighboring sequential letter marker with matching
   source origins, to avoid interpreting a person's initial as structure. Decimal lookalikes do
   not match. A combined marker/content span deliberately falls back: there is no independent
   marker rectangle in the current schema. No schema revision is justified for this scope.
5. Source text stays immutable. A semantic paragraph view removes only proven marker spans,
   preserves content spans and rebases inline style source offsets before map_inline_styles.
6. Translation preprocessing uses semantic text before glossary, foreign-language preparation,
   protected tokens, segmentation and provider calls. Cache keys use semantic text, cache values
   remain provider semantic output; markers are restored per source occurrence after reuse.
   Ordinary cache entries, behavior revision and resumable/artifact schema versions remain valid.
7. The user-authorized exception replaces a provider marker only for proven source list items.
   Decimal prefixes and semantic initial/surname prefixes remain untouched. Structural metadata
   owns the canonical marker; serialized translated_text retains marker + semantic text so the
   existing fixed-layout fallback remains compatible.
8. Reflow discovery includes proven list items alongside existing body/heading candidates, creates
   ListLayoutContract from source boxes, and maps inline styles on the semantic view. Typography
   uses body style for proven lists without changing roles for unconfirmed lists or ordinary text.
9. PDFTR-39 already owns content_x/marker_x measurement, rich-text insertion, marker font region,
   structural_fragment first-occurrence ownership and pagination. No alternate layout path needed.
10. Existing saved validation checks local presence but not marker multiplicity or forbidden
    continuation markers. Extend that same validator using typed occurrence identity and exact
    marker tokens in local structural lanes; never use page-global marker presence as proof.
11. BODY/HEADING/FOOTNOTE and inline regressions are covered by test_reflow_production,
    test_typography, test_style_reconstruction, test_inline_styles and the existing list contract
    tests. Add fake-provider and real saved-PDF list evidence tests, including negative probes.

## Boundaries and risks

Production scope: pure reconstruction list helper and the same-block source-line join,
paragraph translation, body reflow discovery,
typography evidence adapter and the shared saved-output validator. Source PDF remains immutable;
no model loading, OCR, CLI, dependencies, cache schema, document schema or backend changes.
Provider output remains cached independently of each list marker. Unsupported layouts and marker
fit fail through the existing fallback/error contracts. No graph rebuild is needed unless the
new helper's cross-stage imports materially change architecture; refresh affected graph context.
Unit/integration fixtures use fake providers, bundled fonts and repository-local temp directories.
Run focused list/translation/reflow/style tests, Wiki lint and scripts/check.ps1 (full pytest,
coverage, Ruff, mypy). CI and exact-SHA reviewer outcome require separate evidence after push.
YouTrack lookup returned issue-not-found, so ticket field updates/attachments are unavailable.

## Attempt 2: reviewer findings R1–R4

Reviewed baseline: `d44410d56bafa74a8e9863d1ad1f11003cc0264d`; the validator has already
entered IMPLEMENTING. The working tree is clean. Reused the existing Graphify/CRG context
built at that SHA and source-verified all four reproduction paths during review.

- R1: aligned sequential initials do not prove a list. Name-shaped letter-dot content must
  remain ambiguous. A physically split initial/surname can still be joined as source text,
  without authorizing structural separation or a ListLayoutContract.
- R2: LIST_BOUNDARY prevents source continuation lines from joining the item. Join only
  same-block, same-column, close, content-aligned, compatible BODY fragments after confirmed
  first-line evidence. Unresolved same-block fragments must prevent partial-item reflow.
- R3: explicit ListLayoutContract accepts single-token markers beyond automatic detection.
  Saved validation must compare structural-lane tokens to the authoritative contract.
- R4: also count the contract token throughout the local placement rectangle, allowing exactly
  the planned semantic occurrences plus the first structural occurrence. This catches extra
  markers in semantic rectangles without rejecting legitimate planned prefixes.

No schema, cache revision, translation preprocessing, dependency, renderer or planner change is
needed. Add real extracted/saved-PDF regressions and retain the existing focused suites.
