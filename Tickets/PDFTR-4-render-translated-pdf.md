# PDFTR-4 — Render translated Russian text into a copy of the source PDF

## Summary

Create a translated PDF from the source PDF and translated document JSON while preserving images, vector graphics, page size, and general layout.

## Dependencies

Requires:

- `PDFTR-1`;
- `PDFTR-2`;
- `PDFTR-3`.

## Goal

Implement:

```bash
pdftranslate render input.pdf document.ru.json --output input.ru.pdf
```

## Rendering strategy

For each translated text block:

1. validate that the JSON block matches the source page;
2. cover or redact the original English text region;
3. insert Russian text into the original bounding box;
4. preserve page images and vector content;
5. reduce font size when translated text does not fit;
6. record unresolved overflow warnings;
7. never modify the source PDF.

Use PyMuPDF.

## Font handling

Requirements:

- support Cyrillic;
- allow explicit font path:

```text
--font PATH
```

- provide a Windows-safe default font discovery strategy;
- do not commit proprietary font files;
- embed the selected font where required;
- fail clearly when no usable Cyrillic font is available;
- validate that the selected font contains necessary Cyrillic glyphs.

## Layout fitting

Implement deterministic fitting:

1. start from the original block font size when reliable;
2. otherwise use a documented default;
3. wrap text inside the original rectangle;
4. reduce size in configurable steps;
5. stop at `--min-font-size`;
6. optionally expand the block downward only within safe limits;
7. report overflow rather than silently clipping text.

Required options:

```text
--min-font-size
--font-size-step
--line-height
--allow-expand
--debug-layout
```

## Original text removal

Use redaction or another reliable technique.

Requirements:

- original English text must not remain visibly overlaid;
- source images must not be rasterized unnecessarily;
- redaction must not erase unrelated neighboring elements;
- small padding must be configurable;
- white background cannot be assumed for every page.

For non-white backgrounds, implement a conservative background strategy and record limitations.

## Debug output

`--debug-layout` must draw or annotate:

- source block boundaries;
- final text boundaries;
- overflow blocks;
- expanded blocks.

Debug output must go to a separate output PDF or require explicit overwrite.

## Integrity validation

Before rendering, validate:

- source file identity or fingerprint;
- page count;
- page dimensions;
- block identifiers;
- schema compatibility.

Refuse unsafe rendering when the translated JSON belongs to a different source PDF, unless a deliberate override flag is provided.

## Output validation

After saving:

- reopen the generated PDF;
- verify page count;
- verify that the file is readable;
- verify presence of inserted Cyrillic text on translated pages;
- report final file size and warnings.

## Tests

Cover:

- simple paragraph replacement;
- heading replacement;
- multiline wrapping;
- Russian text longer than English;
- font reduction;
- overflow warning;
- Cyrillic font validation;
- pages with images;
- source mismatch rejection;
- output reopening;
- paths with spaces and Cyrillic characters.

Use generated test PDFs. Avoid large committed binaries.

## Acceptance criteria

- [ ] `render` creates a new PDF.
- [ ] Source PDF remains unchanged.
- [ ] Images and page geometry are preserved.
- [ ] Original text is covered or removed.
- [ ] Russian text is inserted with a Cyrillic-capable font.
- [ ] Font size is reduced when required.
- [ ] Overflow is reported and never silently ignored.
- [ ] Source/JSON mismatch is detected.
- [ ] Generated PDF can be reopened by PyMuPDF.
- [ ] Debug layout mode exists.
- [ ] All quality checks pass.
- [ ] README and CHANGELOG are updated.

## Non-goals

Do not implement:

- OCR;
- translation inside images;
- perfect reproduction of every original font;
- semantic table reconstruction;
- manual translation editor;
- GUI.
