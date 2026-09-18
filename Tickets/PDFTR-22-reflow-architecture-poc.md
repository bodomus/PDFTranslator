# PDFTR-22 — Reflow architecture + proof of concept for body text

## Goal

Design and prove a new rendering architecture that can place translated body text as flowing content instead of forcing every translation back into its original fixed bounding box.

PDFTR-20 established a strict fail-closed invariant: no required translated logical paragraph may silently disappear. The Robitzsch regression then exposed the structural limitation of the current renderer: 61 required logical paragraph occurrences, 40 rendered successfully, 21 overflowed and correctly blocked publication. PDFTR-21 fixed Latin/Greek preservation without weakening that boundary.

The next problem is architectural. The current model is essentially:

```text
source logical paragraph
        ↓
original paragraph bbox
        ↓
shrink font / optionally expand
        ↓
insert translated text into roughly the same region
```

That is insufficient for translated book prose because Russian often requires substantially more vertical space.

PDFTR-22 must investigate, design, and prove a **flow-based body-text layout architecture**.

This ticket is **architecture + proof of concept**, not yet the full production reflow implementation.

It must end with:
- a concrete architecture;
- typed implementation boundaries;
- a small executable PoC;
- real evidence from the Robitzsch document;
- a concrete PDFTR-23 production scope.

---

## Branch

Create from current `master`:

```text
codex/PDFTR-22-reflow-architecture-poc
```

---

## ProjectWiki pilot

This is the **third real post-PDFTR-19 ProjectWiki pilot ticket**.

Before implementation:
1. read `knowledge/wiki/index.md`;
2. search for rendering completeness, foreign-language preservation, paragraph reconstruction, rendering, layout, overflow, and atomic publication;
3. inspect canonical code/reports where Wiki knowledge is incomplete or must be source-verified;
4. record concrete pilot observations.

After PDFTR-22, update the pilot evaluation and make the first evidence-based Phase 1 decision:

```text
keep as-is
adjust
expand
abandon
```

Do not add embeddings, QMD, MCP, semantic search, or automated ingestion merely because the three-ticket pilot is complete.

---

## Current evidence

Use the Robitzsch regression:

```powershell
uv run pdftranslate ".\tests\Robitzsch Jan Maximilian - Epicurean Justice. Nature, Agreement, and Virtue - 2024_50.pdf" `
  --device cuda `
  --output .\test10textpages.ru.pdf
```

Expected current behavior:

```text
translation completes
Latin/Greek preservation is correct
render planning finds 21 required overflows
render fails closed
final PDF is not published
```

This behavior is correct and must not be weakened.

---

# Primary question

Determine how PDFTranslator should render translated **body prose** when translated text no longer fits the original paragraph rectangles.

Target direction:

```text
source page
    ↓
identify stable non-flow content
    ↓
identify body-flow region(s)
    ↓
collect ordered logical body paragraphs
    ↓
layout sequentially top-to-bottom
    ↓
continue overflow into next region/page
    ↓
preserve anchored content according to explicit policy
```

This is a hypothesis to validate, not a predetermined implementation.

---

# Required investigation

Follow `.codex/PRE_TICKET_WORKFLOW.md`.

Inspect at minimum:
- schema 1.3 `LogicalParagraph`;
- paragraph kinds and fragment mappings;
- repeated-element classifications;
- source page geometry;
- reconstruction ordering;
- `_render_units_by_page`;
- `_plan_page`;
- `safe_expanded_bbox`;
- `_fit`;
- redaction behavior;
- `_insert_page`;
- render completeness results;
- diagnostics;
- images and vector drawings;
- footnote/header/page-number behavior;
- debug-layout support;
- atomic publication boundaries.

Analyze Robitzsch pages:

```text
page 1
page 3
page 4
```

For each page record:
- page dimensions;
- logical paragraphs in order;
- paragraph kind;
- source bbox;
- source fragment count;
- repeated-element policy;
- translated character count;
- current fixed-layout render state;
- images/drawings intersecting candidate body area;
- candidate flow regions;
- anchored/non-flow content.

Do not infer body regions from whitespace alone.

---

# Content classification

Define explicit categories:

```text
body prose
section/chapter headings
block quotations
verse / poetry
footnotes
running headers
page numbers
watermarks
captions
tables
figures / images
unknown or ambiguous blocks
```

For each classify as:

```text
flowable now
anchored now
deferred
unsupported / fail closed
```

The PoC does not need to solve every category, but the architecture must not silently treat everything as ordinary body prose.

---

# Body-flow region model

Design an explicit representation, for example:

```text
FlowRegion
page_number
rect
column_index
order
```

Exact names may differ.

The architecture should support future multiple regions/columns, while the PoC may deliberately support only:

```text
single-column book page
one rectangular body region
no tables
no floating figures in flow area
```

Unsupported cases must be detected explicitly.

---

# Reflow planner

Design a planner that consumes ordered flowable logical paragraphs and produces typed placement evidence without mutating the PDF.

Conceptually:

```text
FlowParagraph
    ↓
measure
    ↓
place into remaining region
    ↓
if insufficient space:
    continue in next region/page
```

Planning evidence should contain:

```text
paragraph occurrence
source page
target page
target rect
continuation index
font size
measured height / line count
state
```

Do not encode authoritative planning state only in warning strings.

---

# Continuation semantics

A logical paragraph may span several placement segments.

The plan must preserve:
- paragraph identity;
- deterministic reading order;
- exact translated text;
- no duplication;
- no dropped prefix/suffix;
- diagnostic reconstructability.

Do not assume one paragraph must remain on one page.

---

# Page strategy

Compare and recommend one production direction:

### Option A — existing pages only
Reuse existing page body regions and fail if total capacity is insufficient.

### Option B — create additional pages
Insert/append pages when translated content exceeds source capacity.

### Option C — hybrid
Reuse source pages first, then create pages under explicit rules.

Compare at minimum:
- source pagination;
- headers/footers;
- figures;
- citations;
- footnotes;
- fidelity to book pagination;
- selectable text;
- implementation complexity;
- user expectations.

PDFTR-22 must recommend a concrete approach for PDFTR-23.

---

# Source-content preservation

Explicitly define handling for:

```text
body source text to redact
anchored text to preserve or separately replace
images
vector drawings
backgrounds
page numbers
headers/footers
```

Do not rasterize full pages by default.
Do not flatten text into images.
Selectable/searchable text is mandatory.

---

# Typography boundary

Do not solve typography fidelity fully here, but keep the design extensible for:
- font family;
- size;
- bold/italic;
- paragraph spacing;
- first-line indent;
- alignment;
- line height;
- heading/quotation/footnote styles.

One body style is acceptable in the PoC.

---

# Proof of concept

Implement a small isolated executable PoC, preferably under:

```text
scripts/reflow_poc/
```

or another clearly non-production location consistent with the repository.

Do **not** wire it into the normal pipeline unless investigation proves that is necessary and safe.

The PoC must:
1. load an existing schema 1.3 translated artifact or generate it via existing code;
2. select one controlled Robitzsch page or page range;
3. identify one body-flow region;
4. consume ordered body paragraphs;
5. place translated paragraphs sequentially top-to-bottom;
6. continue overflow to a second region/page if configured;
7. produce a PDF or diagnostic PDF with selectable text;
8. emit a machine-readable layout plan.

Preferred demonstration page:

```text
page 3
```

because previous manual comparison showed major body-text loss there.

The PoC must prove:

```text
all selected source body paragraphs are represented
no selected translated paragraph disappears
text is selectable
reading order is preserved
overflow moves forward rather than being dropped
```

Preferred stronger demonstration:

```text
page 3 body prose
        ↓
fills page 3
        ↓
remaining text continues onto page 4 or an added PoC page
```

---

# Measurement

Report:

```text
input logical paragraph count
input translated character count
planned paragraph count
planned continuation count
output paragraph count
output extracted character count
unplaced text count
new pages created, if any
```

Critical invariant:

```text
unplaced required translated text = 0
```

for controlled PoC input.

Reopen PoC output with PyMuPDF and verify:
- valid PDF;
- expected page count;
- selectable text;
- expected translated substrings;
- no selected body paragraph omitted.

Visual inspection is required, but extraction is the machine-verifiable baseline.

---

# Debug visualization

Where practical, provide optional debug output showing:
- flow-region boundaries;
- paragraph placement boxes;
- continuation segments;
- paragraph IDs / occurrence indices;
- overflow direction.

Keep debug output separate from user-facing PDF output.

---

# Deterministic tests

If reusable planner/PoC Python modules are introduced, add focused tests:

### 1. Sequential placement
Three paragraphs fit in one region.

Expected:
```text
same page
correct order
no overlap
no loss
```

### 2. Region overflow
The third paragraph does not fit.

Expected:
```text
continues to next region/page
no paragraph dropped
```

### 3. Long single paragraph
One paragraph spans multiple continuation segments.

Expected:
```text
all translated content accounted for exactly once
```

### 4. Non-flow content
Header/page number/anchored content is not accidentally injected into body flow.

### 5. Unsupported layout
Fail clearly rather than silently produce a malformed plan.

### 6. Selectable output
PoC PDF reopens and expected text can be extracted.

Normal tests must not require CUDA or model downloads.

---

# Previous-ticket invariants

### PDFTR-17
Marker/pass-through handling remains unchanged.

### PDFTR-18
Saved-PDF validation remains conceptually required. Future reflow may adapt locality checks for continuation segments, but must not disable validation.

### PDFTR-20
Strict render completeness is non-negotiable. Reflow exists to convert overflow into valid placement, not back into warnings.

### PDFTR-21
Foreign-language preserved units/spans remain exact. Reflow must never retranslate or normalize them.

---

# Architecture document

Create a durable design document, preferably:

```text
docs/reflow-architecture.md
```

It must document:
- problem;
- fixed-layout limitation;
- goals/non-goals;
- terminology;
- content classification;
- flow-region model;
- planner model;
- continuation model;
- page strategy;
- source-content preservation;
- diagnostics;
- validation;
- failure behavior;
- PoC findings;
- recommended PDFTR-23 scope;
- deferred problems.

---

# Questions that must be answered

At completion, explicitly answer:

1. What is the unit of flow: paragraph, line, span, or continuation segment?
2. How are source body regions identified?
3. How are headings distinguished from body flow?
4. How are footnotes handled in the first production implementation?
5. How are images/drawings kept out of text flow?
6. Can content flow across source page boundaries?
7. When should the renderer create a new page?
8. How is paragraph identity preserved across continuations?
9. How should post-save validation work for split paragraphs?
10. How do diagnostics map source paragraph → target continuation segments?
11. What layouts are explicitly unsupported by PDFTR-23?
12. What happens when a page cannot be safely classified?

No unresolved `TBD` for these core questions unless the report explains why a decision genuinely cannot yet be made.

---

# Do not include

Do NOT implement the full production reflow renderer.

Do NOT attempt to solve:
- arbitrary multi-column magazines;
- tables;
- sidebars;
- floating figures;
- complex mathematical layout;
- full typography fidelity;
- automatic font matching;
- complete footnote pagination;
- bibliography-specific layout;
- OCR redesign;
- translation-model changes;
- GUI;
- cloud layout services.

---

# Expected PDFTR-23

Finish PDFTR-22 with a concrete proposed scope for:

```text
PDFTR-23 — Production body-text reflow for single-column book pages
```

Expected direction:

```text
single-column text-heavy book pages
body prose
basic headings
preserve images/backgrounds
cross-page continuation
strict completeness
selectable translated text
```

The final PDFTR-23 scope must come from PDFTR-22 evidence, not assumptions.

---

# ProjectWiki update

After implementation:
1. update only affected Wiki pages;
2. add a durable reflow/layout architecture page;
3. cross-link render-completeness;
4. document unsupported/deferred layouts;
5. append a concise Wiki log entry;
6. update `knowledge/wiki/testing/pilot-evaluation.md`;
7. make the first Phase 1 decision: `keep as-is`, `adjust`, `expand`, or `abandon`;
8. run:

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

The implementation report must record:
- Wiki pages consulted;
- canonical/raw sources additionally opened;
- missing/stale Wiki knowledge;
- Wiki pages updated;
- whether Wiki avoided rediscovery;
- whether review exposed a Wiki gap;
- final Phase 1 decision.

Do not claim token/time savings unless measured.

---

# Quality gates

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src
.\scripts\check.ps1
```

Run focused PoC/tests first.

If a safe translated Robitzsch workspace already exists, reuse it. Do not rerun NLLB/CUDA unnecessarily just to test layout architecture.

Update CRG after implementation.
Refresh Graphify only if a meaningful module boundary changes.

---

# Required artifacts

Create:

```text
.implementation-plans/investigation-PDFTR-22.md
.implementation-plans/implementation-plan-PDFTR-22.md
.implementation-reports/implementation-report-PDFTR-22.md
reviews/review-PDFTR-22.md
docs/reflow-architecture.md
```

Update:

```text
CHANGELOG.md
affected ProjectWiki pages
```

README only if a developer/user-visible command is introduced.

---

# Acceptance criteria

PDFTR-22 is complete when:

- the fixed-layout limitation is documented with real evidence;
- Robitzsch pages 1, 3, and 4 are structurally analyzed;
- flowable vs anchored/deferred content is explicitly defined;
- a typed body-flow region model is designed;
- a typed paragraph/continuation layout plan is designed;
- page-boundary/page-creation strategy is recommended;
- source-content preservation strategy is documented;
- a small executable reflow PoC exists;
- the PoC demonstrates at least one previously failing Robitzsch page;
- selected body paragraphs do not disappear;
- overflow continues forward rather than being dropped;
- PoC text remains selectable/extractable;
- machine-readable layout planning evidence is produced;
- deterministic planner/PoC tests pass where applicable;
- PDFTR-17/18/20/21 guarantees are not weakened;
- a durable reflow architecture document exists;
- PDFTR-23 production scope is concretely proposed;
- the full repository quality gate passes;
- the third ProjectWiki pilot result is recorded;
- the first evidence-based ProjectWiki Phase 1 decision is recorded.
