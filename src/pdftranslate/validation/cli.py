"""Standard-library CLI for the opt-in validation harness."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from pdftranslate.pipeline.models import DeviceRequest, OcrMode
from pdftranslate.validation.models import ValidationOptions
from pdftranslate.validation.runner import run_validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate-real-pdfs",
        description="Run reproducible, source-preserving PDFTranslate corpus validation.",
    )
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manual-results", type=Path)
    parser.add_argument("--subset", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--pages")
    parser.add_argument("--model", default="facebook/nllb-200-distilled-600M")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-input-tokens", type=int, default=512)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--ocr", choices=("auto", "on", "off"), default="auto")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    corpus_root = cast(Path, arguments.corpus_root)
    output_root = cast(Path | None, arguments.output_root)
    if output_root is None:
        output_root = corpus_root.with_name(f"{corpus_root.name}_validation")
    try:
        result = run_validation(
            ValidationOptions(
                corpus_root=corpus_root,
                output_root=output_root,
                manifest_path=cast(Path | None, arguments.manifest),
                manual_results_path=cast(Path | None, arguments.manual_results),
                subsets=tuple(cast(list[str], arguments.subset)),
                dry_run=cast(bool, arguments.dry_run),
                continue_on_error=not cast(bool, arguments.fail_fast),
                pages=cast(str | None, arguments.pages),
                model=cast(str, arguments.model),
                device=cast(DeviceRequest, arguments.device),
                batch_size=cast(int, arguments.batch_size),
                max_input_tokens=cast(int, arguments.max_input_tokens),
                cache_dir=cast(Path | None, arguments.cache_dir),
                offline=cast(bool, arguments.offline),
                resume=cast(bool, arguments.resume),
                overwrite=cast(bool, arguments.overwrite),
                font_path=cast(Path | None, arguments.font),
                ocr=cast(OcrMode, arguments.ocr),
            )
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Validation status: {result.summary.status}")
    print(f"JSON: {result.summary_json_path}")
    print(f"Markdown: {result.summary_markdown_path}")
    print(f"Manual review template: {result.manual_template_path}")
    return 0 if result.summary.status in {"planned", "passed"} else 1
