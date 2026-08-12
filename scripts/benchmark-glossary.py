"""Deterministic end-to-end glossary benchmark using repository-local temporary files."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pdftranslate.domain.document import (
    DocumentMetadata,
    ExtractedDocument,
    SourceDocument,
)
from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox, TextBlock
from pdftranslate.glossary import GlossaryEntryMode, LoadedGlossary, load_glossary
from pdftranslate.reconstruction import (
    LogicalParagraph,
    ParagraphFragment,
    ParagraphKind,
    ParagraphReconstruction,
    ParagraphReconstructionOptions,
    ReconstructionMetrics,
    SourceBlockMapping,
)
from pdftranslate.repeated import (
    RepeatedBlockClassification,
    RepeatedElementAnalysis,
    RepeatedElementKind,
    RepeatedElementMetrics,
    RepeatedElementOptions,
    RepeatedElementPolicy,
)
from pdftranslate.translation import TranslationCache, TranslationOptions
from pdftranslate.translation.paragraphs import translate_paragraphs
from pdftranslate.translation.pipeline import TranslationProgress

PAGE_COUNT = 8
PARAGRAPHS_PER_PAGE = 8
BATCH_SIZE = 8
MAX_INPUT_TOKENS = 14
FIXED_CLOCK = datetime(2026, 1, 1, tzinfo=UTC)


class DeterministicFakeTranslator:
    """Identity-like translator that records every model-facing segment."""

    backend_name = "deterministic-fake"
    model_name = "pdftr-13a-fake-v1"
    device = "cpu"

    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def count_tokens(self, text: str) -> int:
        return len(text.split()) + 2

    def translate_batch(self, texts: Sequence[str]) -> list[str]:
        self.batches.append(list(texts))
        return [f"RU {text}" for text in texts]


@dataclass(frozen=True)
class RunMetrics:
    paragraphs: int
    glossary_matches: int
    required_targets: int
    violations: int
    false_matches: int
    translator_calls: int
    translated_segments: int
    cache_hits: int
    cache_misses: int
    elapsed_seconds: float


@dataclass(frozen=True)
class Dataset:
    document: ExtractedDocument
    canary_paragraph_ids: frozenset[str]
    translated_paragraph_ids: frozenset[str]
    preserved_paragraph_ids: frozenset[str]
    skipped_paragraph_ids: frozenset[str]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--glossary", type=Path, default=Path("docs/glossary.example.json"))
    parser.add_argument("--output", type=Path, default=Path("temp/glossary-benchmark.json"))
    args = parser.parse_args()
    output = args.output.resolve()
    temp_root = Path("temp").resolve()
    if temp_root not in output.parents:
        parser.error("--output must be below repository-local ./temp")

    output.parent.mkdir(parents=True, exist_ok=True)
    run_directory = output.parent / f"{output.stem}-run-{uuid4().hex}"
    run_directory.mkdir(parents=True)
    glossary = load_glossary(args.glossary)
    changed_glossary = _changed_glossary(glossary, run_directory / "changed-glossary.json")
    dataset = _build_dataset(glossary)
    baseline_cache = run_directory / "baseline-cache.sqlite3"
    glossary_cache = run_directory / "glossary-cache.sqlite3"

    baseline, baseline_result, baseline_translator = _run(
        dataset, cache_path=baseline_cache, glossary=None
    )
    cold, cold_result, cold_translator = _run(dataset, cache_path=glossary_cache, glossary=glossary)
    warm, warm_result, warm_translator = _run(dataset, cache_path=glossary_cache, glossary=glossary)
    changed, changed_result, changed_translator = _run(
        dataset, cache_path=glossary_cache, glossary=changed_glossary
    )

    assertions = _assert_results(
        dataset=dataset,
        glossary=glossary,
        changed_glossary=changed_glossary,
        baseline=baseline,
        baseline_result=baseline_result,
        baseline_translator=baseline_translator,
        cold=cold,
        cold_result=cold_result,
        cold_translator=cold_translator,
        warm=warm,
        warm_result=warm_result,
        warm_translator=warm_translator,
        changed=changed,
        changed_result=changed_result,
        changed_translator=changed_translator,
    )
    report = {
        "schema_version": "2.0",
        "pipeline": [
            "LogicalParagraph",
            "repeated policy",
            "glossary",
            "protect_text",
            "segmentation",
            "deterministic fake translator",
            "restore",
            "glossary validation",
            "TranslationCache",
        ],
        "dataset": {
            "pages": PAGE_COUNT,
            "paragraphs": len(dataset.document.paragraphs),
            "translatable_paragraphs": len(dataset.translated_paragraph_ids),
            "preserved_paragraphs": len(dataset.preserved_paragraph_ids),
            "skipped_paragraphs": len(dataset.skipped_paragraph_ids),
            "canary_paragraphs": len(dataset.canary_paragraph_ids),
        },
        "cache_isolation": {
            "strategy": (
                "dedicated new SQLite databases; glossary scenarios share only the glossary cache"
            ),
            "database_count": 2,
        },
        "glossary": {
            "entries": len(glossary.document.entries),
            "fingerprint": glossary.fingerprint,
            "changed_fingerprint": changed_glossary.fingerprint,
        },
        "runs": {
            "baseline_no_glossary": asdict(baseline),
            "glossary_cold": asdict(cold),
            "glossary_warm_same_fingerprint": asdict(warm),
            "glossary_changed_target": asdict(changed),
        },
        "assertions": assertions,
        "claim": (
            "Measures the complete logical-paragraph translation path with a deterministic fake "
            "translator and real SQLite caches; it does not measure NLLB semantic quality."
        ),
    }
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output)
    return 0


def _run(
    dataset: Dataset,
    *,
    cache_path: Path,
    glossary: LoadedGlossary | None,
) -> tuple[RunMetrics, ExtractedDocument, DeterministicFakeTranslator]:
    translator = DeterministicFakeTranslator()
    started = time.perf_counter()
    with TranslationCache(cache_path) as cache:
        result = translate_paragraphs(
            dataset.document,
            translator=translator,
            cache=cache,
            options=TranslationOptions(
                batch_size=BATCH_SIZE,
                max_input_tokens=MAX_INPUT_TOKENS,
                glossary=glossary,
            ),
            resume_document=None,
            checkpoint=None,
            progress=None,
            clock=lambda: FIXED_CLOCK,
            progress_factory=TranslationProgress,
        )
    elapsed = time.perf_counter() - started
    metadata = result.translation
    assert metadata is not None
    glossary_evidence = metadata.glossary
    false_matches = 0
    if glossary_evidence is not None:
        false_matches = sum(
            len(item.occurrences)
            for item in glossary_evidence.paragraphs
            if item.paragraph_id in dataset.canary_paragraph_ids
        )
    return (
        RunMetrics(
            paragraphs=len(result.paragraphs),
            glossary_matches=(
                glossary_evidence.statistics.applied_occurrences
                if glossary_evidence is not None
                else 0
            ),
            required_targets=(
                glossary_evidence.statistics.mandatory_translation_occurrences
                if glossary_evidence is not None
                else 0
            ),
            violations=(
                glossary_evidence.statistics.violations if glossary_evidence is not None else 0
            ),
            false_matches=false_matches,
            translator_calls=len(translator.batches),
            translated_segments=metadata.statistics.translated_segments,
            cache_hits=metadata.statistics.cache_hits,
            cache_misses=metadata.statistics.cache_misses,
            elapsed_seconds=elapsed,
        ),
        result,
        translator,
    )


def _build_dataset(glossary: LoadedGlossary) -> Dataset:
    translate_entry = next(
        item for item in glossary.document.entries if item.mode is GlossaryEntryMode.TRANSLATE
    )
    preserve_entry = next(
        item for item in glossary.document.entries if item.mode is GlossaryEntryMode.PRESERVE
    )
    pages: list[ExtractedPage] = []
    paragraphs: list[LogicalParagraph] = []
    classifications: list[RepeatedBlockClassification] = []
    canary_ids: set[str] = set()
    translated_ids: set[str] = set()
    preserved_ids: set[str] = set()
    skipped_ids: set[str] = set()
    y_positions = (20.0, 100.0, 185.0, 270.0, 420.0, 520.0, 770.0, 335.0)

    for page_number in range(1, PAGE_COUNT + 1):
        texts = (
            f"{translate_entry.source} operational briefing.",
            (
                f"{translate_entry.source} tracks {preserve_entry.source} on "
                f"2026-08-{page_number:02d}. The analyst reads "
                f"https://example.test/page/{page_number} and "
                f"C:\\records\\case-{page_number}.txt. This extended sentence contains "
                "alpha beta gamma delta epsilon zeta eta theta."
            ),
            (
                f"The {translate_entry.source} reviews operational term {page_number} in a "
                "deterministic paragraph."
            ),
            (
                f"{translate_entry.source}s and {preserve_entry.source}0 are near misses on "
                f"control page {page_number}."
            ),
            f"{translate_entry.source} confirms {preserve_entry.source} for page {page_number}.",
            f"Protected asset {preserve_entry.source} belongs to batch {page_number}.",
            str(page_number),
            "DRAFT",
        )
        blocks: list[TextBlock] = []
        for order, (text, y0) in enumerate(zip(texts, y_positions, strict=True)):
            block_id = f"p{page_number:04d}-b{order:04d}"
            paragraph_id = f"paragraph-{page_number:02d}-{order:02d}"
            bbox = BoundingBox(x0=50, y0=y0, x1=550, y1=y0 + 14)
            block = TextBlock(
                id=block_id,
                text=text,
                bbox=bbox,
                original_order=order,
                normalized_order=order,
            )
            blocks.append(block)
            if order == 0:
                paragraph_kind = ParagraphKind.HEADER
                repeated_kind = RepeatedElementKind.RUNNING_HEADER
                policy = RepeatedElementPolicy.TRANSLATE
            elif order == 6:
                paragraph_kind = ParagraphKind.PAGE_NUMBER
                repeated_kind = RepeatedElementKind.PAGE_NUMBER
                policy = RepeatedElementPolicy.PRESERVE
                preserved_ids.add(paragraph_id)
            elif order == 7:
                paragraph_kind = ParagraphKind.WATERMARK
                repeated_kind = RepeatedElementKind.WATERMARK_CANDIDATE
                policy = RepeatedElementPolicy.SKIP
                skipped_ids.add(paragraph_id)
            else:
                paragraph_kind = ParagraphKind.BODY
                repeated_kind = RepeatedElementKind.BODY
                policy = RepeatedElementPolicy.TRANSLATE
            if policy is RepeatedElementPolicy.TRANSLATE:
                translated_ids.add(paragraph_id)
            if order == 3:
                canary_ids.add(paragraph_id)
            mapping = SourceBlockMapping(
                source_block_id=block_id,
                page_number=page_number,
                bbox=bbox,
                original_order=order,
                normalized_order=order,
            )
            fragment = ParagraphFragment(
                id=f"{paragraph_id}-fragment",
                text=text,
                bbox=bbox,
                mapping=mapping,
                column=0,
            )
            paragraphs.append(
                LogicalParagraph(
                    id=paragraph_id,
                    text=text,
                    kind=paragraph_kind,
                    anchor_page_number=page_number,
                    bbox=bbox,
                    fragments=(fragment,),
                )
            )
            classifications.append(
                RepeatedBlockClassification(
                    block_id=block_id,
                    page_number=page_number,
                    bbox=bbox,
                    kind=repeated_kind,
                    confidence=1.0,
                    group_id=(f"group-{order}" if order in {0, 6, 7} else None),
                    policy=policy,
                )
            )
        pages.append(
            ExtractedPage(
                page_number=page_number,
                source_index=page_number - 1,
                width=600,
                height=800,
                rotation=0,
                classification=PageClassification.TEXT,
                text_blocks=tuple(blocks),
            )
        )

    paragraph_count = len(paragraphs)
    reconstruction = ParagraphReconstruction(
        mode="conservative",
        options=ParagraphReconstructionOptions(),
        metrics=ReconstructionMetrics(
            raw_blocks=paragraph_count,
            raw_lines=paragraph_count,
            logical_paragraphs=paragraph_count,
            merged_fragments=0,
            ambiguous_decisions=0,
            cross_page_merges=0,
            soft_hyphens_removed=0,
        ),
    )
    repeated = RepeatedElementAnalysis(
        mode="auto",
        options=RepeatedElementOptions(),
        blocks=tuple(classifications),
        metrics=RepeatedElementMetrics(
            total_blocks=paragraph_count,
            classified_blocks=paragraph_count,
            ambiguous_blocks=0,
            groups=3,
            counts={
                RepeatedElementKind.BODY.value: PAGE_COUNT * 5,
                RepeatedElementKind.RUNNING_HEADER.value: PAGE_COUNT,
                RepeatedElementKind.PAGE_NUMBER.value: PAGE_COUNT,
                RepeatedElementKind.WATERMARK_CANDIDATE.value: PAGE_COUNT,
            },
        ),
    )
    document = ExtractedDocument(
        schema_version="1.2",
        source=SourceDocument(path="benchmark-source.pdf", file_size=0, sha256="0" * 64),
        page_count=PAGE_COUNT,
        selected_pages=tuple(range(1, PAGE_COUNT + 1)),
        metadata=DocumentMetadata(),
        encrypted=False,
        password_required=False,
        pages=tuple(pages),
        paragraphs=tuple(paragraphs),
        reconstruction=reconstruction,
        repeated_elements=repeated,
    )
    return Dataset(
        document=document,
        canary_paragraph_ids=frozenset(canary_ids),
        translated_paragraph_ids=frozenset(translated_ids),
        preserved_paragraph_ids=frozenset(preserved_ids),
        skipped_paragraph_ids=frozenset(skipped_ids),
    )


def _changed_glossary(glossary: LoadedGlossary, path: Path) -> LoadedGlossary:
    payload = glossary.document.model_dump(mode="json")
    changed = False
    for entry in payload["entries"]:
        if entry["mode"] == GlossaryEntryMode.TRANSLATE.value and not changed:
            entry["target"] = f"{entry['target']} (изменено)"
            changed = True
    if not changed:
        raise ValueError("benchmark glossary requires a translate entry")
    version = str(payload["glossary_version"]).split(".")
    version[-1] = str(int(version[-1]) + 1)
    payload["glossary_version"] = ".".join(version)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return load_glossary(path)


def _assert_results(
    *,
    dataset: Dataset,
    glossary: LoadedGlossary,
    changed_glossary: LoadedGlossary,
    baseline: RunMetrics,
    baseline_result: ExtractedDocument,
    baseline_translator: DeterministicFakeTranslator,
    cold: RunMetrics,
    cold_result: ExtractedDocument,
    cold_translator: DeterministicFakeTranslator,
    warm: RunMetrics,
    warm_result: ExtractedDocument,
    warm_translator: DeterministicFakeTranslator,
    changed: RunMetrics,
    changed_result: ExtractedDocument,
    changed_translator: DeterministicFakeTranslator,
) -> dict[str, bool]:
    del baseline_result, baseline_translator
    translate_entry = next(
        item for item in glossary.document.entries if item.mode is GlossaryEntryMode.TRANSLATE
    )
    changed_entry = next(
        item for item in changed_glossary.document.entries if item.id == translate_entry.id
    )
    expected_paragraphs = PAGE_COUNT * PARAGRAPHS_PER_PAGE
    expected_translatable = len(dataset.translated_paragraph_ids)
    expected_unique_sources = PAGE_COUNT * 5 + 1
    expected_in_run_hits = expected_translatable - expected_unique_sources
    expected_matches = PAGE_COUNT * 7
    expected_required_targets = PAGE_COUNT * 4

    assert baseline.paragraphs == cold.paragraphs == warm.paragraphs == changed.paragraphs
    assert baseline.paragraphs == expected_paragraphs
    assert baseline.cache_misses == cold.cache_misses == changed.cache_misses
    assert baseline.cache_misses == expected_unique_sources
    assert baseline.cache_hits == cold.cache_hits == changed.cache_hits == expected_in_run_hits
    assert cold.glossary_matches == warm.glossary_matches == changed.glossary_matches
    assert cold.glossary_matches == expected_matches
    assert cold.required_targets == warm.required_targets == changed.required_targets
    assert cold.required_targets == expected_required_targets
    assert cold.violations == warm.violations == changed.violations == 0
    assert cold.false_matches == warm.false_matches == changed.false_matches == 0
    assert baseline.translator_calls > 0 and cold.translator_calls > 0
    assert changed.translator_calls > 0
    assert baseline.translated_segments > baseline.cache_misses
    assert cold.translated_segments > cold.cache_misses
    assert warm.cache_hits == expected_translatable
    assert warm.cache_misses == warm.translator_calls == warm.translated_segments == 0
    assert glossary.fingerprint != changed_glossary.fingerprint
    assert changed.cache_misses > 0
    assert sum(len(batch) for batch in cold_translator.batches) == cold.translated_segments
    assert sum(len(batch) for batch in changed_translator.batches) == changed.translated_segments
    assert warm_translator.batches == []

    cold_outputs = _translated_outputs(cold_result, dataset.translated_paragraph_ids)
    warm_outputs = _translated_outputs(warm_result, dataset.translated_paragraph_ids)
    changed_outputs = _translated_outputs(changed_result, dataset.translated_paragraph_ids)
    assert cold_outputs == warm_outputs
    assert (
        sum(text.count(translate_entry.target) for text in cold_outputs)
        == expected_required_targets
    )
    assert (
        sum(text.count(changed_entry.target) for text in changed_outputs)
        == expected_required_targets
    )
    assert all("__PDFTR_" not in text for text in cold_outputs + changed_outputs)
    assert all(
        paragraph.translated_text == paragraph.text
        for paragraph in cold_result.paragraphs
        if paragraph.id in dataset.preserved_paragraph_ids
    )
    assert all(
        paragraph.translated_text == ""
        for paragraph in cold_result.paragraphs
        if paragraph.id in dataset.skipped_paragraph_ids
    )
    assert all(
        expected in "\n".join(cold_outputs)
        for expected in ("2026-08-01", "https://example.test/page/1", "C:\\records\\case-1.txt")
    )
    cold_inputs = [text for batch in cold_translator.batches for text in batch]
    assert "DRAFT" not in cold_inputs
    assert not any(text.strip().isdigit() for text in cold_inputs)

    return {
        "logical_paragraph_count_in_range": 50 <= expected_paragraphs <= 100,
        "full_translate_paragraphs_path_completed": True,
        "repeated_preserve_and_skip_proven": True,
        "protected_tokens_restored": True,
        "segmentation_proven": cold.translated_segments > cold.cache_misses,
        "no_placeholder_leaks": True,
        "same_glossary_cache_reuse_proven": warm.cache_hits == expected_translatable,
        "changed_target_cache_miss_proven": changed.cache_misses == expected_unique_sources,
        "glossary_fingerprints_differ": glossary.fingerprint != changed_glossary.fingerprint,
    }


def _translated_outputs(document: ExtractedDocument, paragraph_ids: frozenset[str]) -> list[str]:
    return [
        paragraph.translated_text or ""
        for paragraph in document.paragraphs
        if paragraph.id in paragraph_ids
    ]


if __name__ == "__main__":
    raise SystemExit(main())
