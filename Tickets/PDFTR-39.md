# PDFTR-39 — Shared list-item layout contract

## Summary

Introduce the minimal shared layout contract required to represent structural list markers independently from semantic paragraph content.

PDFTR-38 was stopped with `BLOCKED` because the current reflow model has no architecture-level representation for independent source-owned marker/content geometry.

This ticket does **not** implement full list-marker fidelity.

It adds the missing shared representation and proves that it can flow safely through the existing reflow pipeline without introducing a second list-specific layout system.

---

# Motivation

The current paragraph/reflow model can represent paragraph text and ordinary indentation, but it does not have a first-class contract for:

```text
marker identity
marker_x
content_x
semantic content
continuation content edge
```

That prevents a list item from being modeled as two structurally distinct first-line origins while still using one shared reflow path.

Without this contract, list-marker implementation tends to collapse into one of the following invalid approaches:

```text
embed marker into semantic text
guess marker width from font metrics
use spaces/tabs
use HTML tables / inline layout hacks
post-adjust x positions
validate only semantic content
```

PDFTR-39 must solve the representation problem first.

---

# Goal

Add a reusable source-backed list-item layout contract that can survive the full shared layout pipeline:

```text
source evidence
→ paragraph/reflow model
→ measurement
→ pagination
→ insertion
→ saved-PDF validation
```

The contract must make it possible to represent:

```text
marker_text
marker_x
content_x
semantic_text
```

without requiring marker text to be merged into semantic text.

---

# Non-goal

Do not implement end-user list-marker fidelity in this ticket.

Specifically, do not add broad marker detection, translation behavior changes, translated-prefix stripping, or final product-level list reconstruction.

PDFTR-39 is an architecture-enabling ticket only.

---

# Required contract

Introduce the smallest architecture-consistent representation for a structural list item.

Conceptually:

```text
ListLayoutContract
    marker_text
    marker_x
    content_x
```

The actual type/name is implementation-defined.

The model must preserve these invariants:

```text
marker_x <= content_x
marker_text is structural, not semantic
semantic text remains ordinary paragraph content
continuation lines begin at content_x
marker is only eligible for the first logical line/item occurrence
```

If source evidence is unavailable or invalid, the contract must be absent rather than guessed.

---

# Shared-pipeline requirement

The new contract must integrate with the existing shared reflow model.

Do not create:

```text
list-specific planner
list-specific renderer
list-specific pagination engine
parallel validation path
```

The same planner and insertion path used by ordinary paragraphs must remain authoritative.

List-specific data may influence shared measurement/insertion behavior through explicit model fields or a reusable structural fragment abstraction.

---

# Measurement requirements

Measurement must understand that a list item can have:

```text
marker origin  = marker_x
content origin = content_x
```

The first semantic line must be measured from:

```text
content_x → right edge
```

Continuation lines must use the same semantic content edge unless normal paragraph layout explicitly changes it.

The marker region must be measurable independently:

```text
marker_x → content_x
```

No hard-coded character widths.

No assumption that semantic font advance determines marker placement.

---

# Pagination requirements

Pagination must preserve logical marker ownership.

If a list item spans multiple pages:

```text
marker appears only with the first logical occurrence
continuation pages contain semantic continuation only
```

The contract must make this representable without special-case post-processing.

Do not duplicate marker state independently in multiple page fragments.

---

# Insertion requirements

Insertion must be able to place:

```text
marker at source-backed marker_x
semantic content at source-backed content_x
```

within the existing shared insertion path.

Marker placement must not depend on semantic paragraph alignment.

The contract should support future LEFT/CENTER/RIGHT semantic alignment without moving source-owned marker position.

Do not implement full list product behavior yet; prove the primitive is architecturally possible.

---

# Saved-PDF validation requirements

The saved-output model must be able to distinguish:

```text
semantic occurrence
structural marker occurrence
```

Validation architecture must have enough identity to support future checks for:

```text
missing marker
duplicate marker
marker repeated on continuation page
semantic content complete
```

PDFTR-39 does not need to implement all future product validations, but the data model must not make them impossible.

At minimum, add a deterministic structural occurrence representation or metadata path suitable for later validation.

---

# Translation boundary

Do not change translation provider behavior in this ticket.

However, the contract must make this future ownership model possible:

```text
source PDF owns marker
provider owns semantic translation
reflow owns geometry
```

Do not encode provider-specific behavior into the layout contract.

---

# Ambiguity and fallback

The contract must only exist when valid source-backed geometry is available.

Invalid geometry must fail closed or fall back to existing non-list/fixed-layout behavior.

Examples:

```text
content_x < marker_x
missing source coordinates
non-finite coordinates
unsupported structural evidence
```

Do not silently normalize invalid geometry into a guessed layout.

---

# Architecture constraints

Prefer a small reusable model change over multiple special-case booleans.

Allowed:

```text
new immutable layout metadata type
small model fields
shared measurement helper
shared structural-fragment representation
saved-output occurrence metadata
```

Forbidden:

```text
HTML tables
inline-block hacks
padding tricks
spaces/tabs as geometry
post-render relocation
manual clipping
font-width compensation heuristics
second renderer
second planner
provider-specific marker logic
translated-prefix heuristics
```

---

# Investigation

Before implementation, create:

```text
.implementation-plans/investigation-PDFTR-39.md
```

Answer at least:

1. Which existing model currently owns paragraph geometry?
2. Where are first-line and continuation origins represented today?
3. Can the existing paragraph model safely carry structural first-line metadata, or is a small new type cleaner?
4. Where does measurement currently obtain left/right bounds?
5. Where does insertion currently obtain first-line origin?
6. How does pagination split logical paragraphs into page segments?
7. What identity survives from logical paragraph to saved-PDF validation?
8. What is the smallest contract that can distinguish structural marker from semantic text?
9. How can marker metadata survive pagination without duplicating marker ownership?
10. How can future saved validation associate a marker with the correct logical item?
11. Which current body typography and inline-style paths must remain untouched?
12. Which existing tests best prove that ordinary paragraphs are unaffected?
13. What production files need to change?
14. What future PDFTR-38-style feature work becomes possible after this contract exists?
15. What remains intentionally out of scope?

Do not implement before investigation is complete.

---

# Required implementation

Implement only the minimum architecture needed to prove the contract.

The implementation should demonstrate at least one internal synthetic/list-aware paragraph flowing through:

```text
model construction
→ planner/measurement
→ pagination
→ insertion
→ saved representation/validation metadata
```

without requiring product-level list detection.

A synthetic or explicitly constructed contract in tests is acceptable.

---

# Required tests

Add deterministic tests for:

```text
contract accepts valid marker_x/content_x
contract rejects invalid geometry
semantic text remains independent from marker text
planner measures semantic first line from content_x
continuation geometry uses content_x
marker ownership remains first-occurrence-only across pagination
marker_x survives to insertion metadata
semantic paragraph alignment does not mutate marker_x
saved representation can distinguish marker occurrence from semantic occurrence
ordinary non-list paragraphs remain unchanged
BODY typography regression remains green
inline-style regression remains green
```

Add at least one multi-page synthetic list-layout fixture.

No real translation provider calls.

---

# Compatibility

The contract must be optional.

Existing documents/artifacts without list-layout metadata must continue to render as before.

Do not bump translation behavior revision unless investigation proves it is unavoidable.

Do not invalidate existing artifacts merely because the new optional model exists.

If serialization schema changes are required, keep backward compatibility explicit and tested.

---

# Workflow

For this ticket:

```text
implementer = Codex
reviewer    = Codex
```

Separate processes/contexts.

Recommended:

```powershell
uv run python scripts/pi_ticket_cycle.py PDFTR-39 --preset codex-codex
```

Maximum automatic review rounds remain 2.

No auto-merge.

---

# Reviewer focus

The reviewer must answer:

```text
1. Is marker identity structurally separate from semantic text?
2. Are marker_x and content_x represented explicitly and source-backed?
3. Does measurement use content_x for semantic width?
4. Can marker fit be measured independently?
5. Does pagination preserve first-occurrence marker ownership?
6. Can insertion place marker/content independently without a second renderer?
7. Can saved-output validation distinguish structural marker from semantic text?
8. Are invalid geometries fail-closed?
9. Are existing non-list paragraphs behaviorally unchanged?
10. Was any forbidden workaround introduced?
11. Is this genuinely shared infrastructure rather than hidden list-specific layout duplication?
```

Any architectural workaround that bypasses the shared reflow path is `CHANGES_REQUIRED`.

---

# Quality gate

Run:

```powershell
uv run pytest
uv run python scripts/project_wiki/wiki_lint.py
.\scripts\check.ps1
```

Required:

```text
ruff format/check: PASS
mypy: PASS
full pytest: PASS
coverage threshold: PASS
Windows CI: PASS
Ubuntu CI: PASS
working tree: clean
```

---

# Completion criteria

PDFTR-39 is complete when:

```text
shared model can represent structural marker independently
marker_x/content_x are explicit and validated
semantic first-line measurement starts at content_x
continuation geometry remains content_x-backed
pagination retains first-occurrence marker ownership
insertion can consume structural marker geometry through shared path
saved-output metadata can distinguish marker vs semantic occurrence
invalid geometry fails closed
non-list behavior remains unchanged
no list-specific renderer/planner exists
no whitespace/table/font-metric workaround exists
full local gate passes
Windows CI passes
Ubuntu CI passes
exact-SHA review returns PASS
```

After PDFTR-39 passes, the product-level list-marker fidelity task can be reconsidered on top of the new shared contract.

Final merge remains a human decision.
