# Implementation plan — PDFTR-34 Human-readable inline-style diagnostics summary

1. Inspect report construction (`builder.py`) and the existing HTML assertions in
   `tests/test_diagnostics.py` (done during investigation).
2. In `src/pdftranslate/diagnostics/reporting.py::_render_html`, add four rows to the summary table
   reading `report.summary.inline_style_candidate_count`, `inline_style_applied_count`,
   `inline_style_deferred_count`, and `inline_style_applied_character_count` directly:
   - `Inline style candidates`
   - `Inline styles applied`
   - `Inline styles deferred`
   - `Inline styled characters`
   Keep the existing rows and the embedded JSON unchanged. No compact status row (keep scope
   minimal; the four raw counts are the requirement).
3. Add focused regressions to `tests/test_diagnostics.py`:
   - A: non-zero totals (12/3/9/41) visible in the summary table.
   - B: zero totals render valid explicit zero rows.
   - C: privacy — a block inline decision hash/source-like text is not newly exposed in the
     summary; embedded JSON behavior unchanged.
   - D: existing rows (Pages, Blocks, Cache, Overflow, Footnotes reflowed) remain.
   - E: escaping — assert the count-only rows introduce no unescaped label path (constants); confirm
     existing escaping still applies to `status`/`run_id`.
4. Update `README.md` diagnostics section and `CHANGELOG.md` `[Unreleased]` → `Added`.
5. Add a short `knowledge/wiki/log.md` entry (presentation-only; no page rewrite) and run wiki lint.
6. Run focused tests, then the full local quality gate (`uv run pytest`,
   `wiki_lint.py`, `.\scripts\check.ps1`).
7. Commit and push the ticket branch.
8. Produce `.implementation-reports/implementation-report-PDFTR-34.md` and
   `reviews/review-PDFTR-34.md`, then record the agent-cycle handoff with the exact pushed HEAD SHA.
9. Stop for the Codex read-only review.
