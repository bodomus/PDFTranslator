# PDFTR-17 implementation plan

## Scope

Fix the render-time failure where schema 1.3 documents can contain translate-policy
logical paragraphs with empty `translated_text`, causing the renderer to report
missing translated paragraphs.

## Investigation checklist

- Verify the four reported IDs in the restored Robitzsch workspace across source
  extraction, paragraph reconstruction, repeated-element policy, translation output,
  serialization, and renderer validation.
- Source-check the schema 1.3 renderer path and keep its missing-translation and
  structural validation strict.
- Identify whether the empty values are produced by translator output, repeated
  reuse, paragraph ID collisions, or JSON round-trip loss.

## Implementation approach

- Treat PDF private-use marker-only text as non-linguistic pass-through content in
  translation preparation, similar to page numbers and identifiers.
- Keep mixed private-use plus prose text translatable so section headings still go
  through the model.
- Add focused tests for private-use marker pass-through, JSON round-trip, render
  completeness, and strict failure when a genuinely translated paragraph is empty.
- Update CHANGELOG and write the required implementation/report review artifacts.

## Validation

- Run focused pytest targets for translation, serialization, and rendering.
- Run `ruff format`, `ruff check`, `mypy src`, and `.\scripts\check.ps1`.
- Rerun the CUDA reproducer on the Robitzsch PDF and inspect the previously failing
  paragraph lifecycle in the resulting workspace.
