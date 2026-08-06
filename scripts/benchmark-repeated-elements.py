"""Deterministic generated benchmark for PDFTR-12 repeated-element noise reduction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox, TextBlock, TextLine, TextSpan
from pdftranslate.repeated import RepeatedElementKind, classify_repeated_elements


def _block(page: int, order: int, text: str, y0: float, *, font_size: float = 10) -> TextBlock:
    identifier = f"p{page:04d}-b{order:04d}"
    box = BoundingBox(x0=50, y0=y0, x1=550, y1=y0 + 14)
    span = TextSpan(text=text, bbox=box, font_size=font_size)
    line = TextLine(
        id=f"{identifier}-l0001",
        text=text,
        bbox=box,
        original_order=0,
        spans=(span,),
    )
    return TextBlock(
        id=identifier,
        text=text,
        bbox=box,
        original_order=order,
        normalized_order=order,
        spans=(span,),
        lines=(line,),
    )


def _fixture() -> tuple[ExtractedPage, ...]:
    return tuple(
        ExtractedPage(
            page_number=number,
            source_index=number - 1,
            width=600,
            height=800,
            rotation=0,
            classification=PageClassification.TEXT,
            text_blocks=(
                _block(number, 0, "Odd handbook" if number % 2 else "Even handbook", 20),
                _block(number, 1, f"Unique body paragraph {number}.", 150),
                _block(number, 2, "Copyright 2026. All rights reserved.", 750, font_size=8),
                _block(number, 3, str(number), 775),
            ),
        )
        for number in range(1, 9)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("temp/pdftr12-benchmark/repeated-elements.json"),
    )
    args = parser.parse_args()
    output: Path = args.output
    pages = _fixture()
    result = classify_repeated_elements(pages)
    counts = result.metrics.counts
    baseline_body_blocks = sum(len(page.text_blocks) for page in pages)
    classified_body_blocks = counts.get(RepeatedElementKind.BODY.value, 0)
    removed_body_noise = baseline_body_blocks - classified_body_blocks
    payload = {
        "fixture": "generated-eight-page-alternating-header-footer-sequence-v1",
        "pages": len(pages),
        "baseline_body_blocks": baseline_body_blocks,
        "classified_body_blocks": classified_body_blocks,
        "removed_body_noise_blocks": removed_body_noise,
        "noise_reduction_ratio": removed_body_noise / baseline_body_blocks,
        "groups": result.metrics.groups,
        "ambiguous_blocks": result.metrics.ambiguous_blocks,
        "counts": counts,
    }
    expected = {
        "body": 8,
        "page_number": 8,
        "running_header": 8,
        "repeated_boilerplate": 8,
    }
    if any(counts.get(kind) != count for kind, count in expected.items()):
        raise SystemExit(f"unexpected benchmark classification: {counts}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown = output.with_suffix(".md")
    markdown.write_text(
        "# PDFTR-12 Repeated-element Benchmark\n\n"
        f"- Pages: {len(pages)}\n"
        f"- Baseline body blocks: {baseline_body_blocks}\n"
        f"- Classified body blocks: {classified_body_blocks}\n"
        f"- Removed body-noise blocks: {removed_body_noise}\n"
        f"- Noise reduction: {payload['noise_reduction_ratio']:.1%}\n"
        f"- Ambiguous blocks: {result.metrics.ambiguous_blocks}\n"
        f"- Counts: `{json.dumps(counts, sort_keys=True)}`\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
