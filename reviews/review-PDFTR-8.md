# Review — PDFTR-8

## Результат ревью

Первоначальное доказательство по страницам 3 и 5 отклонено. Оно не подтверждало перевод
полноценного текста: страница 5 содержит только blank-page label, а на странице 3 появились
фрагменты перевода поверх неизменённого графического титула.

Исправленный результат подтверждён на странице 7. В финальном PDF виден связный русский абзац,
исходный английский абзац отсутствует, расположение сохранено, русский текст находится, выделяется
и копируется из text layer.

## Что изменено

- Защищённые токены переведены с Unicode sentinel на collision-safe ASCII placeholder.
- Фрагменты одного абзаца консервативно объединяются и корректно дедефисуются.
- Saved-PDF validation нормализует Unicode-дефисы.
- Pipeline identity получил behavior revision, исключающую resume со старыми extracted artifacts.
- Добавлены regression tests и ужесточены правила real-PDF evidence в документации.
- `Tasks/` исключён из итогового Git diff; временные файлы находятся только в `./temp`.

## Проверяемый артефакт

Финальный PDF:
`temp/pdftr8-correction/page7-final-revision/outputs/The_Sword_And_The_Shield_The_Mitrokhin_Archive_And_The_Secret_History_1.ru.pdf`

Визуальный render страницы 7:
`temp/pdftr8-correction/page7-final-revision-render/page-07.png`

Автоматический validation report:
`temp/pdftr8-correction/page7-final-revision/validation-summary.md`

## Фактические результаты

- Source: 10 pages, 73,160 bytes, SHA-256 неизменён.
- Output: 10 pages, 681,968 bytes, reopens successfully.
- Page 7 paragraph bbox: `(40.30, 382.97, 350.73, 419.29)`.
- Русские поисковые фразы: три из трёх найдены, по одному совпадению.
- Английские контрольные фразы: четыре из четырёх отсутствуют.
- Цельный русский абзац копируется из text layer.
- Page geometry unchanged; image count on page 7 = 1.
- Fresh run: all six stages passed; 0 cache hits / 10 misses.
- Resume: 0.59 s; all six stages reused.
- Full gate: Ruff clean, mypy clean, 134 passed, 1 skipped, coverage 86.93%.

## Отдельный дефект страницы 3

- Severity: major.
- Stage: rendering / block mapping.
- Reproducibility: deterministic on the inspected source.
- Наблюдение: перевод вставлен короткими фрагментами, исходный `SWORD/SHIELD` остаётся частью
  оформления; результат не является корректной заменой исходного блока.
- Решение для PDFTR-8: исключить страницу 3 из положительного evidence.
- Follow-up: отдельный сфокусированный тикет по graphical-title/block-mapping rendering.

## Все замечания

1. Страницы 3 и 5 не являются доказательством успешного real-world перевода.
2. Положительное доказательство относится к полноценному абзацу страницы 7, а не ко всему
   10-страничному документу.
3. Программная и визуальная проверки подтверждают отсутствие исходного английского абзаца,
   размещение, поиск и text-layer copy/select. Ручной PDF-XChange checklist остаётся `not_checked`.
4. Реальный OCR не проверен из-за отсутствующих OCRmyPDF/Tesseract/Ghostscript/English data;
   соответствующий opt-in test — единственный skipped.
5. CUDA не проверена из-за CPU-only Torch.
6. Корпус ограничен одним 10-страничным PDF и не покрывает длинные, табличные и two-column cases.
7. NLLB работал offline из существующего model cache; модель и generated PDF не входят в Git.
8. Сохраняются runtime warnings Transformers о `max_new_tokens`/`max_length` и Hugging Face об
   unauthenticated requests; на результат они не повлияли.
9. Потеря protected token исправлена и больше не считается открытым дефектом PDFTR-9.
10. Локальные `Tasks/` сохранены, но удалены из tracked tree ветки и не должны попасть в PR diff.
11. Следующий тикет не начат.

## Рекомендация

Рассматривать PDFTR-8 только по исправленному page-7 артефакту и настоящим результатам проверок.
Не закрывать отдельный дефект страницы 3 этим тикетом. После просмотра отчёта и PDF можно принять
решение по PDFTR-8; к следующему тикету до этого не переходить.
