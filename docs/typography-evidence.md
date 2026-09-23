# Typography evidence baseline

PDFTR-27 adds a typed, source-backed typography baseline for logical paragraph occurrences. It is
diagnostic input for later style reconstruction; production rendering does not consume it yet.

## Architecture and storage

`pdftranslate.typography.extract_typography_evidence(document)` reads an already extracted schema
1.2 or 1.3 `ExtractedDocument`. It does not reopen the PDF, run OCR, rasterize pages, resolve local
fonts, call a model, or mutate the document. The result is a versioned `TypographyBaseline` with one
`ParagraphTypographyEvidence` per paragraph occurrence. The zero-based `occurrence_index` is the
authoritative locator because paragraph IDs can repeat.

Typography is intentionally derived rather than embedded in `ExtractedDocument`. This preserves
schema 1.3, translation-cache/resume compatibility, and current renderer behavior. The source
extraction model gained only optional `TextSpan.font_flags` and `TextSpan.origin` fields. Existing
JSON without those fields remains readable.

Every property has a typed value or explicit unknown, categorical confidence, typed provenance,
and an explicit downstream fallback category.

## Direct source evidence

- **Source font name:** meaningful-character-weighted dominant `TextSpan.font_name`. Only the
  canonical six-uppercase-letter subset prefix (for example `ABCDEE+`) is removed. A name is source
  identity, not proof that the font is installed locally.
- **Font size:** meaningful-character-weighted dominant size rounded to 0.001 pt. Isolated
  superscripts and footnote markers cannot win over the main text merely by adding another span.
- **Bold and italic:** PyMuPDF span-flag results. The raw integer flags are retained alongside the
  existing booleans.
- **Color:** meaningful-character-weighted packed source color decoded to 8-bit RGB.
- **Role:** conservative mapping from `ParagraphKind` to body, heading, footnote, or other.

Dominant direct evidence may remain high confidence when a small minority differs. Its mixed-style
flag is still true, distinguishing a reliable paragraph baseline from uniform inline styling.

## Geometry inference

Alignment uses ordered line/fragment rectangles. Stable following-line left edges plus stable full
non-final right edges and a short final line indicate justification. Stable left edges indicate
left alignment; stable right edges indicate right alignment; stable line centers indicate centered
text. A narrow one-line item is centered only when its center is clearly near the page center.
Ambiguous geometry remains `unknown`.

Line height is the median positive distance between retained PyMuPDF span baselines on consecutive
source lines. The ratio is line-height points divided by dominant font-size points. When baseline
origin is unavailable, consecutive line-box tops provide low-confidence evidence. A one-line
paragraph remains unknown.

First-line indent is the first line's left edge relative to the median following-line edge, so
hanging indents remain negative. Whole-paragraph left/right indents are measured against the
observed source-page region for the same role and column; headings share the body region within
their own column. Cross-column edges are never combined.

Spacing uses one canonical representation: `space_before_points` is the non-negative gap from the
immediately preceding same-page, same-column occurrence and has low confidence.
`space_after_points` remains unknown so the same physical gap is never counted twice. Missing line
baselines are not removed before pairing, preventing non-adjacent lines from creating a false
doubled line height.

## Mixed inline evidence

The baseline reports distinct flags for mixed font family, size, weight, italic, and color.
PDFTR-27 does not emit inline render runs. Encoded subfont names such as
`AGaramondPro-Regular+f6` are not rewritten as PDF subset prefixes, and a dominant black paragraph
with an isolated teal source marker remains both black-baseline and mixed-color.

## Developer inspection

Inspect all occurrences or filter by one-based source page and zero-based occurrence index:

```powershell
uv run python -m scripts.typography_inspect SOURCE.pdf --pages 1,3-4
uv run python -m scripts.typography_inspect SOURCE.pdf --occurrences 38-42 `
  --output .\temp\pdftr27\typography.json
```

The console view is compact. JSON contains all property values, confidence, provenance, fallback,
and mixed-style flags without dumping raw span arrays.

Add `--resolved` for the PDFTR-28 role baseline, final values, decision sources, and explicit
fallback reasons. The command rejects any JSON output path that resolves to the source PDF. See
[paragraph style reconstruction](style-reconstruction.md).

## Robitzsch source verification

The four-page source has 61 reconstructed occurrences: 26 body and 35 footnote. It exposes no
`ParagraphKind.HEADING`; the visually heading-like page-4 running title remains classified as body,
and PDFTR-27 does not invent a heading level.

Raw PyMuPDF spans, reconstructed paragraphs, and the derived baseline agree for representative
occurrences:

| Page / occurrence | Role | Direct baseline | Inferred geometry | Mixed/unknown evidence |
| --- | --- | --- | --- | --- |
| 1 / 4 | body | AGaramondPro-Regular, 10.959 pt, regular, black | justified; 12.472 pt line height; about 11 pt first-line indent | italic, size, font-name and color variants detected |
| 1 / 8 | footnote | AGaramondPro-Regular, 7.970 pt | left; one-line height/first indent unknown | italic/font/size variants detected |
| 3 / 39 | body | AGaramondPro-Regular, 10.959 pt | justified; 12.472 pt / 1.138 ratio | italic/font variants detected |
| 3 / 40 | body | AGaramondPro-Regular, 10.959 pt | justified; about 11 pt first-line indent | isolated 7.749 pt marker and mixed color do not replace the dominant style |
| 3 / 42 | footnote | AGaramondPro-Regular, 7.970 pt | one-line alignment and line height unknown | size/font/color variants detected |
| 4 / 49 | body (source classification) | AGaramondPro-Italic, 10.959 pt | centered; one-line height/first indent unknown | mixed italic/font evidence; no invented heading role |
| 4 / 56 | footnote | AGaramondPro-Regular, 7.970 pt | left; one-line height unknown | marker-size and color variants detected |

The source SHA-256 recorded by the baseline is
`739163d0cb4a7ec189e069ceed3b0c719db0a00c57bc5b5465139815e0d6b3de`.

## Current limitations

- Source font identity is not a render-font resolver.
- Mixed inline runs are detected but not reconstructed for rendering.
- Geometry is conservative and does not infer semantic styles from book conventions or text.
- A one-line paragraph usually cannot establish line height or first-line indent.
- `space_before_points` is observed layout evidence, not a normalized stylesheet value.
- Arbitrary columns, tables, marginalia, and complex layouts may remain unknown.
- Current production `ReflowStyle`, font-size selection, pagination, and PDF output are unchanged.
