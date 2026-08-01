# Implementation Report — PDFTR-8

## Итог

PDFTR-8 исправлен после отклонения первоначального real-world доказательства. Страницы 3 и 5
не считаются подтверждением успешного перевода. Финальное положительное доказательство получено
на странице 7, содержащей полноценный английский абзац: создан PDF со связным русским текстом,
без исходного английского абзаца под переводом, с сохранённым размещением, поиском, выделением и
копированием русского текста.

Ветка: `codex/PDFTR-8-real-pdf-end-to-end-validation`, создана от `master`.

## Исправление ошибочного вывода

- Предыдущий результат на страницах 3 и 5 отклонён.
- Страница 5 содержит только `This Page Intentionally Left Blank` и не является содержательным
  примером перевода.
- Страница 3 содержит графический титул. Перевод вставился отдельными фрагментами поверх страницы,
  а исходное оформление `SWORD/SHIELD` осталось. Это отдельный воспроизводимый дефект рендеринга
  или сопоставления блоков, а не успешный перевод.
- Формулировки о подтверждённом real-world переводе по страницам 3/5 удалены из отчёта и review.

## Выявленные причины и изменения

1. NLLB удалял Unicode-маркеры защищённых токенов. Маркеры заменены на collision-safe ASCII
   placeholders вида `__PDFTR_0000__`; добавлена проверка восстановления и коллизий.
2. Полноценный абзац страницы 7 извлекался тремя блоками, включая перенос `infor-` / `mation`.
   Добавлено консервативное объединение только явно продолжающихся соседних блоков с
   детерминированной дедефисацией. Титульные блоки страницы 3 не объединяются.
3. Проверка сохранённого PDF ошибочно различала ASCII hyphen и Unicode PDF hyphen. Валидация
   текста теперь выполняет NFKC-нормализацию, унифицирует дефисы и пробелы.
4. В identity workspace добавлена `PIPELINE_BEHAVIOR_REVISION = 2`, чтобы resume не использовал
   артефакты, извлечённые до изменения поведения.
5. README и `docs/real-pdf-validation.md` теперь прямо запрещают считать титульные фрагменты,
   номера страниц и blank-page labels положительным real-world доказательством.
6. В `.gitignore` закреплены `/temp/` и `Tasks/`; все временные артефакты создавались в `./temp`.
7. Лишние файлы `Tasks/` удалены из итогового diff ветки и сохранены локально как ignored files.

Зависимости не добавлялись; `pyproject.toml` и `uv.lock` не изменены.

## Архитектурная и blast-radius проверка

- Graphify использован для ориентации по цепочке extraction → translation → rendering →
  validation; важные связи перепроверены по исходникам.
- CRG post-change update: 51 files updated, 77 nodes и 849 edges пересчитаны; FTS index содержит
  647 rows.
- `detect-changes` оценил risk как 0.60 и указал затронутые extraction helpers, protected-token
  handling, saved-PDF validation и pipeline identity.
- CRG эвристически отметил paragraph-merge helpers как test gaps, однако их положительный,
  dehyphenation и page-3 non-merge сценарии прямо покрыты в `tests/test_pdf_extraction.py`; исходные
  тесты и полный executable gate приняты как авторитетные.
- Схемы extracted/translated JSON не изменены. Намеренное compatibility-изменение — старые
  pipeline workspaces считаются несовместимыми из-за behavior revision.
- Новых архитектурных слоёв и зависимостей от Typer в domain/translation коде не появилось.

## Автоматические проверки

- Целевой набор: 64 теста прошли; отдельный неполный запуск вернул exit 1 только из-за глобального
  порога coverage, что ожидаемо для выборочного набора.
- `./scripts/check.ps1`: успешно.
  - Ruff format: 87 files already formatted.
  - Ruff lint: passed.
  - mypy: no issues in 54 source files.
  - pytest: 134 passed, 1 skipped.
  - coverage: 86.93% при требовании 80%.
- Пропущен только opt-in OCR integration test: системные OCR-зависимости недоступны.

## Финальное real-PDF доказательство

Источник:
`tests/The_Sword_And_The_Shield_The_Mitrokhin_Archive_And_The_Secret_History_1.pdf`

- Размер: 73,160 bytes; страниц: 10.
- SHA-256 до и после:
  `801d700f6aaf4dbc27774b4a857c56db42ede309e3bea15d051156f02f65dfce`.
- Выбрана страница 7 (`mixed`), содержащая полноценный copyright-абзац.
- NLLB: offline, CPU, OCR off, `MaxInputTokens=64`, свежий translation cache.
- Первый запуск: все шесть стадий прошли примерно за 12.78 s; translate занял примерно 12.24 s;
  0 cache hits / 10 misses.
- Resume: 0.59 s по result JSON; inspect, OCR, extract, translate, render и validate переиспользованы.
- Выходной PDF: 681,968 bytes, 10 страниц, успешно переоткрывается.
- Итоговый абзац копируется из text layer целиком:

  > Все права защищены. Издан в Соединенных Штатах Америки. Ни одна часть этой книги не может
  > быть воспроизведена каким-либо образом без письменного разрешения, кроме случаев кратких
  > цитат, содержащихся в критических статьях и обзорах. Для получения информации, обратитесь к
  > адресу Basic Books, 10 East 53rd Street, Нью-Йорк, Нью-Йорк 10022-5299.

- Русский поиск: `Все права защищены`, `письменного разрешения`,
  `критических статьях и обзорах` — по одному совпадению.
- Английские фразы `All rights reserved`, `No part of this book`, `written permission` и
  `brief quotations` отсутствуют в extracted text итоговой страницы.
- Bounding box абзаца: `(40.30, 382.97, 350.73, 419.29)`; визуально русский текст остаётся в
  исходной области, не выходит за страницу и не перекрывает соседние блоки.
- Изображение страницы сохранено: image count = 1; геометрия страницы совпадает с источником.
- Рендер для визуальной проверки:
  `temp/pdftr8-correction/page7-final-revision-render/page-07.png`.
- Финальный PDF:
  `temp/pdftr8-correction/page7-final-revision/outputs/The_Sword_And_The_Shield_The_Mitrokhin_Archive_And_The_Secret_History_1.ru.pdf`.

## Все замечания и ограничения

1. Страница 3 зафиксирована как отдельный дефект рендеринга/сопоставления блоков: перевод
   вставляется фрагментами и не заменяет исходный графический титул. Она исключена из acceptance
   evidence PDFTR-8 и требует отдельного сфокусированного тикета.
2. Страница 5 — intentional blank-page label; она исключена из acceptance evidence.
3. Программно проверены поиск, извлечение/копирование text layer, отсутствие английского текста,
   геометрия и визуальный PNG. Ручной checklist непосредственно в PDF-XChange Editor всё ещё имеет
   состояние `not_checked`; человеческая проверка UI не заявляется как выполненная.
4. OCR не проверялся на реальных scanned pages: OCRmyPDF, Tesseract, Ghostscript и English OCR data
   недоступны. Страницы 1, 2 и 8 требуют отдельной OCR-среды.
5. CUDA не проверялась: установлен CPU-only Torch, хотя на машине имеется RTX 4080.
6. Реальный корпус пока состоит из одного 10-страничного документа; 100–300-страничные,
   table-heavy и two-column документы этим прогоном не покрыты.
7. Модель использована из существующего локального Hugging Face cache через junction внутри
   `./temp`; веса и generated PDFs не добавлены в Git.
8. Transformers предупреждает, что `max_new_tokens=128` имеет приоритет над `max_length=200`.
   Hugging Face также печатает предупреждение об unauthenticated requests даже в offline/cache
   режиме. Эти предупреждения не помешали успешному прогону.
9. Старый дефект потери protected token больше не переносится в PDFTR-9 как нерешённый: он исправлен
   ASCII placeholder и подтверждён real-model прогоном с адресом `10022-5299`.
10. Локальные файлы `Tasks/` не удалены с диска, но удалены из отслеживаемого дерева ветки; ZIP и
    Markdown из `Tasks/` не входят в итоговый diff относительно `master`.
11. Следующий тикет не начат.

## Acceptance status

- Полноценный английский абзац → связный русский абзац: **passed (page 7)**.
- Английский текст не остаётся под переводом: **passed programmatically and visually**.
- Размещение: **passed visual render and geometry checks**.
- Выделение/копирование: **passed through PDF text-layer extraction**.
- Поиск русского текста: **passed**.
- Изображение на mixed page сохранено: **passed**.
- Source unchanged и resume: **passed**.
- Human PDF-XChange checklist: **not_checked**.
- Page 3 title rendering/mapping: **separate known defect, not acceptance evidence**.
