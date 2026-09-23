"""Inspect source-backed paragraph typography without translation or rendering."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pdftranslate.pdf import PdfExtractor
from pdftranslate.typography import ParagraphTypographyEvidence, extract_typography_evidence


def _positive_csv(value: str) -> set[int]:
    selected: set[int] = set()
    for raw in value.split(","):
        part = raw.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start < 0 or end < start:
                raise argparse.ArgumentTypeError("ranges must be non-negative and increasing")
            selected.update(range(start, end + 1))
        else:
            number = int(part)
            if number < 0:
                raise argparse.ArgumentTypeError("values must be non-negative")
            selected.add(number)
    return selected


def _matches(
    item: ParagraphTypographyEvidence,
    pages: set[int] | None,
    occurrences: set[int] | None,
) -> bool:
    return (pages is None or item.source_page_number in pages) and (
        occurrences is None or item.occurrence_index in occurrences
    )


def _console_line(item: ParagraphTypographyEvidence) -> str:
    font = item.source_font_name.value or "?"
    size = f"{item.font_size_points.value:g}pt" if item.font_size_points.value else "?pt"
    alignment = item.alignment.value or "unknown"
    mixed = (
        ",".join(
            name.removeprefix("mixed_")
            for name, value in item.mixed_styles.model_dump().items()
            if value
        )
        or "none"
    )
    return (
        f"[{item.occurrence_index}] page={item.source_page_number} id={item.paragraph_id} "
        f"role={item.role.value} font={font} size={size} alignment={alignment} mixed={mixed} "
        f"text={item.text_preview!r}"
    )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_pdf", type=Path)
    parser.add_argument("--pages", type=_positive_csv, help="one-based pages, for example 1,3-4")
    parser.add_argument(
        "--occurrences", type=_positive_csv, help="zero-based occurrence indexes, for example 38-41"
    )
    parser.add_argument("--output", type=Path, help="optional compact JSON destination")
    args = parser.parse_args()

    document = PdfExtractor().extract(args.source_pdf)
    baseline = extract_typography_evidence(document)
    selected = tuple(
        item for item in baseline.paragraphs if _matches(item, args.pages, args.occurrences)
    )
    if args.output is None:
        for item in selected:
            print(_console_line(item))
        return

    destination = args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = baseline.model_copy(update={"paragraphs": selected}).model_dump(mode="json")
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(selected)} typography occurrences to {destination}")


if __name__ == "__main__":
    main()
