# PDFTR-2 — Inspect PDFs and extract structured text blocks

## Summary

Add PDF inspection and structured extraction for text-based PDF documents.

## Dependency

Requires completion of `PDFTR-1`.

## Goal

The CLI must analyze a PDF, classify its pages, extract text blocks with layout metadata, and optionally save a JSON representation for later translation and rendering.

## Scope

Add PyMuPDF as the PDF backend.

Implement:

```bash
pdftranslate inspect input.pdf
pdftranslate extract input.pdf --output document.json
```

## Required architecture

Add domain models and services without coupling them to Typer:

```text
src/pdftranslate/
├── domain/
│   ├── document.py
│   ├── page.py
│   └── text_block.py
├── pdf/
│   ├── analyzer.py
│   ├── extractor.py
│   └── pymupdf_backend.py
└── serialization/
    └── document_json.py
```

Equivalent names are acceptable when responsibilities remain clear.

## Document model

Represent at least:

- document source path;
- page count;
- PDF metadata;
- page width and height;
- page rotation;
- page classification;
- extracted text blocks;
- block bounding boxes;
- block ordering;
- font name when available;
- font size when available;
- text color when available;
- flags such as bold or italic when derivable;
- image count;
- extraction warnings.

Coordinates must use the PDF page coordinate system and be serializable.

## Page classification

Classify each page as one of:

```text
text
scanned
mixed
empty
```

Use deterministic heuristics based on:

- amount of extractable text;
- number and size of images;
- page area;
- text block count.

Keep thresholds configurable and documented.

Do not run OCR in this ticket.

## `inspect` command

Report at least:

- file path;
- file size;
- page count;
- text pages;
- scanned pages;
- mixed pages;
- empty pages;
- text block count;
- image count;
- encrypted status;
- whether a password is required;
- probable source language when it can be inferred cheaply;
- warnings.

Do not add a heavy language-detection model. A lightweight dependency or conservative heuristic is acceptable.

Support:

```bash
pdftranslate inspect input.pdf --json
```

The JSON output must be machine-readable and free from Rich markup.

## `extract` command

Extract the document into a versioned JSON format.

Required options:

```text
--output PATH
--pages RANGE
--pretty / --compact
--overwrite
```

Examples:

```bash
pdftranslate extract manual.pdf --output manual.document.json
pdftranslate extract manual.pdf --pages 1-20 --output first-pages.json
```

Page ranges are one-based in the CLI.

## Reading order

Preserve a stable reading order.

At minimum:

1. use PyMuPDF block ordering;
2. normalize blocks deterministically;
3. expose original and normalized order indexes;
4. avoid merging unrelated columns automatically.

Document limitations for multi-column layouts.

## Security and validation

Handle:

- missing input file;
- non-PDF input;
- corrupt PDF;
- encrypted PDF;
- unsupported password-protected files;
- invalid page range;
- existing output without `--overwrite`;
- empty PDF.

Never overwrite the source PDF.

## JSON format

Include:

```text
schema_version
source
metadata
pages
warnings
```

The schema must be stable enough for later translation and rendering tickets.

Store coordinates as numbers, not strings.

Use UTF-8.

## Tests

Create small generated PDF fixtures during tests where practical.

Cover:

- one-page text PDF;
- multi-page PDF;
- empty page;
- image-only page;
- mixed page;
- invalid PDF;
- encrypted PDF behavior;
- page range parsing;
- JSON round-trip;
- stable extraction order;
- paths containing spaces and Cyrillic characters.

Do not commit large binary fixtures.

## Acceptance criteria

- [ ] PyMuPDF is added and locked.
- [ ] `inspect` produces a readable report.
- [ ] `inspect --json` produces valid machine-readable JSON.
- [ ] `extract` writes versioned UTF-8 JSON.
- [ ] Text, scanned, mixed, and empty pages are classified.
- [ ] Page ranges are validated.
- [ ] Existing output is protected unless `--overwrite` is supplied.
- [ ] Corrupt and encrypted files fail with useful errors.
- [ ] All quality checks pass.
- [ ] README and CHANGELOG are updated.

## Non-goals

Do not implement:

- translation;
- OCR;
- PDF text replacement;
- layout reconstruction;
- image translation;
- tables as semantic structures;
- GUI.
