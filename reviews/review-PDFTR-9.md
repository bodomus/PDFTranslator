# Review — PDFTR-9

## Решение

Работа готова к check-in, но не к заявлению о безусловно высоком качестве перевода. Инструмент
benchmark реализован, обязательные исторические дефекты разделены по происхождению и стадии,
полный gate зелёный. Реальный NLLB-прогон дал 60/61 passed и выявил один текущий дефект защиты
command tokens.

## Проверено

- Dataset содержит 61 образец и обязательные `pdftr8-token-1900-1` и
  `pdftr8-page7-numbers-junk`.
- Текущий NLLB сохранил `1900-1`, `1999`, `2001`, `10`, `53`, `10022-5299`; `F￾` не появился.
- Исторические повреждения не скрыты: они маркируются `historical_trace`, а текущие результаты —
  `current_run`.
- Status текущего sample не загрязняется историческим trace.
- Единственный current failure корректно показывает перевод `data.json`, `--device`, `--offline`.
- JSON/Markdown atomic output, malformed input, cache reuse, missing segments, protected-token
  restore failure, baseline comparison и CLI проверены тестами.
- `scripts/check.ps1`: 144 passed, 1 skipped, coverage 87.27%, Ruff/mypy passed.

## Замечания review

1. Human review отсутствует; automated result нельзя трактовать как оценку adequacy/fluency.
2. Историческое замечание об HTTP metadata requests при `--offline` исправлено в PDFTR-9A:
   model ID теперь до импорта Transformers разрешается в локальный snapshot, а config/tokenizer/model
   загружаются local-only под scoped offline environment. Реальный прогон с заблокированными proxy
   прошёл без HTTP request lines.
3. Transformers печатает предупреждение о приоритете `max_new_tokens` над `max_length`.
4. CUDA, OCR и реальный rendering не входят в этот прогон и не проверены.
5. Graphify incremental refresh завис после timeout и был остановлен без изменения graph output;
   pre-ticket graph analysis и source verification выполнены, CRG обновлён.
6. Финальный CRG audit проанализировал все 15 файлов и эвристически отметил CLI handler как test
   gap, хотя он покрыт end-to-end CLI unit test с fake backend.
7. Baseline comparison протестировано, но исторического real-model JSON baseline нет.
8. Ветка продолжена от текущего PDFTR-8 HEAD по прямому указанию пользователя, не от master.
9. Следующий тикет до check-in не начат.

## Артефакты

- `implementation-report.md`
- `reviews/review-PDFTR-9.md`
- `temp/pdftr9-benchmark/nllb.json`
- `temp/pdftr9-benchmark/nllb.md`

## PDFTR-9A corrective check-in

- Cache больше не переносит findings/status между samples с одинаковым source.
- Protected-token, human-review и historical-trace проверки выполняются для каждого sample.
- Strict offline real benchmark: 61 samples, 60 passed, 1 failed, 0 errors; 44.183 seconds;
  0 cache hits / 61 misses; network blocked through invalid proxies.
- Единственный прежний `command-01` defect остаётся отдельным и не исправлялся.
- Полный gate после correction: 152 passed, 1 skipped, coverage 87.70%.
- Подробный review: `reviews/review-PDFTR-9A.md`.
