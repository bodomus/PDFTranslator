# PDFTR-44 — Agent Progress Journal and Last Meaningful Activity

## Goal

Добавить в Pi agent-cycle наблюдаемость долгих implementer/reviewer runs без вывода chain-of-thought и без заметного роста token usage.

Текущий heartbeat показывает только длительность:

```text
[PDFTR-43] implementer running... 95m
```

Этого недостаточно, чтобы понять:

- agent реально работает или завис;
- на каком этапе он находится;
- когда была последняя значимая активность;
- упёрся ли он в tests, external API, network, authorization или другую проблему;
- стоит ли продолжать ждать или нужен human intervention.

Нужен короткий operational progress journal, который фиксирует только фактические milestones.

---

## Background

Во время PDFTR-43 implementer работал около 165 минут и завершился с exit code 1.

Обычный runner heartbeat не позволял понять, что происходило внутри процесса.

После human-approved recovery был введён ручной progress log:

```text
.agent-cycle/PDFTR-43/implementer-progress.log
```

Он показал реальную последовательность событий и позволил отличить зависание от внешнего блокера.

PDFTR-44 должен сделать эту наблюдаемость штатной частью harness.

---

## 1. Progress journal

Для каждого active role должен существовать отдельный progress journal.

Например:

```text
.agent-cycle/PDFTR-44/implementer-progress.log
.agent-cycle/PDFTR-44/reviewer-progress.log
```

Файл append-only в рамках role execution.

Journal является coordination/diagnostic artifact.

Он не является reasoning transcript.

---

## 2. Allowed content

Progress journal должен содержать только короткие factual milestones.

Примеры:

```text
[10:15] Inspecting existing implementation and ticket scope
[10:24] Added project tracking adapter skeleton
[10:31] Running focused project-tracking tests
[10:35] Focused tests failed: 3 failures in idempotency handling
[10:47] Fixed duplicate-comment idempotency
[10:55] Focused tests PASS: 67 passed
[11:03] Running full scripts/check.ps1
[11:17] Full scripts/check.ps1 PASS
[11:20] Push blocked: github.com DNS unavailable
```

Не записывать:

- chain-of-thought;
- internal reasoning;
- подробный пересказ каждого file read;
- каждую мелкую правку;
- длинные explanations;
- secrets;
- credentials;
- raw prompts;
- authentication tokens.

---

## 3. Logging frequency

Agent пишет progress entry только при meaningful event:

- начало крупного investigation step;
- завершение крупного implementation step;
- запуск focused tests;
- результат focused tests;
- запуск full validation;
- validation failure;
- существенный blocker;
- изменение направления из-за discovered issue;
- external integration limitation;
- commit;
- push;
- final completion.

Не писать entry для каждого command/file/minor edit.

Цель — обычно порядка 5–20 строк на role run, а не сотни строк.

---

## 4. Timestamp format

Использовать стабильный timestamp format:

```text
[HH:MM] message
```

или общий timestamp utility harness.

Выбрать один формат и документировать timezone.

---

## 5. Harness-owned journal contract

Предпочтительно не полагаться только на prompt convention.

Harness должен:

1. определить journal path для role;
2. передать этот path в agent prompt;
3. разрешить role писать только свой progress journal;
4. не позволять reviewer писать implementer journal;
5. сохранять journal после success/failure/cancel;
6. не удалять его при recovery/resume;
7. не использовать journal как authoritative state.

Authoritative state остаётся в manifest / handoff / review artifacts.

Progress journal — diagnostic evidence only.

---

## 6. Heartbeat integration

Текущий heartbeat:

```text
[PDFTR-XX] implementer running... 95m
```

должен показывать last meaningful activity.

Например:

```text
[PDFTR-XX] implementer running... 95m — last: [19:42] Running focused project-tracking tests
```

Формат должен оставаться читаемым в PowerShell/Cmder.

---

## 7. Last meaningful activity parser

Harness должен безопасно читать последнюю валидную journal line.

Requirements:

- journal may not exist yet;
- journal may be empty;
- last line may be partially written;
- malformed line must not crash runner;
- excessively long line should be truncated;
- control characters should be sanitized.

Если journal unavailable, heartbeat может оставаться в старом формате или показывать:

```text
last activity: none reported yet
```

---

## 8. Stale activity warning

Добавить configurable warning, если process жив, но meaningful activity давно не менялась.

Например:

```text
[PDFTR-XX] implementer running... 75m
[PDFTR-XX] WARNING: no new meaningful activity for 35m
last: [14:20] Running YouTrack schema discovery
```

Это только diagnostic warning.

Он не должен автоматически kill process в PDFTR-44.

Suggested default:

```text
progress_stale_minutes = 30
```

---

## 9. No automatic timeout in PDFTR-44

PDFTR-44 не вводит hard execution timeout.

Долгий task может быть legitimate.

В этом тикете нужны только:

- progress visibility;
- stale detection;
- diagnostics.

Controlled checkpoint / execution budget — отдельный follow-up.

---

## 10. Prompt contract

Implementer/reviewer prompts должны автоматически получать короткую секцию:

```text
Maintain a concise operational progress log at:

.agent-cycle/<ticket>/<role>-progress.log

This is NOT a reasoning journal.

Append only short factual milestones:
- major step started/completed
- tests started/result
- meaningful blocker
- external integration failure
- commit/push/completion

Do not write chain-of-thought or detailed reasoning.
Do not log every file read or minor edit.
Keep each entry to one short line.
```

Эта policy должна генерироваться централизованно в harness.

---

## 11. Reviewer behavior

Reviewer тоже ведёт progress journal, но короче.

Например:

```text
[13:05] Verified exact reviewed SHA and clean tree
[13:11] Reviewing previous findings
[13:18] Running targeted regression probes
[13:23] Review PASS
```

Reviewer journal:

- не является review verdict;
- не заменяет `review-N.json`;
- не может содержать repository mutations;
- не ослабляет read-only restrictions.

---

## 12. Resume behavior

При resume:

- existing journal не удалять;
- новый execution продолжает append;
- желательно добавить boundary entry:

```text
[15:10] Resumed implementer execution after interrupted run
```

Допустимы same-role journal или per-attempt journal.

Главное — история предыдущего run не должна теряться.

---

## 13. Failure / cancellation

Если role process exits non-zero, cancelled или terminated, journal должен сохраниться.

Runner final diagnostic должен показать:

```text
ERROR: implementer exited with code 1
Last activity: [09:11] Push remains blocked by github.com DNS failures
Progress log: .agent-cycle/PDFTR-43/implementer-progress.log
```

---

## 14. Token / context policy

Progress logging должен иметь минимальный token overhead.

Requirements:

- no reasoning summaries;
- no duplicated implementation report content;
- one-line milestones only;
- no periodic agent-generated heartbeat messages;
- harness heartbeat reads local journal instead of asking model for status.

Target: practically negligible overhead, ideally around 1–2% or less for normal runs.

---

## 15. Security

Never log:

- API tokens;
- passwords;
- OAuth codes;
- Authorization headers;
- full environment dumps;
- secret-bearing URLs.

External failures should be summarized rather than pasted raw if output may contain secrets.

---

## 16. Configuration

Добавить minimal configuration, если это соответствует current harness architecture.

Example:

```toml
[agent_progress]
enabled = true
stale_minutes = 30
max_console_chars = 180
```

Defaults должны работать без project-specific configuration.

---

## 17. Tests

Добавить deterministic tests минимум для:

### Journal parsing

- missing journal;
- empty journal;
- valid last line;
- malformed final line;
- partially written final line;
- very long line truncation;
- control-character sanitization.

### Heartbeat

- heartbeat without progress;
- heartbeat with last activity;
- updated activity replaces previous console value;
- stale threshold emits warning;
- no warning before threshold.

### Role isolation

- implementer receives implementer journal path;
- reviewer receives reviewer journal path;
- reviewer cannot mutate implementer journal through allowed role capabilities.

### Resume

- existing journal preserved;
- resume appends rather than truncates;
- attempt/round boundary retained.

### Failure

- non-zero exit reports last activity;
- cancelled role reports last activity;
- journal remains after STOPPED cycle.

### Safety regression

Existing tests for process cleanup, Windows Job Object, POSIX process groups, role permissions, review read-only mode, resume/recovery and exact-SHA handling must remain green.

---

## 18. Acceptance criteria

- Implementer and reviewer can maintain concise progress journals.
- Journals contain factual milestones only.
- Runner heartbeat shows last meaningful activity.
- Stale meaningful activity emits a warning.
- No hard timeout is introduced.
- Progress logging does not alter authoritative cycle state.
- Progress artifacts survive failure, cancellation and resume.
- Reviewer read-only guarantees remain intact.
- No sensitive credentials are logged.
- Logging overhead remains small.
- Full `scripts/check.ps1` passes.
- Windows and Ubuntu CI pass.

---

## Non-goals

Do not implement in PDFTR-44:

- hard execution timeout;
- automatic process kill based on stale activity;
- automatic recovery decisions;
- chain-of-thought logging;
- full command transcript recording;
- shell/session recording;
- agent performance analytics;
- UI dashboard;
- remote log shipping.

---

## Follow-up candidates

Potential next infrastructure tickets:

- Agent execution budget and controlled checkpointing
- Automatic stale-run escalation
- Progress journal aggregation into PR / human-review handoff
- Historical runtime metrics per provider/model
- Operator dashboard for active agent cycles
