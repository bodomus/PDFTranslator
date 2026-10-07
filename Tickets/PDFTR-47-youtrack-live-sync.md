# PDFTR-47 — YouTrack Live Synchronization Validation and Hardening

## Human-approved post-cycle correction R6

Address only the independent P2 finding at reviewed baseline
`c8ff18631b6c8d17b3bd8d4311cedfae2befcef7`: reconciliation-read errors must never downgrade
an uncertain creation POST. Retain the original mutation uncertainty and non-repeatable protection
across HTTP 401/403/408/502/503/504, socket timeout, connection loss and restart. Only successful
exact ticket/project reconciliation may resolve that creation, with no second POST. Identity
mismatches remain fail-closed. Parameterize real transport mutation/read failures, preserve existing
preparation/rejection/fencing/GitHub regressions, run focused/broader/full validation, then commit
and push the existing branch with a clean tree. No historical .agent-cycle artifacts, reviewer
permissions, PDFTR-45/46 behavior or unrelated ticket scope changes.

## Human-approved post-cycle correction R5

Address only the remaining pre-write preparation finding at reviewed baseline
`fd1ca03b45fa6f0bfea39ff04fca85016301b0e7`. Issue creation, lifecycle comments, attachments and
YouTrack PR cross-links must finish GETs, exact identity/duplicate checks and payload preparation
before pending mutation intent is persisted. Preparation failures leave diagnostic events only,
with no pending/uncertain mutation, conflicting-write fence or non-repeatable guard. Healthy retries
after restart must execute the same action exactly once. Preserve write-ahead crash safety and
post-dispatch timeout/connection-loss/HTTP 408/5xx uncertainty, definite rejection behavior,
GitHub isolation and PDFTR-45/46 protections. Run focused/broader/full validation, commit and push
the existing ticket branch. Do not modify historical agent-cycle artifacts or reviewer permissions.

## Goal

Довести существующую YouTrack integration до подтверждённой end-to-end синхронизации и убрать текущий best-effort/неопределённый режим.

После PDFTR-43 integration code существует, но live behavior не подтверждён.

Реальные наблюдения последних циклов:

```text
Integration warning: YouTrack credentials unavailable
```

и:

```text
Issue not found: PDFTR-45
```

Дополнительно live field/state mappings, attachments и lifecycle updates не были подтверждены end-to-end.

PDFTR-47 должен:

- подтвердить реальные credentials/configuration;
- безопасно найти или создать issue;
- проверить mapping полей;
- проверить lifecycle updates;
- проверить idempotency;
- проверить exact ticket identity;
- обеспечить понятные diagnostics;
- сохранить non-blocking behavior там, где это было задумано;
- не допустить silent divergence между local cycle и YouTrack.

---


## Clarification — Live YouTrack behavior during implementation

Absence of live YouTrack credentials **MUST NOT block implementation or handoff**.

PDFTR-47 implementation must be completed using deterministic mocks/fakes and explicit operator-invoked live-validation commands.

During the normal PDFTR-47 implementation run:

- do not require real YouTrack credentials;
- do not require successful live mutation;
- do not stop and wait for operator confirmation;
- do not create or update remote YouTrack issues automatically merely to prove the implementation works;
- missing credentials must be reported as a non-blocking integration limitation;
- unknown field/state mappings must be reported and remain non-blocking;
- deterministic fake/mock tests are sufficient for implementation acceptance;
- the implementation report must clearly separate:
  - behavior validated deterministically in tests;
  - behavior still unverified live because credentials or live access are unavailable.

Live mutation is permitted only through an explicit operator action, for example:

```powershell
uv run python scripts/project_tracking.py validate-live PDFTR-47 --allow-create
```

Exact-key creation policy:

- issue creation is permitted only when explicitly enabled by the operator;
- a definite exact-key `not found` result may proceed to create when `--allow-create` is supplied;
- ambiguous lookup failures caused by network/auth/server errors must **never** trigger create;
- after create, the returned issue must be re-read and exact identity verified before any further mutation;
- no guessed issue, project, assignee, field value, or state is allowed.

Implementer completion requirement:

Even if live YouTrack access is unavailable, the implementer must still:

1. finish the code;
2. run focused tests;
3. run the full quality gate;
4. commit and push;
5. produce the normal `implementer.json` handoff;
6. record live-access limitations in the implementation report instead of stopping the cycle.

This clarification overrides any interpretation of the acceptance criteria that would require live credentials or live remote mutation during the normal agent implementation run.

---

## 1. Source of truth

Authoritative execution state остаётся локальным:

```text
Tickets/
.agent-cycle/
Git branch / exact SHA
GitHub PR
```

YouTrack является synchronized project-tracking projection, а не authority для safety-critical cycle state.

YouTrack outage или mapping failure не должен:

- менять agent-cycle state;
- подменять exact SHA;
- разрешать запрещённый transition;
- блокировать reviewer safety;
- ломать local implementation flow.

Но integration failure должен быть явно видим.

---

## 2. Configuration

Определить один канонический configuration path для live YouTrack integration.

Например:

```toml
[youtrack]
enabled = true
base_url = "https://bodomus.youtrack.cloud"
project = "PDFTR"
assignee = "bodomus"
```

Secrets не хранить в repository.

Token/API credentials должны поступать через environment или approved local secret mechanism.

Не логировать:

- token;
- Authorization header;
- full secret-bearing URL;
- credential payload.

---

## 3. Credential preflight

Добавить explicit preflight validation.

До первого mutation проверить:

- base URL reachable;
- credentials present;
- credentials accepted;
- target project accessible;
- required API endpoints available.

Статусы должны различаться:

```text
YouTrack: disabled
YouTrack: credentials unavailable
YouTrack: authentication failed
YouTrack: project unavailable
YouTrack: ready
```

Не сводить все ошибки к generic warning.

---

## 4. Ticket identity

Для `PDFTR-47` integration должна работать только с issue:

```text
PDFTR-47
```

Нельзя:

- fallback на похожий issue;
- искать по summary и молча выбрать первый;
- создавать duplicate при transient lookup failure;
- mutating issue из другого project.

Перед mutation проверить:

```text
issue idReadable == requested ticket
project == PDFTR
```

При mismatch:

```text
fail remote mutation closed
continue local cycle safely
record integration warning
```

---

## 5. Find-or-create behavior

Реализовать deterministic:

```text
ensure_youtrack_issue(ticket)
```

Flow:

1. exact lookup by ticket key;
2. if exists — reuse;
3. if definitely not found — create;
4. if lookup failed ambiguously due to network/auth/server error — DO NOT create;
5. after create — re-read and verify identity;
6. persist remote issue identity in integration artifact.

Не трактовать arbitrary request failure как `not found`.

---

## 6. Missing issue behavior

Текущий реальный кейс:

```text
Issue not found: PDFTR-45
```

должен быть диагностирован однозначно.

Если local ticket существует и YouTrack integration configured for create:

```text
exact issue absent
→ create issue
→ verify returned key
→ continue synchronization
```

Если create permission отсутствует:

```text
remote create unavailable
→ record warning
→ continue local cycle
```

без fake success.

---

## 7. Field discovery and mapping

Не hardcode field names/values вслепую.

Интроспектировать доступные fields для target project и map required semantics.

Минимально:

- Assignee
- State
- Estimation
- Due Date
- Type, если используется
- Priority, если используется

Если field отсутствует или value unknown:

```text
field unavailable: <semantic name>
```

Это не должно блокировать local work.

---

## 8. Assignee mapping

Target assignee:

```text
bodomus
```

Resolve user identity through API.

Не предполагать, что login/display name/internal id одинаковы.

Если assignee unresolved:

- issue creation/update продолжается без assignee if allowed;
- warning persisted;
- no guessed user.

---

## 9. Estimation and due date

Поддержать estimation и due date только если они заданы локальным contract/config.

Requirements:

- preserve units;
- reject malformed estimation;
- do not invent missing values;
- verify API format/timezone for due date;
- read-after-write must confirm semantic value.

---

## 10. Lifecycle mapping

Проверить live mapping local lifecycle → YouTrack State.

Desired semantics:

```text
NEW / ticket bootstrap     -> Open
IMPLEMENTING               -> In Progress
READY_FOR_REVIEW           -> Ready for Review
READY_FOR_REVIEW_2         -> Ready for Review
PASSED                     -> Ready for Human Review
merged / explicit close    -> Done
```

Actual YouTrack state names должны быть discovered/configurable.

Не предполагать, что display names существуют.

Если exact target state unavailable:

- log warning;
- do not guess another state;
- continue local cycle.

---

## 11. Human merge / Done transition

`PASSED` не должен автоматически означать `Done`, если merge остаётся human-owned.

Предпочтительно:

```text
PASSED -> Ready for Human Review
```

`Done` только после explicit merge/close signal.

---

## 12. Comments / lifecycle evidence

YouTrack updates должны быть concise and idempotent.

Примеры:

```text
Implementation started
Implementation SHA: <sha>
Review round 1: CHANGES_REQUIRED
Review round 2: PASS
Ready for human review
```

Не дублировать огромные logs/reports и chain-of-thought.

Можно включать только подтверждённые:

- exact SHA;
- review round;
- verdict;
- PR URL;
- CI state.

---

## 13. No fabricated remote state

Нельзя писать в YouTrack `CI passed`, `PR ready`, `review passed`, если это не подтверждено.

Если CI unavailable — публиковать `CI status unavailable` либо не делать claim.

---

## 14. Idempotency

Каждая remote mutation должна иметь deterministic idempotency behavior.

Повторный запуск bootstrap/lifecycle/comment/field update не должен создавать duplicates.

Logical identity можно derived from:

```text
ticket + role + round + attempt + SHA + action
```

Если API не поддерживает native idempotency key — использовать safe read-before-write / event marker strategy.

---

## 15. Retry and timeout policy

Не вводить агрессивный automatic retry loop.

Допустим небольшой bounded retry только для transient failures:

```text
max 2-3 attempts
short bounded delay
```

Не retry:

- 401/403;
- invalid field;
- issue identity mismatch;
- malformed request;
- permission denied.

Все remote calls должны иметь finite connect/read/overall timeout.

YouTrack не должен зависать на десятки минут и блокировать agent cycle.

---

## 16. Integration artifacts

Persist safe evidence:

```text
.agent-cycle/PDFTR-47/youtrack.json
.agent-cycle/PDFTR-47/youtrack-events.jsonl
```

`youtrack.json` может содержать:

```json
{
  "ticket": "PDFTR-47",
  "issue_key": "PDFTR-47",
  "issue_url": "...",
  "project": "PDFTR",
  "last_sync_status": "ok",
  "last_sync_action": "READY_FOR_REVIEW",
  "warnings": []
}
```

Events file append-only.

Never persist credentials.

---

## 17. Diagnostics

Console output должен быть конкретным:

```text
[PDFTR-47] YouTrack ready: PDFTR-47
[PDFTR-47] YouTrack created issue PDFTR-47
[PDFTR-47] YouTrack state -> In Progress
[PDFTR-47] Integration warning: Assignee field unavailable
```

Избегать generic `YouTrack failed`, если можно безопасно указать категорию.

---

## 18. Best-effort boundary

Сохранить intended non-blocking behavior:

```text
local work continues
remote mutation fails closed
warning is persisted
```

YouTrack failure не должен ломать implementation/review cycle, кроме identity/security ambiguity внутри remote mutation itself.

---

## 19. Live validation mode

Добавить explicit operator command для end-to-end проверки без запуска полного agent cycle.

Например:

```powershell
uv run python scripts/project_tracking.py validate-live PDFTR-47
```

или отдельный script.

Команда должна проверить:

1. credentials;
2. project;
3. issue lookup;
4. create permission / exact issue creation when explicitly allowed;
5. field discovery;
6. state mapping;
7. assignee resolution;
8. read-after-write;
9. idempotent second run.

Не выполнять destructive transitions без explicit opt-in.

---

## 20. Dry-run

Добавить `--dry-run` для отображения planned actions without mutation.

Пример:

```text
Would create: PDFTR-47
Would assign: bodomus
Would set state: In Progress
Would set estimation: 4h
```

---

## 21. Read-after-write verification

После important mutation:

- issue create;
- state change;
- assignee;
- estimation;
- due date;

повторно прочитать remote entity и verify expected result.

Не считать HTTP success достаточным подтверждением semantic update.

---

## 22. Concurrency

Два concurrent runner invocation не должны создать два YouTrack issues.

Flow:

- exact lookup;
- create;
- re-read;
- duplicate/conflict detection.

Если race произошёл, выбрать exact canonical issue и stop further duplicate creation.

---

## 23. GitHub / YouTrack cross-link

Если PR существует, YouTrack issue получает concise link/evidence.

Если YouTrack issue существует, PR body может содержать issue URL.

Отсутствие одной системы не должно ломать другую.

---

## 24. Historical gaps

PDFTR-38..46 могут не иметь корректной YouTrack history.

PDFTR-47 не обязан автоматически реконструировать весь прошлый timeline.

Для PDFTR-47 onward synchronization должна быть deterministic.

Historical backfill — отдельный follow-up.

---

## 25. Security

Проверить:

- no token in logs;
- no token in exception text;
- no token in `.agent-cycle`;
- HTTPS required unless explicit test/local override;
- exact host binding;
- no arbitrary URL supplied by agent intent;
- no reviewer capability to change credentials/config;
- remote issue identity validated before mutation.

---

## 26. Reviewer isolation

Reviewer может предложить structured intent, но не получает direct unrestricted YouTrack write capability.

Harness остаётся mutation boundary.

Reviewer read-only repository guarantees не должны ослабляться.

---

## 27. Tests

Добавить deterministic fake/mock tests минимум для:

### Credentials
- unavailable;
- invalid;
- accepted.

### Lookup
- exact issue exists;
- issue definitely absent;
- network failure;
- ambiguous failure does not trigger create.

### Creation
- exact creation;
- read-after-create identity verify;
- race/duplicate handling.

### Project identity
- wrong project rejected.

### Fields
- discovered fields;
- missing assignee;
- missing estimation;
- missing due date;
- unsupported state value.

### Lifecycle
- Open;
- In Progress;
- Ready for Review;
- Ready for Human Review;
- Done only on explicit finalization.

### Idempotency
- second bootstrap creates no duplicate;
- duplicate lifecycle event creates no duplicate comment/update.

### Security
- token redaction;
- host mismatch;
- arbitrary issue mismatch;
- reviewer cannot bypass harness.

### Timeouts
- hung fake endpoint bounded.

### Live validator
- dry-run;
- successful validation;
- partial-field warnings;
- no destructive mutation by default.

### Regression
Existing tests for:
- PDFTR-43 tracking hooks;
- PDFTR-45 operational retry;
- PDFTR-46 startup module coherence;
- reviewer read-only;
- exact-SHA review;
- process containment;
- progress journals;

must remain green.

---

## 28. Acceptance criteria

PDFTR-47 is complete when:

- live credentials can be validated explicitly;
- exact issue lookup works;
- missing issue can be created safely when allowed;
- `Issue not found` no longer leaves ambiguous behavior;
- project/ticket identity verified before mutation;
- assignee `bodomus` resolution tested live;
- state mapping discovered/configurable and verified;
- estimation/due date behavior verified or explicitly reported unavailable;
- lifecycle updates verified read-after-write;
- idempotency verified;
- remote failures remain non-blocking for local cycle;
- integration diagnostics are specific;
- secrets never persist;
- dry-run exists;
- live validation command exists;
- full `scripts/check.ps1` passes;
- Windows and Ubuntu CI pass.

---

## Non-goals

Do not implement in PDFTR-47:

- historical backfill for all old tickets;
- bidirectional authority where YouTrack controls agent-cycle state;
- arbitrary YouTrack automation by reviewer;
- automatic merge;
- complex retry queues;
- background sync daemon;
- full project-management dashboard;
- replacement of GitHub PR workflow.

---

## Recommended live verification sequence

After implementation:

```powershell
# 1. Dry-run
uv run python scripts/project_tracking.py validate-live PDFTR-47 --dry-run

# 2. Read-only live validation
uv run python scripts/project_tracking.py validate-live PDFTR-47

# 3. Explicit create/update validation if issue is absent
uv run python scripts/project_tracking.py validate-live PDFTR-47 --allow-create

# 4. Repeat same command
# Expected: no duplicate issue/comment/update
```

Implementation report must state exactly which remote operations were actually verified live and which remain mocked/unverified.
