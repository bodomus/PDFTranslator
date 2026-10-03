# PDFTR-38 implementer summary

This is an implementer-authored deliverable summary, **not** an independent review verdict.

## Outcome

Blocker investigation completed under the ticket's explicit fallback instruction. Production list
marker fidelity is **not implemented**. Existing production behavior remains unchanged.

The complete [investigation](../.implementation-plans/investigation-PDFTR-38.md) answers all required
questions. Saved-PDF characterization tests reproduce the current HTML representation's boundary:
conventional native markers work, custom marker string/pseudo-element CSS does not, and ordinary
paragraph/native padding does not express independent source marker/content edges.

## Evidence

- Added 13 deterministic capability/semantic-lookalike cases; no translation provider called.
- Focused regression suites: 116 passed.
- Full pytest: 500 passed, 3 skipped; coverage 89.10%.
- Wiki lint and Windows `scripts/check.ps1`: PASS (Ruff format/check, mypy, full pytest).
- Windows and Ubuntu CI: not verified; GitHub CLI is not authenticated.
- No source PDF, cache/resume, schema, model/device, OCR or production rendering changes.

See the [report](../.implementation-reports/implementation-report-PDFTR-38.md) for commands,
limitations and next-step requirements. Human approval of a verified shared structural placement
extension is needed before proceeding. This ticket should not be marked product-complete.

Remote ticket attachments/field changes were unavailable in this agent context. The independent
runner-owned exact-SHA review and all merge decisions remain outstanding.
