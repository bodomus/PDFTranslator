# PDFTR-34 implementation report

## Outcome

Added a small, privacy-safe inline-style section to the human-readable HTML diagnostic report. The
summary table now exposes the four document-level totals already present on `ReportSummary`
(inline-style candidates, applied, deferred, and applied-character counts). This is a
presentation-only change: rendering, translation, the PDFTR-32 mapping contract, the diagnostics
model, and the embedded machine-readable JSON are unchanged.

## Scope

- Workflow level: 1 (isolated presentation change in one diagnostics module).
- Modules: `src/pdftranslate/diagnostics/reporting.py` (`_render_html` only).
- Pipeline stages: none executed; diagnostics presentation only.
- Dependency impact: none; no dependency or lockfile change.
- Model/device/OCR impact: none.
- CLI/public contract impact: none; command names, options, exit codes unchanged.
- PDF/output integrity impact: none; no rendering or PDF mutation path touched.
- Schema impact: none; `TranslationReport.schema_version` remains `"1.0"`.

## Investigation summary

- The four totals are populated in `src/pdftranslate/diagnostics/builder.py` (success report lines
  390-395 from the render summary; failure report leaves model defaults of `0`).
- `_render_html` builds its top table solely from `report.summary.*`, then embeds the full JSON.
- Only `tests/test_diagnostics.py::test_report_writer_never_replaces_an_existing_artifact` asserted
  on HTML content before this ticket.
- No failed-report path needs special handling: `build_failure_report` yields zero-default totals and
  the renderer reads them unconditionally.

Full answers are in `.implementation-plans/investigation-PDFTR-34.md`.

## Changes

- `src/pdftranslate/diagnostics/reporting.py`: added four `<tr>` rows to the summary table reading
  `report.summary.inline_style_candidate_count`, `inline_style_applied_count`,
  `inline_style_deferred_count`, and `inline_style_applied_character_count`. Existing rows and the
  embedded `<pre>` JSON are untouched.
- `tests/test_diagnostics.py`: added deterministic HTML tests for non-zero totals, explicit zeros,
  privacy, existing-row regression, and escaping.
- `README.md`: documented the new inline-style summary rows in "Translation diagnostics".
- `CHANGELOG.md`: added an `[Unreleased] → Added` entry.
- `knowledge/wiki/log.md`: added a 2026-09-28 entry and the new ticket source.
- `Tickets/PDFTR-34-human-readable-inline-style-diagnostics-summary.md`: saved the authoritative
  ticket text.

No compact "fidelity" row was added; the four required raw counts are the whole human-readable
addition, keeping scope minimal.

## Validation

- Focused: `uv run pytest tests/test_diagnostics.py --no-cov` → `10 passed`.
- Full suite: `uv run pytest` → `390 passed, 1 skipped`, coverage `89.10%`.
- `.\scripts\check.ps1` → passed (Wiki lint, Ruff format check, Ruff check, mypy, full pytest).
- Ruff format check: `265 files already formatted`.
- Ruff lint: `All checks passed!`.
- mypy `src`: `Success: no issues found in 97 source files`.
- ProjectWiki lint: `15` pages, `108` links, `0` errors, `0` warnings.

No model download, CUDA, OCR executable, or network access was required.

## Documentation

Updated `README.md`, `CHANGELOG.md`, and `knowledge/wiki/log.md`. No ProjectWiki page body changed:
the inline-style evidence is already documented durably in
`knowledge/wiki/architecture/style-reconstruction.md`; only the presentation surfaced in HTML.

## Two-agent pilot

- cycle initialized successfully: yes. `init` and `begin-implementation` ran on branch
  `pdftr-34-human-readable-inline-style-diagnostics-summary` (base `master`).
- implementer handoff SHA: the exact 40-character final implementation commit bound by the agent
  cycle. The validator records it as `system.current_head_sha` in
  `.agent-cycle/PDFTR-34/handoff.json` at handoff time; this report is part of that same commit.
- review round count: `0` recorded at handoff (Codex round 1 pending).
- stale-SHA protection exercised: not yet; no second implementation SHA exists. The validator
  enforces it for any resubmission.
- validator friction: one environmental blocker before initialization — the working tree contained
  the pre-existing `opencode.json` modification and `temp/.agents.zip` deletion, which fail the
  clean-tree gate. The user resolved them; no validator defect.
- manual recovery: none after initialization.

No time or token savings are claimed.

## Scope and risk

- No PDFTR-32 mapping, renderer, translation, glossary, OCR, cache, or document-domain behavior
  changed.
- No diagnostics schema bump and no duplicated/renamed JSON fields.
- No inline plaintext is newly exposed: the new rows are counts sourced only from `ReportSummary`.
- Residual risk is limited to visible HTML wording; the values are authoritative model fields.

## Final status

READY FOR REVIEW. Independent exact-SHA Codex review and the human merge decision remain pending.
