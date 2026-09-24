# PDFTR-30 implementation report

## Outcome

Production single-column HEADING reflow now consumes the authoritative reconstructed typography
for each paragraph occurrence. The same resolved font size, line-height ratio, RGB color, physical
alignment, indents, and one-gap spacing drive measurement, pagination, heading-orphan protection,
continuation planning, HTML/CSS insertion, saved-PDF validation, and diagnostics.

## Implementation

- Refactored the BODY-only conversion into one common resolved-style mapper with thin BODY and
  HEADING role-validating adapters.
- Preserved occurrence index as the only style lookup key. The embedded occurrence index and
  paragraph id are validation checks; duplicate paragraph ids remain safe.
- Made missing, mismatched, and wrong-role HEADING styles render-page ineligibility conditions
  before planning or PDF mutation.
- Preserved `heading=True` and `ContentDisposition.FLOWABLE_HEADING` while applying resolved size,
  line height, color, physical alignment, first/left/right indents, and before/after spacing.
- Removed `_single_heading_style()`. Its source-size tolerance was obsolete because each occurrence
  already owns its `ReflowStyle`, and the planner, geometry checks, PyMuPDF insertion, and saved
  validation all operate per occurrence.
- Extended applied-style diagnostics from BODY to HEADING. FOOTNOTE diagnostics and styling remain
  unchanged.
- Preserved the existing font boundary: bold/italic requests and mixed-style/fallback metadata are
  reported, while `bold_applied=False` and `italic_applied=False`; no local face resolver, synthetic
  styling, or inline-run rendering was added.
- Preserved exact segment accounting, automatic-downscaling prohibition, bounded continuation
  pages, strict capacity failure, segment-local saved validation, source immutability, and atomic
  publication.

## Regression coverage

- occurrence-index HEADING mapping with duplicate paragraph ids;
- heterogeneous safe heading styles with different size/alignment;
- missing occurrence, embedded-index mismatch, paragraph-id mismatch, and wrong-role failure;
- resolved size, line height, RGB, alignment, indents, and before/after spacing;
- BODY/HEADING role isolation and unchanged FOOTNOTE behavior;
- style-aware heading-orphan movement using resolved heading height and spacing;
- first-segment, continuation, and final-segment spacing semantics;
- unsafe HEADING indent geometry failing before mutation;
- requested/unapplied bold and italic, mixed-style state, and fallback count;
- selectable Cyrillic/Latin/Greek heading text, zero unplaced characters, and strict saved-segment
  validation through the production renderer.

## Verification

- Focused reflow/rendering/diagnostics/style tests: 78 passed.
- Full `uv run pytest`: 335 passed, 1 skipped, 89.14% total coverage.
- Full `scripts/check.ps1`: ProjectWiki lint clean, Ruff format/check clean, mypy clean, and the
  same 335 passed / 1 skipped result.
- Post-change code-review-graph update: 1,480 nodes / 13,061 edges on the PDFTR-30 branch. Its
  heuristic risk score was 0.65; source review and the focused/full tests cover the changed adapter,
  discovery, planner interaction, renderer diagnostics, FOOTNOTE isolation, and saved PDF path.

## Representative PDF limitation

The cached Robitzsch artifact still has no classified HEADING and was not relabelled. The other
repository real-PDF aliases (`tests/test1.pdf` and the Sword-named fixture, identical SHA-256)
contain naturally classified HEADING evidence: 106 resolved occurrences with a 53-occurrence
HEADING baseline. However, no page in that artifact passes the existing strict production reflow
eligibility boundary when evaluated with identity translated text and the reconstructed styles.
Consequently, no real-PDF heading render is claimed. Deterministic production fixtures provide the
saved-PDF validation for this ticket, including selectable Cyrillic/Latin/Greek heading text,
strict local segment validation, no clipping/overlap failure, and zero unplaced characters.

## Remaining external gate

GitHub Windows and Ubuntu CI have not run because this working branch has not been committed or
pushed. Per the ticket, final status must not be marked `READY FOR REVIEW` until both jobs are green.
Current status: **LOCAL IMPLEMENTATION COMPLETE — CI PENDING**.
