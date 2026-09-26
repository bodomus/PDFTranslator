# PDFTR-32 — Safe inline style runs for mixed-style paragraphs

## Goal

Introduce a deterministic, fail-safe inline-style run contract for production reflow so source-backed
mixed typography can be preserved **only where the correspondence between source text and translated
text is provable**.

PDFTR-32 is the next fidelity layer after paragraph-level typography:

```text
PDFTR-27  typography evidence
PDFTR-28  paragraph style reconstruction
PDFTR-29  BODY typography fidelity
PDFTR-30  HEADING typography fidelity
PDFTR-31  FOOTNOTE typography fidelity
PDFTR-32  safe inline style runs for mixed-style paragraphs   ← this ticket
```

The ticket must not guess how translated Russian words correspond to arbitrary source spans.

The production renderer must continue to prefer a correct complete PDF over speculative style
preservation.

---

## Current state

After PDFTR-31, BODY, HEADING, and FOOTNOTE all consume authoritative
`ResolvedParagraphStyle` values during:

```text
measurement
pagination
continuation planning
HTML/CSS insertion
saved-PDF validation
diagnostics
```

Paragraph-level mixed-style information is currently diagnostic only:

```text
mixed_font_family
mixed_font_size
mixed_weight
mixed_italic
mixed_color
```

The source domain already retains same-style source spans:

```python
TextSpan(
    text=...,
    font_name=...,
    font_size=...,
    text_color=...,
    bold=...,
    italic=...,
)
```

and `LogicalParagraph` / `ParagraphFragment` retain those source spans.

However, `LogicalParagraph.translated_text` is a new target-language string whose character offsets
do not generally correspond to source offsets.

Current production HTML insertion renders each reflow segment as one paragraph style:

```python
_segment_html(segment.text)
_segment_css(..., ReflowStyle, ...)
```

Therefore arbitrary inline source styling cannot safely be applied merely by copying source span
positions.

---

## Core safety rule

**Never infer translated inline offsets from source offsets.**

A source inline style may be activated in translated output only when the implementation can prove
the exact target substring to which it belongs.

If correspondence is ambiguous or unavailable:

```text
render the text with the resolved paragraph style
preserve mixed-style diagnostics
do not fail the entire paragraph merely because optional inline fidelity is unavailable
```

This is a fidelity enhancement, not a completeness exception.

---

## Scope

PDFTR-32 must implement:

1. a typed source-backed inline-run evidence contract;
2. deterministic mapping of safe preserved source runs into translated text;
3. run-aware measurement;
4. run-aware segment splitting;
5. run-aware HTML/CSS insertion using the same style contract as measurement;
6. saved-PDF validation that remains exact;
7. diagnostics explaining which inline styles were applied or deferred.

The implementation must work for production reflow roles already supported:

```text
BODY
HEADING
FOOTNOTE
```

No separate layout engine is allowed.

---

## 1. Inline run contracts

Add a small immutable domain/rendering contract for inline runs.

Suggested conceptual model:

```python
class InlineStyleRun(...):
    text_start: int
    text_end: int

    font_size_points: float | None
    color_rgb: ...
    bold_requested: bool | None
    italic_requested: bool | None

    source_font_name: str | None
    source_font_family_group: str | None

    mapping_kind: ...
    confidence: ...
```

The exact naming/location may differ after investigation.

Required invariants:

```text
0 <= text_start < text_end <= len(translated_text)
runs are ordered
runs do not overlap
ranges refer to translated-text offsets, not source-text offsets
run text is auditable
mapping provenance is explicit
```

A run must never silently modify paragraph geometry outside its declared target range.

---

## 2. Source run reconstruction

Build source inline-style evidence from existing `TextSpan` data.

Do not add a second PDF extraction path.

The reconstruction must be deterministic and conservative.

At minimum retain source evidence for:

```text
source span text
font name
font size
text color
bold
italic
source order
source fragment/page identity where needed for diagnostics
```

Adjacent spans may be merged only when their relevant inline style is identical and text ordering is
proven.

Do not merge across uncertain source-text boundaries.

---

## 3. Mapping source runs to translated text

This is the critical requirement.

### Allowed mapping

A source-styled run may be mapped to translated output only when the exact source text survives in
the translated paragraph and its target location can be identified unambiguously.

Examples may include:

```text
Latin terminus
Ελληνικά
API
CUDA
C#
class names
identifiers
protected glossary terms
other exact untranslated/preserved tokens
```

Use existing translation preservation behavior where useful, but do not introduce semantic word
alignment in this ticket.

### Safe deterministic matching

Implement a conservative ordered matcher.

A candidate run is eligible only when all required conditions are satisfied, for example:

```text
source run text is non-empty after normalization
exact normalized text survives in translated_text
target occurrence can be identified unambiguously
mapping preserves source run order
mapped ranges do not overlap
the target substring equals the preserved text
```

Repeated identical text must not be assigned arbitrarily.

If:

```text
source: API ... API
target: API ... API
```

mapping may be accepted only if deterministic monotonic correspondence is proven.

If multiple valid assignments remain, defer the run.

### Forbidden mapping

Do not:

- copy source character offsets into translated text;
- style “the word in roughly the same position”;
- use fuzzy matching to guess translated words;
- use Levenshtein similarity for semantic alignment;
- ask the translation model to emit style markup as part of this ticket;
- rewrite translated text to make style matching easier;
- silently style a translated Russian word because it came from a styled English word.

---

## 4. Paragraph fallback behavior

Every paragraph keeps its already resolved paragraph style as the authoritative base style.

Inline runs are overlays.

Conceptually:

```text
ResolvedParagraphStyle = base style
InlineStyleRun         = proven local overrides
```

If zero inline runs are safely mapped:

```text
current PDFTR-31 rendering remains unchanged
```

If only some mixed spans are provable:

```text
apply those proven runs
render all remaining text with paragraph style
```

Do not reject an otherwise safe paragraph merely because optional inline style mapping is incomplete.

---

## 5. Which style properties may be activated

For PDFTR-32, inline activation may cover only properties supported safely by both measurement and
insertion.

Required initial properties:

```text
font size
RGB color
```

Bold/italic must continue to obey the existing face-resolution boundary.

Record:

```text
bold_requested
bold_applied = False

italic_requested
italic_applied = False
```

unless a pre-existing safe face resolver exists by implementation time.

Do not synthesize bold or italic.

Font-family identity remains evidence/diagnostic only unless an already-approved local font resolver
exists.

Do not introduce arbitrary font substitution.

---

## 6. Run-aware measurement is mandatory

Do not implement rich insertion with plain paragraph-only measurement.

This is a hard acceptance requirement.

Current measurement:

```text
text + ReflowStyle → Measurement
```

must be extended/refactored so inline font-size changes used during insertion also participate in
fitting.

Conceptually:

```text
text
base paragraph style
inline runs
        ↓
shared rich-text representation
        ↓
PyMuPDF measurement
PyMuPDF insertion
```

Measurement and insertion must produce HTML/CSS from the same rendering contract.

No duplicate formatting logic.

No “measure plain, insert rich”.

Automatic PyMuPDF downscaling remains disabled:

```text
scale_low = 1
```

---

## 7. Shared rich-text representation

Refactor `_segment_html()` / `_segment_css()` only as much as necessary to support styled ranges
without creating separate measurement/insertion implementations.

Preferred conceptual output:

```html
<p>
  normal translated text
  <span class="r0">Latin terminus</span>
  normal text
</p>
```

with deterministic generated CSS.

Requirements:

```text
HTML escaping remains correct
numeric/XML-safe mixed-script handling remains correct
no source text injection into markup
stable class/run ordering
same HTML/CSS builder used by measure and insert
```

Do not expose raw source font names directly as unescaped CSS.

---

## 8. Segment splitting

The planner may split a paragraph across continuation regions.

Inline runs are expressed against full translated paragraph offsets.

When creating each `PlacementSegment`, clip/rebase relevant runs to:

```text
segment.text_start
segment.text_end
```

Example:

```text
paragraph run = [40, 70)
segment       = [55, 100)

segment-local run = [0, 15)
```

A run crossing a segment boundary must be safely split.

No character duplication or loss is allowed.

The concatenation invariant remains:

```python
"".join(segment.text for segment in paragraph_segments) == paragraph.translated_text
```

Run boundaries must not alter text offsets.

---

## 9. Planner fitting

Prefix fitting must remain exact.

If the fitting algorithm probes progressively shorter text prefixes, the rich-text subset supplied
to the measurer must correspond exactly to each candidate prefix.

Do not apply a run beyond the current prefix.

Do not drop runs silently from measurement and restore them only during insertion.

Inline font-size changes may affect:

```text
line wrapping
used height
orphan decisions
continuation count
footnote pagination
```

Those effects are expected and must be measured, not guessed.

---

## 10. Heading orphan behavior

PDFTR-29/PDFTR-30 heading-orphan safety must remain valid.

If a HEADING or its following BODY contains applied inline size overrides, orphan evaluation must
use the same run-aware measurement as normal production fitting.

Do not reintroduce a height estimate.

---

## 11. Footnote behavior

PDFTR-31 behavior must remain intact.

Applied inline runs inside FOOTNOTE must participate in:

```text
measurement
pagination
continuation splitting
saved insertion
diagnostics
```

while preserving:

```text
footnote region eligibility
separator ownership
BODY → FOOTNOTE continuation ordering
capacity bounds
```

---

## 12. Diagnostics

Extend diagnostics with explicit inline-style information.

At minimum expose aggregate fields such as:

```text
inline_style_candidate_count
inline_style_applied_count
inline_style_deferred_count
inline_style_applied_character_count
```

and enough detail in debug/report output to determine:

```text
which translated ranges received inline overrides
why a candidate was deferred
which properties were actually applied
```

Suggested defer reasons include:

```text
not_preserved_in_translation
ambiguous_target_occurrence
overlapping_mapping
unsupported_property
unsafe_or_invalid_source_run
```

Exact model design may differ after investigation.

Do not dump excessive source text into normal CLI output.

Detailed run evidence may live in debug diagnostics.

---

## 13. Saved-PDF validation

Current segment-local validation must remain strict.

For every successful render:

```text
all segment text remains selectable
expected text is present in its local clip
no text is missing
no text is duplicated
zero unplaced characters
```

Add inline-style validation where reliably inspectable.

For color/size tests, use PyMuPDF span extraction on deterministic synthetic fixtures and prove that
the preserved substring has the expected local style while surrounding text retains paragraph style.

Do not weaken text validation because rich HTML is harder.

---

## 14. Deterministic tests

Use the repository-bundled deterministic Liberation Sans test font.

Do not return to OS-dependent fonts.

Add focused regressions for at least the following.

### A. Exact preserved inline color

Example translated text:

```text
Русский текст Latin terminus продолжение.
```

Source `Latin terminus` has a distinct source color.

Verify:

```text
exact target range found
run applied only to Latin terminus
surrounding Russian text uses paragraph color
saved PDF remains selectable
```

### B. Exact preserved inline font size

Use a preserved token with a materially different size.

Verify run-aware measurement changes fitting/pagination when appropriate.

The same run must appear during insertion with the measured size.

### C. Source offsets differ from target offsets

Construct:

```text
source:     Before Latin terminus after.
translated: До длинного русского текста Latin terminus после.
```

Verify the style is applied to the translated location of `Latin terminus`, not to the old source
offset.

This regression is mandatory.

### D. Ambiguous repeated token

Example:

```text
source contains two identically styled/unidentically styled occurrences of API
target contains repeated API occurrences
```

If the mapping cannot be proven uniquely, the uncertain run must be deferred.

No arbitrary first-match behavior.

### E. Partial mixed-style preservation

A paragraph has several mixed source spans but only one survives translation exactly.

Verify:

```text
one applied run
remaining candidates deferred
paragraph still renders successfully
base paragraph style covers unproven text
```

### F. Continuation split through an inline run

Force a long styled preserved substring or suitable fixture so the styled range crosses a
`PlacementSegment` boundary.

Verify:

```text
run clipped/rebased correctly
no missing/duplicated characters
both segments measured with correct local run subset
saved output validates
```

### G. Heading orphan with inline size

Verify a heading/following BODY case where inline size materially affects fit.

The orphan decision must follow rich measurement.

### H. Footnote continuation with inline style

Verify mixed-script FOOTNOTE with a preserved inline run across normal/continuation pagination.

Separator and page ordering remain correct.

### I. Unsupported bold/italic

Source run requests bold/italic.

Verify:

```text
requested metadata retained
applied remains false
no synthetic CSS font-weight/font-style is emitted
```

unless a separately approved safe face resolver already exists.

### J. Unsafe/invalid run contract

Reject or defer:

```text
negative range
end beyond translated text
zero-length range
overlapping applied ranges
text/range mismatch
unordered ranges
```

No PDF mutation from structurally invalid production run data.

---

## 15. Real-document validation

Inspect available repository/cached real PDFs for naturally mixed paragraphs.

Robitzsch already contains mixed-style evidence, but do not claim production inline fidelity unless
there are exact source runs that survive translation and can be proven in translated output.

For any real artifact used, record:

```text
mixed-style paragraph count
candidate inline run count
applied run count
deferred run count
defer reason distribution
BODY/HEADING/FOOTNOTE unplaced characters
overflow count
inserted pages
final page count
```

Visually inspect representative applied runs.

Verify:

```text
styled preserved term remains selectable
local color/size is plausible and isolated
surrounding translated prose remains base style
no clipping
no overlap
no pagination corruption
```

If the real artifact yields zero safely mappable runs, document that honestly and rely on
deterministic production fixtures.

Do not manufacture preserved source terms.

---

## 16. Translation boundary

Do not change the translation backend contract merely to make PDFTR-32 easier.

Existing translation behavior may be consumed as evidence, especially exact preserved foreign or
protected terms.

Out of scope for this ticket:

```text
model-generated markup
translation word alignment
token-level bilingual alignment
forced placeholder markup for every source style span
rewriting translations to preserve source span boundaries
```

If investigation concludes that full arbitrary inline translation fidelity requires explicit
translation alignment metadata, document that as a future ticket rather than guessing.

---

## 17. Schema / persistence boundary

Prefer a derived renderer-facing inline-run contract rather than expanding persisted
`ExtractedDocument` schema unless persistence is demonstrably required.

If a schema change is proposed, Codex must justify:

```text
why derived reconstruction is insufficient
resume/cache compatibility impact
migration/versioning behavior
```

Do not casually bump schema 1.3.

---

## 18. Performance

Avoid quadratic substring mapping across large documents.

Mapping should be bounded per paragraph and deterministic.

Do not add an LLM/model call for style alignment.

No GPU dependency is required.

The feature must remain practical on long PDFs.

---

## 19. Existing guarantees that must remain unchanged

Preserve:

```text
authoritative occurrence-index paragraph style mapping
BODY typography fidelity
HEADING typography fidelity
FOOTNOTE typography fidelity
strict capacity failure
exact segment accounting
source immutability
atomic destination replacement
saved segment validation
disabled automatic downscaling
deterministic bundled test font
separator preservation
continuation ordering
repeated-element policy
foreign-language preservation
glossary protection
```

---

## Expected investigation questions

Before implementation, Codex must answer in
`.implementation-plans/investigation-PDFTR-32.md`:

1. How are source `TextSpan`s ordered relative to `LogicalParagraph.text`?
2. Can source span ranges be reconstructed without ambiguity for all current paragraph fragments?
3. Which existing preserved-translation mechanisms expose enough evidence to prove target ranges?
4. What exact run contract should planner/measurer/inserter share?
5. How will `_largest_fitting_prefix()` measure candidate prefixes with clipped runs?
6. How will a run crossing segment boundaries be represented?
7. How will saved-PDF style validation inspect size/color without becoming font-platform dependent?
8. Does any current API assume `TextMeasurer.measure(text, style)` and need a backward-compatible
   extension?
9. Can implementation remain a derived renderer contract without schema changes?
10. Which real artifacts contain safely mappable mixed-style preserved text?
11. Which PDFTR-32 architecture facts were recovered correctly from ProjectWiki before source inspection?
12. Which exact questions still required canonical source inspection?
13. Did the Wiki contain any stale, incomplete, or contradictory statement relevant to PDFTR-32?

Do not implement before these questions are source-verified.

---

## Expected code areas

Likely blast radius:

```text
src/pdftranslate/typography/
src/pdftranslate/rendering/reflow/models.py
src/pdftranslate/rendering/reflow/planner.py
src/pdftranslate/rendering/reflow/pymupdf_layout.py
src/pdftranslate/rendering/reflow/regions.py
src/pdftranslate/rendering/reflow/footnotes.py
src/pdftranslate/rendering/renderer.py
tests/test_reflow_production.py
```

Potential helper module for inline run mapping is acceptable.

Do not broaden into translation/backend code unless investigation proves it is necessary.

---

## Documentation

Update as required:

```text
README.md
CHANGELOG.md
docs/reflow-architecture.md
docs/style-reconstruction.md
knowledge/wiki/architecture/reflow-layout.md
knowledge/wiki/architecture/style-reconstruction.md
knowledge/wiki/log.md
```

Create/update:

```text
.implementation-plans/investigation-PDFTR-32.md
.implementation-plans/implementation-plan-PDFTR-32.md
.implementation-reports/implementation-report-PDFTR-32.md
reviews/review-PDFTR-32.md
```

Document clearly that:

```text
paragraph typography = authoritative base
inline typography = applied only for provably mapped translated ranges
unmapped source variation = diagnostic/deferred, never guessed
```

---

## ProjectWiki retrieval validation

PDFTR-32 must also serve as a real workflow validation of the existing ProjectWiki.

This is not a separate product feature and must not distract from the rendering scope.

The goal is to verify whether the current curated Markdown Wiki helps Codex recover durable
architecture and safety constraints before deep source inspection, while still preserving the rule
that canonical source/tests/runtime evidence are authoritative.

### Required order

Before implementation and before deep source-code analysis, Codex must:

1. read repository-level `AGENTS.md`;
2. read `knowledge/AGENTS.md`;
3. read `knowledge/wiki/index.md`;
4. run targeted Wiki searches;
5. write down what the Wiki alone establishes;
6. only then inspect canonical source/tests/Graphify/CRG as required;
7. compare Wiki claims with current source and record gaps or contradictions.

Do not skip directly to source and later claim the Wiki was useful.

### Required Wiki searches

At minimum run:

```powershell
uv run python scripts/project_wiki/wiki_search.py "inline style mixed typography"
uv run python scripts/project_wiki/wiki_search.py "reflow measurement insertion"
uv run python scripts/project_wiki/wiki_search.py "foreign language preservation"
uv run python scripts/project_wiki/wiki_search.py "paragraph style reconstruction"
uv run python scripts/project_wiki/wiki_search.py "render completeness"
```

Additional searches are allowed when investigation requires them.

### Pre-source Wiki summary

Before deep implementation inspection, add a section to:

```text
.implementation-plans/investigation-PDFTR-32.md
```

named:

```text
## ProjectWiki pre-source retrieval
```

Record:

```text
Wiki pages consulted
Search queries used
Architecture facts recovered from Wiki
Safety constraints recovered from Wiki
Open questions that Wiki cannot answer
Potentially stale or ambiguous Wiki claims
```

The Wiki should be able to recover at least these durable facts if current documentation is healthy:

```text
BODY / HEADING / FOOTNOTE resolved typography is active
occurrence_index is authoritative for resolved paragraph styles
mixed inline styles are currently diagnostic/deferred
measurement and insertion must remain consistent
automatic downscaling is disabled
strict render completeness must not be weakened
bold/italic face application is intentionally deferred
source/test/runtime evidence is more authoritative than Wiki summaries
```

Do not force the Wiki to contain implementation details that belong only in source.

### Source-of-truth cross-check

After reading canonical source/tests, add:

```text
## ProjectWiki source cross-check
```

to the investigation.

For every material Wiki-derived claim used by PDFTR-32, classify it as:

```text
CONFIRMED
INCOMPLETE
STALE
CONTRADICTED
```

For `INCOMPLETE`, `STALE`, or `CONTRADICTED`, record:

```text
Wiki page
Wiki claim
Current source/runtime evidence
Required Wiki correction
```

A contradiction is not to be silently fixed in the investigation narrative.

It must be called out explicitly.

### Negative retrieval test

Perform at least one query whose answer should require canonical source inspection.

Use this or an equivalent concrete question:

```text
How exactly should inline runs be clipped and rebased while
_largest_fitting_prefix() probes candidate prefixes?
```

Expected Wiki behavior:

```text
the Wiki may describe the architectural constraint,
but it should not be treated as authoritative for exact private planner behavior
```

If the Wiki appears to contain stale implementation detail or encourages an unsupported answer,
record that as a Wiki quality issue.

### Success criteria for Wiki validation

ProjectWiki passes the PDFTR-32 workflow validation when:

- searches surface the relevant architecture pages;
- durable safety boundaries are recovered before source inspection;
- source inspection confirms those boundaries;
- exact implementation questions still correctly require canonical source;
- stale/missing knowledge is identified rather than guessed;
- only genuinely changed durable knowledge is updated;
- no near-duplicate Wiki pages are created;
- `wiki_lint.py` passes after updates.

Do not claim token/time savings unless actually measured.

### Required implementation-report section

Add to:

```text
.implementation-reports/implementation-report-PDFTR-32.md
```

a section:

```text
## ProjectWiki validation
```

containing at minimum:

```text
search queries
pages consulted
knowledge recovered before source inspection
canonical source still required for
missing/stale knowledge found
contradictions found
Wiki pages updated
whether obvious rediscovery was avoided
final retrieval verdict
```

Use one of these final retrieval verdicts:

```text
KEEP AS-IS
KEEP WITH CONTENT FIXES
RETRIEVAL GAP — REASSESS SEARCH
ARCHITECTURE GAP — REASSESS WIKI STRUCTURE
```

Do not propose semantic search, embeddings, MCP, QMD, automated ingestion, or graph-generated Wiki
content unless this ticket produces a concrete retrieval failure that the current lexical workflow
cannot reasonably address.

### Wiki maintenance after implementation

After PDFTR-32 behavior is finalized:

1. update only affected durable-topic Wiki pages;
2. update `knowledge/wiki/index.md` only if navigation genuinely changes;
3. append one concise meaningful entry to `knowledge/wiki/log.md`;
4. run:

```powershell
uv run python scripts/project_wiki/wiki_lint.py
```

5. include Wiki lint in the normal project quality gate.

The Wiki must document the durable post-PDFTR-32 boundary, not the temporary implementation history.


---

## Quality gate

Run focused tests for:

```text
source run reconstruction
translated-range mapping
ambiguous mapping
run clipping/rebasing
planner prefix fitting
PyMuPDF rich measurement
rich insertion
heading orphan behavior
footnote continuation
diagnostics
saved-PDF validation
```

Then run:

```powershell
uv run pytest
scripts/check.ps1
```

GitHub CI must pass on:

```text
windows-latest
ubuntu-latest
```

No platform-specific font/layout failures are acceptable.

---

## Acceptance criteria

PDFTR-32 is complete only when:

- a typed inline-style run contract exists;
- every applied run refers to translated-text offsets;
- source offsets are never reused as target offsets;
- ambiguous mappings are deferred rather than guessed;
- paragraph style remains the base fallback;
- exact preserved mixed-style substrings can retain supported inline size/color;
- run-aware measurement and insertion share one rich-text representation;
- planner prefix fitting clips inline runs correctly;
- continuation segments clip/rebase runs without changing text accounting;
- heading orphan logic remains run-aware and correct;
- FOOTNOTE pagination and separator behavior remain correct;
- bold/italic remain requested-but-unapplied unless a safe resolver already exists;
- exact text accounting remains zero-unplaced for successful renders;
- saved-PDF validation remains strict;
- deterministic test font remains pinned;
- full local quality gate passes;
- GitHub CI is green on Windows and Ubuntu;
- implementation report explains applied/deferred real-document evidence honestly;
- ProjectWiki pre-source retrieval and source cross-check are recorded;
- ProjectWiki validation ends with an explicit retrieval verdict;
- Wiki lint passes after any durable knowledge update.

Final review status:

```text
READY FOR REVIEW
```

only after all acceptance criteria and CI checks pass.

---

## Non-goals

Explicitly out of scope:

- semantic alignment of translated words to source words;
- LLM-based span alignment;
- arbitrary source-offset reuse after translation;
- source font installation/discovery;
- local font-family resolver;
- synthetic bold/italic;
- model-generated HTML/style markup;
- per-glyph positioning;
- multi-column production reflow;
- relaxing strict render completeness;
- weakening saved-PDF validation;
- increasing page limits to mask rich-text fitting regressions.
