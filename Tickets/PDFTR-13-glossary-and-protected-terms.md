# PDFTR-13 — Glossary, protected terms, and terminology consistency

## Summary

Implement glossary-driven English → Russian translation on top of the stable logical text structure introduced by PDFTR-11 and the repeated-element classification introduced by PDFTR-12.

The glossary must operate on logical paragraphs and repeated translation units, not on raw PDF spans or visual fragments.

The implementation must preserve:

- paragraph reconstruction and reading order;
- repeated header/footer/boilerplate classifications;
- source block mappings;
- protected-token guarantees;
- translation cache and resume determinism;
- renderer behavior;
- diagnostics and privacy defaults.

Do not modify OCR or PDF layout heuristics in this ticket.

## Dependencies

Required base:

- PDFTR-11 — Paragraph reconstruction and reading order;
- PDFTR-12 — Repeated headers, footers and boilerplate detection.

Create the branch only after PDFTR-12 is merged into `master`.

Suggested branch:

```text
codex/PDFTR-13-glossary-and-protected-terms
```

## Goal

Allow users to provide a versioned glossary that defines how specific English terms, phrases,
names, abbreviations and protected values must be handled during English → Russian translation.

The glossary must support:

1. mandatory translations;
2. terms that must remain unchanged;
3. case-sensitive and case-insensitive matching;
4. whole-word and phrase matching;
5. optional inflection policy;
6. ambiguity detection;
7. deterministic conflict resolution;
8. diagnostics for applied, missed and conflicting glossary entries;
9. cache/resume identity integration;
10. repeated paragraph/header reuse without reapplying inconsistent terminology.

## Non-goals

Do not implement:

- GUI glossary editor;
- automatic glossary generation from arbitrary PDFs;
- morphological generation with an external NLP service;
- online terminology lookup;
- translation memory;
- fuzzy OCR correction;
- PDF layout changes;
- OCR changes;
- renderer redesign;
- PDFTR-14 performance work;
- PDFTR-15 packaging.

## Required workflow

Treat this as a Level 2 architectural change.

Before editing:

1. verify Git status and branch base;
2. read:
   - `AGENTS.md`;
   - `.codex/PRE_TICKET_WORKFLOW.md`;
   - PDFTR-11 and PDFTR-12 tickets, plans, reports and reviews;
   - current paragraph translation pipeline;
   - protected-token implementation;
   - cache/resume identity implementation;
   - diagnostics models and builders;
3. run Graphify and CRG preflight;
4. verify graph conclusions against source;
5. record the affected pipeline path.

Expected path:

```text
extraction
→ paragraph reconstruction
→ repeated-element classification
→ glossary preparation
→ protected-token preparation
→ segmentation
→ model translation
→ protected-token restoration
→ glossary validation
→ cache/checkpoint
→ rendering
→ diagnostics
```

## Glossary file format

Add a versioned UTF-8 JSON glossary format.

Suggested file:

```json
{
  "schema_version": "1.0",
  "glossary_version": "1.0.0",
  "source_language": "en",
  "target_language": "ru",
  "entries": [
    {
      "id": "kgb",
      "source": "KGB",
      "target": "КГБ",
      "mode": "translate",
      "case_sensitive": true,
      "match": "whole_word",
      "inflection": "fixed",
      "priority": 100,
      "notes": "Mandatory abbreviation translation."
    },
    {
      "id": "isbn",
      "source": "ISBN",
      "target": "ISBN",
      "mode": "preserve",
      "case_sensitive": true,
      "match": "whole_word",
      "inflection": "fixed",
      "priority": 100
    },
    {
      "id": "secret-service",
      "source": "Secret Service",
      "target": "Секретная служба",
      "mode": "translate",
      "case_sensitive": false,
      "match": "phrase",
      "inflection": "fixed",
      "priority": 50
    }
  ]
}
```

Equivalent typed schema is acceptable, but it must remain simple and deterministic.

### Required fields

Glossary:

- `schema_version`;
- `glossary_version`;
- `source_language`;
- `target_language`;
- `entries`.

Entry:

- stable `id`;
- `source`;
- `target`;
- `mode`;
- `case_sensitive`;
- `match`;
- `inflection`;
- `priority`;
- optional `notes`.

### Entry modes

Required:

```text
translate
preserve
```

Meaning:

- `translate`: the final Russian output must contain the specified target form;
- `preserve`: the source form must remain unchanged.

Optional future modes must not be added unless required by implementation.

### Matching

Required modes:

```text
whole_word
phrase
exact
```

Definitions:

- `whole_word`: match a standalone lexical term;
- `phrase`: match an exact normalized multi-word phrase;
- `exact`: the entire logical paragraph must match the source value.

Matching must not operate across logical paragraph boundaries.

Do not match across pages unless PDFTR-11 already reconstructed the content as one logical paragraph.

### Case behavior

- `case_sensitive=true`: source casing must match exactly;
- `case_sensitive=false`: Unicode-aware case-insensitive matching;
- preservation must retain the glossary-defined output exactly;
- do not invent title-case transformations unless explicitly implemented and tested.

### Inflection

Required initial values:

```text
fixed
allow_model
```

- `fixed`: final output must contain the target exactly;
- `allow_model`: glossary target may be supplied as model context or replacement evidence, but
  deterministic validation should record whether the preferred term appears.

Do not claim grammatical inflection generation.

## Typed domain model

Add a glossary package independent from Typer, PyMuPDF and Transformers.

Suggested modules:

```text
src/pdftranslate/glossary/
    __init__.py
    models.py
    loader.py
    matcher.py
    processor.py
    diagnostics.py
```

Responsibilities:

- models: Pydantic/domain contracts;
- loader: strict UTF-8 JSON loading and validation;
- matcher: deterministic entry matching;
- processor: placeholder preparation/restoration and final validation;
- diagnostics: typed evidence generation.

Typer and CLI types must not leak into this package.

## Conflict detection

Reject invalid or ambiguous glossaries before model loading.

At minimum detect:

1. duplicate entry IDs;
2. identical source/match/case settings with different targets;
3. identical source with conflicting modes;
4. overlapping phrases with equal priority where deterministic resolution is impossible;
5. empty source or target;
6. unsupported language pair;
7. invalid schema/version;
8. duplicate normalized entries;
9. preserve entry that conflicts with translate entry;
10. placeholder collisions.

Conflict errors must identify the relevant entry IDs.

## Conflict resolution

For valid overlaps, apply deterministic precedence:

1. higher priority;
2. longer source phrase;
3. case-sensitive match before case-insensitive match;
4. exact before phrase before whole-word;
5. stable entry ID as final deterministic ordering only when semantics do not conflict.

Do not silently pick between semantically conflicting entries.

## Translation integration

Glossary processing must occur on logical paragraph text.

Do not change the stable paragraph structure.

### Required behavior

For each translatable logical paragraph:

1. find matching glossary entries;
2. replace mandatory/preserved source terms with collision-safe internal placeholders;
3. pass prepared text into the existing protected-token and segmentation pipeline;
4. translate through the existing backend;
5. restore glossary values;
6. restore existing protected tokens;
7. validate final glossary compliance;
8. record diagnostics;
9. cache the final validated output.

The exact ordering of glossary and existing protected-token placeholders must be source-verified and
designed so the two systems cannot corrupt each other.

### Important constraint

Glossary placeholders must not leak into:

- model output;
- translated JSON;
- rendered PDF;
- diagnostics text unless explicit text diagnostics are enabled;
- cache keys or cached translated values in unresolved form.

### Repeated content

Repeated headers, footers and boilerplate with `translate` policy must:

- use the same glossary rules;
- translate once through existing deduplication/cache;
- render consistently on every mapped page.

`preserve` and `skip` repeated-element policies must take precedence over glossary translation.

Examples:

- a page number remains preserved even if a glossary contains a numeric entry;
- a watermark candidate with `skip` is not translated by glossary;
- a preserved repeated unit is not changed;
- a translated repeated header applies glossary exactly once and reuses the result.

## Protected tokens

Existing protected-token guarantees must remain compatible.

Cover at least:

- numbers and dates;
- filenames;
- Windows paths;
- URLs;
- CLI options;
- placeholders;
- ISBN/DOI;
- glossary-preserved terms;
- glossary-translated terms;
- overlapping protected and glossary spans.

When the same span is covered by both systems, define and test one deterministic owner.

Preferred rule:

```text
explicit glossary entry takes precedence over generic token protection
```

except where repeated-element policy is `preserve` or `skip`.

Document the final rule.

## Cache and resume identity

Glossary configuration changes translation behavior and must participate in cache/resume identity.

Required identity inputs:

- glossary schema version;
- glossary version;
- normalized glossary content hash;
- language pair;
- matching options;
- conflict-resolution behavior revision.

Changing any effective glossary entry must invalidate incompatible resume state.

Do not rely only on glossary file path or modification time.

Translation cache keys must prevent reuse across different effective glossaries.

Preferred:

```text
backend
model
source language
target language
normalized source text
glossary fingerprint
translation behavior revision
```

Existing cache schema migration must be explicit and backward compatible where practical.

Do not silently reuse old cache entries without glossary identity.

## CLI

Add optional glossary support to:

- root translation command;
- `batch`;
- any direct translation command that uses the production translation pipeline.

Suggested option:

```text
--glossary PATH
```

Optional compatibility option:

```text
--glossary-mode strict|warn|off
```

Recommended semantics:

- `strict`: violations/conflicts fail the run;
- `warn`: conflicts still fail during load, but final missing preferred terms produce diagnostics
  and warnings rather than publication failure;
- `off`: ignore configured glossary and preserve previous behavior.

Do not add mode options unless their behavior is fully tested.

CLI help must explain:

- supported JSON format;
- language limitation EN → RU;
- strict validation;
- glossary impact on cache/resume;
- no automatic inflection guarantee.

## Batch behavior

Batch runs must:

- load and validate the glossary once;
- compute one glossary fingerprint;
- reuse the loaded glossary for all files;
- include the fingerprint in each workspace identity;
- report per-file glossary statistics;
- fail before processing files if the glossary itself is invalid;
- not partially process a batch with an invalid glossary.

## Configuration

Add typed configuration/environment settings only where useful.

Suggested:

```text
PDFTRANSLATE_GLOSSARY
PDFTRANSLATE_GLOSSARY_MODE
```

CLI must override environment configuration according to existing precedence rules.

Do not encode glossary entries directly in environment variables.

## Diagnostics

Extend PDFTR-10 diagnostics without exposing source text by default.

Document-level summary:

- glossary enabled;
- glossary schema/version;
- glossary fingerprint;
- total entries;
- matched entries;
- unmatched entries;
- applied occurrences;
- preserved occurrences;
- mandatory translation occurrences;
- violations;
- conflicts;
- ambiguous matches.

Per paragraph/unit evidence:

- paragraph ID;
- entry IDs;
- occurrence count;
- applied mode;
- priority;
- match type;
- compliance status;
- warning/error code.

Stable diagnostic codes should include:

```text
GLOSSARY_CONFLICT
GLOSSARY_MATCH_AMBIGUOUS
GLOSSARY_TARGET_MISSING
GLOSSARY_PRESERVE_VIOLATION
GLOSSARY_PLACEHOLDER_LEAK
GLOSSARY_ENTRY_UNUSED
```

Text values must remain excluded under the current privacy-default diagnostic behavior.

When explicit diagnostic text is enabled, include only the minimum necessary evidence.

## Error handling

Fail clearly for:

- missing glossary file;
- unreadable file;
- invalid UTF-8;
- malformed JSON;
- unsupported schema;
- unsupported language pair;
- duplicate IDs;
- conflicting entries;
- invalid mode/match/inflection;
- unresolved placeholder;
- strict final glossary violation;
- resume mismatch caused by glossary changes.

Source PDF must never be overwritten.

Partial output must not be published as final after a glossary failure.

## Serialization

Persist enough glossary evidence in translated schema/output metadata to make rendering and resume
auditable.

Do not copy the full glossary into every paragraph.

Persist at minimum:

- glossary fingerprint;
- glossary version;
- effective mode;
- matched entry IDs per logical paragraph where appropriate;
- compliance result;
- behavior revision.

Legacy documents without glossary metadata must remain readable.

## Tests

Add focused tests covering at least:

### Loading and validation

- valid glossary;
- malformed JSON;
- invalid UTF-8;
- duplicate ID;
- conflicting target;
- preserve/translate conflict;
- unsupported language pair;
- deterministic fingerprint;
- path-independent fingerprint;
- entry-order normalization where semantically equivalent.

### Matching

- case-sensitive term;
- case-insensitive term;
- whole-word boundaries;
- multi-word phrase;
- exact paragraph match;
- punctuation around terms;
- multiple occurrences;
- overlapping short and long terms;
- priority resolution;
- ambiguity rejection;
- no matching across paragraphs.

### Translation integration

- fixed mandatory translation;
- preserved term;
- glossary plus numbers/date;
- glossary plus filename/path/URL;
- glossary plus CLI option;
- glossary plus existing protected token;
- placeholder leak detection;
- model damages placeholder;
- final target missing;
- strict and warning behavior if implemented;
- segmentation of long paragraph with glossary terms;
- repeated source paragraph deduplication.

### Stable text structure

- glossary operates on logical paragraphs, not raw blocks;
- one paragraph reconstructed from several fragments is translated once;
- cross-page logical paragraph uses one glossary operation;
- headings/body remain separate;
- two-column order remains unchanged;
- source mappings remain unchanged;
- no paragraph IDs or fragment mappings are rewritten.

### Repeated elements

- translated running header uses glossary;
- repeated header translates once and renders on every source page;
- page number remains preserved;
- watermark candidate remains skipped;
- preserved/unknown repeated text remains unchanged;
- legal boilerplate with `translate` applies glossary consistently.

### Cache and resume

- same paragraph + same glossary → cache hit;
- same paragraph + changed target → cache miss;
- changed glossary version only → behavior follows documented fingerprint/version rule;
- changed entry order with equivalent semantics → deterministic identity;
- changed effective entry → resume mismatch;
- no glossary → existing behavior and old tests remain valid;
- batch files share the same loaded glossary/fingerprint.

### CLI and configuration

- root help;
- batch help;
- direct translation help where applicable;
- option propagation;
- environment precedence;
- missing glossary;
- invalid glossary fails before model load;
- `off` mode preserves compatibility if implemented.

### Diagnostics

- summary counts;
- entry IDs without text by default;
- stable warning/error codes;
- text privacy default;
- explicit text opt-in;
- unused entry diagnostics;
- glossary violations;
- repeated-element statistics remain present.

### Generated PDF end-to-end

Generate a deterministic PDF fixture with:

- multi-line paragraph reconstructed from several physical blocks;
- repeated header;
- page numbers;
- body terminology;
- preserved ISBN/URL;
- glossary term appearing on multiple pages.

Run:

```text
extract
→ reconstruct
→ classify repeated elements
→ glossary translation with fake backend
→ render
→ reopen PDF
→ verify extracted text
```

Verify:

- mandatory Russian terms appear;
- preserved terms remain unchanged;
- English source terms are absent where translation was required;
- page numbers remain;
- repeated headers are consistent;
- no placeholder appears;
- paragraph mappings are not duplicated;
- output remains searchable/selectable.

## Real validation

Use a small user-owned or generated PDF with stable text structure.

Real NLLB validation should cover a limited page subset where practical.

Record:

- glossary file;
- selected pages;
- model/device;
- source terms;
- expected targets;
- actual targets;
- violations;
- output PDF path;
- manual review status.

Do not claim CUDA validation unless it was actually executed.

Do not claim OCR glossary validation unless OCR was actually used.

## Benchmark

Add a deterministic glossary benchmark.

Dataset should include at least:

- 50–100 logical paragraphs;
- repeated terms;
- overlapping terms;
- preserved values;
- abbreviations;
- technical phrases;
- names;
- punctuation variants;
- long segmented paragraphs;
- repeated headers/boilerplate.

Report:

- total paragraphs;
- total glossary entries;
- matched entries;
- applied occurrences;
- violations;
- false matches;
- unused entries;
- cache hits/misses;
- model calls;
- elapsed time;
- deterministic fingerprint.

Compare:

```text
baseline translation without glossary
vs
translation with glossary
```

The benchmark must not claim semantic quality beyond what is measured.

## Documentation

Update:

- `README.md`;
- `CHANGELOG.md`;
- CLI help;
- glossary schema documentation;
- cache/resume documentation;
- diagnostics documentation;
- limitations;
- examples.

Add:

```text
docs/glossary.md
docs/glossary.example.json
Tickets/PDFTR-13-glossary-and-protected-terms.md
```

The example glossary must contain only synthetic/public-safe examples.

## Validation commands

Run at minimum:

```powershell
uv run pytest tests/test_glossary.py -q --no-cov
uv run pytest tests/test_translation.py tests/test_paragraph_reconstruction.py `
  tests/test_repeated_elements.py tests/test_rendering.py `
  tests/test_diagnostics.py tests/test_cli.py tests/test_batch_cli.py -q --no-cov
uv run ruff format --check .
uv run ruff check .
uv run mypy src
.\scripts\check.ps1
```

Also run:

- direct root/batch/help checks;
- generated-PDF round trip;
- glossary benchmark;
- real limited NLLB validation when local model files are available;
- Graphify refresh/query;
- CRG post-change impact analysis.

## Acceptance criteria

- [ ] Glossary operates on logical paragraphs from PDFTR-11.
- [ ] Repeated-element policies from PDFTR-12 take precedence.
- [ ] Versioned JSON glossary schema is implemented.
- [ ] Mandatory translations are enforced.
- [ ] Preserve entries remain unchanged.
- [ ] Matching is deterministic and paragraph-bounded.
- [ ] Conflicting glossaries fail before model loading.
- [ ] Overlap resolution is deterministic.
- [ ] Existing protected-token behavior remains correct.
- [ ] No internal placeholder leaks.
- [ ] Glossary fingerprint participates in cache identity.
- [ ] Glossary fingerprint participates in resume/workspace identity.
- [ ] Changed effective glossary content cannot reuse incompatible cache/resume state.
- [ ] Batch loads and validates the glossary once.
- [ ] Repeated translated terms reuse model/cache work.
- [ ] Page numbers, skipped watermarks and preserved repeated units remain unchanged.
- [ ] Diagnostics expose glossary evidence without text by default.
- [ ] Legacy no-glossary behavior remains compatible.
- [ ] Generated-PDF end-to-end validation passes.
- [ ] Full quality gate passes.
- [ ] README, CHANGELOG and glossary documentation are updated.
- [ ] Graphify and CRG are refreshed and source-verified.
- [ ] `implementation-report.md` and `reviews/review-PDFTR-13.md` are created.
- [ ] GitHub Actions is green.
- [ ] PDFTR-14 is not started.

## Required completion report

Create:

```markdown
# Implementation Report — PDFTR-13

## Git state
- Branch:
- Base commit:
- Working tree before changes:
- PDFTR-11/PDFTR-12 prerequisite confirmation:

## Investigation
- Current paragraph translation path:
- Protected-token path:
- Repeated-element policy path:
- Cache/resume identity:
- Diagnostics path:
- Graphify/CRG findings and source verification:

## Glossary design
- Schema:
- Matching rules:
- Conflict rules:
- Placeholder strategy:
- Protected-token precedence:
- Inflection behavior:
- Fingerprint algorithm:

## Implementation
- Modules:
- Pipeline integration:
- Repeated-element integration:
- Cache/resume changes:
- Batch behavior:
- CLI/configuration:
- Diagnostics:
- Serialization/compatibility:

## Tests
- Loading/validation:
- Matching:
- Translation integration:
- Stable text structure:
- Repeated elements:
- Cache/resume:
- CLI/batch:
- Diagnostics:
- Generated PDF:

## Benchmark
- Dataset:
- Baseline:
- With glossary:
- Violations:
- False matches:
- Cache/model calls:
- Timing:

## Real validation
- PDF:
- Pages:
- Model/device:
- Glossary:
- Expected terms:
- Actual terms:
- Manual review:
- Limitations:

## Full validation
- Focused tests:
- Full pytest:
- Coverage:
- Ruff:
- mypy:
- check.ps1:
- GitHub Actions:

## Remaining risks
- ...

## Recommendation
- Ready / not ready for review
```

## Review file

Create:

```text
reviews/review-PDFTR-13.md
```

It must state:

- verdict;
- files and pipeline boundaries reviewed;
- stable-text-structure verification;
- repeated-element precedence verification;
- glossary conflict behavior;
- protected-token compatibility;
- cache/resume correctness;
- diagnostics privacy;
- generated/real validation;
- limitations;
- merge recommendation.
