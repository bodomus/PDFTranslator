# Review — PDFTR-20

## Verdict

Ready for review. The implementation satisfies the strict completeness acceptance criteria and
converts the real Robitzsch regression from a misleading successful publication into an explicit,
diagnosable, atomic render failure.

## What was reviewed

- Every schema 1.3 logical paragraph occurrence receives an ordered terminal result.
- Duplicate paragraph IDs cannot collapse completeness evidence.
- Required overflow and missing plans fail before redaction, insertion, save, or publication.
- `PRESERVE`, `SKIP`, and `REMOVE` are explicitly accounted without false failures.
- Marker/pass-through behavior from PDFTR-17 remains covered.
- Local saved-PDF text validation from PDFTR-18 remains active after successful insertion.
- New-output and overwrite paths are atomic under failure.
- Normal errors contain concise geometry/fitting evidence without full book text.
- Debug failure creates a separate layout diagnostic only.
- README, CHANGELOG, ProjectWiki navigation, failure-mode guidance, pilot evaluation, and log agree
  with the implementation.

## Evidence

- Focused/integration suite: 66 passed.
- Full `scripts/check.ps1`: 243 passed, 1 skipped, 88.65% coverage.
- Wiki lint: 11 pages, 49 links, no errors or warnings.
- Ruff format/lint and mypy: passed.
- Real CUDA Robitzsch run: 61 translated units, 40 renderable, 21 explicit overflows; requested
  final output absent; all unresolved occurrence IDs reported; diagnostic failed-layout retained.
- Post-change CRG: 124 files, 1111 nodes, 9771 edges; blast radius matches the plan.

## Scope check

No full reflow, page creation, repagination, cross-page flow, foreign-language detection, model
change, OCR change, or dependency addition was introduced.

## Residual risk

The current renderer still cannot produce a complete Robitzsch PDF. This is the accepted Outcome B:
publication is intentionally blocked until a future reflow design can place all required content.
