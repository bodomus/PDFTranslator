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

## Implementer attempt 2 — R1–R4

Baseline: independently reviewed `d44410d56bafa74a8e9863d1ad1f11003cc0264d`. The validator
already entered IMPLEMENTING for this attempt; no reviewer action or manual state edit is performed.

- R1: name-shaped letter-dot prefixes remain ambiguous despite sequential aligned neighbors.
  Physically split initials/surnames are joined only as source text, without structural ownership.
  A real A. Smith / B. Jones PDF now retains both complete provider inputs and creates no list
  contract. Existing real-source genuine letter-list regressions continue to pass.
- R2: same-block, same-column, content-aligned BODY continuation lines with compatible styles,
  bounded spans and close vertical geometry join the confirmed item before translation. Unresolved
  same-block tails and nearby indented neighboring paragraphs prevent partial-item reflow, including
  the different-block tail produced by MuPDF for additional indentation. Real multiline-source
  tests verify complete semantic provider input, continuation origin 70, marker origin 40,
  one occurrence of each source marker, and fallback for unproved ownership.
- R3: saved structural-lane tokens are compared directly to the authoritative contract, without
  automatic-detector vocabulary restrictions. Real saved PDFs cover + and § success, missing and
  duplicate rejection, alongside the existing 1. contract.
- R4: contract-marker counts throughout each occurrence's local placement must equal planned
  semantic token counts plus first structural ownership. Extra copies in first-placement and
  continuation semantic rectangles fail. Planned A. Smith, 1.5 mm, 3.14 and literal contract-marker
  tokens continue to pass.

Changes stay within source evidence/reconstruction, reflow eligibility and the existing shared saved
validator, plus focused tests and required documentation. Translation/cache code, schema versions,
dependencies, planner, measurer and insertion remain unchanged. No second rendering or validation
path was introduced. Graphify context was reused (no module-boundary change); incremental CRG
updated the affected symbols and dependants without errors. Both added source helpers have only
the expected reconstruction caller; existing translation, typography and rendering callers remain.

Attempt 2 validation: focused eight-file suite 220 passed; full scripts/check.ps1 passed with
647 passed / 3 skipped and 89.50% coverage. Wiki lint: 15 pages / 125 links, zero errors/warnings;
Ruff format/check and mypy (98 source files) passed. PDFs and caches stay under repository temp;
fake providers only, no model downloads. CI for the new commit is subsequent handoff evidence.

Conservative limits remain: ambiguous short capitalized letter-dot labels can resemble names and
retain fallback. Cross-block continuation ownership is not inferred; nearby uncertain tails retain
fallback. Existing combined-span, unsupported geometry/layout and marker-font limits still apply.
External YouTrack availability is unchanged. This is an implementer report, not a reviewer verdict.
