# Implementation Report

## Ticket

PDFTR-38 — List marker fidelity, attempt 1.

**Outcome: BLOCKER DOCUMENTED; product feature NOT implemented.** The ticket explicitly permits
blocker documentation instead of workaround layers when the current architecture cannot safely
support source marker geometry. This report completes that investigation deliverable, not the
product completion criteria. Do not resolve PDFTR-38 as implemented based on local test success.

## Workflow

- Level: 2.
- Graphify: queried existing graph; source-verified candidate pipeline boundaries.
- CRG: `update --brief` and `detect-changes --brief`; Windows console encoding required
  `PYTHONIOENCODING=utf-8`. No changed production nodes or unexpected production dependants.
- Working tree before changes: clean.
- Runner owns transitions. No agent-cycle transition or system-owned coordination file was changed.
- No prior stopped list experiments, implementation reports or review findings were consulted.

## Scope

- Modules: no production changes; added `tests/test_list_layout_capabilities.py`.
- Pipeline stages investigated: extraction, paragraph reconstruction, paragraph translation,
  typography, shared reflow measurement/planning/insertion and saved-PDF validation.
- Dependencies, model/device, OCR, CLI, public schema/cache/resume: unchanged.
- PDF/output integrity: existing fixed-layout behavior and fail-closed eligibility retained.
  Capability fixtures are created only under repository-local `temp/` and are not committed.

## Investigation

See [the complete investigation](../.implementation-plans/investigation-PDFTR-38.md) and
[plan](../.implementation-plans/implementation-plan-PDFTR-38.md).

Source classification currently recognizes marker-like prefixes but does not retain authoritative
marker identity, semantic offsets and independent marker/content-edge geometry. Even `A. Smith`
is a candidate `LIST_ITEM`; no prefix stripping is safe on that label alone. List fragments do not
participate in BODY reflow. The provider currently receives the full paragraph text.

`build_rich_text` emits one paragraph with first-line text-indent. The planner owns left/right
insets and first-segment-only indentation. These can represent ordinary first-line indentation,
but do not supply a separate arbitrary source marker slot. Native HTML lists emit conventional
markers and hanging lines, but tested custom string list styles and `::marker` content do not emit
the requested marker. Inline span padding is ignored. Native list padding moves marker and content
together instead of independently changing their separation.

The smallest safe current outcome is to leave production unchanged and document this boundary,
rather than introduce forbidden spaces/tabs, tables, inline-block layouts or marker x patches.
This is not proof of an impossibility in all PyMuPDF APIs. A future shared structural representation
needs a verified placement primitive and coordinated semantic offset/completeness contracts before
translation or reflow activation.

## Changes

- Saved-PDF capability characterization: conventional bullet, decimal and letter positive controls
  each emit exactly one marker and complete semantic text; wrapping content aligns with continuation.
- Negative capability evidence: arbitrary `2)` marker via custom string CSS or `::marker` is absent;
  inline padding does not change geometry; narrow/wide native padding moves both edges together;
  current shared paragraph output aligns continuation with marker, not semantic content.
- Semantic lookalike extraction/reconstruction retains complete `A. Smith`, `1.5 mm`, and `3.14`.
- README, CHANGELOG and affected reflow Wiki page state that production list fidelity is unsupported.
- Investigation and plan answer the required architectural questions before tracked tests/docs changed.

These tests are **not** assertions that translated list identity, overflow, pagination, multi-page
continuation or structural saved validation have been implemented. Existing reflow regression tests
exercise ordinary BODY/HEADING/FOOTNOTE pagination, typography, inline styles and local validation.

## Graph and source validation

- Graphify query: `reconstruct_paragraphs discover_reflow_page PyMuPdfMeasurer`, budget 1300.
- Source validation: reconstruction regex/kind boundaries, `LogicalParagraph` and `TextSpan` contracts,
  paragraph translation cache/preparation, typography indent extraction, region candidate filtering,
  planner geometry/prefix accounting, shared HTML builder and saved segment validator.
- CRG reports zero changed production functions/classes; no production impact is claimed from graphs.
- Graphify refresh: not required because no production module/schema/orchestration changes.
- Context7: unavailable in this context; installed-library execution used for capability evidence.
- No external provider, model, CUDA, OCR, or user-document translation was executed.

## Validation

- Initial new-test run exposed test fixture mistakes (wrong reconstruction option and assumed wrap
  token); corrected to the actual API and emitted physical continuation line before final validation.
- Focused capability/reconstruction/reflow/inline/typography/style suites: **116 passed**.
  Command: `uv run pytest tests/test_list_layout_capabilities.py tests/test_paragraph_reconstruction.py
  tests/test_reflow_production.py tests/test_inline_styles.py tests/test_typography.py
  tests/test_style_reconstruction.py --no-cov --basetemp=temp/pytest-focused-pdftr38`.
- Full pytest: **500 passed, 3 skipped**, coverage **89.10%**, threshold 80% passed.
  Command: `uv run pytest --basetemp=temp/pytest-full-pdftr38`.
- Wiki lint: **PASS**, 15 pages, 117 links, zero errors/warnings.
- `scripts/check.ps1`: **PASS** via Windows PowerShell, including Wiki lint, Ruff format/check,
  mypy (97 source files), and full tests. Temporary environment variables and pytest base temp point
  to repository-local `temp/`.
- Logs: ignored `temp/pdftr38-full-tests.log`, `temp/pdftr38-check.log`.
- `git diff --check`: **PASS** before commit.
- Windows CI / Ubuntu CI: **NOT VERIFIED**. `gh auth status` reports no authenticated GitHub host.
  Local Windows gate is not a substitute for either CI job. Exact-SHA review is runner-owned and
  has not occurred in this context.

## Documentation and ticket workflow

Updated README, CHANGELOG, `knowledge/wiki/architecture/reflow-layout.md`, Wiki log, investigation,
plan, this report and `reviews/review-PDFTR-38.md` (implementer summary, not reviewer verdict).
The ticket already exists at `Tickets/PDFTR-38.md`. No YouTrack/attachment tools are exposed;
remote ticket fields and attachments could not be updated.

## Remaining risks / human decision

- All product list-fidelity completion criteria remain unmet: source-owned marker translation,
  independent source indentation, list pagination and marker-specific saved validation.
- Do not treat native-list positive controls as production support or turn candidate labels into
  confidence evidence. Do not claim semantic/provider marker safety from these extraction-only tests.
- An approved shared structural-layout extension is needed to proceed. There is no second list
  renderer/planner or speculative workaround in this attempt.
- CI and read-only exact-SHA review remain outstanding; human final review and merge remain required.
