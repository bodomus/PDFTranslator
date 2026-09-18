# Review — PDFTR-21

## Verdict

Ready for review. Foreign-language preservation is now explicit, deterministic, serialized,
cache-safe, and proven with the real CUDA Robitzsch artifact.

## What was reviewed

- Confident Latin and Greek whole units bypass NLLB and remain source-exact.
- Mixed English prose is translated while required Latin/French terms and Greek runs never enter
  model inference and are restored exactly.
- Ordinary English remains on the translation path; Latin script alone is never preservation
  evidence.
- Explicit glossary translation overrides automatic whole-unit preservation; glossary and generic
  protected-token validation remain intact.
- Per-occurrence classifications, reasons, counts, page/paragraph identity, and inference evidence
  survive JSON round-trip and appear in privacy-safe diagnostics.
- Translation revision 5 prevents old cache, partial resume, or completed workspace artifacts from
  bypassing the new policy.
- Repeated-element/marker behavior, output validation, and strict render completeness remain
  unchanged.

## Evidence

- Focused translation/glossary/diagnostics regressions passed.
- Final full repository gate: 250 passed, 1 skipped, 88.65% coverage.
- Wiki lint: 12 pages, 58 links, no errors or warnings.
- Ruff and mypy passed.
- Post-change CRG: 1123 indexed rows, 24 changed symbols, risk score 0.55.
- Refreshed Graphify: 2591 nodes, 5218 edges, 190 communities; the new translation module is
  reachable from paragraph orchestration and covered by regression tests.
- Real CUDA Robitzsch translation: 61/61 units completed; 7 whole units and 12 spans preserved.
  Both Latin stanzas are source-equal, Greek remains Greek, inline terminology is exact, and
  surrounding prose translates to Russian.
- Rendering then failed safely on the known 21 PDFTR-20 overflow occurrences; no incomplete final
  PDF was published.

## Scope and residual risk

No dependency, universal language detector, translation model, OCR change, CLI option, renderer
relaxation, or reflow was introduced. Conservative Latin heuristics may leave ambiguous foreign
text on the normal translation path, and splitting around protected spans can affect nearby model
fluency; both are explicit tradeoffs in favor of avoiding silent source corruption.
