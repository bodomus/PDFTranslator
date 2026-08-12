"""Run the PDFTR-14 production-path performance benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path

from pdftranslate.glossary import load_glossary
from pdftranslate.performance import (
    BenchmarkConfig,
    build_performance_dataset,
    run_performance_benchmark,
    write_performance_reports,
)
from pdftranslate.translation.nllb import DEFAULT_NLLB_MODEL, NllbTranslator


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("synthetic", "real-model"), required=True)
    parser.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cpu")
    parser.add_argument("--batch-sizes", default="1,4,8")
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--max-input-tokens", type=int, default=64)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--model", default=DEFAULT_NLLB_MODEL)
    parser.add_argument("--glossary", type=Path, default=Path("docs/glossary.example.json"))
    parser.add_argument("--output", type=Path, default=Path("temp/pdftr14-performance"))
    args = parser.parse_args()
    batch_sizes = tuple(int(value.strip()) for value in args.batch_sizes.split(","))
    config = BenchmarkConfig(
        mode=args.mode,
        device=args.device,
        batch_sizes=batch_sizes,
        iterations=args.iterations,
        warmup=args.warmup,
        max_input_tokens=args.max_input_tokens,
        offline=args.offline,
    )
    glossary = load_glossary(args.glossary)
    dataset = build_performance_dataset(glossary)
    if args.mode == "synthetic":
        from pdftranslate.performance.runner import DeterministicTranslator

        def factory() -> DeterministicTranslator:
            return DeterministicTranslator(args.device)

    else:
        if args.cache_dir is None:
            parser.error("real-model mode requires --cache-dir")
        model_cache = args.cache_dir

        def factory() -> NllbTranslator:
            return NllbTranslator(
                model_name=args.model,
                device=args.device,
                cache_dir=model_cache,
                offline=args.offline,
                max_input_tokens=args.max_input_tokens,
            )

    report = run_performance_benchmark(
        dataset,
        config=config,
        translator_factory=factory,
        output_root=args.output,
    )
    json_path, markdown_path = write_performance_reports(report, args.output)
    print(json_path)
    print(markdown_path)
    return 0 if report.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
