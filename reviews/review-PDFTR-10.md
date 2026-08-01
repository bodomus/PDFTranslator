# Review — PDFTR-10

## Решение

PDFTR-10 готов к повторному check-in. PDFTR-9A (`a6027c4`) влит в master как `cb7cde8`, новый master в PDFTR-10 — `f8c43a9`. Исходная diagnostics implementation — `5e82e21`, follow-up no-overwrite/run-specific fix — `43dac4b`. Обычный PDF и cache identity не изменены.

## Проверено

- Новые модули: `src/pdftranslate/diagnostics/{models,builder,reporting}.py` и публичный `__init__.py`.
- Pipeline сохраняет `RenderResult`, длительности стадий, peak RAM, OCR evidence и best-effort failure report без маскировки исходной ошибки.
- Fresh translation progress даёт точные `cache_status`/`segmentation_count`; renderer даёт exact fitting attempts, boxes, font и final state.
- JSON schema `1.0`; текст исключён по умолчанию, кириллица включается только явным opt-in.
- HTML полностью автономен и не содержит внешних assets.
- Debug PDF содержит source/final rectangles и извлекаемый block ID, не изменяя normal output.
- Каждый запуск получает отдельный `run-<timestamp>-<workspace>-<UUID>` каталог; JSON/HTML/debug PDF не могут молча заменить существующие targets.
- Ошибка success-report/debug publication возвращает exit code 11 и явно сохраняет уже валидированный normal PDF. Failure-report publication по-прежнему не маскирует исходную stage error.
- CLI: `--report`, `--report-format`, `--report-dir`, `--debug-layout`, `--include-report-text`.
- Focused с тестами PDFTR-9A: `68 passed in 4.24s`.
- Full `scripts/check.ps1`: formatter/Ruff/mypy passed; `161 passed, 1 skipped in 10.89s`; coverage `87.78%`.
- Реальные JSON `2,965 B`, HTML `4,679 B` и debug PDF `586,769 B` находятся в уникальном `temp/pdftr10-followup-validation/reports/run-20260801T125703.565212Z-9395d0524fee-5b7c0a19f0db47488c70d109f1f381ba/`; normal output `586,129 B` находится уровнем выше и не изменён diagnostics.
- Реальный generated-PDF прогон подтвердил отсутствие исходного английского абзаца, извлекаемый русский абзац, exact block evidence и извлекаемый debug block ID.

## Замечания review

1. Прогон artifacts использует deterministic fake translator, поэтому не доказывает качество NLLB, CUDA/VRAM или OCR. Цель PDFTR-10 — диагностика, не улучшение модели/вида PDF.
2. VRAM остаётся `null`; RAM — Python peak allocations, не полный RSS.
3. Reused historical translation stage не имеет старых per-block callbacks и честно показывает `null/unknown`.
4. В извлечённом русском PDF PyMuPDF выдаёт NBSP; поиск подтверждён после whitespace normalization. UTF-8 JSON корректен, хотя PowerShell без явного encoding способен показать mojibake.
5. Failure report не создаётся для ошибок до инициализации workspace/report destination.
6. Debug PDF больше normal output из-за шрифта и annotations; он не предназначен для публикации.
7. CRG follow-up: `725` FTS rows, risk `0.40`, `8` heuristic gaps; прямые tests покрывают отмеченные writer/exit-code/pipeline contracts. Graphify: `1475/3163/90`, три zero-node JSON/config files — ограничение индексатора.
8. Windows sandbox потребовал повторить pytest/Graphify с корректным доступом. Ошибочные root pytest-cache directories проверены и удалены; финальный gate использовал только `./temp`.
9. Из-за отказа `apply_patch` на split writable roots применялись точечные replacements; промежуточные ошибки механической замены были пойманы Ruff/mypy, а mojibake в Markdown — проверкой diff. Всё исправлено до коммита.
10. Generated artifacts, cache, helper scripts, model files и user-specific absolute paths не коммитятся.
11. No-replace publication использует hard links. Неподдерживаемая filesystem приводит к явному exit code 11, а не к fallback с перезаписью; основной PDF сохраняется.
12. При `both` возможен явный partial diagnostics result (JSON опубликован, HTML упал); существующий JSON сохраняется и запуск возвращает 11.
13. Debug-only failure до render может оставить пустой уникальный run directory; повторно он не используется.
14. Итоговый combined gate с учётом PDFTR-9A: `161 passed, 1 skipped`. Блокирующих замечаний нет; следующий тикет не начат.

## Вердикт

Готово к повторному review/check-in после push обновлённой ветки. Полный отчёт PDFTR-10: `implementation-report.md`.
