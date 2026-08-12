# PDFTR-13A — End-to-end glossary benchmark correction

## Scope

Fix only the PDFTR-13 benchmark. Do not rewrite the glossary implementation.

## Requirements

- Build 50–100 `LogicalParagraph` instances.
- Use a deterministic fake translator.
- Run the complete `translate_paragraphs()` path:
  - first without a glossary;
  - then with a glossary.
- Use separate SQLite caches or explicitly controlled empty cache databases.
- Measure:
  - paragraphs;
  - glossary matches;
  - required targets;
  - violations;
  - false matches;
  - translator calls;
  - translated segments;
  - cache hits;
  - cache misses;
  - elapsed time.
- Add a repeat run with the same glossary to prove cache reuse.
- Add a run with a changed glossary target to prove a cache miss.

The benchmark must execute:

```text
LogicalParagraph
→ repeated policy
→ glossary
→ protect_text
→ segmentation
→ deterministic fake translator
→ restore
→ glossary validation
→ TranslationCache
```

Update the implementation report and review with measured numbers.

## Validation boundary

Real NLLB is not required. Generated-PDF validation remains fake-backed, and the review must
continue to state that NLLB, CUDA, OCR, and manual PDF-XChange validation were not performed.
