# Performance benchmark

PDFTR-14 measures the production logical-paragraph translation path with isolated SQLite caches.
All artifacts are written below repository-local `./temp/`; the user's normal translation memory
is never opened.

Synthetic accounting run:

```powershell
uv run python scripts/benchmark-performance.py --mode synthetic `
  --output temp/pdftr14-performance-synthetic
```

Strict offline NLLB runs using an existing Hugging Face cache:

```powershell
uv run python scripts/benchmark-performance.py --mode real-model --device cpu --offline `
  --cache-dir <hugging-face-hub-cache> --output temp/pdftr14-performance-cpu

uv run python scripts/benchmark-performance.py --mode real-model --device cuda --offline `
  --cache-dir <hugging-face-hub-cache> --output temp/pdftr14-performance-cuda
```

The deterministic public-safe dataset contains 120 `LogicalParagraph` objects, repeated headers
and boilerplate, preserved page numbers, skipped watermark candidates, glossary matches, protected
identifiers, dates, URLs, Windows paths, and forced segmentation. Reports separate cold model load,
warm-model inference, warm translation-cache reuse, multi-document reuse, and batch sizes 1/4/8.
Separate short, medium, long, and forced-segmentation scenarios record their own paragraphs,
characters, source tokens, translated segments, timing, throughput, and memory.
The batch matrix performs one excluded warmup followed by five measured iterations by default;
each report includes count, minimum, median, 95th percentile, and maximum wall time. A reduced
three-iteration CPU run is permitted when the full NLLB matrix would be disproportionately slow.

JSON byte values are RSS/working-set and PyTorch allocated/reserved CUDA bytes. Markdown renders
them in binary units. CUDA timers synchronize before observation. Normal CI uses synthetic fakes;
it neither downloads NLLB nor requires GPU hardware.

Benchmark values are not portable performance promises: they depend on CPU/GPU, driver, operating
system, model cache, process state, thermals, and background load. Synthetic results prove only
accounting and report behavior, never NLLB throughput or quality.

An explicit `--device cuda` request is a hard requirement: if the production translator does not
report CUDA as its effective device, the benchmark fails instead of silently collecting CPU data.
Select a new run-specific `--output` directory for every invocation. The runner rejects a non-empty
directory so an old SQLite cache cannot be mislabeled as a cold run and existing reports are never
silently replaced.
