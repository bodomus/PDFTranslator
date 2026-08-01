# Implementation Report — PDFTR-9

## Итог

Реализован воспроизводимый benchmark качества перевода English → Russian, который отделяет
текущий результат модели от исторических наблюдений и классифицирует дефекты по границам:
извлечение, сегментация, защищённые токены, модель, терминология и рендеринг. Внешний вид PDF и
rendering pipeline не изменялись.

Ветка `codex/PDFTR-9-translation-quality-benchmark` продолжена от текущего исправленного HEAD
PDFTR-8 (`d16ed0efa708ee45c89767bb1af5129656848255`), как отдельно указал пользователь, а не от
`master`.

## Реализация

- Добавлен версионированный dataset `benchmarks/translation-en-ru-v1.json`: 61 безопасный
  synthetic/CC0 пример и два обязательных user-provided regression trace из PDFTR-8.
- Добавлен независимый от Typer пакет `pdftranslate.benchmark` с Pydantic-контрактами, runner,
  stage-aware checks, атомарными JSON/Markdown отчётами и сравнением с baseline.
- Добавлена команда `pdftranslate benchmark-translation` с фиксацией версии dataset, commit,
  backend/model/tokenizer, устройства, настроек сегментации, времени и cache statistics.
- Один экземпляр модели используется на весь прогон; одинаковые source внутри запуска кэшируются.
- Findings имеют `origin=current_run|historical_trace`. Исторические дефекты остаются видимыми,
  но не превращаются в ложную текущую регрессию и не влияют на pass/fail текущего запуска.
- Автоматические проверки покрывают числа/даты, единицы, URL, Windows paths, CLI options,
  placeholders, защищённые токены, count сегментов, подозрительные Unicode-символы и грубые
  структурные отклонения. Семантическая adequacy/fluency не заявляется без человека.
- Опциональная human review шкала 1–5 включает adequacy, fluency, terminology, token preservation,
  segmentation и overall acceptability.
- Обновлены README и CHANGELOG. Зависимости не добавлялись.

## Реальный benchmark

Команда:

```powershell
uv run pdftranslate benchmark-translation .\benchmarks\translation-en-ru-v1.json `
  --output .\temp\pdftr9-benchmark\nllb.json `
  --device cpu --offline --max-input-tokens 64 `
  --cache-dir .\temp\pdftr9-benchmark\cache --overwrite
```

Результат NLLB `facebook/nllb-200-distilled-600M`:

- dataset `1.0.0`, 61 sample;
- 60 passed, 1 failed, 0 execution errors;
- model elapsed 42.789 s; CLI wall time 47.11 s;
- 0 cache hits / 61 misses;
- current findings: 1 protected-token + 1 model finding, оба в `command-01`;
- historical findings: extraction 1, segmentation 1, protected-token 3, model 3, rendering 2;
- human review: все 61 результата `not reviewed`.

Единственный текущий failure: NLLB перевёл `data.json`, `--device` и `--offline` в command sample.
Это зафиксировано как повреждение защищаемого filename и CLI options; не относится к extraction,
segmentation или rendering.

### Обязательные дефекты PDFTR-8

1. `pdftr8-token-1900-1`: текущий прогон **passed**. Выход:
   `Вход в архив 1900-1 должен оставаться неизменным.` Токен `1900-1` сохранён. Историческое
   повреждение `1900 1` сохранено отдельно как `historical_trace` на границах protected token/model.
2. `pdftr8-page7-numbers-junk`: текущий прогон **passed**. Выход сохраняет `1999`, `2001`, `10`,
   `53`, `10022-5299`; `F￾` отсутствует. Исторические повреждения `19F￾`, `20O1` и потеря числа
   сохранены отдельно как model/protected-token trace.

Файлы результата находятся только в `./temp` и не добавляются в Git:
`temp/pdftr9-benchmark/nllb.json` и `temp/pdftr9-benchmark/nllb.md`.

## Проверки и анализ влияния

- Focused benchmark tests: 10 passed.
- `./scripts/check.ps1`: passed.
- Ruff format/lint: passed; mypy: no issues in 59 source files.
- pytest: 144 passed, 1 skipped; coverage 87.27% при пороге 80%.
- Пропущен только существующий opt-in OCR integration test.
- CRG index обновлён: 648 FTS rows. Финальный post-commit `detect-changes --base HEAD~1`
  проанализировал все 15 изменённых файлов, дал risk 0.30 и эвристически
  отметил Typer entry point `benchmark_translation` как test gap; фактически CLI покрыт тестом с
  fake translator, а все 144 теста прошли.
- Graphify использован для pre-ticket архитектурной ориентации. Обязательные связи проверены по
  source. Инкрементальный refresh после изменения module boundary завис и был остановлен после
  внешнего timeout; graph output не изменился. Это замечание не скрывается и не влияет на runtime.

## Все замечания и ограничения

1. `--offline` передан в NLLB и веса взяты из существующего локального cache через junction внутри
   `./temp`; большие модели не скачивались и не коммитились. Однако Hugging Face Hub выполнил
   metadata HTTP-запросы. Поэтому наблюдаемое поведение не соответствует буквальному обещанию CLI
   «never use network» и должно рассматриваться как отдельный дефект offline-интеграции.
2. Transformers повторно предупреждает, что `max_new_tokens=128` имеет приоритет над
   `max_length=200`; benchmark завершился успешно.
3. Benchmark диагностирует структурную целостность, но не доказывает качество смысла. Human review
   пока не выполнено; reference translations автоматически не сравниваются метрикой BLEU/COMET.
4. Реальный прогон выполнен только на CPU; CUDA не проверялась.
5. PDF extraction/OCR/rendering в реальном benchmark не запускались: это намеренная граница PDFTR-9.
   Исторические stage traces позволяют классифицировать такие дефекты, но не заменяют новый PDF E2E.
6. Baseline comparison покрыто автоматическим тестом; отдельного прошлого real-model baseline для
   статистического сравнения не было.
7. Единственный текущий выявленный дефект — защита filenames/CLI options в `command-01`.
8. Все временные артефакты созданы под `./temp`; reviews хранятся под `reviews/`; лишние `Tasks/`
   в изменения PDFTR-9 не добавлены.
9. Следующий тикет не начат: требуется check-in по этому отчёту и реальным результатам.

## Acceptance

- Dataset 50–100 примеров: **passed (61)**.
- Два обязательных PDFTR-8 regression inputs: **included and current run passed**.
- Разделение model/segmentation/protected/extraction/rendering: **passed**.
- JSON + Markdown + metadata + raw outputs: **passed**.
- Baseline support: **passed by tests**.
- Full project gate: **passed**.
- Human quality review: **not reviewed**.
