# PDFTR-42 — Resumable Pi Ticket Cycle and Human-Approved Recovery

## Goal

Сделать `scripts/pi_ticket_cycle.py` возобновляемым и убрать необходимость вручную проводить agent-cycle через промежуточные состояния.

Текущий runner умеет штатно стартовать только из `NEW`.

В PDFTR-41 это привело к ручному recovery после состояний:

- `READY_FOR_REVIEW`
- `CHANGES_REQUIRED`
- `READY_FOR_REVIEW_2`
- `STOPPED` после `repeated_finding`

Низкоуровневая state machine в `scripts/agent_cycle.py` уже поддерживает большую часть необходимых переходов, но orchestration wrapper не умеет продолжать существующий цикл.

---

## Required behavior

### 1. Resume from `READY_FOR_REVIEW`

При запуске:

```powershell
uv run python scripts/pi_ticket_cycle.py PDFTR-XX --preset codex-codex
```

если cycle находится в:

```text
READY_FOR_REVIEW
```

runner должен:

1. не запускать implementer повторно;
2. вызвать `begin_review`;
3. запустить reviewer round 1;
4. обработать результат обычным образом.

---

### 2. Resume from `CHANGES_REQUIRED`

Если состояние:

```text
CHANGES_REQUIRED
```

runner должен:

1. загрузить findings предыдущего review;
2. вызвать `begin_implementation`;
3. запустить implementer следующего attempt;
4. потребовать новый SHA;
5. принять новый `implementer.json`;
6. перейти к следующему review round.

---

### 3. Resume from `READY_FOR_REVIEW_2`

Если состояние:

```text
READY_FOR_REVIEW_2
```

runner должен:

1. не запускать implementer;
2. начать review round 2;
3. проверить exact SHA;
4. записать verdict через существующий `record_review`.

---

### 4. Preserve terminal states

Следующие состояния не должны автоматически продолжаться:

```text
PASSED
BLOCKED
STOPPED
```

Runner должен fail closed с понятным сообщением.

Пример:

```text
cycle is STOPPED: repeated_finding
manual or human-approved recovery is required
```

---

## Human-approved recovery

Добавить явный безопасный recovery-механизм для цикла, остановленного после исчерпания автоматических review rounds.

Предпочтительный интерфейс:

```powershell
uv run python scripts/pi_ticket_cycle.py PDFTR-XX `
    --recover `
    --reason "human-approved follow-up for repeated finding R1"
```

или отдельная команда:

```powershell
uv run python scripts/agent_cycle.py reopen PDFTR-XX `
    --reason "human-approved follow-up for repeated finding R1"
```

Recovery должен быть возможен только при явном human approval.

### Required properties

Recovery:

- не удаляет существующие review artifacts;
- не переписывает `review-1.json`, `review-2.json`;
- сохраняет историю предыдущих attempts;
- сохраняет старые reviewed SHA;
- требует clean working tree;
- требует текущий HEAD == manifest HEAD;
- требует ту же ticket branch;
- фиксирует reason;
- создаёт новый implementation attempt;
- позволяет последующий independent exact-SHA review.

---

## Review round model

Не расширять автоматически `MAX_REVIEW_ROUNDS`.

Автоматический цикл остаётся:

```text
implementation 1
→ review 1
→ implementation 2
→ review 2
```

После исчерпания лимита:

```text
STOPPED
```

Дальнейшая работа разрешается только через explicit human recovery.

Это должно быть видно в coordination state.

---

## Suggested recovery state

Рассмотреть добавление состояния:

```text
HUMAN_APPROVED_REWORK
```

или эквивалентного audit metadata.

Пример:

```text
STOPPED
    ↓ human-approved recovery
HUMAN_APPROVED_REWORK
    ↓
IMPLEMENTING
    ↓
READY_FOR_REVIEW_RECOVERY
    ↓
REVIEWING
```

Не обязательно использовать именно такие названия, если можно сохранить существующую state machine проще.

Главное требование — recovery должен быть явным, проверяемым и аудируемым.

---

## Runner behavior

`pi_ticket_cycle.py` должен определять действие по текущему state.

Expected dispatch:

```text
NEW
    → implementer

READY_FOR_REVIEW
    → reviewer

CHANGES_REQUIRED
    → implementer next attempt

READY_FOR_REVIEW_2
    → reviewer round 2

PASSED
    → report completed

BLOCKED
    → fail closed

STOPPED
    → fail closed unless explicit human recovery was requested
```

Runner не должен требовать новый cycle только потому, что состояние не `NEW`.

---

## Safety

Preserve existing safeguards:

- exact branch binding;
- exact SHA binding;
- repository fingerprint;
- clean-tree enforcement;
- reviewer read-only tool allowlist;
- maximum automatic review rounds;
- immutable review artifacts;
- duplicate/repeated finding detection;
- Windows Job Object process containment;
- POSIX process-group cleanup;
- strict JSON schemas;
- no shell capability for reviewer;
- fail-closed behavior.

Resume/recovery must not weaken any existing PDFTR-35A / PDFTR-40 safety guarantees.

---

## Diagnostics

Ошибки должны быть actionable.

Вместо:

```text
runner expects a NEW cycle but found READY_FOR_REVIEW; recover manually
```

ожидается нормальное resume-поведение.

Для невозможного recovery сообщения должны содержать:

- current state;
- current HEAD;
- manifest HEAD;
- review round;
- stop reason;
- required human action.

---

## Tests

Добавить deterministic tests минимум для:

### Resume

- `NEW → implementer`
- `READY_FOR_REVIEW → reviewer`
- `CHANGES_REQUIRED → implementer round 2`
- `READY_FOR_REVIEW_2 → reviewer round 2`

### Terminal states

- `PASSED` не перезапускается;
- `BLOCKED` не перезапускается;
- `STOPPED` без explicit recovery отклоняется.

### Human recovery

- recovery требует explicit flag/action;
- dirty tree отклоняется;
- wrong branch отклоняется;
- changed HEAD отклоняется;
- previous review artifacts остаются byte-for-byte unchanged;
- stop reason сохраняется в audit trail;
- новый implementation SHA обязателен;
- independent review привязывается к новому exact SHA.

### Regression

Существующие tests для:

- repeated findings;
- review round limit;
- reviewer read-only restrictions;
- JSON validation;
- process cleanup;
- git safety guards;

должны продолжать проходить.

---

## Acceptance criteria

- `pi_ticket_cycle.py` можно безопасно повторно запускать после interruption или partial completion.
- `READY_FOR_REVIEW` и `READY_FOR_REVIEW_2` автоматически продолжаются с reviewer.
- `CHANGES_REQUIRED` автоматически продолжается с implementer следующего attempt.
- Existing implementation не запускается повторно без необходимости.
- Terminal states остаются fail-closed.
- Human recovery из `STOPPED` требует явного approval.
- Existing coordination artifacts не уничтожаются и не переписываются.
- Resume/recovery сохраняет exact-SHA review guarantees.
- Full `scripts/check.ps1` passes.
- Windows and Ubuntu CI pass.

---

## Non-goals

Не менять в этом тикете:

- translation pipeline;
- PDF layout/reflow behavior;
- ticket-specific implementation logic;
- provider/model selection;
- automatic merge behavior;
- GitHub PR automation.

Этот тикет касается только orchestration/state recovery layer.

---

## Follow-up

После PDFTR-42 отдельным тикетом оформить интеграцию GitHub PR / ChatGPT Work, чтобы после `PASSED` harness мог создавать или обновлять PR и передавать его в независимый финальный review workflow.

> По масштабу это уже близко к небольшому специализированному agent harness / job execution framework: stateful resume, immutable artifacts, exact-SHA review, role isolation, bounded retries и explicit human recovery.
