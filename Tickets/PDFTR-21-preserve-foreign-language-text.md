# PDFTR-21 — Preserve Latin/Greek/foreign-language quotations and terminology

## Goal

Prevent the translation pipeline from corrupting non-English source material that should remain
verbatim in academic PDFs.

The Robitzsch regression showed inconsistent handling of Latin:

- on page 1, the Latin verse

```text
praesidium reges ipsi sibi perfugiumque,
et pecudes et agros divisere atque dedere
pro facie cuiusque et viribus ingenioque.
```

was translated/transliterated into Cyrillic-like output:

```text
Президиум Регес Ипси Сиби Перфугиумк,
...
```

- on page 2, another Latin verse beginning with

```text
inde magistratum partim docuere creare
```

remained in Latin.

Academic source quotations, original-language passages, and selected foreign-language terminology
must not be fed blindly through the English→Russian translator.

This ticket must make that behavior explicit, deterministic, testable, and source-preserving.

This is a **translation preservation** ticket, not a layout/reflow ticket.

---

## Branch

Create a new branch from current `master`:

```text
codex/PDFTR-21-preserve-foreign-language-text
```

---

## ProjectWiki pilot

This is the **second real post-PDFTR-19 ProjectWiki pilot ticket**.

Before implementation:

1. read `knowledge/wiki/index.md`;
2. search ProjectWiki for:
   - translation;
   - protected tokens;
   - glossary;
   - paragraph reconstruction;
   - rendering completeness;
   - foreign language;
3. inspect canonical code/reports only where Wiki knowledge is insufficient or must be verified;
4. record concrete ProjectWiki pilot observations in the implementation report.

Do not bypass the existing Graphify/CRG workflow.

---

## Real-world evidence

Use the same Robitzsch PDF that exposed the issue:

```powershell
uv run pdftranslate ".\tests\Robitzsch Jan Maximilian - Epicurean Justice. Nature, Agreement, and Virtue - 2024_50.pdf" `
  --device cuda `
  --output .\test10textpages.ru.pdf
```

Important examples to inspect:

### Page 1 — Latin passage that must be preserved

```text
praesidium reges ipsi sibi perfugiumque,
et pecudes et agros divisere atque dedere
pro facie cuiusque et viribus ingenioque.
```

Current bad behavior:

```text
Президиум Регес Ипси Сиби Перфугиумк,
...
```

Expected behavior:

```text
praesidium reges ipsi sibi perfugiumque,
et pecudes et agros divisere atque dedere
pro facie cuiusque et viribus ingenioque.
```

### Page 2 — Latin passage already preserved

```text
inde magistratum partim docuere creare
iuraque constituere, ut vellent legibus uti.
...
```

This existing good behavior must remain good.

### Inline academic terminology

Examples from the same document include:

```text
ipsi
sibi
lex
ius
nomos
magistratus
faute de mieux
```

These must not be corrupted merely because they occur inside otherwise translatable prose.

Do not assume every Latin-script word is English or every non-English token must always be preserved.
Investigate the context and existing protected-span/glossary mechanisms first.

---

## Required investigation

Follow `.codex/PRE_TICKET_WORKFLOW.md`.

Inspect at minimum:

- paragraph reconstruction;
- translation segmentation;
- protected-token handling;
- glossary/protected-term pipeline;
- translation behavior revision / cache identity;
- NLLB input/output boundary;
- paragraph translation batching;
- serialization;
- repeated-element policies;
- marker/pass-through logic from PDFTR-17;
- real Robitzsch translation workspace/artifacts;
- tests added by PDFTR-16 / PDFTR-16A / PDFTR-17.

Trace the page-1 Latin stanza from:

```text
source extraction
→ logical paragraph
→ preprocessing/protected spans
→ translator input
→ translator output
→ persisted translated JSON
→ renderer input
```

Also trace the page-2 Latin stanza that already survives unchanged.

The implementation report must explain **why one stanza was corrupted while the other survived**.

Do not start by adding ad-hoc Latin words to a protected-token regex.

---

## Core requirement

Introduce an explicit preservation decision for foreign-language material that must remain source
verbatim.

The implementation must distinguish at least:

```text
translate normally
preserve whole unit
preserve protected foreign-language span(s) inside translated prose
```

Exact class/enum naming should follow existing project conventions.

Do not infer preservation from accidental translator behavior.

---

## Whole-unit preservation

If a logical paragraph is confidently identified as a foreign-language quotation/passage that
should remain unchanged, it must:

```text
not be sent to NLLB
translated_text == source text
be explicitly marked/accounted as preserved/pass-through
survive serialization/cache/resume
render normally
```

Examples:

```text
Latin verse paragraph
Greek original-language quotation
```

The decision must be deterministic and testable.

---

## Mixed-language prose

Academic prose often contains foreign-language terminology or citations inside English prose.

Example:

```text
The passage mentions lex and ius, while Lucretius writes ipsi ... sibi.
```

Expected behavior:

```text
English prose → Russian translation
lex / ius / ipsi / sibi → preserved where required
```

Do not preserve the entire paragraph merely because it contains one Latin word.

Where appropriate, reuse or extend the existing protected-span / glossary mechanism instead of
inventing a parallel placeholder system.

---

## Greek handling

Greek text must never be transliterated into Russian merely because the surrounding document is
English.

At minimum support deterministic recognition of Greek-script runs using Unicode script/range
evidence.

For Greek quotations:

```text
source Greek → preserved Greek
```

Mixed English + Greek paragraphs should translate the English prose while preserving the Greek
span where structurally possible.

---

## Latin handling

Latin is harder because it uses the same script as English.

Do not use a naive rule such as:

```text
"contains Latin characters" => preserve
```

That would preserve all English.

Investigate a conservative, evidence-based strategy.

Possible evidence may include combinations of:

- quotation/block context;
- verse-like line structure;
- ratio of known English words vs non-English words;
- known Latin function-word patterns;
- surrounding citation context;
- italics/font metadata if reliable;
- existing protected terminology;
- explicit glossary/preservation configuration if already supported.

Do not add a heavyweight language-detection dependency unless there is a concrete, documented need.

Prefer conservative behavior:

```text
if confidently foreign → preserve
if ambiguous → keep normal translation path and emit diagnostic evidence where appropriate
```

No silent guessing.

---

## Foreign terminology

Support source-preservation for short academic terms where existing project mechanisms can do so
safely.

Examples:

```text
lex
ius
nomos
ipsi
sibi
magistratus
```

Do not globally protect every occurrence of short common strings if that can create false positives.

If the robust solution is to integrate with glossary/protected terms, do so explicitly and document
the precedence.

---

## Preservation model

Prefer a small explicit model instead of hidden regex side effects.

For example, each translated logical unit may carry or derive a preservation classification such as:

```text
translate
preserve_foreign_unit
translate_with_preserved_spans
```

Exact names may differ.

The implementation should make it possible to answer programmatically:

```text
How many paragraphs were preserved as foreign-language units?
How many foreign-language spans were preserved inside translated prose?
Which paragraph IDs were affected?
```

Avoid adding a second document model if existing translation metadata can be extended cleanly.

---

## Cache / resume correctness

If translation behavior changes, inspect cache and workspace identity.

A translation produced before PDFTR-21 must not be reused if it would bypass the new preservation
logic.

If behavior revision / cache identity needs to change:

- update it deliberately;
- add deterministic regression coverage;
- document the compatibility impact.

Do not silently reuse stale cached translations that contain corrupted Latin/Greek output.

---

## Diagnostics

Add concise diagnostics/reporting where appropriate.

Useful evidence may include:

```text
paragraph ID
page number
preservation classification
reason/evidence
preserved span count
translator called? yes/no
```

Do not dump full book text into normal logs.

If classification is ambiguous and normal translation proceeds, make that diagnosable without
turning every paragraph into a warning.

---

## Tests

Add deterministic tests.

At minimum:

### 1. Whole Latin passage

Input:

```text
praesidium reges ipsi sibi perfugiumque,
et pecudes et agros divisere atque dedere
pro facie cuiusque et viribus ingenioque.
```

Expected:

```text
translator is not called for this unit
translated_text == source text
```

### 2. Existing page-2 Latin-style regression

A second Latin quotation must also be preserved.

This prevents the implementation from special-casing only the page-1 text.

### 3. Greek quotation

Input containing a Greek-script quotation.

Expected:

```text
Greek remains Unicode-equivalent after translation pipeline
translator does not rewrite the preserved Greek unit/span
```

### 4. Mixed English + Latin terms

Input:

```text
The passage distinguishes lex from ius and refers to ipsi and sibi.
```

Expected:

```text
English prose is translated
protected foreign terms survive exactly
```

Use a deterministic fake translator capable of demonstrating whether protected spans survive.

### 5. Mixed English + Greek span

English prose translates while the Greek span remains unchanged.

### 6. Ordinary English

Normal English paragraphs must still be sent to the translator.

No broad false-positive preservation.

### 7. Proper names / technical tokens

Existing protected-token regressions from PDFTR-16 must remain green.

### 8. Marker/pass-through

PDFTR-17 behavior must remain green.

### 9. Cache revision

If preservation behavior affects cache identity, verify an old behavior revision cannot bypass the
new logic.

### 10. Serialization round-trip

Preservation metadata/state, if added to the document schema, must survive JSON round-trip.

Avoid a schema change unless it is actually necessary.

---

## Real regression

After deterministic tests pass, rerun the Robitzsch case with CUDA.

Because PDFTR-20 now fails closed on layout overflow, a complete final PDF may not be published.

That is acceptable.

The purpose of this real regression is to inspect the translation artifact **before rendering fails**.

Required evidence:

```text
page-1 Latin stanza remains original Latin
page-2 Latin stanza remains original Latin
Greek passages remain Greek
mixed English prose still translates to Russian
inline protected terminology remains intact
no Cyrillic transliteration of preserved Latin quotation
```

Use persisted workspace/translated JSON evidence if final rendering stops at PDFTR-20 completeness.

Do not weaken PDFTR-20 to obtain a final PDF.

---

## Translation quality boundary

This ticket does NOT replace NLLB or generally improve Russian translation quality.

Do not attempt to solve awkward Russian phrasing here.

Scope is only:

```text
preserve foreign-language source material that should not be translated
```

---

## Do not include in this ticket

Do NOT implement:

- full page reflow;
- repagination;
- cross-page flow;
- typography redesign;
- translation-model replacement;
- LLM translation provider;
- universal language identification for dozens of languages;
- cloud language-detection APIs;
- OCR language redesign;
- bibliography/reference parser;
- footnote layout redesign.

Keep the solution conservative and focused.

---

## Expected follow-up

After PDFTR-21, the next major stage is a dedicated layout/reflow design based on the overflow
evidence from PDFTR-20.

Do not implement reflow preemptively in this branch.

---

## ProjectWiki update

After implementation:

1. update only affected Wiki pages;
2. document the foreign-language preservation policy/constraint;
3. record any interaction with protected tokens, glossary, cache identity, or translation metadata;
4. append a concise Wiki log entry;
5. update `knowledge/wiki/testing/pilot-evaluation.md` with the second real pilot result;
6. run:

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

The implementation report must contain a `ProjectWiki pilot` section with:

```text
Wiki pages consulted before implementation
canonical/raw sources additionally opened
missing/stale Wiki knowledge discovered
Wiki pages updated
whether Wiki avoided rediscovery of known facts
whether review exposed a Wiki gap
```

Do not claim time/token savings unless actually measured.

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
according to repository workflow.

---

## Required artifacts

Use the existing repository conventions:

```text
.implementation-plans/investigation-PDFTR-21.md
.implementation-plans/implementation-plan-PDFTR-21.md
.implementation-reports/implementation-report-PDFTR-21.md
reviews/review-PDFTR-21.md
```

Update:

```text
CHANGELOG.md
ProjectWiki pages affected by the implementation
```

Update README only if user/developer-visible behavior requires it.

---

## Acceptance criteria

PDFTR-21 is complete when:

- the page-1 Robitzsch Latin stanza is preserved verbatim through translation;
- another independent Latin quotation is preserved without special-casing one text;
- Greek quotations/spans are preserved;
- mixed English prose still translates while required foreign terms/spans survive;
- ordinary English is not falsely preserved;
- preservation is explicit and testable rather than accidental model behavior;
- stale translation cache/resume cannot bypass the new behavior if compatibility changes;
- PDFTR-16 protected-token regressions remain green;
- PDFTR-17 marker/pass-through behavior remains green;
- PDFTR-18 saved-PDF validation remains unchanged;
- PDFTR-20 strict render completeness remains unchanged;
- deterministic tests pass;
- full repository quality gate passes;
- real Robitzsch translation artifacts show preserved Latin/Greek before the expected fixed-layout
  render-completeness boundary;
- second ProjectWiki pilot evidence is recorded.
