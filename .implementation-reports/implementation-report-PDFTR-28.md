# Implementation Report — PDFTR-28 style model / style reconstruction

## Ticket

PDFTR-28 — Style model / style reconstruction

## Result

Implemented a production, renderer-facing paragraph-style reconstruction contract over PDFTR-27
typography evidence. The contract is role-aware, deterministic, serializable, and fully traceable,
while remaining intentionally disconnected from production rendering until PDFTR-29.

## Workflow

- Level: 2
- Branch: `codex/PDFTR-28-style-model-reconstruction`
- Base: merged `master` commit `161b941219efe484459bf7c41e7fba98efba0ba7`
- Graphify: reused for preflight, then refreshed for the new module boundary
- CRG: rebuilt before implementation and updated after implementation
- Working tree before changes: clean in the isolated worktree
- Environment: Python 3.12.10, uv 0.5.26, locked dependencies unchanged

## Scope

- Modules: `pdftranslate.typography.style_models`,
  `pdftranslate.typography.reconstruction`, evidence extractor hardening, developer inspector
- Pipeline stages: derived typography/style diagnostics only
- Dependency impact: none
- Model/device impact: none; no inference or model download
- OCR impact: none
- CLI/public contract impact: no Typer command change; developer argparse script adds `--resolved`
- PDF/output integrity impact: source/output alias protection added; reconstruction performs no PDF
  writes; production rendering is unchanged

## Investigation

### Current behavior

PDFTR-27 produced immutable per-occurrence evidence, but `ReflowStyle` was constructed separately by
body and footnote rendering paths. No document role baseline, property resolution policy, or
per-decision trace existed.

### Expected behavior

Convert evidence into stable resolved styles using reliable direct evidence, robust same-role
aggregation, a narrowly safe document fallback, and explicit renderer defaults. Preserve source
evidence, mixed inline flags, fallback reasons, and authoritative occurrence indexes.

### Root cause / implementation gap

The evidence and renderer contracts intentionally had no policy boundary between them. Review of
merged PDFTR-27 also found four input correctness/safety defects: developer output could alias the
source PDF; role regions and gaps could cross columns; and filtered missing baselines could pair
non-adjacent lines.

### Main symbols

- `StyleDecision`, `StyleDecisionSource`, `StyleBaselineValue`
- `StyleStabilityPolicy`, `RoleStyleBaseline`, `DocumentStyleBaseline`
- `FontRole`, `ResolvedParagraphStyle`, `ResolvedStyleDocument`
- `build_document_style_baseline`, `resolve_paragraph_style`, `reconstruct_styles`
- `normalize_font_family_group`, `infer_font_role`
- `scripts.typography_inspect --resolved`

### Configuration/schema

The derived resolved-style schema is `1.0`. It is not embedded in `ExtractedDocument`, cache,
workspace, or resume manifests. Default stability policy requires two samples, two-thirds support,
and medium confidence; numeric tolerance is 0.75 pt for font size, 0.08 for line-height ratio, and
2 pt for indentation/spacing.

### Expected blast radius

Typography domain models/policy, developer diagnostics, tests, README/CHANGELOG/docs, and the
typography/reflow ProjectWiki boundary. Rendering, translation, OCR, cache, and pipeline modules
remain outside the change.

## Changes

- Added strict immutable style decisions carrying resolved value, original evidence value and
  confidence, typed source, fallback status, and reason.
- Added role baselines for BODY, HEADING, FOOTNOTE, and OTHER with candidate stability/support
  metadata. A missing role stays absent.
- Added robust categorical dominance and numeric median/inlier aggregation so a single anomalous
  paragraph cannot redefine a role.
- Implemented direct high/medium → stable same-role → safe document color → explicit default
  precedence. Low/unknown evidence remains visible but is not authoritative.
- Kept font source name, conservative family group, generic role, and future local font resolution
  separate. No OS scan, font path substitution, or download occurs.
- Preserved all mixed-style flags and occurrence identity.
- Enforced the one-gap spacing invariant: `space_before` owns evidence; `space_after` resolves to
  zero with an explicit decision.
- Added versioned JSON round-trip and opt-in side-by-side developer output.
- Protected the source PDF from inspection output aliasing before extraction/write.
- Isolated evidence regions and gap measurements by column and prevented missing baseline rows
  from bridging non-adjacent lines.

## Precedence per property

| Property | Precedence |
| --- | --- |
| Role | reliable paragraph evidence → OTHER |
| Source font identity | preserve source value → unresolved |
| Family group | normalized source value → stable same-role group → unresolved |
| Generic font role | source-name inference → stable same-role role → UNKNOWN |
| Font size | paragraph → same role → 11 pt |
| Bold/italic | paragraph → same role → regular/non-italic |
| Color | paragraph → same role → stable document color → black |
| Alignment | paragraph → same role → LEFT |
| Line-height ratio | paragraph → same role → 1.2 |
| Indents | paragraph → same role → 0 pt |
| Space before | paragraph → same role → 0 pt |
| Space after | one-gap invariant → 0 pt |

## Graph and source validation

- Graphify preflight identified typography evidence, logical paragraphs, reflow discovery,
  renderer options, and typography/reflow tests as the adjacent boundary; source verified that no
  rendering import existed.
- Refreshed Graphify result: 3,492 nodes, 7,075 edges, 244 communities.
- Final Graphify `ResolvedParagraphStyle` reachability is limited to reconstruction, the developer
  inspector, validators, and dedicated tests.
- Initial CRG build: 143 files, 1,390 nodes, 12,250 edges.
- Final CRG status: 143 files, 1,393 nodes, 12,166 edges, current branch/base recorded.
- CRG diff risk: 0.55, 14 changed symbols/classes, zero affected application flows. Its private
  helper “test gap” list is conservative: alias validation and public reconstruction are directly
  tested; `_paragraph_evidence` is exercised through extraction tests; `main` and resolved console
  output were exercised on the real Robitzsch source.
- No graph/source disagreement remains. Graphify and CRG cannot prove PDF visual semantics, so
  source tests and the retained real artifact were checked separately.

## Robitzsch validation

Input SHA-256: `739163d0cb4a7ec189e069ceed3b0c719db0a00c57bc5b5465139815e0d6b3de`.

The developer workflow reconstructed all 61 occurrences and separately inspected representative
page 1, 3, and 4 BODY, FOOTNOTE, mixed-style, justified, centered, one-line, and indented examples.

| Metric | Result |
| --- | ---: |
| BODY occurrences | 26 |
| FOOTNOTE occurrences | 35 |
| HEADING baseline | absent |
| BODY family | AGaramondPro, stable |
| BODY font size | 10.959 pt, stable (22/26 inliers) |
| BODY line-height ratio | 1.138, stable (15/15 inliers) |
| FOOTNOTE font size | 7.970 pt, stable (35/35 inliers) |
| BODY mixed-style occurrences | 17 |
| FOOTNOTE mixed-style occurrences | 29 |

BODY alignment remains an intentionally unstable role aggregate because the source evidence has
comparable LEFT and JUSTIFIED groups plus centered/unknown items. Reliable individual justified or
centered values still win directly. One-line FOOTNOTE alignment/line-height stays explicit
fallback, not fabricated evidence.

The retained PDFTR-24 output was reopened read-only after the change: 9 pages and 8,907 extracted
characters. Its established result is 61 required occurrences, zero overflow, zero unplaced text,
and 9 pages. Renderer/reflow production files have no PDFTR-28 diff, and all rendering/reflow tests
pass.

## Post-change impact

- CRG updated: yes
- Graphify refreshed: yes, because two production typography modules were added
- Blast radius: derived typography domain, developer diagnostics, tests, docs only
- Unexpected dependants: none
- Compatibility concerns: none for extraction schema, cache/resume, translation, or rendering

## Validation

- Focused style/evidence tests: 50 passed
- Focused style/evidence/reflow/render/diagnostics tests: 86 passed
- Real developer script: 61 resolved occurrences; page and occurrence filtering verified
- JSON round-trip: covered by tests and real output generation
- Source/output alias protection: covered by a direct test
- ProjectWiki lint: 15 pages, 94 links, zero errors/warnings
- Ruff format: 235 files already formatted
- Ruff lint: passed
- Mypy: 95 source files, no issues
- Full `scripts/check.ps1`: 319 passed, 1 skipped, 88.64% coverage
- `git diff --check`: passed
- Real-model/CUDA/OCR validation: not applicable; reconstruction uses no model, device, or OCR
- PDF manual validation: no new PDF generated because rendering is intentionally inactive; retained
  nine-page PDF reopened successfully

## Documentation

- Added `docs/style-reconstruction.md`.
- Updated README developer commands, typography evidence documentation, CHANGELOG, ProjectWiki
  index, system/typography/reflow architecture pages, and Wiki log.

## Remaining risks

- BODY is a coarse semantic role; genuine layout substyles can make an aggregate property unstable.
  The contract exposes this rather than choosing a misleading value.
- Inline style runs, exact font resolution, justification/indent/spacing application, and visual
  fidelity belong to PDFTR-29 or later.
- The retained nine-page artifact proves the prior output is readable and unchanged; this ticket
  deliberately does not regenerate rendering from the resolved style contract.
