# Glossaries

PDFTranslate accepts an optional strict UTF-8 JSON glossary on the normal PDF command, `batch`,
and direct `translate` command:

```powershell
uv run pdftranslate input.pdf --glossary .\docs\glossary.example.json
uv run pdftranslate batch .\manuals --glossary .\docs\glossary.example.json
uv run pdftranslate translate .\input.json -o .\translated.json --glossary .\glossary.json
```

Only English-to-Russian glossaries and schema `1.0` are supported. Loading is strict: malformed
JSON, invalid UTF-8, unknown fields, duplicate IDs, conflicting normalized source entries,
unsupported values, and the reserved `__PDFTR_GLOSSARY_` namespace fail before model inference.

## Schema

The document fields are `schema_version`, semantic `glossary_version`, `source_language`,
`target_language`, and a non-empty `entries` array. Every entry has a stable `id`, `source`,
`target`, `mode`, `case_sensitive`, `match`, `inflection`, and integer `priority`; `notes` is
optional.

- `mode=translate` requires the preferred Russian target in strict output validation.
- `mode=preserve` requires `target` to exactly equal `source` and never asks the model to change it.
- `match=whole_word` or `phrase` uses Unicode word boundaries and stays within one logical
  paragraph. `exact` matches the complete paragraph, apart from surrounding whitespace.
- `inflection=fixed` uses a protected replacement. `allow_model` leaves the source visible to the
  model but still requires the configured preferred target; it is not a morphology engine.
- Higher priority wins an overlap, then the longer match, case-sensitive match, match specificity,
  and stable entry ID. Semantically conflicting duplicates fail instead of being selected.

Repeated-element `preserve` and `skip` policies have higher precedence than glossary entries.
Otherwise, explicit glossary spans own overlaps with generic number/path/URL/identifier
protection. The glossary placeholder is itself protected during model inference; generic tokens
are restored first so the glossary value can then be restored and validated. No internal
placeholder is written to translated JSON, cache values, reports, or rendered PDFs.

## Identity, resume, and privacy

The semantic fingerprint is SHA-256 over the schema/version/language pair, behavior revision, and
canonical effective entries sorted by ID. It excludes the file path, modification time, entry
order, and notes. The fingerprint participates in translation-cache keys and pipeline workspace
identity, so an effective target or version change cannot reuse incompatible cached/resume data.

Batch validates and loads the glossary once and shares that immutable instance across files.
Batch success records include its fingerprint and per-file counts. Translation metadata and
PDFTR-10 reports include IDs, modes, counts, compliance, and stable glossary diagnostic codes.
Source and target text remain excluded from diagnostics unless the existing explicit report-text
opt-in is used.

The initial release intentionally implements strict mode only. There is no `warn` or `off` mode,
automatic term extraction, automatic inflection, or raw-PDF-span matching.
