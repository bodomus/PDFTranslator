# PDFTR-34 — Human-readable inline-style diagnostics summary

## Goal

Expose the inline-style diagnostics introduced by PDFTR-32 in the human-readable HTML diagnostic
report.

The machine-readable JSON report already contains block-level and document-level inline-style
evidence, but the current HTML summary does not surface it.

PDFTR-34 must add a small, readable inline-style summary without changing rendering behavior,
translation behavior, document schema, or the PDFTR-32 mapping contract.

This ticket is the **first real two-agent workflow pilot after PDFTR-33**.

---

# Two-agent execution requirement

PDFTR-34 must use:

```text
implementer: DeepSeek
reviewer: Codex
```

through the product-neutral PDFTR-33 agent-cycle contract.

Roles remain:

```text
implementer
reviewer
system
```

Concrete agent names are orchestration metadata only.

Required high-level sequence:

```text
DeepSeek implements
    ↓
tests / commit / push
    ↓
handoff exact HEAD SHA
    ↓
Codex read-only review of that SHA
    ↓
PASS
or
CHANGES_REQUIRED
    ↓
DeepSeek fixes / commits / pushes new SHA
    ↓
Codex second review if required
    ↓
human final review
    ↓
human merge decision
```

No parallel execution.

No third automated review round.

---

# Agent-cycle bootstrap for PDFTR-34

Before implementation begins, initialize the cycle on the PDFTR-34 task branch.

Use the actual branch chosen for the ticket.

Expected flow:

```powershell
uv run python scripts/agent_cycle.py init PDFTR-34
uv run python scripts/agent_cycle.py begin-implementation PDFTR-34
```

After implementation is committed and pushed, the implementer must create its role-specific handoff
input and run:

```powershell
uv run python scripts/agent_cycle.py handoff PDFTR-34 --file <IMPLEMENTER-INPUT>
```

The implementation agent must then stop.

Codex review must begin only for the exact pushed 40-character SHA:

```powershell
uv run python scripts/agent_cycle.py begin-review PDFTR-34 --sha <FULL-SHA>
```

Codex must remain read-only.

Its result must be recorded with:

```powershell
uv run python scripts/agent_cycle.py record-review PDFTR-34 --file <REVIEWER-INPUT>
```

Follow:

```text
AGENTS.md
.codex/PRE_TICKET_WORKFLOW.md
.agents/skills/two-agent-ticket-workflow/SKILL.md
```

The agent-cycle state under:

```text
.agent-cycle/PDFTR-34/
```

is local runtime state and must not be committed.

---

# Current behavior

The diagnostic model already contains document-level inline-style totals:

```text
inline_style_candidate_count
inline_style_applied_count
inline_style_deferred_count
inline_style_applied_character_count
```

Block diagnostics also contain:

```text
inline_style_candidate_count
inline_style_applied_count
inline_style_deferred_count
inline_style_applied_character_count
inline_style_decisions
```

PDFTR-32 also records privacy-safe per-run information such as:

```text
status
text_sha256
mapping_kind
confidence
defer_reason
font_size_points
color_rgb
bold_requested
bold_applied
italic_requested
italic_applied
source_font_name
source_font_family_group
```

The current HTML report summary in:

```text
src/pdftranslate/diagnostics/reporting.py
```

shows high-level rows such as:

```text
Pages
Blocks
Cache
Overflow
Footnotes reflowed
Footnote segments
Footnote continuation pages
Footnote unplaced text
```

but does not expose the inline-style summary.

The complete JSON is embedded below as machine-readable details, but a user should not have to inspect
raw JSON to answer:

```text
Did this document contain mixed inline-style candidates?
How many were applied?
How many were deferred?
How many translated characters received a safe inline override?
```

---

# Required change

Extend the human-readable HTML summary with a small inline-style section.

At minimum expose:

```text
Inline style candidates
Inline styles applied
Inline styles deferred
Inline styled characters
```

Example:

```text
Inline style candidates    12
Inline styles applied       3
Inline styles deferred      9
Inline styled characters   41
```

Exact wording may be adjusted for readability, but the meaning must remain stable.

Use the already-authoritative values from:

```python
report.summary.inline_style_candidate_count
report.summary.inline_style_applied_count
report.summary.inline_style_deferred_count
report.summary.inline_style_applied_character_count
```

Do not recompute these totals independently in the HTML renderer.

---

# Optional compact status

If it improves readability without expanding scope, add one compact status row such as:

```text
Inline style fidelity    3 applied / 9 deferred
```

But the four raw counts above must remain visible.

Do not add percentages.

Do not invent a quality score.

---

# Privacy requirement

The HTML summary must remain privacy-safe.

Do not display:

```text
source run plaintext
translated run plaintext
full source paragraph text
full translated paragraph text
```

unless the existing report was explicitly generated with the repository's existing include-text
behavior.

PDFTR-34 must not alter that policy.

The summary needs counts only.

The machine-readable block decisions already use hashes/offsets for inline evidence and must remain
unchanged.

---

# Zero-count behavior

A report with no inline-style candidates must still render valid HTML.

Preferred behavior:

```text
Inline style candidates    0
Inline styles applied      0
Inline styles deferred     0
Inline styled characters   0
```

Do not hide the section merely because the counts are zero.

This makes absence explicit and keeps report structure deterministic.

---

# Failed/incomplete reports

Investigate whether the same HTML renderer is used for non-success report objects.

Do not assume all reports contain render output.

The summary must safely display zero/default counts when rendering did not produce inline-style
evidence.

Do not introduce special rendering-side behavior just for this ticket.

---

# No PDFTR-32 behavior changes

PDFTR-34 must not change:

```text
inline-style source candidate reconstruction
translated-text mapping
ambiguity rules
repeated-token handling
font-size application
RGB-color application
run clipping/rebasing
measurement
pagination
insertion
saved-PDF validation
bold/italic application policy
font-family resolution
```

This ticket is presentation-only for existing diagnostic evidence.

---

# No diagnostics schema bump

Do not change `TranslationReport` schema version merely to expose already-existing fields in HTML.

Do not add duplicate summary fields.

Do not rename existing JSON fields.

If investigation proves a model change is genuinely necessary, stop and document why before
broadening scope.

Expected result: no diagnostics model change is necessary.

---

# Expected files

Likely:

```text
src/pdftranslate/diagnostics/reporting.py
tests/test_diagnostics.py
or the existing diagnostic-report test module
README.md
CHANGELOG.md
possibly one affected ProjectWiki page/log entry if durable workflow/architecture knowledge changes
```

Avoid touching unrelated renderer, translation, OCR, cache, or document-domain files.

If only `reporting.py`, tests, and changelog/docs are required, prefer that smaller scope.

---

# Tests

Add deterministic HTML-report tests.

Required cases:

## A. Non-zero inline-style totals

Build a report with:

```text
candidate_count = 12
applied_count = 3
deferred_count = 9
applied_character_count = 41
```

Assert the HTML visibly contains all four values with their labels.

Do not validate only by checking raw embedded JSON.

The test must prove these values are part of the human-readable summary/table.

## B. Zero totals

Build a report with all four values equal to zero.

Assert the HTML renders successfully and exposes zero values.

## C. Privacy

Use a block-level inline decision with a known SHA/hash and, if applicable, source-like test text.

Assert the new human-readable summary does not expose inline plaintext.

Do not weaken the existing machine-readable details behavior.

## D. Existing summary regression

Ensure existing rows remain present:

```text
Pages
Blocks
Cache
Overflow
Footnotes reflowed
```

PDFTR-34 must not replace or remove existing summary information.

## E. Escaping

If any new label or value path can contain non-constant text, verify normal HTML escaping.

For the expected count-only implementation, no new untrusted text should be necessary.

---

# Investigation

Before implementation, create:

```text
.implementation-plans/investigation-PDFTR-34.md
```

Answer briefly:

1. Where are the four document-level inline-style totals currently populated?
2. Are they already correct for success reports?
3. Does the HTML renderer currently read only `report.summary` for its top table?
4. Which existing tests cover `_render_html()` / `write_report()`?
5. Can this ticket remain isolated to diagnostic presentation?
6. Is a diagnostics schema/version change unnecessary?
7. What is the smallest test fixture that proves the new rows are human-visible rather than only
   present in embedded JSON?
8. Does any failed-report path require special handling?
9. Which documentation needs updating?
10. What is the exact expected blast radius?

Do not implement before source verification.

---

# Implementation plan

Create:

```text
.implementation-plans/implementation-plan-PDFTR-34.md
```

Keep it short.

Expected implementation steps:

```text
1. inspect report construction and HTML tests
2. add four summary rows
3. add focused regressions
4. update minimal docs/changelog
5. run focused tests
6. run full quality gate
7. commit and push
8. produce agent-cycle handoff
9. stop for Codex review
```

---

# Implementer handoff requirements

DeepSeek must not hand off until:

```text
working tree clean
implementation committed
commit pushed
focused tests pass
full required local gate pass
implementation report exists
```

Create:

```text
.implementation-reports/implementation-report-PDFTR-34.md
reviews/review-PDFTR-34.md
```

The normal `reviews/review-PDFTR-34.md` is implementation readiness documentation, not the
agent-cycle reviewer artifact.

The authoritative Codex review result belongs to the local `.agent-cycle` workflow.

The implementer handoff must name the exact pushed HEAD SHA.

After handoff:

```text
STOP
```

Do not continue editing while Codex review is active.

---

# Codex reviewer requirements

Codex must review the exact SHA supplied through the agent cycle.

Codex is read-only.

Review at minimum:

```text
ticket acceptance criteria
diff against base
reporting.py change
tests
privacy behavior
scope containment
docs/changelog
CI/local validation evidence
```

Codex must return one of:

```text
PASS
CHANGES_REQUIRED
BLOCKED
```

If `CHANGES_REQUIRED`, every finding must be concrete and machine-readable per the PDFTR-33
reviewer contract.

Codex must not edit repository project files.

---

# Quality gate

Focused diagnostic-report tests first.

Then:

```powershell
uv run pytest
uv run python scripts/project_wiki/wiki_lint.py
.\scripts\check.ps1
```

GitHub CI must pass on:

```text
windows-latest
ubuntu-latest
```

No model download, CUDA, OCR executable, or network access may be required.

---

# Acceptance criteria

PDFTR-34 is complete when:

- human-readable HTML exposes inline-style candidate count;
- HTML exposes applied run count;
- HTML exposes deferred run count;
- HTML exposes applied-character count;
- values come directly from `ReportSummary`;
- zero-count reports remain explicit and valid;
- no inline plaintext is newly exposed;
- existing report rows remain intact;
- embedded machine-readable JSON remains intact;
- no PDFTR-32 mapping/render behavior changes;
- no document schema changes;
- no diagnostics schema bump unless independently justified;
- focused tests pass;
- full local quality gate passes;
- Windows CI passes;
- Ubuntu CI passes;
- DeepSeek implementation was handed off through `.agent-cycle/PDFTR-34`;
- Codex reviewed an exact SHA read-only;
- at most two Codex review rounds occur;
- final merge remains a human decision.

---

# Non-goals

Do not implement:

- new inline-style mapping rules;
- source/target alignment;
- bold/italic rendering;
- font-family resolver;
- new PDF rendering behavior;
- new report format;
- charts;
- percentages or quality scoring;
- per-run human-readable tables;
- report filtering UI;
- JavaScript;
- external dependencies;
- orchestrator automation;
- agent process launching;
- automatic merge.

---

# Pilot objective

In addition to the product change, PDFTR-34 is intended to validate the PDFTR-33 workflow on a real
ticket.

The implementation report must include a short section:

```text
## Two-agent pilot
```

recording:

```text
cycle initialized successfully
implementer handoff SHA
review round count
whether stale-SHA protection was exercised
whether any validator friction was encountered
whether any manual recovery was required
```

Do not claim time/token savings unless measured.

The product acceptance criteria remain authoritative; workflow observations are secondary evidence.
