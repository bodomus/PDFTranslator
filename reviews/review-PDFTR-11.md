# Review — PDFTR-11

## Verdict

Implementation is ready for branch review. The complete local quality gate passes, the new
behavior is covered by generated fixtures, and no real-model/CUDA/OCR dependency was introduced.

## Findings and remarks

1. Physical extraction data is no longer destructively merged. Raw blocks, typed lines, spans,
   geometry, and stable order remain available beside logical paragraphs.
2. Reconstruction is deterministic and auditable. Every adjacency decision records action,
   reasons, page, and cross-page state; uncertainty is preserved as a boundary and diagnostic.
3. The default is deliberately conservative. Columns, headings/body, separate list items,
   captions, footnotes, and repeated headers/footers do not merge by default.
4. Cross-page merge requires strong edge, alignment, column, kind, and continuation evidence.
5. Soft hyphen removal preserves CLI options, identifiers, compound tokens, and protected
   prefixes. The existing PDFTR-8 protected-token behavior remains in the translation layer.
6. Source mapping is reversible from paragraph fragments to source block ID, page, line IDs,
   order, and rectangles.
7. Translation/caching/checkpointing now operates once per logical paragraph. Legacy schema
   1.0/1.1 remains readable; new extracted/translated schemas are 1.2/1.3.
8. Renderer redacts every mapped fragment and inserts one translation on the anchor page, so a
   cross-page paragraph does not produce duplicate Russian text. Source revalidation compares the
   current reconstructed paragraph structure with JSON before modifying an output copy.
9. Pipeline behavior revision 3 invalidates incompatible resume artifacts rather than reusing old
   block-level work silently.
10. Diagnostics include the effective typed configuration, full reconstruction evidence, plus raw-line, paragraph, ambiguity, and
    cross-page metrics. Ambiguous decisions produce `READING_ORDER_AMBIGUOUS` findings.
11. Root, extract, and batch CLI workflows expose `--paragraph-reconstruction conservative|off`;
    configuration tolerances remain typed and Typer-independent.
12. No dependency, model-loading, CUDA, OCR subprocess, or source-PDF mutation change was made.
13. Focused validation passed: 5 reconstruction tests and 83 broader extraction/translation/
    rendering/pipeline/batch tests.
14. Full `scripts/check.ps1` passed with 166 tests, 1 expected skip, 86.81% coverage, Ruff, and
    mypy over 67 source files.
15. Generated end-to-end output under `temp/pytest-pdftr11d/` reopened successfully, contains
    searchable/extractable `Русский перевод`, and does not contain `English source paragraph`.
16. Synthetic benchmark result for 1,000 blocks: 999 decisions, deterministic repeated result,
    0.011996 seconds, 83,357.65 blocks/s. The result is stored only in
    `temp/PDFTR-11-benchmark.json` and is not a model/rendering benchmark.
17. Graphify preflight conclusions were source-verified; the post-change graph was rebuilt to
    1,576 nodes, 3,467 edges, and 112 communities.
18. CRG post-change reported risk 0.60 and 39 heuristic test gaps. Its test-gap detector does not
    reliably connect fixture-driven pytest, dynamic Typer registration, or Pydantic paths; direct
    source inspection and the successful test suite are authoritative. No unexpected dependant
    or disconnected production path was found.
19. The first Graphify update was denied by the restricted Windows sandbox and then succeeded with
    approved local graph writes. The first CRG panel hit CP1251 output encoding after updating;
    rerunning with UTF-8 completed cleanly.
20. The generated fixture is valid automated evidence, but this review does not claim new
    real-model, CUDA, OCR, or representative real-world PDF visual validation.
21. Remaining risk is conservative under-merging on unusual producer geometry and normal renderer
    fitting/overflow limits for complex non-rectangular paragraph shapes. These cases are surfaced
    instead of silently merged or clipped.

## Final status

Ready for commit, push, CI, and review. PDFTR-12 has not been started.
