# PDFTR-41 implementer report

## Delivered behavior

Source-confirmed structural markers are separated before provider preprocessing and restored from
source evidence after translation/cache reuse. The required example is covered end to end:
`1. Configure project` -> provider `2. Настройте проект` -> `1. Настройте проект`.
Ordinary text and semantic `A. Smith`, `1.5 mm`, `3.14` prefixes retain their content.

The shared ListLayoutContract receives actual independent source span rectangles. Source marker
and content origins drive ordinary shared measurement, pagination and insertion, including LEFT,
CENTER and RIGHT alignment, source-backed narrow/wide gaps and first-occurrence-only markers.
The existing saved-output validator now rejects missing, duplicate and continuation markers in the
local occurrence lane and continues to reject missing semantic content. A marker elsewhere on the
page cannot establish success. No alternate renderer, planner, paginator or post-render patch exists.

## Changes and compatibility

- `reconstruction/list_items.py`: pure source evidence and semantic view. Finite, positive,
  contained, ordered, nonoverlapping source spans must share a physical line. Supported forms are
  bullets, hyphen/en dash/asterisk, numeric dot/parenthesis and ASCII letter dot/parenthesis.
  Letter-dot classification additionally requires neighboring sequential source evidence.
- `reconstruction/reconstructor.py`: joins MuPDF marker/content line fragments only when the
  same raw source block and shared physical-line rectangles prove the list; excludes repeated
  margin/header/footer/footnote roles. Original fragments and mappings remain intact.
- `translation/paragraphs.py`: semantic preprocessing before glossary, foreign spans, protected
  tokens and provider segmentation. Raw semantic cache values are restored per target occurrence,
  so distinct list markers and ordinary text can share translation work safely.
- `rendering/reflow/regions.py`: confirmed lists join the existing safe body flow; at least two
  aligned confirmed lists can establish a list-only region. Unsupported layouts keep fallback.
- `typography/extractor.py`: proved list semantic views use body typography without structural
  span contamination. Inline mapping receives semantic source/target offsets.
- `rendering/reflow/pymupdf_layout.py`: typed occurrence-local marker ownership validation.
- Added deterministic fake-provider/source and real saved-PDF regressions; updated README,
  CHANGELOG and the affected Wiki page/log.

Source PDF bytes remain unchanged in the production-renderer probe. No dependencies, schema
versions, global cache behavior revision, model loading, OCR, CLI, body/heading/footnote contracts
or agent-cycle transitions were redesigned. Translated JSON stores the canonical source marker
for the existing fixed-layout fallback; source text/spans remain immutable and JSON round-trip is
covered. Temporary files, PDFs, graphs, caches and fonts are not part of the implementation commit.

## Investigation and graph validation

See `.implementation-plans/investigation-PDFTR-41.md` and the ticket-specific implementation plan.
Graphify was queried first and refreshed after the new cross-stage helper with
`graphify update . --no-cluster`: 4860 nodes / 11247 edges. Four JSON/config sources produced zero
nodes (hooks, translation prompt, glossary example, validation corpus example); the code graph is
usable but does not provide coverage for those files. All relevant claims were source-verified.
CRG was incrementally updated before and after implementation, including new files after staging.
Exact source_list_item callers include reconstruction, translation, typography and reflow.
Two-hop radius reaches seven additional files; bounded output and unresolved call sites limit
graph completeness. Adjacent tests and the glossary benchmark caller were inspected; no unexpected
production responsibility was added. Current source and runtime tests remain authoritative.

## Validation

- Focused list/reconstruction/translation/reflow/inline/typography/style suite: 214 passed.
- Full `scripts/check.ps1`: PASS; full pytest 641 passed / 3 skipped, coverage 89.47% (80% required).
- Wiki lint: 15 pages / 125 links / zero errors or warnings; Ruff format/check: PASS;
  mypy: PASS (98 source files).
- Fake providers only; no model downloads or real inference.
- Real source extraction and production rendering cover every supported marker family.
- Saved-PDF negative probes cover missing marker/content, duplicate markers, continuation markers
  and unrelated same-page markers; pagination/geometry probes use the bundled font.

CI runs are evaluated after the implementation commit is pushed. Subsequent CI evidence belongs
in the role-owned implementer.json, avoiding a commit/hash loop. This report does not claim an
independent reviewer verdict or a merge decision.

## Limits and handoff

Combined marker/content spans, isolated letter-dot initials, ambiguous/contradictory rectangles,
cross-source-block marker joins and unsupported page layouts retain fallback behavior. Marker font
uses the shared base font; exact source marker font reproduction is outside this ticket. Semantic
initial/surname output is preserved conservatively even for source-confirmed lists.
YouTrack returned issue-not-found for PDFTR-41, so field updates and ticket/review attachment uploads
could not be performed through that connection. Ticket, plan, report and completion note are local.
The earlier unrelated user edits were explicitly restored; clarification commit `c6b114c` changed
only Tickets/PDFTR-41.md. The old stopped cycle was archived under repository temp and a new cycle
entered IMPLEMENTING through the validator. Final exact-SHA review and merge remain human-owned.
