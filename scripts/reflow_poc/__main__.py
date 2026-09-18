"""Command-line entry point for the isolated PDFTR-22 reflow PoC."""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.reflow_poc.models import Rect
from scripts.reflow_poc.planner import PlannerOptions
from scripts.reflow_poc.pymupdf_adapter import run_poc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan and render a controlled single-column body-text reflow proof of concept."
    )
    parser.add_argument("source", type=Path, help="Immutable source PDF")
    parser.add_argument("translated", type=Path, help="Completed schema 1.3 translated JSON")
    parser.add_argument("--source-page", type=int, required=True, help="One-based source page")
    parser.add_argument(
        "--occurrences",
        type=_parse_indexes,
        required=True,
        help="Reviewed zero-based occurrence indexes, for example 38-41",
    )
    parser.add_argument(
        "--allow-ambiguous-occurrences",
        type=_parse_indexes,
        default=(),
        help="Explicit reviewed overrides; must be a subset of --occurrences",
    )
    parser.add_argument(
        "--region",
        type=_parse_rect,
        required=True,
        help="Reviewed body rectangle x0,y0,x1,y1",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--debug-output", type=Path)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--font-size", type=float, default=12.0)
    parser.add_argument("--line-height", type=float, default=1.2)
    parser.add_argument("--paragraph-spacing", type=float, default=6.0)
    parser.add_argument("--max-new-pages", type=int, default=2)
    parser.add_argument("--overwrite", action="store_true")
    arguments = parser.parse_args()

    layout = run_poc(
        arguments.source,
        arguments.translated,
        source_page_number=arguments.source_page,
        occurrence_indexes=arguments.occurrences,
        region_rect=arguments.region,
        output_path=arguments.output,
        plan_path=arguments.plan,
        debug_output_path=arguments.debug_output,
        allow_ambiguous_occurrences=arguments.allow_ambiguous_occurrences,
        font_path=arguments.font,
        planner_options=PlannerOptions(
            font_size=arguments.font_size,
            line_height=arguments.line_height,
            paragraph_spacing=arguments.paragraph_spacing,
        ),
        max_new_pages=arguments.max_new_pages,
        overwrite=arguments.overwrite,
    )
    metrics = layout.metrics
    print(f"input logical paragraphs: {metrics.input_logical_paragraph_count}")
    print(f"input translated characters: {metrics.input_translated_character_count}")
    print(f"planned paragraphs: {metrics.planned_paragraph_count}")
    print(f"planned continuations: {metrics.planned_continuation_count}")
    print(f"output paragraphs: {metrics.output_paragraph_count}")
    print(f"output extracted characters: {metrics.output_extracted_character_count}")
    print(f"unplaced translated characters: {metrics.unplaced_text_count}")
    print(f"new pages created: {metrics.new_pages_created}")


def _parse_indexes(value: str) -> tuple[int, ...]:
    indexes: set[int] = set()
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue
        if "-" in item:
            start_text, end_text = item.split("-", 1)
            start, end = int(start_text), int(end_text)
            if end < start:
                raise argparse.ArgumentTypeError("index ranges must be increasing")
            indexes.update(range(start, end + 1))
        else:
            indexes.add(int(item))
    if not indexes or min(indexes) < 0:
        raise argparse.ArgumentTypeError("occurrence indexes must be non-negative")
    return tuple(sorted(indexes))


def _parse_rect(value: str) -> Rect:
    try:
        values = tuple(float(item.strip()) for item in value.split(","))
        if len(values) != 4:
            raise ValueError
        return Rect(*values)
    except ValueError as error:
        raise argparse.ArgumentTypeError("region must be x0,y0,x1,y1") from error


if __name__ == "__main__":
    main()
