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
