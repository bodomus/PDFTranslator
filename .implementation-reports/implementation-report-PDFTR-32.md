# PDFTR-32 implementation report

## Outcome

Production BODY, HEADING, and FOOTNOTE reflow now supports immutable source-backed inline style
runs without guessing translated offsets. The resolved paragraph style remains authoritative;
font-size and RGB-color overrides are applied only where exact preserved text proves a deterministic
translated range. Missing, ambiguous, overlapping, invalid, and unsupported candidates are
deferred without making an otherwise safe paragraph fail.

## Workflow

- Level: 2, cross-cutting production reflow change.
- Branch: `codex/PDFTR-32-safe-inline-style-runs`, created from `master` at `c7a991e6e190`.
- Working tree before changes: dirty only for the unrelated pre-existing deletion of
  `temp/.agents.zip`; it was preserved.
- Graphify: existing repository graph queried for reflow, style, span, and preservation paths;
  every material conclusion was checked against source.
- code-review-graph: full preflight rebuild plus post-change incremental update completed.

## Contract and safety decisions

- Added immutable source-candidate, translated-run, deferred-run, and aggregate mapping contracts.
- Reconstructed candidates only from retained `LogicalParagraph` / `ParagraphFragment` /
  `TextSpan` evidence; no second PDF extraction path was added.
- Reconstructed source offsets using the existing paragraph joining and soft-hyphen rules. Any
  fragment/span mismatch is deferred as unsafe instead of searched approximately.
- Mapped exact text only when it occurs once in both source and target. Repeated source or target
  occurrences are ambiguous without independent identity evidence; ordinal assignment is not used.
  Source character offsets are never copied to translated text, and fuzzy or semantic alignment is
  not used.
- Applied only font size and RGB color. Bold/italic stay requested-but-unapplied; source font name
  and family stay diagnostic evidence.
- Preserved schema 1.3, translation/cache behavior, source immutability, atomic publication,
  repeated-element policy, and strict completeness.

## Reflow integration

- BODY, HEADING, and FOOTNOTE discovery derive inline mappings over their resolved paragraph base.
- `FlowParagraph` owns full translated-text runs; `PlacementSegment` owns clipped, segment-local
  runs and validates range/text invariants.
- Every whole-paragraph measurement, binary-search prefix probe, heading-orphan BODY probe, and
  continuation segment receives the exact applicable run subset.
- A crossing run is split and rebased without changing text offsets or character accounting.
- Measurement and insertion use one escaped, numeric-safe HTML/CSS builder with deterministic run
  classes and `scale_low=1`.
- Saved validation retains exact segment-local selectable-text validation and additionally checks
  size/color when PyMuPDF span extraction aligns the segment unambiguously.

## Diagnostics

- Added block- and document-level candidate, applied, deferred, and applied-character counts.
- Added per-run applied/deferred decisions with translated/source ranges, mapping kind, confidence,
  defer reason, requested/applied properties, and source font evidence.
- Run text is represented by SHA-256 in diagnostics; plaintext source-run text is not emitted.

## Deterministic regression coverage

- target offsets shifted from source offsets;
- ambiguous repeated tokens and partial preservation;
- unsupported face-only candidates and invalid source reconstruction;
- crossing-run clipping/rebasing and exact continuation accounting;
- prefix and final-segment use of the same runs;
- run-aware heading-orphan behavior;
- BODY and FOOTNOTE production discovery;
- PyMuPDF size-aware measurement;
- invalid, unordered, overlapping, and text-mismatched contracts;
- HTML/XML escaping and absence of synthetic face CSS;
- saved selectable PDF size/color validation;
- privacy-safe applied/deferred render decisions.

## Real-document validation

The existing four-page Robitzsch source and translated schema-1.3 artifact were rendered with the
bundled Liberation Sans font. The result was reopened by strict production validation and all eight
pages were rendered through Poppler for visual inspection.

- Mixed-style paragraphs: 46
- Candidate inline runs: 167
- Applied runs: 0
- Deferred runs: 167
- Deferred because exact text was not preserved: 37
- Deferred because only unsupported properties differed: 130
- Applied characters: 0
- BODY unplaced characters: 0
- FOOTNOTE unplaced characters: 0
- Overflow count: 0
- Inserted pages: 4
- Final pages: 8

No natural source run in this cached translation satisfied the safe size/color mapping contract,
so no real-document inline fidelity is claimed. Visual review found no new clipping, overlap, or
pagination corruption. Applied size/color isolation is instead proved by the deterministic saved-
PDF fixture, which also verifies surrounding selectable text.

## Graph and blast-radius validation

- Post-change graph: 1,496 nodes, 13,356 edges, 147 files.
- Changed symbols/classes: 38 across 23 files; affected known flows: 0.
- Heuristic risk score: 0.60.
- CRG's name-based gaps include new data models and diagnostics conversion paths; direct focused
  tests and the full suite cover the production mapping, planning, insertion, validation, and
  privacy-safe conversion behavior.
- No dependency, model/device, OCR, CLI, translation backend, or persisted-schema boundary changed.

## ProjectWiki validation

Search queries run before deep source inspection:

- `inline style mixed typography`
- `reflow measurement insertion`
- `foreign language preservation`
- `paragraph style reconstruction`
- `render completeness`
- the negative exact-planner query for clipping/rebasing inside `_largest_fitting_prefix()`

Pages consulted included the system overview, reflow layout, typography evidence, style
reconstruction, foreign-language preservation, and render-completeness pages.

The Wiki correctly recovered occurrence-index authority, active BODY/HEADING/FOOTNOTE paragraph
typography, paragraph style as the fallback base, measurement/insertion consistency, disabled
automatic downscaling, requested-but-unapplied faces, and strict completeness. Canonical source was
still required for fragment joining, exact planner clipping, PyMuPDF span validation, renderer
diagnostic plumbing, and precise caller/dependant reachability.

One stale statement in `architecture/system-overview.md` said reconstructed typography was not
connected to production; older reflow/typography wording also described the pre-PDFTR-29 boundary.
No source contradiction affected the implementation because the investigation explicitly marked
those claims stale before correction. Updated pages:

- `architecture/system-overview.md`
- `architecture/reflow-layout.md`
- `architecture/style-reconstruction.md`
- `architecture/typography-evidence.md`
- `log.md`

The lexical Wiki avoided rediscovering the durable safety model while correctly leaving private
planner behavior to source inspection. Final retrieval verdict: **KEEP WITH CONTENT FIXES**.

## Validation

- Focused inline/reflow/diagnostics tests: 49 passed.
- Full pytest: 354 passed, 1 skipped, 89.08% coverage.
- ProjectWiki lint: 15 pages, 104 links, zero errors/warnings.
- Ruff format/check: clean.
- Strict mypy: clean across 97 source files.
- `scripts/check.ps1`: passed completely.

### Follow-up validation (2026-09-26)

- Focused `test_inline_styles.py` plus `test_reflow_production.py`: 46 passed.
- Added explicit `2 source / 2 target` ambiguity coverage; both candidates defer with
  `AMBIGUOUS_TARGET_OCCURRENCE`.
- Added a real `PyMuPdfMeasurer` orphan regression proving a 28 pt inline span on one physical line
  reports one rendered line and moves a heading when two following lines are required.
- Full `scripts/check.ps1`: 356 passed, 1 skipped, 89.10% coverage; Ruff format/lint, strict mypy,
  and ProjectWiki lint all passed.
- Post-change CRG update: 1,548 nodes, 13,859 edges, 149 files; zero affected known flows. The
  reported 0.60 risk remains the whole PDFTR-32 branch diff against `master`, not an isolated
  follow-up score.

## Documentation and artifacts

Updated README, CHANGELOG, reflow/style architecture documents, affected ProjectWiki pages, and
the Wiki log. Added the ticket copy, investigation, implementation plan, this report, and the review
artifact.

## Remaining external gate

GitHub Windows and Ubuntu CI have not run because the branch has not been committed or pushed.
Per the ticket, `READY FOR REVIEW` is withheld until both jobs are green.

Current status: **LOCAL IMPLEMENTATION COMPLETE - CI PENDING**.
