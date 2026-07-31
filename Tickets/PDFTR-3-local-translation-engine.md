# PDFTR-3 — Add local English-to-Russian translation pipeline

## Summary

Translate extracted PDF text blocks from English to Russian using a local model and produce a translated document JSON file.

## Dependencies

Requires:

- `PDFTR-1`;
- `PDFTR-2`.

## Goal

Implement:

```bash
pdftranslate translate document.json --output document.ru.json
```

The translation model must load once per process and be reused for all blocks.

## Translation abstraction

Create a backend-independent interface similar to:

```python
class Translator(Protocol):
    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        ...
```

Do not expose Transformers types outside the backend implementation.

## Initial backend

Implement the NLLB backend using:

```text
facebook/nllb-200-distilled-600M
```

Default language mapping:

```text
English: eng_Latn
Russian: rus_Cyrl
```

Support CPU and CUDA:

```text
--device auto
--device cpu
--device cuda
```

`auto` must prefer CUDA only when it is usable.

## CLI

Required command:

```bash
pdftranslate translate document.json \
  --output document.ru.json \
  --from en \
  --to ru \
  --backend nllb \
  --device auto
```

Options:

```text
--model
--device
--batch-size
--max-input-tokens
--cache-dir
--overwrite
--offline
--resume
```

## Model acquisition

Normal runtime may download the model when it is absent.

Requirements:

- clearly report that a download is needed;
- use the configured cache directory;
- support offline mode;
- fail clearly in offline mode when model files are absent;
- never download models during unit tests or CI;
- document approximate storage requirements without hard-coding a guarantee.

## Text preparation

Before translation:

- preserve empty blocks;
- skip blocks containing only whitespace;
- avoid translating standalone page numbers;
- preserve URLs;
- preserve email addresses;
- preserve file paths;
- preserve obvious code snippets;
- preserve measurement values and numeric identifiers;
- retain paragraph breaks where practical.

Do not silently remove content.

## Segmentation

Long blocks must be split safely.

Requirements:

- prefer sentence-aware splitting;
- respect tokenizer limits;
- preserve segment order;
- recombine segments deterministically;
- record warnings when segmentation may reduce quality.

Do not truncate text silently.

## Batching

Batch by token-aware or conservative size limits.

Requirements:

- configurable batch size;
- safe fallback after CUDA out-of-memory;
- no retry loop without bounds;
- log effective device and batch size;
- deterministic output for the same model and settings where possible.

## Translation memory cache

Add a local cache keyed by at least:

- backend;
- model;
- source language;
- target language;
- normalized source text.

Use SQLite or another robust local format.

Requirements:

- repeated blocks must not be translated again;
- cache location must come from application settings;
- cache corruption must produce a clear recoverable error;
- cache access must be tested;
- no global user data may be written into the repository.

## Output JSON

Preserve the source document structure and add:

- translation metadata;
- translated block text;
- backend;
- model;
- source and target language;
- timestamps;
- warnings;
- original text unchanged;
- schema version.

## Progress reporting

Display:

- model loading;
- blocks completed;
- cache hits;
- cache misses;
- elapsed time;
- current page or block;
- final summary.

Non-interactive output must remain usable in logs.

## Tests

Use fake translator backends for unit tests.

Cover:

- backend abstraction;
- batching;
- long-block segmentation;
- empty text;
- protected tokens;
- repeated-text cache hits;
- offline missing-model failure;
- CPU selection;
- CUDA unavailable fallback;
- output JSON integrity;
- interruption and resume metadata.

Do not download NLLB in CI.

## Acceptance criteria

- [ ] Translation backend abstraction exists.
- [ ] NLLB backend supports EN → RU.
- [ ] Model loads once per process.
- [ ] CPU, CUDA, and auto device selection work.
- [ ] Long text is not silently truncated.
- [ ] URLs, paths, and obvious identifiers are preserved.
- [ ] Translation cache prevents duplicate work.
- [ ] Unit tests do not download models.
- [ ] Output JSON retains original and translated text.
- [ ] Progress and final statistics are shown.
- [ ] README and CHANGELOG are updated.
- [ ] All quality checks pass.

## Non-goals

Do not implement:

- PDF rendering;
- OCR;
- cloud translation APIs;
- GUI;
- more language pairs;
- model fine-tuning;
- glossary editor.
