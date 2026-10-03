# PDFTR-39 implementation plan

1. Add validated immutable source-backed list layout and optional paragraph metadata, reusable structural fragment and derived saved occurrence identity.
2. Extend existing geometry and shared measurement to use content_x for semantic text; independently measure marker in its source-owned region with LEFT alignment. Only first segment owns structural placement.
3. Reuse shared rich-text insertion and saved-local occurrence validation for semantic/structural fragments; redact source marker evidence through existing redaction loop.
4. Test valid/invalid evidence, independent semantics, first/continuation measurement, pagination ownership, alignment independence, marker fit, missing saved marker and multi-page real PyMuPDF output. Run existing BODY/inline regressions.
5. Update README, CHANGELOG, reflow Wiki/log, review and implementation report. Run required gates, inspect diff/blast radius, commit/push and write only runner-designated implementer input. Runner owns transitions; human owns merge.
