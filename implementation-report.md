# Implementation report — PDFTR-10

## Итог

PDFTR-10 реализован в ветке `codex/PDFTR-10-layout-diagnostics-and-reporting`. Исходная реализация — `5e82e21`; PDFTR-9A (`a6027c4`) сначала влит в `master` merge-коммитом `cb7cde8`, затем новый master влит в PDFTR-10 как `f8c43a9`. Follow-up исправления diagnostics находятся в `43dac4b`. Зависимости не добавлялись.

## Follow-up после merge PDFTR-9A

- Каждый запуск резервирует уникальный каталог `run-<UTC timestamp>-<workspace prefix>-<execution UUID>` под `--report-dir` или рядом с output PDF.
- JSON, HTML и debug PDF публикуются только внутри каталога запуска; предыдущие артефакты не переиспользуются и не заменяются.
- `write_report()` заранее отклоняет существующие targets, а финальная публикация использует same-directory temporary file и атомарный hard link, который не умеет заменять destination.
- Debug PDF использует ту же no-replace схему.
- Ошибка success-report/debug publication после успешной валидации PDF преобразуется в `PipelineExecutionError` с отдельным `ExitCode.DIAGNOSTIC_PUBLICATION_FAILED = 11`. Сообщение и log явно указывают, что валидный переведённый PDF уже опубликован и остаётся доступен.
- Ошибка публикации failure report остаётся best-effort и не маскирует исходную stage error.

## Новые файлы diagnostics

- `src/pdftranslate/diagnostics/__init__.py` — публичный диагностический API.
- `src/pdftranslate/diagnostics/models.py` — версия схемы `1.0`, модели run/summary/page/block/finding и стабильные коды.
- `src/pdftranslate/diagnostics/builder.py` — сбор success/failure отчётов из фактических данных pipeline, translation, OCR и renderer.
- `src/pdftranslate/diagnostics/reporting.py` — атомарная запись UTF-8 JSON и автономного HTML без внешних ресурсов.
- `tests/test_diagnostics.py` — стабильность кодов, валидация CLI-настроек и неизменность identity переводимого артефакта.

Стабильные коды: `READING_ORDER_AMBIGUOUS`, `TRANSLATION_TOKEN_MISMATCH`, `FONT_REDUCED`, `BLOCK_EXPANDED`, `BLOCK_OVERFLOW`, `OCR_LOW_TEXT_GAIN`, `OUTPUT_VALIDATION_FAILED`, `PIPELINE_STAGE_FAILED`, `RENDER_WARNING`.

## Pipeline и translation

`PipelineOptions` и `PipelineResult` расширены настройками/путями diagnostics. Параметры отчёта намеренно исключены из `identity_values()`, поскольку не меняют содержимое переводимого PDF.

`run_pipeline()` теперь:

- измеряет общую длительность и длительности всех шести стадий;
- собирает измеримый peak RAM через `tracemalloc` только при запросе отчёта и гарантированно останавливает tracing;
- сохраняет `RenderResult` вместо потери block-level данных;
- связывает `TranslationProgress` с block ID, точным `segmentation_count` и `cache_status` для свежей стадии перевода;
- формирует success report после успешной валидации;
- формирует best-effort failure report и не заменяет им исходную pipeline-ошибку;
- при `--resume` повторяет render, если требуются report/debug evidence, вместо выдачи отчёта без layout-данных;
- атомарно публикует `debug-layout.pdf` в уникальный каталог текущего запуска.

Translation progress различает `hit`, `miss`, `skipped`, `unknown`. Для исторически переиспользованной стадии, у которой block-level события уже отсутствуют, значения остаются честно `null`/`unknown`.

## Renderer

Renderer теперь сохраняет точное число попыток fitting для каждого блока. Отдельный debug PDF содержит:

- исходный и финальный прямоугольники;
- цветовое состояние rendered/expanded/overflow/skipped;
- извлекаемую подпись со стабильным block ID, например `p0001-b0001 [rendered]`;
- отметки OCR pages.

Обычный PDF создаётся и валидируется отдельно; debug overlay в него не попадает. В summary также записывается выбранный renderer font, а общие renderer warnings получают код `RENDER_WARNING`.

## JSON- и HTML-отчёты

`translation-report.json` содержит статус, run ID, пути входа/выхода, стадии, размеры, page types, OCR/cache/translation/render counters, fitting/geometry/final state по блокам, findings, измеримый RAM и nullable VRAM.

`translation-report.html` строится из той же версии модели, экранирует значения, содержит встроенный CSS и не использует скрипты, ссылки, CDN или сетевые assets.

Исходный и переведённый текст по умолчанию равны `null`. Поля заполняются только при явном `--include-report-text` вместе с `--report`.

## CLI

Добавлены опции основного end-to-end запуска:

- `--report`;
- `--report-format json|html|both`;
- `--report-dir PATH`;
- `--debug-layout`;
- `--include-report-text`.

CLI печатает пути созданных report/debug artifacts. Typer остаётся только boundary для разбора аргументов; domain, translation, renderer и diagnostics от него не зависят.

## Focused tests

Команда:

```powershell
uv run pytest tests/test_diagnostics.py tests/test_end_to_end_pipeline.py tests/test_rendering.py tests/test_cli.py tests/test_nllb.py tests/test_translation_benchmark.py --no-cov --basetemp temp/pdftr10-followup-focused2 -o cache_dir=temp/pdftr10-followup-focused2-cache
```

Результат после merge PDFTR-9A: `68 passed in 4.24s`. Перед тестами также прошли Ruff и mypy (`63 source files`).

Покрыты success/failure reports, no-replace writer, два независимых run-specific каталога, exit code 11 с сохранением normal PDF, сохранение исходной stage error, privacy default, opt-in Cyrillic, offline HTML, block IDs в debug PDF, cache/segmentation/fitting evidence, selected font, CLI propagation и создание всех трёх диагностических артефактов.

## Full tests

Обязательный `./scripts/check.ps1` повторён после всех изменений с `TEMP`, `TMP`, uv cache и pytest cache/basetemp под `./temp`.

Результат:

- formatter: `101 files already formatted`;
- Ruff: passed;
- mypy: `63 source files`, no issues;
- pytest: `161 passed, 1 skipped in 10.89s`;
- coverage: `87.78%` при требовании `80%`.

Один skip — существующий opt-in integration path; unit/CI gate не скачивал model weights и не требовал CUDA/OCR tools.

## Реально созданные диагностические артефакты

Локальный end-to-end прогон с generated English paragraph и детерминированным fake translator (без скачивания модели) создал source/normal output в `temp/pdftr10-followup-validation/`, а JSON/HTML/debug PDF — в уникальном `temp/pdftr10-followup-validation/reports/run-20260801T125703.565212Z-9395d0524fee-5b7c0a19f0db47488c70d109f1f381ba/`:

| Артефакт | Размер | Проверка |
|---|---:|---|
| `diagnostic-source.pdf` | 1,005 B | один полноценный английский абзац |
| `diagnostic-output.pdf` | 586,129 B | английский абзац отсутствует; связный русский текст извлекается и ищется после нормализации NBSP |
| `translation-report.json` | 2,965 B | schema `1.0`, status `success`, все 6 стадий |
| `translation-report.html` | 4,679 B | нет `<script src>`, `<link rel>`, `http://`, `https://` |
| `debug-layout.pdf` | 586,769 B | извлекается block ID `p0001-b0001`; normal output не изменён overlay-разметкой |

Фактические значения блока: `cache_status=miss`, `segmentation_count=1`, `fitting_attempts=1`, `final_state=rendered`; summary: `1` text page, `1` block, `1` translated segment, `0` overflow, `0` OCR pages, peak RAM `1,822,099 B`, peak VRAM `null`, renderer выбрал `arial.ttf`.

PDF extractor возвращает между русскими словами NBSP (`U+00A0`), поэтому точная автоматическая проверка поиска нормализует whitespace. Это не повреждение текста: извлечение, выделение/копирование и поиск после стандартной нормализации подтверждены. JSON прочитан Python как корректный UTF-8 с кириллицей; отображаемый PowerShell `Get-Content` без явного encoding может показывать mojibake и не является дефектом файла.

Сгенерированные PDF/JSON/HTML, cache и validation helper scripts находятся только в `./temp` и не включены в Git.

## Repository intelligence и blast radius

- CRG post-change: `725` FTS rows; follow-up diff содержит `16` changed symbols, `0` affected flows, heuristic risk `0.40`, `8` heuristic test gaps. CRG пометил `write_report`, `_atomic_write_new`, `ExitCode` и `run_pipeline` как gaps, хотя они прямо покрыты no-replace, exit-code и E2E тестами; source/pytest являются авторитетными.
- Graphify post-change: `1475 nodes`, `3163 edges`, `90 communities`. BFS нашёл новый run-directory → no-replace writer → explicit publication-error path и соответствующий тест; связность подтверждена исходниками и runtime.
- Graphify сообщил три существующих source-файла с zero nodes (`hooks.json`, `translation-en-ru-v1.json`, `validation-corpus.example.json`); это ограничение индексатора, не runtime defect PDFTR-10.
- Изменение пересекает CLI, orchestration, translation progress и renderer result, но не меняет cache key, document schema, model lifecycle, OCR subprocess или атомарную публикацию обычного PDF.

## Все замечания и ограничения

1. Реальный artifact run использовал локальный deterministic fake translator. Качество NLLB, CUDA/VRAM и реальный OCR этим тикетом не подтверждались; full tests намеренно не скачивают большие модели. Это диагностика pipeline/layout, а не заявление о качестве модели.
2. Peak VRAM остаётся `null`, пока нет надёжного доступного измерителя без новой зависимости. Peak RAM отражает Python allocations `tracemalloc`, а не полный process RSS.
3. Исторически reused translation stage не может восстановить per-block callbacks; поэтому её `segmentation_count/cache_status` остаются `null/unknown`. Свежая стадия даёт точные значения.
4. Text inclusion — сознательный privacy opt-in. В validation example он включён для проверки кириллицы; production default исключает оба текста.
5. Debug PDF предназначен для диагностики и заметно увеличивает размер за счёт встроенного шрифта/разметки; normal PDF остаётся отдельным артефактом.
6. Failure report возможен только после успешной инициализации workspace/report path. Ошибки до этой точки возвращаются обычным `PipelineExecutionError` без ложного отчёта.
7. Первые sandboxed pytest-запуски на Windows не могли читать автоматически созданные temp ACL. Проверки повторены с escalation и явными путями под `./temp`.
8. Один промежуточный full-gate вызов с абсолютными Windows paths в `PYTEST_ADDOPTS` был разобран pytest как строки без backslashes и создал три cache-каталога в root. Их точные пути были проверены и каталоги удалены; финальный gate повторён с `temp/...` и прошёл.
9. Встроенный `apply_patch` дважды отказал из-за Windows split writable-root sandbox. Применялись узкие проверяемые PowerShell replacements. Две ранние слишком широкие механические замены были обнаружены Ruff/mypy до тестов. Позднее encoding-sensitive редактирование Markdown временно дало mojibake; `git diff` обнаружил его, файлы восстановлены как UTF-8 без BOM. Ни одна из этих промежуточных ошибок не присутствует в итоговом diff.
10. Graphify без escalation получил `WinError 5` при обходе sandbox ACL; повторный локальный update с доступом прошёл. CRG heuristic gaps не заменяют test evidence.
11. Не добавлены зависимости, generated PDFs, model weights, caches, logs или user-specific absolute paths.
12. PDFTR-9A присутствует в новом master и в текущей ветке; финальный gate учитывает оба набора тестов и составляет `161 passed, 1 skipped`.
13. No-replace atomic publication использует hard links и требует файловую систему с их поддержкой. На неподдерживаемой filesystem diagnostics завершается явным exit code 11; уже опубликованный основной PDF не удаляется.
14. При формате `both` JSON может быть уже опубликован, если последующая HTML publication падает. Это не скрывается: запуск возвращает exit code 11, существующий JSON не перезаписывается, partial evidence сохраняется для диагностики.
15. При debug-only запуске, завершившемся до render publication, зарезервированный уникальный каталог может остаться пустым; он никогда не переиспользуется.
16. Следующий тикет не начат; ветка готова к повторному check-in/review.

## Acceptance criteria

Все критерии PDFTR-10 выполнены: success/failure JSON, offline HTML, stable codes, page/block evidence, annotated debug PDF, privacy default, cache/OCR/fitting/overflow/validation data, run-specific paths, запрет silent overwrite, явная success-report failure semantics, совместимый CLI и зелёный combined gate `161 passed, 1 skipped`.
