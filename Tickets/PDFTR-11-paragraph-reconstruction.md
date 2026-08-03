**# PDFTR-11 — Paragraph reconstruction and reading order**

**## Summary**

Reconstruct logical paragraphs from fragmented PDF lines before translation while preserving layout semantics.

**## Dependencies**

Requires completion of PDFTR-1 through PDFTR-10 unless this ticket explicitly refers to findings that can be gathered in parallel.

**## Required workflow**

Treat this as a Level 2 task under \`.codex/PRE_TICKET_WORKFLOW.md\`.

Before implementation:

1\. inspect the current repository, Git state, \`AGENTS.md\`, workflow instructions, tests, CLI, schemas and relevant pipeline stages;

2\. run confirmed Graphify and CRG preflight when available;

3\. validate graph findings in Python source;

4\. create \`investigation.md\` and \`implementation-plan.md\`;

5\. preserve unrelated user changes;

6\. implement the smallest coherent solution.

**## Goal**

Improve translation quality by translating coherent paragraphs instead of arbitrary line fragments and retain a reversible mapping to source blocks for rendering.

**## Scope and requirements**

Introduce explicit typed concepts for raw spans/lines, logical paragraphs, fragments and source-block mapping.

Use conservative deterministic signals: page, column, vertical gap, alignment, indentation, font/style, line height, punctuation, lowercase continuation, trailing hyphen, list marker, heading traits, width, page boundary and repeated-header/footer classification.

Handle ordinary wrapped paragraphs, soft hyphenation, headings, bullets, numbering, captions, two columns, footnotes and strong-evidence cross-page continuation.

Never merge columns by default, headings into body text, or separate list items. Do not blindly remove trailing hyphens; preserve legitimate compounds, dash punctuation, CLI options and identifiers.

Retain original block IDs and define one deterministic rendering strategy for one paragraph mapped to multiple source rectangles. Avoid duplicate translated paragraphs.

Expose typed configuration for tolerances and modes rather than scattered constants. Integrate reconstruction metrics and ambiguous decisions into PDFTR-10 reports.

**## Tests and validation**

Generated fixtures must cover split paragraph, separate paragraphs, heading/body, bullets, numbering, soft and real hyphens, CLI option, two columns, caption, footnote, page continuation, ambiguity and reversible mapping. Add benchmark before/after cases.

Normal unit tests and CI must not download translation models, require CUDA, or require OCR system tools. Use generated fixtures, fakes and mocks. Real-model, GPU, OCR and real-PDF tests must be explicit opt-in checks.

**## Acceptance criteria**

\- [ ] Logical paragraphs are deterministic.

\- [ ] Original mapping is preserved.

\- [ ] Columns, headings and lists remain separate in fixtures.

\- [ ] Soft hyphens are handled conservatively.

\- [ ] Legitimate hyphens/options survive.

\- [ ] Rendering does not duplicate text.

\- [ ] Benchmark improves or shows no unexplained regression.

\- [ ] Diagnostics show merge decisions.

\- [ ] All checks pass.

**## Non-goals**

No full semantic understanding, arbitrary table reconstruction, ML layout model, GUI editor, or promise of perfect support for every PDF.

**## Documentation**

Update the applicable files:

\- \`README.md\`;

\- \`CHANGELOG.md\`;

\- CLI \`--help\`;

\- configuration/schema documentation;

\- troubleshooting or Windows instructions where relevant.

**## Required completion report**

Provide:

1\. repository state before changes;

2\. workflow level and Graphify/CRG status;

3\. investigation findings and root cause or capability gap;

4\. files and symbols changed;

5\. commands actually executed;

6\. focused and full test results;

7\. Ruff, mypy and script results;

8\. real-model, CUDA, OCR and real-PDF validation status;

9\. remaining risks and deferred work.
