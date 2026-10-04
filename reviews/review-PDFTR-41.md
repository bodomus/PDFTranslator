# PDFTR-41 completed implementation note

This implementer-authored work summary is not the independent exact-SHA reviewer verdict.

Implemented source-backed list marker separation and canonical source marker restoration under
the clarified provider rule. Actual source rectangles populate the PDFTR-39 shared contract;
measurement, semantic inline styles, pagination, insertion and saved-output validation use that
same path. Local validation rejects missing/duplicate/continuation markers and missing content.
Ordinary text, semantic initials/decimals, artifact versions and global cache revision are preserved.

Focused regressions: 214 passed, including real source PDF extraction and production renderer
probes, all supported marker families, source marker/content positions, LEFT/CENTER/RIGHT alignment,
multi-page ownership, fake provider changes, per-marker cache restoration and semantic inline offsets.
Final full gate/CI evidence is recorded in the implementation report and implementer handoff.

Source/PDF safety, unsupported evidence fallback, unchanged dependencies and adjacent
BODY/HEADING/FOOTNOTE/inline behavior were checked. Graphify and CRG context was refreshed and
source-verified; graph coverage limitations are documented in the report.
No automatic independent review or merge is represented by this note. External YouTrack updates
and attachments are unavailable because PDFTR-41 was not found by the configured connection.

## Implementer attempt 2

Addressed R1–R4: preserve adjacent semantic initial/surname prefixes, join only source-proven
continuation lines (otherwise retain fallback), validate authoritative explicit contract tokens,
and reject unexpected extra markers in semantic target rectangles while allowing planned literals.
Added real-source and reopened-PDF regressions. Attempt-specific validation evidence is in the
implementation report and implementer input; this note still does not claim an independent verdict.

## Human-approved remaining R1 recovery

Extended initial/name ambiguity handling to surname qualifiers, lowercase particles and compound
names. Real-source probes preserve complete source/provider/translated semantic text and create no
list contract; genuine prose A./B. lists remain supported. Focused suite: 236 passed. Full
scripts/check.ps1: 663 passed / 3 skipped, coverage 89.53%; Wiki lint, Ruff and mypy passed.
The exhausted cycle's review artifacts, manifest and handoff remain unchanged. This completion note
does not create an additional automated review round or claim an independent verdict.

## Human-approved apostrophe-component follow-up

Resolved the remaining lowercase apostrophe-component R1 without a surname allowlist. Real-source
name/name and prose/name pairs retain full initials in source/provider/translated text and create
no list contracts. Geometry-backed letter-prefix joining preserves full text when an ambiguous
name invalidates neighboring list evidence; genuine prose letter lists remain supported.
Focused eight-file suite: 244 passed. Full scripts/check.ps1: 671 passed / 3 skipped,
89.54% coverage; Wiki lint, Ruff and mypy passed. All stopped-cycle artifacts retain their
original hashes. This implementer completion note is not an independent exact-SHA review verdict.
