# PDFTR-39 completion summary

Implementer-authored summary, not the read-only reviewer's verdict.

- Added optional immutable source-backed marker/content geometry independent of semantic text.
- Shared measurement uses content_x for first/continuation semantic lines and independently measures marker_x to content_x. Invalid evidence and unmeasurable marker regions fail closed.
- Shared pagination attaches structural placement only to the first logical segment, including when first occurrence moves to a later page.
- Shared insertion and saved validation consume typed semantic/structural occurrence identities without a second planner or renderer. Marker placement stays independent of semantic alignment.
- Kept artifacts, provider behavior, BODY typography and inline style paths compatible. No automatic list detection or final list reconstruction.
- Focused tests: 73 passed. PowerShell gate: Wiki/Ruff/mypy PASS; full tests 514 passed, 3 skipped; coverage 89.46%.
- Remote CI and exact-SHA reviewer verdict remain external pending gates. No auto-merge.

See `.implementation-reports/implementation-report-PDFTR-39.md` and
`.implementation-plans/investigation-PDFTR-39.md` for source verification, scope and limitations.
Ticket-service attachments unavailable in this session.
