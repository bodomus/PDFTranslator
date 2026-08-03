"""Deterministic generated-input benchmark for PDFTR-11 reconstruction."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from pdftranslate.domain.page import ExtractedPage, PageClassification
from pdftranslate.domain.text_block import BoundingBox, TextBlock
from pdftranslate.reconstruction import reconstruct_paragraphs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocks", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.blocks < 2:
        parser.error("--blocks must be at least 2")

    blocks = tuple(
        TextBlock(
            id=f"p0001-b{index + 1:04d}",
            text=f"generated continuation {index}",
            bbox=BoundingBox(
                x0=50,
                y0=20 + index * 12,
                x1=550,
                y1=30 + index * 12,
            ),
            original_order=index,
            normalized_order=index,
        )
        for index in range(arguments.blocks)
    )
    page = ExtractedPage(
        page_number=1,
        source_index=0,
        width=600,
        height=max(800, 40 + arguments.blocks * 12),
        rotation=0,
        classification=PageClassification.TEXT,
        text_blocks=blocks,
    )

    started = time.perf_counter()
    first = reconstruct_paragraphs((page,))
    elapsed = time.perf_counter() - started
    second = reconstruct_paragraphs((page,))
    deterministic = first == second
    payload = {
        "schema_version": "1.0",
        "generated_blocks": arguments.blocks,
        "logical_paragraphs": len(first.paragraphs),
        "decisions": len(first.evidence.decisions),
        "merged_fragments": first.evidence.metrics.merged_fragments,
        "elapsed_seconds": round(elapsed, 6),
        "blocks_per_second": round(arguments.blocks / elapsed, 2),
        "deterministic_repeat": deterministic,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    if arguments.output is not None:
        output = arguments.output.resolve()
        repository_temp = (Path.cwd() / "temp").resolve()
        if output != repository_temp and repository_temp not in output.parents:
            parser.error("--output must be below repository-local ./temp")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
