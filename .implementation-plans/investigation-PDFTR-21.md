# Investigation — PDFTR-21

## Workflow

- Level: 2 (translation behavior, cache/resume identity, serialized evidence, diagnostics).
- Baseline: `master` at `334ef2c93fb6bc1d964cf9df8841d6ddccf8e9d5`.
- Pre-existing user changes preserved: `.gitignore` modified; `temp/.agents.zip` deleted.
- Branch: `codex/PDFTR-21-preserve-foreign-language-text`.

## ProjectWiki pilot preflight

Searched for translation, protected tokens, glossary, paragraph reconstruction, rendering
completeness, and foreign language. The system overview and PDFTR-20 rendering page provided the
pipeline and fail-closed rendering boundary. The Wiki has no durable description of protected-token
or glossary behavior and no foreign-language preservation policy, so canonical source and runtime
artifacts were required.

## Graph and source findings

- Graphify identifies `translate_document` → `translate_paragraphs` as the schema 1.2/1.3
  translation path, with `protect_text`, `prepare_glossary_text`, `TranslationCache`, and
  `PdfRenderer.render` as adjacent boundaries. Source inspection confirms this.
- CRG was refreshed successfully and confirms the current branch has no code delta before work.
- `translate_paragraphs` applies repeated-element policy and marker pass-through first, then cache,
  glossary placeholders, generic protected tokens, segmentation, NLLB, restoration, persistence,
  and rendering.
- Cache and workspace identity include `TRANSLATION_BEHAVIOR_REVISION`; direct resume validation
  currently checks model/settings/glossary identity but not a persisted translation revision.

## Robitzsch trace

Workspace inspected:
`006fa75fccf481b61335aef4e1c7efe6e95d928ae876eb30460e68fcf0ddbf0b`.

- Page 1 `p0001-b0001` is a schema 1.2 logical body paragraph with repeated-element policy
  `translate`. It is cached/translated as Cyrillic-like text in schema 1.3.
- Page 2 `p0002-b0002` is also policy `translate`. Its result looks mostly Latin but contains model
  changes (`languebat` → `linguebat`, among others), proving it was not preserved.
- Greek footnote units sharing `p0001-b0007` are sent through translation and lose or alter Greek
  characters.
- Mixed English prose containing `lex`, `ius`, `nomos`, `faute de mieux`, and `magistratus` is
  translated; some terms happen to survive, but no explicit invariant guarantees it.

The two Latin stanzas differ because NLLB/cached model output happened to treat them differently,
not because the pipeline made a preservation decision.

## Smallest correct change

Add one focused foreign-language preprocessing/classification component used by paragraph-aware
translation:

- conservatively preserve confident whole Greek or Latin units;
- protect Greek-script spans and a narrowly defined academic-term vocabulary in mixed prose;
- compose after explicit glossary preparation and before generic protected-token preparation;
- persist privacy-safe per-unit evidence in existing translation metadata;
- bump translation behavior revision and validate it for direct resume and completed workspace
  reuse.

No new dependency, CLI option, document schema version, renderer change, OCR change, or model change
is required.

## Expected blast radius

- Translation preprocessing and paragraph orchestration.
- Translation metadata JSON and diagnostic report fields.
- Cache/workspace invalidation through behavior revision.
- Tests for translation, serialization, diagnostics, resume, protected tokens, and markers.
- README, CHANGELOG, and affected ProjectWiki pages.
