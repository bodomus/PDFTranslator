# Review — PDFTR-10

## Решение

PDFTR-10 готов к check-in. Реализация в `codex/PDFTR-10-layout-diagnostics-and-reporting`, implementation commit `5e82e21`. Добавлены privacy-safe JSON/HTML reports, отдельный selectable `debug-layout.pdf`, block-level translation/render evidence и CLI options. Обычный PDF и cache identity не изменены.

## Проверено

- Новые модули: `src/pdftranslate/diagnostics/{models,builder,reporting}.py` и публичный `__init__.py`.
- Pipeline сохраняет `RenderResult`, длительности стадий, peak RAM, OCR evidence и best-effort failure report без маскировки исходной ошибки.
- Fresh translation progress даёт точные `cache_status`/`segmentation_count`; renderer даёт exact fitting attempts, boxes, font и final state.
- JSON schema `1.0`; текст исключён по умолчанию, кириллица включается только явным opt-in.
- HTML полностью автономен и не содержит внешних assets.
- Debug PDF содержит source/final rectangles и извлекаемый block ID, не изменяя normal output.
- CLI: `--report`, `--report-format`, `--report-dir`, `--debug-layout`, `--include-report-text`.
- Focused: `42 passed in 3.60s`.
- Full `scripts/check.ps1`: formatter/Ruff/mypy passed; `150 passed, 1 skipped in 10.41s`; coverage `87.44%`.
- Реальные artifacts находятся в `temp/pdftr10-validation-final/`: JSON `2,872 B`, HTML `4,591 B`, debug PDF `586,769 B`, normal output `586,129 B`.
- Реальный generated-PDF прогон подтвердил отсутствие исходного английского абзаца, извлекаемый русский абзац, exact block evidence и извлекаемый debug block ID.

## Замечания review

1. Прогон artifacts использует deterministic fake translator, поэтому не доказывает качество NLLB, CUDA/VRAM или OCR. Цель PDFTR-10 — диагностика, не улучшение модели/вида PDF.
2. VRAM остаётся `null`; RAM — Python peak allocations, не полный RSS.
3. Reused historical translation stage не имеет старых per-block callbacks и честно показывает `null/unknown`.
4. В извлечённом русском PDF PyMuPDF выдаёт NBSP; поиск подтверждён после whitespace normalization. UTF-8 JSON корректен, хотя PowerShell без явного encoding способен показать mojibake.
5. Failure report не создаётся для ошибок до инициализации workspace/report destination.
6. Debug PDF больше normal output из-за шрифта и annotations; он не предназначен для публикации.
7. CRG: risk `0.40`, `21` heuristic gaps; прямые tests покрывают отмеченные CLI/pipeline contracts. Graphify: `1418/3025/89`, три zero-node JSON/config files — ограничение индексатора.
8. Windows sandbox потребовал повторить pytest/Graphify с корректным доступом. Ошибочные root pytest-cache directories проверены и удалены; финальный gate использовал только `./temp`.
9. Из-за отказа `apply_patch` на split writable roots применялись точечные replacements; промежуточные ошибки механической замены были пойманы Ruff/mypy, а mojibake в Markdown — проверкой diff. Всё исправлено до коммита.
10. Generated artifacts, cache, helper scripts, model files и user-specific absolute paths не коммитятся.
11. Блокирующих замечаний по итоговому diff и проверкам нет. Следующий тикет не начат.

## Вердикт

Готово к review/check-in после push ветки. Полный исходный отчёт: `implementation-report.md`.
