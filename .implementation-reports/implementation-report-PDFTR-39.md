# Implementation Report — PDFTR-39

## Workflow
- Level 2; baseline tree had no unrelated changes; expected task branch inspected.
- Investigation and plan completed before code changes. Ticket already tracked as `Tickets/PDFTR-39.md`.
- Runner override followed: no cycle transitions or coordination state edits; only designated implementer input prepared after commit/push.
- Graphify scoped query, AST refresh (`graphify update . --no-cluster`) and affected-node query used; CRG incremental update used with UTF-8 reporting after an initial cp1251 reporting failure.

## Scope and implementation
- Production files: reflow `models.py`, `planner.py`, `pymupdf_layout.py` only.
- Immutable optional `ListLayoutContract` stores mandatory source marker/content rectangles; `marker_x` and `content_x` derive directly from evidence. Invalid/missing/non-finite, overlapping and unsupported single-line evidence fails closed.
- Semantic paragraph text and inline runs remain independent of marker text. Source contract owns first and continuation content edge; semantic alignment/right indent remain ordinary shared layout inputs.
- Shared planner independently measures the marker region via the same `TextMeasurer`, rejecting multiline/unfittable markers and out-of-region geometry before PDF mutation. Only first logical segment carries a structural fragment. No marker state on continuation fragments.
- Shared insertion iterates typed output occurrences using the same HTML/CSS builder and disabled scaling. Marker alignment is always LEFT; semantic alignment does not move marker_x.
- `ReflowBoxOrigin.SOURCE_OWNED` removes PyMuPDF's implicit HTML body margin for explicit source origins. This is an exact-origin mode, not padding/spacing geometry or post-render compensation. Legacy defaults preserve existing HTML and geometry. New style fields are trailing defaults, preserving positional construction compatibility.
- Shared redaction includes marker source evidence. Saved-PDF validation iterates semantic and structural occurrence metadata with deterministic `(occurrence_index, kind, continuation_index)` identities, paragraph id, target page/rectangle. Missing structural text rejects saved output through the same validator.

## Compatibility and safety
No artifact schema, translation behavior revision, provider, cache, resume, glossary, source extraction, typography reconstruction or inline mapping changes. No dependencies added; Python 3.12/uv unchanged. No model downloads, provider calls, CUDA or OCR needed. No source PDF writes. Internal evidence is explicitly constructed; production automatic detection remains disabled as required. Ordinary paragraphs keep legacy defaults and unchanged rich-text representation.

## Source and graph validation
Graph orientation identified shared planner/renderer and historical PoC boundaries; source inspection disambiguated them. Renderer callers remain `PdfRenderer.render` -> `plan_flow`/`insert_reflow_segments`/`validate_saved_segments`. New metadata enters through normal `FlowParagraph` construction (synthetic tests), not a separate planner/renderer. CRG refreshed successfully with PYTHONIOENCODING=utf-8; its reported 24 test gaps are approximate name-based associations, contradicted by executable contract tests. Graphify affected-query identifies contract constructors/tests; current source and tests remain authoritative. No unexpected dependency or stage expansion. Context7 and ticket-service tools are unavailable; existing PyMuPDF APIs were reused and source-owned HTML origin behavior verified against saved PDFs.

## Validation
- Focused: `uv run pytest tests/test_list_layout_contract.py tests/test_reflow_production.py tests/test_inline_styles.py --no-cov --basetemp=temp/pytest-pdftr39-focused`: **73 passed**.
- Full direct pytest before two additional regressions: **512 passed, 3 skipped**, coverage **89.43%**.
- Final `scripts/check.ps1` (PowerShell, repository-local pytest basetemp via PYTEST_ADDOPTS): **PASS**. Wiki lint zero errors/warnings; Ruff format/check PASS; mypy PASS (97 source files); final full pytest **514 passed, 3 skipped**, branch coverage **89.46%** (80% gate).
- Synthetic real PyMuPDF multi-page fixtures exercise shared continuation-page creation, pagination, insertion, reopen validation, missing-marker rejection and LEFT/CENTER/RIGHT independence. Recording measurer proves independent widths, semantic first-line and continuation edges, and deferred first-occurrence ownership. Ordinary BODY and inline regressions remain green.
- `git diff --check`: PASS. Temporary PDFs/logs/tests remain under ignored `temp/`.
- Remote Windows/Ubuntu CI: not verified here; `gh auth status` reports no logged-in hosts. Exact-SHA review is runner/reviewer-owned and pending; no review verdict or merge claim is made.

## Documentation
Updated README, CHANGELOG, affected reflow Wiki page and Wiki log; investigation and ticket-specific implementation plan stored under `.implementation-plans/`. Completion summary stored under `reviews/review-PDFTR-39.md` (not an authoritative reviewer verdict). Ticket attachment/update tools unavailable.

## Remaining scope boundaries
No broad detection, provider-prefix stripping, translated marker heuristics, marker font fidelity or product list reconstruction. Duplicate/repeated-continuation marker product checks remain future work; deterministic occurrence identity now supports them. This proves the shared infrastructure primitive, not end-user list fidelity. Remote CI and immutable-SHA review remain external completion gates; human owns final merge.
