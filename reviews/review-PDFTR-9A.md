# Review — PDFTR-9A

## Решение

**Ready for check-in.** Обе заявленные ошибки воспроизведены и исправлены без расширения scope.

## Cache isolation

- До исправления новые tests доказали, что второй sample наследовал `passed` от первого при ином
  `protected_tokens` или human review.
- После исправления cache содержит только model-execution artifacts.
- Protected tokens, human scores, historical traces, findings и status рассчитываются отдельно.
- Три equal-source сценария подтверждают ровно один cache hit и независимые результаты.

## Strict offline

- Remote model ID не передаётся loaders в offline mode: сначала выбирается существующий local path
  или Hugging Face cache snapshot.
- Config, tokenizer и model получают `local_files_only=True`; model получает уже загруженный config.
- Missing cache завершается до Transformers import с моделью, cache path и recovery guidance.
- Offline environment восстанавливается после success/failure; online=False path не меняется.
- Реальная модель загрузилась и обработала 61 sample при неработающих HTTP/HTTPS/ALL proxy. HTTP
  requests не наблюдались.

## Проверки

- Benchmark: 14 passed.
- Translation: 9 passed.
- Combined focused: 32 passed.
- Full/check.ps1: 152 passed, 1 skipped, coverage 87.70%.
- Ruff/mypy: passed.
- Real benchmark: 60 passed, 1 failed, 0 errors; 44.183 seconds; 0/61 cache hits/misses.

## Замечания

1. Offline verification — blocked proxy plus log observation, не packet capture.
2. Transformers warning о `max_new_tokens`/`max_length` остаётся.
3. `command-01` production token protection остаётся вне scope.
4. Online path проверен mock factories, без реального download.
5. Concurrent threaded model initialization не проверялся; environment scoped, а local path является
   основной strict boundary.
6. CUDA/OCR/PDF rendering не затронуты и не проверялись.
7. CRG final index содержит 705 rows, risk 0.40; heuristic gaps опровергаются прямыми tests.
   Graphify refresh/recluster выполнен, но несколько oversized semantic chunks были отброшены из-за
   Ollama context 8192, а community labels частично stale. Source/AST/CRG использованы как authority.
8. У переданного тикета нет числового YouTrack ID; отдельное приложение к YouTrack невозможно.
9. PDFTR-10 не начат.

## Артефакты

- `implementation-report.md`
- `reviews/review-PDFTR-9.md`
- `reviews/review-PDFTR-9A.md`
- `temp/pdftr9-benchmark/nllb-offline.json`
- `temp/pdftr9-benchmark/nllb-offline.md`
