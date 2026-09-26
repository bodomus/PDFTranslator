# Paragraph style reconstruction

PDFTR-28 converts the source-backed evidence from PDFTR-27 into a stable, versioned style contract.
The policy is pure domain logic: it consumes an in-memory `TypographyBaseline`, does not reopen a
PDF, and does not inspect installed fonts. PDFTR-29 consumes the resolved contract at the
production BODY reflow boundary, PDFTR-30 extends that boundary to HEADING, and PDFTR-31 extends it
to FOOTNOTE. All three roles now use the shared role-aware mapping in production reflow.

## Contracts and API

`pdftranslate.typography.style_models` defines:

- `StyleDecision[T]`, retaining the resolved value, original evidence value/confidence, decision
  source, fallback flag, and reason;
- `StyleBaselineValue[T]`, retaining stability, sample/support counts, dominant share, spread, and
  aggregate confidence;
- `RoleStyleBaseline` and `DocumentStyleBaseline`;
- `ResolvedParagraphStyle` and the derived `ResolvedStyleDocument` schema `1.0`;
- `FontRole` (`serif`, `sans_serif`, `monospace`, or `unknown`) without a local font path.

The production APIs are:

```python
build_document_style_baseline(typography) -> DocumentStyleBaseline
resolve_paragraph_style(evidence, baseline) -> ResolvedParagraphStyle
reconstruct_styles(typography) -> ResolvedStyleDocument
```

All models are strict, immutable, JSON-safe Pydantic domain values. Occurrence index is
authoritative; duplicate paragraph IDs remain valid.

## Stability policy

Only `high` and `medium` evidence participates in aggregation. A role property is stable only when
it has at least two supporting samples. Categorical values need at least two-thirds dominant
support. Numeric values use the median, a property-specific inlier tolerance, at least two inliers,
and at least two-thirds inlier support:

| Property | Tolerance |
| --- | ---: |
| Font size | 0.75 pt |
| Line-height ratio | 0.08 |
| Indents | 2.0 pt |
| Paragraph spacing | 2.0 pt |

The aggregate retains an unstable candidate for diagnostics but resolution never consumes it. A
role with no occurrences is absent rather than synthesized. This is why the current Robitzsch
baseline has no HEADING entry.

## Resolution precedence

The policy accepts a direct value only when it is not unknown and meets the medium confidence
floor. It then uses a stable same-role aggregate. A document-wide aggregate is allowed only for
color; all other typographic properties remain role-isolated.

| Property | Deterministic precedence | Safe terminal value |
| --- | --- | --- |
| Role | reliable evidence | `other` |
| Source font name | preserve source identity, even when uncertain | unresolved (`null`) |
| Family group | conservative normalization, then same-role group | unresolved (`null`) |
| Generic font role | inferred source name, then same-role role | `unknown` |
| Font size | paragraph → same role | 11 pt |
| Bold | paragraph → same role | regular |
| Italic | paragraph → same role | non-italic |
| Color | paragraph → same role → document color | black |
| Alignment | paragraph → same role | left |
| Line-height ratio | paragraph → same role | 1.2 |
| First/left/right indent | paragraph → same role | 0 pt |
| Space before | paragraph → same role | 0 pt |
| Space after | always the one-gap invariant | 0 pt |

Using a role/document/default value sets `used_fallback=true` and records a reason. A source
`LEFT` alignment therefore remains distinguishable from an unknown alignment safely resolved to
`LEFT`. Low-confidence source values remain visible as `evidence_value` but cannot silently
override a stable role baseline.

## Font boundary

Source font identity, normalized family group, generic font role, and a future local render font
are different concepts. Family grouping removes only recognized terminal face tokens, so
`AGaramondPro-Regular`, `AGaramondPro-Italic`, and `AGaramondPro-BoldItalic` group as
`AGaramondPro`; arbitrary names are not rewritten. Generic role inference uses a small conservative
set of recognizable family tokens. It never proves installation, scans the OS registry, downloads
a font, substitutes a path, or bypasses the existing Cyrillic glyph validation.

## Spacing and mixed styles

One observed physical gap is represented once. `space_before` may use reliable evidence or a
stable role aggregate; `space_after` resolves to zero and records the invariant as its fallback
reason. PDFTR-27 currently assigns gap-before low confidence, so real unresolved gaps safely become
zero.

Dominant paragraph values do not erase inline variation. All mixed font-family, size, weight,
italic, and color flags are copied into `ResolvedParagraphStyle`. PDFTR-32 additionally derives
immutable source-backed candidates from retained spans. A candidate is applied only when its exact
text survives in the translated paragraph with equal source/target occurrence counts and a
deterministic ordinal mapping; source offsets are never treated as translated offsets. Missing,
ambiguous, overlapping, invalid, or unsupported candidates are explicitly deferred.

## Developer inspection

Add `--resolved` to compare source evidence, the final value, decision source, fallback reason, and
fallback count:

```powershell
uv run python -m scripts.typography_inspect SOURCE.pdf --pages 1,3-4 --resolved
uv run python -m scripts.typography_inspect SOURCE.pdf --resolved `
  --output .\temp\pdftr28\resolved-styles.json
```

Filtering affects emitted paragraphs, not baseline construction. JSON therefore retains the full
document role baseline while returning only the requested occurrences. The command rejects an
`--output` path that resolves to the source PDF before extraction or writing.

## Robitzsch consistency evidence

The 61-occurrence source reconstructs deterministically as 26 BODY and 35 FOOTNOTE styles. It has
no classified HEADING occurrence and no HEADING baseline.

| Role/property | Stability result |
| --- | --- |
| BODY family | `AGaramondPro`, stable |
| BODY font size | 10.959 pt, stable (22/26 inliers) |
| BODY line-height ratio | 1.138, stable (15/15 inliers) |
| BODY weight/color | regular/black, stable |
| BODY alignment | mixed LEFT/JUSTIFIED/CENTER evidence; no stable aggregate |
| BODY first-line indent | 0 pt dominant cluster; direct ~11 pt evidence is retained per paragraph |
| FOOTNOTE family | `AGaramondPro`, stable |
| FOOTNOTE font size | 7.970 pt, stable (35/35 inliers) |
| FOOTNOTE alignment/line height | insufficient reliable evidence; explicit fallback |

Representative page 1, 3, and 4 body occurrences preserve direct 10.959 pt, justified or centered
alignment, 1.138 ratios where present, and approximately 11 pt first-line indents where present.
Representative footnotes preserve 7.970 pt and fall back explicitly for one-line geometry. Mixed
font/size/italic/color evidence survives in the resolved output. The unstable role alignment is
intentional: the policy does not turn comparable source evidence clusters into a false document
default.

The generated evidence belongs under ignored `temp/pdftr28/`; it is not committed.

## Rendering boundary

The production renderer reconstructs typography once for a schema-1.3 translated document and
maps BODY, HEADING, and FOOTNOTE styles by occurrence index. Thin role-validating adapters share one
`ResolvedParagraphStyle → ReflowStyle` mapping for font size, line-height ratio, paragraph spacing,
first/left/right indents, physical alignment, and RGB color. Duplicate paragraph IDs are therefore
safe and do not participate in style lookup.

The planner subtracts left/right indents from usable width and fails closed when they leave no safe
geometry. Space-before and first-line indent apply only to the first segment; space-after applies
only after the final segment. Alignment and paragraph indents persist across continuation pages.
Measurement and insertion use the same HTML/CSS path so the chosen font, line height, alignment,
indent, and color are evaluated consistently.

The current font boundary deliberately does not synthesize bold or italic faces or substitute a
source font family. Diagnostics retain the requested values and report both faces as unapplied.
For BODY, HEADING, and FOOTNOTE, exact proven runs may override font size and RGB color over the
resolved paragraph base. Planner prefix trials and final continuation segments clip and rebase the
same immutable runs used by insertion; both paths share one escaped HTML/CSS representation with
`scale_low=1`. Saved validation first proves exact local text and, where PyMuPDF exposes an
unambiguous span mapping, verifies the run size and color. Per-run diagnostics store hashes and
offsets rather than plaintext, with applied/deferred totals at block and document level. The
FOOTNOTE adapter preserves `heading=False`; its resolved spacing follows the same first/final
segment semantics as the other roles.
