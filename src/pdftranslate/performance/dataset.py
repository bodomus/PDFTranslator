"""Public-safe deterministic logical-paragraph performance dataset."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from pdftranslate.domain.document import DocumentMetadata, ExtractedDocument, SourceDocument
from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox, TextBlock
from pdftranslate.glossary import LoadedGlossary
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

DATASET_VERSION = "1.0.0"
PAGE_COUNT = 10
PARAGRAPHS_PER_PAGE = 12


@dataclass(frozen=True)
class PerformanceDataset:
    document: ExtractedDocument
    sha256: str
    length_classes: dict[str, int]
    paragraph_length_classes: tuple[str, ...]
    protected_tokens: tuple[str, ...]
    glossary: LoadedGlossary | None

    def select_length_class(self, name: str) -> PerformanceDataset:
        """Return a translation-valid paragraph subset for one length scenario."""
        selected = tuple(
            paragraph
            for paragraph, length_class in zip(
                self.document.paragraphs, self.paragraph_length_classes, strict=True
            )
            if length_class == name
        )
        if not selected:
            raise ValueError(f"unknown or empty length class: {name}")
        identity = json.dumps(
            [paragraph.text for paragraph in selected],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return PerformanceDataset(
            document=self.document.model_copy(update={"paragraphs": selected}),
            sha256=hashlib.sha256(identity).hexdigest(),
            length_classes={name: len(selected)},
            paragraph_length_classes=(name,) * len(selected),
            protected_tokens=self.protected_tokens,
            glossary=self.glossary,
        )


def build_performance_dataset(glossary: LoadedGlossary | None = None) -> PerformanceDataset:
    pages: list[ExtractedPage] = []
    paragraphs: list[LogicalParagraph] = []
    classifications: list[RepeatedBlockClassification] = []
    paragraph_length_classes: list[str] = []
    lengths = {"short": 0, "medium": 0, "long": 0, "forced_segmentation": 0}
    protected = ("ZX-1900-1", "2026-08-12", "https://example.test/api", "C:\\data\\run-14.json")

    for page_number in range(1, PAGE_COUNT + 1):
        texts = _page_texts(page_number)
        blocks: list[TextBlock] = []
        for order, (text, length_class) in enumerate(texts):
            block_id = f"p{page_number:04d}-b{order:04d}"
            paragraph_id = f"perf-{page_number:02d}-{order:02d}"
            y0 = 15.0 + order * 62.0
            bbox = BoundingBox(x0=45, y0=y0, x1=555, y1=min(y0 + 48, 790))
            block = TextBlock(
                id=block_id,
                text=text,
                bbox=bbox,
                original_order=order,
                normalized_order=order,
            )
            blocks.append(block)
            kind, repeated_kind, policy = _policy(order)
            mapping = SourceBlockMapping(
                source_block_id=block_id,
                page_number=page_number,
                bbox=bbox,
                original_order=order,
                normalized_order=order,
            )
            paragraphs.append(
                LogicalParagraph(
                    id=paragraph_id,
                    text=text,
                    kind=kind,
                    anchor_page_number=page_number,
                    bbox=bbox,
                    fragments=(
                        ParagraphFragment(
                            id=f"{paragraph_id}-fragment",
                            text=text,
                            bbox=bbox,
                            mapping=mapping,
                            column=0,
                        ),
                    ),
                )
            )
            paragraph_length_classes.append(length_class)
            classifications.append(
                RepeatedBlockClassification(
                    block_id=block_id,
                    page_number=page_number,
                    bbox=bbox,
                    kind=repeated_kind,
                    confidence=1.0,
                    group_id=f"repeated-{order}" if order in {0, 1, 10, 11} else None,
                    policy=policy,
                )
            )
            lengths[length_class] += 1
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

    count = len(paragraphs)
    reconstruction = ParagraphReconstruction(
        mode="conservative",
        options=ParagraphReconstructionOptions(),
        metrics=ReconstructionMetrics(
            raw_blocks=count,
            raw_lines=count,
            logical_paragraphs=count,
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
            total_blocks=count,
            classified_blocks=count,
            ambiguous_blocks=0,
            groups=4,
            counts={
                RepeatedElementKind.BODY.value: PAGE_COUNT * 8,
                RepeatedElementKind.RUNNING_HEADER.value: PAGE_COUNT,
                RepeatedElementKind.REPEATED_BOILERPLATE.value: PAGE_COUNT,
                RepeatedElementKind.PAGE_NUMBER.value: PAGE_COUNT,
                RepeatedElementKind.WATERMARK_CANDIDATE.value: PAGE_COUNT,
            },
        ),
    )
    document = ExtractedDocument(
        schema_version="1.2",
        source=SourceDocument(path="public-performance-fixture.pdf", file_size=0, sha256="0" * 64),
        page_count=PAGE_COUNT,
        selected_pages=tuple(range(1, PAGE_COUNT + 1)),
        metadata=DocumentMetadata(title="PDFTR-14 public synthetic fixture"),
        encrypted=False,
        password_required=False,
        probable_source_language="en",
        pages=tuple(pages),
        paragraphs=tuple(paragraphs),
        reconstruction=reconstruction,
        repeated_elements=repeated,
    )
    identity = json.dumps(
        [paragraph.text for paragraph in paragraphs], ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return PerformanceDataset(
        document=document,
        sha256=hashlib.sha256(identity).hexdigest(),
        length_classes=lengths,
        paragraph_length_classes=tuple(paragraph_length_classes),
        protected_tokens=protected,
        glossary=glossary,
    )


def _page_texts(page_number: int) -> tuple[tuple[str, str], ...]:
    variant = (page_number - 1) % 5
    medium = (
        f"The Secret Service validates system profile {variant} on 2026-08-12 and keeps "
        "ZX-1900-1 unchanged during translation."
    )
    long = (
        f"Technical procedure {variant} reads https://example.test/api and C:\\data\\run-14.json "
        "before comparing deterministic measurements, checking protected identifiers, preserving "
        "dates and numbers, and recording enough ordinary prose to exercise sentence segmentation "
        "through the same production logical paragraph path used by translated documents."
    )
    forced = " ".join(
        (
            f"The controlled system {variant} completes verification step {index} and records "
            "a stable result for the engineering team."
        )
        for index in range(20)
    )
    return (
        ("PDFTranslate performance benchmark", "short"),
        ("Confidential synthetic benchmark boilerplate.", "short"),
        (f"System status {variant} is ready.", "short"),
        (medium, "medium"),
        (long, "long"),
        (forced, "forced_segmentation"),
        (f"Warning {variant}: verify pressure 42.5 kPa before startup.", "medium"),
        (
            f"Operator {variant} records batch AB-1200 and email ops{variant}@example.test.",
            "medium",
        ),
        (f"Heading for controlled section {variant}", "short"),
        (f"List item {variant}: inspect, translate, validate, and publish.", "medium"),
        (str(page_number), "short"),
        ("DRAFT", "short"),
    )


def _policy(
    order: int,
) -> tuple[ParagraphKind, RepeatedElementKind, RepeatedElementPolicy]:
    if order == 0:
        return (
            ParagraphKind.HEADER,
            RepeatedElementKind.RUNNING_HEADER,
            RepeatedElementPolicy.TRANSLATE,
        )
    if order == 1:
        return (
            ParagraphKind.BOILERPLATE,
            RepeatedElementKind.REPEATED_BOILERPLATE,
            RepeatedElementPolicy.TRANSLATE,
        )
    if order == 10:
        return (
            ParagraphKind.PAGE_NUMBER,
            RepeatedElementKind.PAGE_NUMBER,
            RepeatedElementPolicy.PRESERVE,
        )
    if order == 11:
        return (
            ParagraphKind.WATERMARK,
            RepeatedElementKind.WATERMARK_CANDIDATE,
            RepeatedElementPolicy.SKIP,
        )
    if order == 8:
        return ParagraphKind.HEADING, RepeatedElementKind.BODY, RepeatedElementPolicy.TRANSLATE
    if order == 9:
        return ParagraphKind.LIST_ITEM, RepeatedElementKind.BODY, RepeatedElementPolicy.TRANSLATE
    return ParagraphKind.BODY, RepeatedElementKind.BODY, RepeatedElementPolicy.TRANSLATE
