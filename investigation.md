# PDFTR-3 Investigation

## Scope and baseline

PDFTR-3 is a Level 2 change: local ML inference, device selection, segmentation, SQLite translation memory, resumable output, schema extension, and a public CLI command.

- Repository: `J:/Projects/Python/PDFTranslator`
- Branch: `master`
- Baseline: `84e3e7a45bdb3aaa2dd87d8a7bb9ab0515946f55`
- Python: 3.12.10
- uv: 0.5.26
- Existing input contract: immutable `ExtractedDocument` schema 1.0
- Pre-existing untracked input preserved: `Tasks/PDFTR-3-local-translation-engine.md`

The complete ticket source is already attached to PDFTR-3 in YouTrack and is mirrored under `Tickets/`. PDFTR-1 and PDFTR-2 implementation commits are in current history.

## Graph preflight

Graphify 0.9.8 reused the existing graph. Ticket-focused BFS identified CLI, `ExtractedDocument`, `TextBlock`, settings, serialization, extraction, and adjacent tests. Source validation confirmed that `src/pdftranslate/cli.py` is the composition root; translation can consume extracted JSON without importing or modifying PyMuPDF; original block text can remain immutable; serialization owns atomic writes; and settings own the cache root.

Code-review-graph was updated to the baseline and contains 126 nodes and 874 edges across 26 files. Its communities separate PDF, CLI/CUDA, domain, serialization, and tests. Exact queries showed `document_from_json` is currently test-only while `write_document_json` is reached by extraction. New read/translate/write reachability and post-change graph refresh are therefore required.

## External-library findings

Context7 was used for current Transformers and PyTorch documentation. Tokenizers do not truncate unless requested; explicit max length, padding, tensor output, and length reporting are available. PyTorch documents `torch.cuda.is_available()`, requires `model.eval()` in addition to `torch.inference_mode()`, and recommends leaving an OOM exception handler before retrying.

The official NLLB model card documents direct `AutoTokenizer` and `AutoModelForSeq2SeqLM` loading. Its repository is approximately 2.48 GB at investigation time; documentation will treat this only as an estimate.

## Decisions

1. Add a small `Translator` protocol; keep Transformers and PyTorch types inside the NLLB adapter. Construct one backend per CLI process.
2. Extend schema 1.0 compatibly to 1.1 with optional translated block text and translation metadata. Preserve original text unchanged.
3. Keep skip rules, protected tokens, sentence/paragraph segmentation, and deterministic recombination in pure helpers.
4. Use SQLite under the configured cache root. Keys include backend, model, language pair, and normalized source text. Wrap corruption/errors clearly.
5. Write atomic checkpoints. Completed blocks and settings metadata support interruption and validated `--resume`.
6. `auto` probes CUDA usability and falls back to CPU. Explicit CUDA failures are not masked. Automatic CUDA OOM fallback is bounded to one CPU transition; batch retry is bounded by halving.
7. Offline mode uses local files only. Normal mode reports possible download before construction and uses the configured model cache.
8. Add Transformers and PyTorch for the required NLLB backend. Tests inject fakes and never load or download a model.

## Invariants and limitations

Translation imports neither Typer nor PyMuPDF. Input schema 1.0 remains readable. Backend tokenization never truncates; segmentation proves limits first. Empty/whitespace, page-number, code-like, measurement-only, and identifier-only blocks bypass the model. Embedded URLs, emails, paths, measurements, and identifiers are restored exactly or processing fails. Default cache/resume data is outside the repository. Source PDF identity and original text remain unchanged.

NLLB quality, remote availability, CUDA usability, and VRAM consumption cannot be proven in unit tests. Real-model execution remains an explicit local integration activity. Sentence splitting is deterministic and conservative, not a full linguistic boundary detector.
