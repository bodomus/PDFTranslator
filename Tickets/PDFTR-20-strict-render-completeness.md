# PDFTR-20 — No translated content loss / strict paragraph render completeness

## Goal

Eliminate silent loss of translated document content during rendering.

After PDFTR-18, the pipeline can complete end-to-end and publish a valid translated PDF, but real
validation of the Robitzsch sample showed that substantial translated content can still disappear
from the final PDF when one or more logical paragraphs cannot be rendered into their available
layout area.

The renderer must never treat a document as successfully rendered if a source logical paragraph
that requires translation is absent, truncated, or silently skipped in the final PDF.

This ticket is about **content completeness**, not visual polish.

Do not implement full page reflow in this ticket.

---

## Branch

Create a new branch from current `master`:

```text
codex/PDFTR-20-strict-render-completeness
```

---

## ProjectWiki pilot

This is the **first real post-PDFTR-19 ProjectWiki pilot ticket**.

Before implementation:

1. read `knowledge/wiki/index.md`;
2. search ProjectWiki for:
   - rendering;
   - paragraph reconstruction;
   - output validation;
   - overflow;
   - translation completeness;
3. open canonical source/reports only where Wiki knowledge is missing or must be verified;
4. record the concrete ProjectWiki pilot observations in the implementation report.

Do not bypass the existing Graphify/CRG workflow.

---

## Real-world evidence

Use the existing Robitzsch real PDF regression:

```powershell
uv run pdftranslate ".\tests\Robitzsch Jan Maximilian - Epicurean Justice. Nature, Agreement, and Virtue - 2024_50.pdf" `
  --device cuda `
  --output .\test10textpages.ru.pdf
```

The current pipeline can complete:

```text
1/6 Inspect
2/6 OCR
3/6 Extract
4/6 Translate
5/6 Render
6/6 Validate
```

However, manual comparison of source and output showed large missing sections.

Examples observed during manual review:

- page 1: significant prose after the first translated paragraph is absent;
- page 3: large areas that contain body text in the source become empty/blank after rendering;
- page 4: only part of the source body survives in the output;
- footnote/body coverage is substantially lower than the source document.

This means current output validation proves that **some inserted render units are valid**, but does
not yet prove that **all required translated logical paragraphs made it into the final PDF**.

---

## Scope

Implement strict document-level render completeness for schema 1.3 logical paragraphs.

A successful render must account for every logical paragraph according to its policy.

For each paragraph, the renderer must end in an explicit state such as:

```text
rendered
preserved
removed-by-policy
overflow
failed
```

No paragraph may silently disappear.

---

## Required investigation

Follow `.codex/PRE_TICKET_WORKFLOW.md`.

Inspect at minimum:

- paragraph reconstruction model;
- schema 1.3 logical paragraphs and fragment mappings;
- repeated-element policies;
- paragraph-to-render-block conversion;
- `_plan_page`;
- `_fit`;
- expansion behavior;
- overflow behavior;
- `_insert_page`;
- post-save validation;
- `RenderResult` / `BlockRenderResult`;
- pipeline final validation;
- debug-layout diagnostics;
- serialization/reporting if relevant.

Trace at least several paragraphs from the Robitzsch document that are visibly absent in the final
PDF.

For each investigated paragraph determine:

```text
paragraph id
page
policy
source text
translated text
source bbox
planned bbox
font size attempts
expanded?
overflow?
inserted?
post-save validated?
final render state
```

Do not assume overflow is the only cause until verified.

---

## Core requirement — strict accounting

Introduce one authoritative completeness check for all schema 1.3 logical paragraphs.

Every paragraph that is expected to appear in the output must be accounted for.

At minimum:

### TRANSLATE

Must result in successfully rendered translated text.

If it cannot be rendered completely:

```text
render MUST NOT be considered successful
```

### PRESERVE

Must remain present as original content according to current repeated-element policy.

### SKIP / REMOVE

Must be explicitly excluded by policy and must not be counted as missing translated content.

### Marker/pass-through paragraphs

Must follow the existing PDFTR-17 behavior and remain correctly accounted for.

---

## Overflow policy

Current behavior may report overflow as a warning while continuing publication.

For required translated paragraphs, silent publication with unresolved overflow is no longer
acceptable.

If translated text cannot fit after the currently supported bounded fitting/expansion strategy:

```text
fail the render with an actionable error
```

Example:

```text
render completeness failed:
3 required paragraph(s) could not be rendered completely

p0003-b0004 page=3 state=overflow
p0003-b0005 page=3 state=overflow
p0004-b0002 page=4 state=overflow
```

Do not silently:

- drop text;
- clip text;
- publish partial text;
- replace it with source English;
- shrink below the configured minimum font size;
- move content onto another page without an explicit future reflow design.

Full reflow is deliberately deferred.

---

## Render completeness model

Prefer a small explicit model rather than inferring completeness from warning strings.

For example, extend render result state with a stable status enum or equivalent:

```text
rendered
preserved
removed
overflow
failed
```

Exact naming may follow current project conventions.

The model should make it possible to answer programmatically:

```text
How many logical paragraphs were expected?
How many were rendered?
How many were intentionally preserved/removed?
How many failed or overflowed?
Which IDs?
```

Do not create a second parallel document model if existing render-result structures can be extended
cleanly.

---

## Validation

Add a final completeness invariant before atomic publication.

Conceptually:

```text
required logical paragraphs
==
successfully rendered required paragraphs
+
explicitly policy-excluded paragraphs
```

If the invariant is false, publication must fail.

The existing post-save Cyrillic validation from PDFTR-18 must remain.

PDFTR-20 complements it:

```text
PDFTR-18:
"Did this expected inserted text survive the saved PDF?"

PDFTR-20:
"Did every required logical paragraph reach a valid terminal render state?"
```

Do not weaken PDFTR-18 validation.

---

## Diagnostics

On failure provide concise actionable diagnostics.

At minimum:

```text
paragraph id
page number
render state
source bbox
final bbox
font size / min font size
expanded flag
translated character count
```

Do not dump entire book text in normal logs.

When debug/report mode is enabled, include full per-paragraph completeness evidence in the existing
diagnostic/report system where appropriate.

---

## Tests

Add deterministic tests that prove content cannot silently disappear.

At minimum:

### 1. All paragraphs render

Several logical paragraphs fit normally.

Expected:

```text
render succeeds
all required IDs accounted for
```

### 2. One required paragraph overflows

Create a paragraph that cannot fit even at minimum font size and cannot safely expand.

Expected:

```text
render fails
paragraph ID is reported
final PDF is not published
```

### 3. Partial document failure

Several paragraphs render but one fails.

Expected:

```text
entire output fails publication
```

No "mostly successful" final PDF.

### 4. Policy-excluded content

`PRESERVE`, `SKIP`, and `REMOVE` behavior must not produce false completeness failures.

### 5. Marker/pass-through regression

Preserve PDFTR-17 marker-only paragraph behavior.

### 6. Post-save validation regression

Preserve PDFTR-18 local render-unit validation.

### 7. Atomic output

If completeness fails:

```text
requested final output path must not contain a newly published partial PDF
```

Existing output protection/overwrite semantics must remain correct.

---

## Real regression validation

After implementation run the Robitzsch PDF again:

```powershell
uv run pdftranslate ".\tests\Robitzsch Jan Maximilian - Epicurean Justice. Nature, Agreement, and Virtue - 2024_50.pdf" `
  --device cuda `
  --output .\test10textpages.ru.pdf
```

Two acceptable outcomes exist for PDFTR-20:

### Outcome A — renderer can fit everything

Then:

```text
all 6 stages complete
all required logical paragraphs are accounted for
final PDF is published
```

Perform manual source/output comparison and confirm no body paragraph silently vanished.

### Outcome B — current fixed-layout renderer cannot fit everything

This is also an acceptable and likely result.

Then:

```text
render fails explicitly
final PDF is NOT published
exact overflowing/missing paragraph IDs are reported
```

This is preferable to publishing a misleading incomplete translation.

Do NOT force success by implementing full reflow inside PDFTR-20.

The evidence from Outcome B will be used to design the later reflow ticket.

---

## Manual completeness check

For the real PDF, compare source and output/diagnostics page by page.

At minimum review:

```text
page 1
page 3
page 4
```

Record:

```text
source logical paragraph count
required translated paragraph count
rendered count
policy-excluded count
overflow/failed count
```

If final publication succeeds, verify visually that the previously missing body regions are no longer
missing.

---

## Do not include in this ticket

Do NOT implement:

- Latin/Greek language preservation policy;
- automatic foreign-language detection;
- translation quality/model replacement;
- full page reflow;
- cross-page paragraph flow;
- repagination;
- creation of new pages;
- typography redesign;
- footnote relayout engine;
- semantic layout reconstruction.

Those belong to subsequent tickets.

---

## Expected follow-up roadmap

After PDFTR-20:

```text
PDFTR-21 — Preserve Latin/Greek/foreign-language quotations and terminology
```

Then a larger dedicated reflow/layout ticket based on the evidence collected by PDFTR-20.

Do not implement those features preemptively.

---

## ProjectWiki update

After implementation:

1. update only affected Wiki pages;
2. add a rendering/content-completeness constraint or failure-mode page if the evidence warrants it;
3. record the new strict invariant;
4. append a concise Wiki log entry;
5. update `knowledge/wiki/testing/pilot-evaluation.md` with this first real pilot result;
6. run:

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

The implementation report must include a `ProjectWiki pilot` section with:

```text
Wiki pages consulted before implementation
canonical/raw sources additionally opened
missing/stale Wiki knowledge discovered
Wiki pages updated
whether Wiki avoided rediscovery of known facts
whether review exposed a Wiki gap
```

Do not claim token/time savings unless actually measured.

---

## Quality gates

Run focused tests first, then:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src
.\scripts\check.ps1
```

Run the real CUDA regression only after deterministic tests pass.

Update CRG after implementation and refresh Graphify only if architecture boundaries changed,
according to the repository workflow.

---

## Acceptance criteria

PDFTR-20 is complete when:

- every schema 1.3 logical paragraph reaches an explicit render terminal state;
- no required translated paragraph can silently disappear;
- unresolved required overflow prevents final publication;
- partial render success cannot publish a misleading final PDF;
- policy-excluded paragraphs do not create false failures;
- PDFTR-17 marker behavior remains intact;
- PDFTR-18 post-save validation remains intact;
- actionable paragraph-level diagnostics exist;
- deterministic completeness tests pass;
- full repository quality gate passes;
- the real Robitzsch run either:
  - publishes a demonstrably complete PDF, or
  - fails explicitly with exact unresolved paragraph IDs and no partial final publication;
- ProjectWiki pilot evidence for this ticket is recorded.
