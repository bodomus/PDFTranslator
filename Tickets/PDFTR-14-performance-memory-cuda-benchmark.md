# PDFTR-14 — Performance, memory and CUDA benchmark

**# Performance, memory and CUDA benchmark**

**## Summary**

Add a reproducible performance and resource benchmark for the current PDFTranslate production pipeline after PDFTR-11, PDFTR-12, PDFTR-13 and PDFTR-13A.

The benchmark must measure real translation execution, not only helper functions.

Primary goals:

\- measure CPU and CUDA translation throughput;

\- measure cold vs warm model/runtime behavior;

\- measure model-load time separately from inference;

\- measure process RAM and CUDA VRAM usage;

\- measure segmentation, translation-cache reuse and batch reuse;

\- compare single-file and multi-file execution;

\- prove that performance instrumentation does not change translation results;

\- produce machine-readable JSON and human-readable Markdown reports.

This ticket is measurement-first. Do not optimize production behavior unless a very small instrumentation-related correction is required to make measurements truthful.

**## Dependencies**

Required base:

\- PDFTR-11 — Paragraph reconstruction and reading order;

\- PDFTR-12 — Repeated headers, footers and boilerplate;

\- PDFTR-13 — Glossary/protected terms;

\- PDFTR-13A — End-to-end glossary benchmark correction.

Create the branch from current \`master\`.

Suggested branch:

\`\`\`text

codex/PDFTR-14-performance-memory-cuda-benchmark

\`\`\`

**## Current production assumptions**

The current application is:

\- Windows-first;

\- Python 3.12;

\- local NLLB EN → RU translation;

\- CPU and CUDA capable;

\- paragraph-aware;

\- translation-cache aware;

\- batch-capable with one shared NLLB runtime;

\- glossary-aware;

\- resume/workspace aware;

\- OCR-capable, but OCR is not part of the primary model benchmark.

The benchmark must operate on the same translation path used by the production application.

**## Non-goals**

Do not implement in PDFTR-14:

\- a new translation model;

\- quantization;

\- ONNX/TensorRT conversion;

\- \`torch.compile\` experiments;

\- model architecture changes;

\- CUDA kernel tuning;

\- OCR performance optimization;

\- renderer optimization;

\- multiprocessing redesign;

\- GUI;

\- packaging/release work;

\- automatic hardware overclocking or system tuning.

Potential optimizations discovered here must be documented as follow-up tickets.

**## Required workflow**

Treat this as a Level 2 task because benchmark instrumentation reaches model lifecycle, translation runtime, cache behavior, batch execution and diagnostics.

Before editing:

1\. verify branch is based on current \`master\`;

2\. verify clean Git state;

3\. read \`AGENTS.md\`, \`.codex/PRE_TICKET_WORKFLOW.md\`, current NLLB backend, \`TranslationRuntime\`, \`translate_paragraphs()\`, batch runner, translation cache, pipeline progress/diagnostics, PDFTR-9 benchmark infrastructure where reusable, and PDFTR-13A benchmark;

4\. run Graphify/CRG preflight;

5\. source-verify the actual production path before designing instrumentation.

Expected translation path:

\`\`\`text

LogicalParagraph

→ repeated-element policy

→ glossary

→ protected tokens

→ segmentation

→ NLLB translator

→ restore/validation

→ TranslationCache

→ checkpoint/reporting

\`\`\`

Expected lifecycle path:

\`\`\`text

CLI/batch

→ TranslationRuntime

→ NllbTranslator construction

→ tokenizer/config/model loading

→ device placement

→ repeated translate_batch()

→ runtime disposal/process exit

\`\`\`

**## Benchmark architecture**

Add a dedicated package or focused benchmark module independent of Typer rendering concerns.

Suggested:

\`\`\`text

src/pdftranslate/performance/

&nbsp;&nbsp;&nbsp;&nbsp;__init__.py

&nbsp;&nbsp;&nbsp;&nbsp;models.py

&nbsp;&nbsp;&nbsp;&nbsp;sampler.py

&nbsp;&nbsp;&nbsp;&nbsp;metrics.py

&nbsp;&nbsp;&nbsp;&nbsp;reporting.py

\`\`\`

and:

\`\`\`text

scripts/benchmark-performance.py

\`\`\`

Equivalent structure is acceptable.

The core measurement logic must be callable from tests without launching a subprocess.

**## Benchmark modes**

Required modes:

\`\`\`text

synthetic

real-model

\`\`\`

**### synthetic**

Uses a deterministic fake translator.

Purpose:

\- verify benchmark accounting;

\- verify cache hit/miss counting;

\- verify paragraph/segment counting;

\- verify repeated-source deduplication;

\- verify report reproducibility;

\- verify warm/cold scenario orchestration;

\- keep CI model-free and GPU-free.

**### real-model**

Uses the production NLLB backend.

Purpose:

\- CPU timing;

\- CUDA timing when available;

\- RAM usage;

\- CUDA VRAM usage;

\- cold model load;

\- warm inference;

\- batch-size comparison;

\- cache effects.

CI must not require the real model or GPU.

**## Required benchmark scenarios**

At minimum measure the following scenarios.

**### 1. Cold CPU**

Fresh process/runtime:

\`\`\`text

device=cpu

cache empty

model not yet loaded in current process

\`\`\`

Measure separately:

\- model/config/tokenizer load time;

\- first translation latency;

\- total translation elapsed time;

\- total wall-clock time;

\- peak RSS;

\- paragraph count;

\- segment count;

\- characters;

\- source tokens when available;

\- cache hits/misses.

**### 2. Warm CPU**

Same loaded model/runtime, second equivalent translation pass.

Use a fresh translation cache if the goal is inference throughput.

Also run a separate warm-cache scenario where translation results are already cached.

Do not confuse \`warm model\` with \`warm translation cache\`. These must be reported separately.

**### 3. Cold CUDA**

When CUDA is available:

\`\`\`text

device=cuda

cache empty

fresh process/runtime

\`\`\`

Measure:

\- model load/device placement;

\- first inference;

\- total elapsed time;

\- peak process RAM;

\- peak allocated CUDA memory;

\- peak reserved CUDA memory;

\- CUDA device name;

\- CUDA capability where available.

**### 4. Warm CUDA**

Same loaded model, uncached translation input.

This is the main GPU inference throughput measurement.

**### 5. Warm translation cache**

CPU or CUDA device may be selected, but translator calls should be zero or near zero according to current cache behavior.

Required proof:

\- cache hits;

\- cache misses;

\- translator calls;

\- model-facing segments.

**### 6. Batch reuse**

Use multiple logical documents/files through the production shared runtime.

Measure:

\- model load count;

\- number of documents;

\- number of paragraphs;

\- repeated strings across files;

\- cache hits/misses;

\- elapsed time per file;

\- total elapsed time;

\- translator calls;

\- model-facing segments.

Prove that the model is constructed once for the batch.

**### 7. Batch-size matrix**

Run real-model translation with a small controlled dataset for at least:

\`\`\`text

batch-size = 1

batch-size = 4

batch-size = 8

\`\`\`

Optionally include 16 only when it is safe on the available hardware.

Report each separately. Do not automatically declare the fastest observed value as the new default.

**### 8. Input-length matrix**

Use deterministic logical paragraphs representing:

\- short;

\- medium;

\- long;

\- forced segmentation.

Record paragraph count, source character count, source token count if reliably available, segment count, translated segment count, and elapsed time.

**## Dataset**

Add a public-safe deterministic benchmark dataset.

Minimum:

\`\`\`text

100 logical paragraphs

\`\`\`

Recommended:

\`\`\`text

150–300 logical paragraphs

\`\`\`

Include ordinary prose, technical prose, headings, repeated headers, repeated boilerplate, numbers/dates, URLs, Windows paths, protected identifiers, glossary terms, long paragraphs requiring segmentation, and repeated source paragraphs for dedup/cache tests.

Do not use copyrighted private book text in committed fixtures.

A user-owned real PDF may be used for an opt-in local validation run, but must not be committed.

**## Timing rules**

Use \`time.perf_counter()\` or equivalent monotonic high-resolution timing.

Required timing fields:

\`\`\`text

process_wall_seconds

runtime_open_seconds

model_load_seconds

first_inference_seconds

translation_seconds

cache_only_seconds

total_seconds

\`\`\`

Use \`null\` where a metric does not apply.

**### Warmup policy**

For throughput comparison:

\- perform one warmup run;

\- exclude warmup from reported median;

\- perform at least 5 measured runs when practical.

Report:

\`\`\`text

count

min

median

p95 or max

\`\`\`

For expensive CPU runs, 3 measured iterations are acceptable only if the report clearly explains the reduced sample count.

Do not average cold-start and warm-run timings together.

**## Throughput metrics**

Required:

\`\`\`text

paragraphs_per_second

segments_per_second

characters_per_second

\`\`\`

Optional when tokenizer accounting is trustworthy:

\`\`\`text

source_tokens_per_second

\`\`\`

Do not call token throughput \`tokens/sec\` unless the exact token definition is documented.

**## CPU memory measurement**

Measure process resident memory.

Required:

\`\`\`text

rss_before_model

rss_after_model_load

rss_peak

rss_after_run

\`\`\`

Use a cross-platform mechanism where practical.

\`psutil\` may be added only if justified and approved by the dependency policy.

Clearly document whether values are RSS, working set, or private bytes. Do not mix them under one label.

**## CUDA memory measurement**

When CUDA is selected and available, use PyTorch CUDA memory counters.

Reset peak stats immediately before the measured phase.

Required values:

\`\`\`text

torch.cuda.max_memory_allocated()

torch.cuda.max_memory_reserved()

memory_allocated before inference

memory_reserved before inference

memory_allocated after inference

memory_reserved after inference

\`\`\`

Record values in bytes in JSON. Markdown may also show MiB/GiB.

Synchronize CUDA before stopping timers where required:

\`\`\`python

torch.cuda.synchronize()

\`\`\`

Do this only for benchmark timing, not production translation execution.

**## GPU metadata**

Capture when available:

\`\`\`text

torch version

CUDA runtime reported by torch

CUDA available

device index

GPU name

compute capability

total VRAM if available

\`\`\`

Do not run external \`nvidia-smi\` unless needed for supplementary diagnostics.

**## System metadata**

Record enough metadata to reproduce local results:

\`\`\`text

timestamp UTC

OS

Python version

application version

Git commit

backend

model

tokenizer/model ID

offline flag

device request

effective device

CPU model when obtainable

logical CPU count

system RAM when obtainable

batch size

max input tokens

dataset version/hash

glossary fingerprint when used

translation behavior revision

pipeline behavior revision

\`\`\`

Do not collect personal file paths unnecessarily.

**## Model lifecycle instrumentation**

Current production behavior must remain unchanged.

Instrumentation should expose lifecycle timings without requiring the benchmark to duplicate model loading internals.

Preferred design:

\- add optional timing/evidence hooks or a typed runtime measurement;

\- keep default production behavior silent;

\- avoid global mutable benchmark state;

\- do not print benchmark internals during normal translation;

\- do not add benchmark-only branches to hot translation loops unless negligible.

If accurate model-load timing can be measured externally around \`NllbTranslator\` construction, prefer that simpler approach.

**## Translation result integrity**

Performance measurement must not weaken correctness.

For every compared scenario, verify:

\- same dataset identity;

\- same logical paragraph structure;

\- same source mappings;

\- same glossary fingerprint where applicable;

\- no placeholder leaks;

\- protected terms preserved;

\- expected glossary targets retained;

\- output count equals input translation-unit count.

For deterministic fake translator runs, translated outputs must match exactly across equivalent scenarios.

For real NLLB runs, compare output hashes across identical settings where inference is expected to be deterministic.

If output differs between CPU and CUDA, record it rather than hiding it.

**## Cache isolation**

Performance benchmarks must never use the user's normal production translation cache.

All benchmark caches must live under:

\`\`\`text

./temp/

\`\`\`

Each cold scenario must start with a fresh cache.

Warm-cache scenarios must intentionally reuse only the cache created by their corresponding cold scenario.

**## Output files**

Default output:

\`\`\`text

temp/pdftr14-performance/

\`\`\`

Produce:

\`\`\`text

performance.json

performance.md

\`\`\`

Optional per-run raw data:

\`\`\`text

runs/

  cpu-cold-\*.json

  cpu-warm-\*.json

  cuda-cold-\*.json

  cuda-warm-\*.json

\`\`\`

All runtime benchmark artifacts remain ignored by Git.

**## JSON report**

Add a versioned report schema.

Suggested top-level structure:

\`\`\`json

{

  "schema_version": "1.0",

  "metadata": {},

  "dataset": {},

  "scenarios": [],

  "comparisons": {},

  "warnings": [],

  "limitations": []

}

\`\`\`

Each scenario must include:

\`\`\`text

name

device_request

effective_device

batch_size

iteration

warmup

cache_state

model_state

paragraphs

segments

characters

translator_calls

cache_hits

cache_misses

timings

cpu_memory

cuda_memory

integrity

\`\`\`

**## Markdown report**

Generate a concise comparison table with:

\`\`\`text

Scenario

Device

Batch

Cold/Warm

Cache

Paragraphs

Segments

Wall time

Translation time

Paragraphs/s

Characters/s

Peak RAM

Peak VRAM

Cache hit rate

\`\`\`

Separate CPU, CUDA, cache-only, and batch results.

**## CLI / script interface**

A standalone benchmark script is required.

Examples:

\`\`\`powershell

uv run python scripts/benchmark-performance.py --mode synthetic \`

  --output temp/pdftr14-performance

\`\`\`

\`\`\`powershell

uv run python scripts/benchmark-performance.py --mode real-model \`

  --device cpu --offline \`

  --output temp/pdftr14-performance-cpu

\`\`\`

\`\`\`powershell

uv run python scripts/benchmark-performance.py --mode real-model \`

  --device cuda --offline \`

  --output temp/pdftr14-performance-cuda

\`\`\`

Suggested options:

\`\`\`text

\--mode synthetic\|real-model

\--device cpu\|cuda\|auto

\--batch-sizes 1,4,8

\--iterations N

\--warmup N

\--max-input-tokens N

\--offline

\--cache-dir PATH

\--model MODEL

\--output PATH

\`\`\`

Do not expose this as a normal production CLI command unless there is a clear reason.

**## Failure behavior**

A requested CUDA benchmark must fail clearly when CUDA is unavailable.

Do not silently fall back to CPU for explicit benchmark \`--device cuda\`.

\`--device auto\` may follow normal production resolution, but report the effective device.

Missing offline model files must use the existing strict offline error behavior.

Partial benchmark reports may be written under \`./temp/\`, but must be marked incomplete.

**## Tests**

Add focused tests for:

**### Metrics**

\- timing aggregation;

\- median/min/max or p95 calculation;

\- zero-duration safety;

\- throughput calculation;

\- bytes-to-human-readable formatting;

\- missing CUDA metrics.

**### Scenario accounting**

\- synthetic cold run;

\- synthetic warm-model run;

\- warm-cache run;

\- batch shared-runtime run;

\- repeated-source deduplication;

\- batch-size matrix;

\- long paragraph segmentation.

**### Cache**

\- cold scenario uses empty cache;

\- warm-cache reuses correct cache;

\- unrelated benchmark runs do not leak cache state;

\- benchmark never opens the user's production cache.

**### Integrity**

\- exact deterministic output for fake translator;

\- protected tokens survive;

\- glossary targets survive;

\- repeated preserve/skip behavior survives;

\- placeholder leak causes failure.

**### CUDA abstraction**

CI must not require CUDA.

Use mocks/fakes for unavailable CUDA, allocated/reserved counters, synchronize call, peak reset, and device metadata.

**### Reports**

\- JSON schema validation;

\- deterministic report structure;

\- Markdown contains all required scenarios;

\- incomplete run clearly marked;

\- system metadata does not expose unnecessary paths.

**## Real local benchmark requirements**

On the development workstation, when the local NLLB model cache is available, run both CPU and CUDA.

CUDA validation is a core acceptance requirement for PDFTR-14, not optional.

If CUDA cannot be made available in the existing Python environment, do not fabricate results. Report the environment problem as a blocker.

Record:

\- exact torch version;

\- \`torch.cuda.is_available()\`;

\- GPU name;

\- CPU results;

\- CUDA results;

\- batch matrix;

\- peak RAM;

\- peak VRAM;

\- cold model-load time;

\- warm inference throughput;

\- warm-cache performance.

**## Recommended local comparison**

For the primary real-model dataset use the same input for CPU and CUDA.

Suggested measured sequence:

\`\`\`text

CPU:

  1 warmup

  5 warm runs, batch=1

  5 warm runs, batch=4

  5 warm runs, batch=8

CUDA:

  1 warmup

  5 warm runs, batch=1

  5 warm runs, batch=4

  5 warm runs, batch=8

\`\`\`

Also record one cold-start run per device separately.

If CPU time is excessive, reduce measured CPU iterations to 3 and document it.

**## Acceptance criteria**

\- [ ] Benchmark runs through the production logical-paragraph translation path.

\- [ ] Synthetic mode is deterministic and CI-safe.

\- [ ] Real NLLB CPU benchmark is executed locally.

\- [ ] Real NLLB CUDA benchmark is executed locally.

\- [ ] Explicit CUDA request never silently falls back to CPU.

\- [ ] Cold model load and warm inference are timed separately.

\- [ ] Warm model and warm translation cache are separate scenarios.

\- [ ] CPU process-memory metrics are recorded.

\- [ ] CUDA allocated/reserved peak metrics are recorded.

\- [ ] GPU/device metadata is recorded.

\- [ ] Batch runtime reuse is measured.

\- [ ] Model load count/reuse is proven for batch.

\- [ ] Batch-size 1/4/8 comparison is recorded.

\- [ ] Segmentation-heavy input is included.

\- [ ] Translation-cache reuse is measured.

\- [ ] Benchmark cache is isolated under \`./temp/\`.

\- [ ] Glossary/protected-token/repeated-element correctness remains intact.

\- [ ] JSON report is versioned and machine-readable.

\- [ ] Markdown report is generated.

\- [ ] Reports include Git commit, model, device and dataset identity.

\- [ ] No benchmark claim confuses cache speed with model inference speed.

\- [ ] No benchmark claim confuses synthetic fake results with NLLB performance.

\- [ ] Full test suite passes.

\- [ ] Coverage remains at least 80%.

\- [ ] Ruff passes.

\- [ ] mypy passes.

\- [ ] Graphify/CRG post-change checks are complete and source-verified.

\- [ ] GitHub Actions is green.

\- [ ] PDFTR-15 is not started.

**## Required benchmark interpretation**

The implementation report must explicitly answer:

1\. How long does NLLB take to load on CPU?

2\. How long does NLLB take to load/move to CUDA?

3\. What is warm CPU translation throughput?

4\. What is warm CUDA translation throughput?

5\. What speedup does CUDA provide for the same dataset?

6\. What batch size performs best on the tested GPU?

7\. How much RAM does the model/process use?

8\. How much peak VRAM does CUDA translation use?

9\. How much faster is a full translation-cache hit?

10\. Does multi-file batch reuse avoid repeated model loading?

11\. Does glossary/protected-token processing materially affect measured throughput?

12\. Were CPU and CUDA outputs identical for the tested deterministic settings?

13\. What limitations make the numbers non-portable to other machines?

Use measured report data only.

**## Documentation**

Add:

\`\`\`text

docs/performance-benchmark.md

Tickets/PDFTR-14-performance-memory-cuda-benchmark.md

\`\`\`

Update README and CHANGELOG.

Do not publish machine-specific benchmark numbers in README as universal expectations.

**## Validation commands**

Run at minimum:

\`\`\`powershell

uv run pytest tests/test_performance_benchmark.py -q --no-cov

uv run pytest tests/test_translation.py tests/test_glossary.py \`

  tests/test_glossary_integration.py tests/test_repeated_elements.py -q --no-cov

uv run ruff format --check .

uv run ruff check .

uv run mypy src

.\\scripts\\check.ps1

\`\`\`

Then run synthetic, real CPU, and real CUDA benchmark commands described above.

**## Required completion report**

Create:

\`\`\`text

.implementation-reports/implementation-report-PDFTR-14.md

reviews/review-PDFTR-14.md

\`\`\`

The implementation report must contain:

\`\`\`markdown

**# Implementation Report — PDFTR-14**

**## Git state**

\- Branch:

\- Base commit:

\- Working tree before changes:

**## Investigation**

\- Production translation path:

\- Model lifecycle:

\- Cache lifecycle:

\- Batch lifecycle:

\- Existing benchmark reuse:

\- Graphify/CRG findings:

**## Benchmark design**

\- Dataset:

\- Synthetic mode:

\- Real-model mode:

\- Timing methodology:

\- Warmup/iterations:

\- CPU memory measurement:

\- CUDA memory measurement:

\- Integrity checks:

**## Environment**

\- OS:

\- Python:

\- App commit:

\- torch:

\- CUDA available:

\- CUDA runtime:

\- GPU:

\- CPU:

\- System RAM:

\- Model:

\- Offline/cache source:

**## Results — CPU**

\- Cold model load:

\- First inference:

\- Warm batch=1:

\- Warm batch=4:

\- Warm batch=8:

\- Peak RAM:

\- Cache-only:

\- Notes:

**## Results — CUDA**

\- Cold model load/device placement:

\- First inference:

\- Warm batch=1:

\- Warm batch=4:

\- Warm batch=8:

\- Peak allocated VRAM:

\- Peak reserved VRAM:

\- Cache-only:

\- Notes:

**## Results — Batch reuse**

\- Documents:

\- Model loads:

\- Translator calls:

\- Cache hits/misses:

\- Total elapsed:

\- Per-file timing:

**## CPU vs CUDA**

\- Same dataset:

\- CPU median:

\- CUDA median:

\- Speedup:

\- Output comparison:

**## Correctness**

\- Protected tokens:

\- Glossary:

\- Repeated elements:

\- Placeholder leaks:

\- Cache isolation:

\- Output identity/hash:

**## Validation**

\- Focused tests:

\- Full tests:

\- Coverage:

\- Ruff:

\- mypy:

\- check.ps1:

\- Synthetic benchmark:

\- CPU real benchmark:

\- CUDA real benchmark:

\- GitHub Actions:

**## Findings**

\- Bottlenecks:

\- Recommended default batch size:

\- Follow-up optimization tickets:

\- Measurement limitations:

**## Recommendation**

\- Ready / not ready for review

\`\`\`

**## Review file**

\`reviews/review-PDFTR-14.md\` must independently state benchmark methodology, cold/warm separation, cache/inference separation, CPU/CUDA evidence, RAM/VRAM evidence, batch reuse evidence, correctness/integrity evidence, limitations, and merge recommendation.

Do not start PDFTR-15 until PDFTR-14 has been reviewed.
