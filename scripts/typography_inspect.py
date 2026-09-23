"""Inspect source-backed paragraph typography without translation or rendering."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pdftranslate.pdf import PdfExtractor
from pdftranslate.typography import (
    ParagraphTypographyEvidence,
    ResolvedParagraphStyle,
    StyleDecision,
    extract_typography_evidence,
    reconstruct_styles,
)


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


def _decision_line[T](name: str, decision: StyleDecision[T]) -> str:
    evidence = decision.evidence_value if decision.evidence_value is not None else "unknown"
    suffix = f" fallback={decision.fallback_reason}" if decision.used_fallback else ""
    return (
        f"  {name}: evidence={evidence} / {decision.evidence_confidence.value} "
        f"resolved={decision.value} decision={decision.source.value}{suffix}"
    )


def _resolved_console_block(
    evidence: ParagraphTypographyEvidence,
    resolved: ResolvedParagraphStyle,
) -> str:
    decisions = resolved.decisions
    lines = [
        _console_line(evidence),
        _decision_line("font_family", decisions.source_font_family_group),
        _decision_line("font_role", decisions.font_role),
        _decision_line("font_size", decisions.font_size_points),
        _decision_line("bold", decisions.bold),
        _decision_line("italic", decisions.italic),
        _decision_line("color", decisions.color_rgb),
        _decision_line("alignment", decisions.alignment),
        _decision_line("line_height_ratio", decisions.line_height_ratio),
        _decision_line("first_line_indent", decisions.first_line_indent_points),
        _decision_line("left_indent", decisions.left_indent_points),
        _decision_line("right_indent", decisions.right_indent_points),
        _decision_line("space_before", decisions.space_before_points),
        _decision_line("space_after", decisions.space_after_points),
        f"  fallback_count={resolved.fallback_count}",
    ]
    return "\n".join(lines)


def validate_output_destination(source_pdf: Path, output: Path | None) -> None:
    """Reject an output alias before any extraction or write can touch the source PDF."""
    if output is not None and source_pdf.resolve() == output.resolve():
        raise ValueError("--output must not resolve to the source PDF")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_pdf", type=Path)
    parser.add_argument("--pages", type=_positive_csv, help="one-based pages, for example 1,3-4")
    parser.add_argument(
        "--occurrences", type=_positive_csv, help="zero-based occurrence indexes, for example 38-41"
    )
    parser.add_argument("--output", type=Path, help="optional compact JSON destination")
    parser.add_argument(
        "--resolved",
        action="store_true",
        help="include role baselines and renderer-facing decisions",
    )
    args = parser.parse_args()

    try:
        validate_output_destination(args.source_pdf, args.output)
    except ValueError as error:
        parser.error(str(error))

    document = PdfExtractor().extract(args.source_pdf)
    baseline = extract_typography_evidence(document)
    selected = tuple(
        item for item in baseline.paragraphs if _matches(item, args.pages, args.occurrences)
    )
    resolved = reconstruct_styles(baseline) if args.resolved else None
    if args.output is None:
        if resolved is None:
            for item in selected:
                print(_console_line(item))
            return
        resolved_by_occurrence = {item.occurrence_index: item for item in resolved.paragraphs}
        for item in selected:
            print(_resolved_console_block(item, resolved_by_occurrence[item.occurrence_index]))
        return

    destination = args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    if resolved is None:
        payload = baseline.model_copy(update={"paragraphs": selected}).model_dump(mode="json")
    else:
        selected_occurrences = {item.occurrence_index for item in selected}
        payload = resolved.model_copy(
            update={
                "paragraphs": tuple(
                    item
                    for item in resolved.paragraphs
                    if item.occurrence_index in selected_occurrences
                )
            }
        ).model_dump(mode="json")
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    kind = "resolved style" if resolved is not None else "typography"
    print(f"Wrote {len(selected)} {kind} occurrences to {destination}")


if __name__ == "__main__":
    main()
