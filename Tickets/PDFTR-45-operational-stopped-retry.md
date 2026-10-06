# PDFTR-45 — Human-Approved Retry for Operational STOPPED Before Review

## Goal

Добавить безопасный human-approved retry для agent cycle, который остановился **до первого успешного handoff/review** из-за operational failure.

Реальный кейс PDFTR-44:

```text
State: STOPPED
Review round: 0
Stop reason: implementer exited with code 1
Active agent: none
Working tree: clean
HEAD unchanged
```

Причина была operational — исчерпанные model usage limits. Текущий `--recover` допускает recovery только после:

- `repeated_finding`
- `review_round_limit`

Из-за этого оператор вынужден вручную архивировать `.agent-cycle/<ticket>` и создавать новый cycle.

PDFTR-45 должен убрать эту ручную процедуру без ослабления safety guarantees.

---

## 1. Separate recovery classes

Не смешивать два разных типа recovery.

### A. Existing review recovery

```text
STOPPED
reason = repeated_finding | review_round_limit
```

→ explicit human approval
→ one additional implementer + exact-SHA review pair.

Этот behavior должен остаться без изменений.

### B. New operational retry

```text
STOPPED
operational failure
review_round = 0
no accepted implementation handoff
```

→ explicit human approval
→ retry implementer.

Operational retry **не расходует review budget**.

---

## 2. Structured stop classification

Не принимать recovery decisions по free-text `stop_reason`.

Добавить machine-readable classification, например:

```json
{
  "stop_class": "operational",
  "stop_code": "implementer_process_failed",
  "stop_reason": "implementer exited with code 1"
}
```

Минимально поддержать operational codes для:

- implementer non-zero exit;
- implementer externally terminated;
- provider/model quota or usage-limit failure, если классификация надёжна;
- transient provider failure;
- child launch/runtime failure;
- network/auth failure preventing implementer completion.

Не считать автоматически recoverable:

- repository integrity failure;
- dirty tree safety failure;
- branch mismatch;
- exact HEAD mismatch;
- reviewer safety violation;
- malformed/contradictory handoff or review;
- role capability violation;
- filesystem boundary violation;
- corrupted manifest/artifacts.

Неизвестная классификация должна fail closed.

---

## 3. Eligibility

Operational retry разрешён только если выполняются все условия:

```text
state == STOPPED
stop_class == operational
active_agent == none
working_tree == clean
current HEAD == manifest current_head_sha
current branch == manifest branch
review_round == 0
no accepted review exists for current HEAD
no repository safety errors
```

Дополнительно:

- cycle directory exists;
- manifest parses strictly;
- ticket identity matches;
- repo identity/fingerprint matches existing safeguards;
- explicit human reason supplied.

Любое нарушение → reject without mutation.

---

## 4. CLI

Предпочтительный интерфейс:

```powershell
uv run python scripts/pi_ticket_cycle.py PDFTR-45 `
  --preset codex-codex `
  --recover-operational `
  --reason "Codex usage limits exhausted; limits reset; retry approved"
```

Предпочтителен отдельный `--recover-operational`, а не generic force/override, потому что semantics отличаются от exhausted-review recovery.

Runner должен явно вывести:

```text
Recovery type: operational implementer retry
```

---

## 5. Audit history

Новый retry не должен стирать предыдущий failed attempt.

Добавить immutable audit entry, например:

```json
{
  "type": "operational_retry",
  "reason": "Codex usage limits exhausted; limits reset; retry approved",
  "previous_stop_code": "implementer_process_failed",
  "previous_stop_reason": "implementer exited with code 1",
  "head_sha": "...",
  "branch": "...",
  "review_round": 0,
  "implementation_attempt": 2
}
```

History всех attempts должна сохраняться.

---

## 6. Artifact preservation

При retry не удалять:

- previous implementer stdout/stderr log;
- previous progress journal;
- previous stop diagnostics;
- previous implementation report;
- rejected/partial handoff artifacts, если они существовали;
- recovery approval record.

Если имена конфликтуют, использовать attempt-aware artifacts, например:

```text
pi-implementer-attempt-1.log
pi-implementer-attempt-2.log
implementer-progress-attempt-1.log
implementer-progress-attempt-2.log
```

Нельзя silently truncate historical diagnostics.

---

## 7. State model

Рекомендуемое новое состояние:

```text
HUMAN_APPROVED_OPERATIONAL_RETRY
```

Flow:

```text
STOPPED
  |
  | explicit human approval
  v
HUMAN_APPROVED_OPERATIONAL_RETRY
  |
  v
IMPLEMENTER RUN
  |
  v
READY_FOR_REVIEW
```

Не переиспользовать `HUMAN_APPROVED_REWORK`, если это смешивает review recovery и operational retry.

---

## 8. Attempt accounting

Operational retry увеличивает:

```text
implementation_attempt
```

Например:

```text
1 -> 2
```

Но **не увеличивает `review_round`**.

Transient model/provider failure не должен расходовать review budget.

---

## 9. Retry bound

Не допускать бесконечный retry loop.

Предпочтительно:

```text
MAX_OPERATIONAL_RETRIES = 3
```

или конфигурация:

```toml
[agent_cycle]
max_operational_retries = 3
```

После лимита:

```text
STOPPED
stop_code = operational_retry_limit
```

Дальнейшее продолжение требует отдельного manual intervention.

---

## 10. PDFTR-44 progress integration

Новый attempt должен сохранять progress observability.

Пример:

```text
[09:10] Human-approved operational retry started after previous implementer failure
```

Heartbeat желательно расширить:

```text
[PDFTR-45] implementer attempt 2 running... 15m — last: [09:23] Running focused tests
```

Final diagnostics:

```text
Implementation attempt: 2
Previous operational retries: 1
```

---

## 11. Provider failure classification

Не строить safety policy на brittle parsing provider message strings.

Если adapter надёжно классифицирует quota/usage-limit/temporary unavailable, допускается:

```text
stop_class = operational
```

Если classification uncertain:

```text
stop_class = unknown
```

и operational retry не должен автоматически разрешаться.

---

## 12. Dirty tree

Если failed implementer оставил dirty working tree, operational retry отклоняется.

PDFTR-45 не должен автоматически:

- stash;
- reset;
- clean;
- revert;
- checkout;
- discard WIP.

Dirty WIP recovery — отдельный future workflow.

---

## 13. Exact HEAD / branch binding

Retry разрешён только если:

```text
facts.head_sha == manifest.current_head_sha
facts.branch == manifest.branch
```

Если HEAD изменился:

```text
ERROR: operational retry requires unchanged exact HEAD
```

Нельзя silently rebind manifest.

---

## 14. Handoff semantics

Если failed implementer создал partial/invalid handoff:

- он не считается accepted;
- retry стартует как новый implementation attempt;
- old artifact сохраняется для audit.

Если accepted handoff уже существует и state дошёл до `READY_FOR_REVIEW`, operational retry не применяется — используется normal resume flow PDFTR-42.

---

## 15. Reviewer isolation

PDFTR-45 не расширяет reviewer permissions.

Reviewer:

- остаётся read-only;
- не получает recovery write powers;
- не может approve retry;
- не может mutate manifest для reopen.

Human/operator остаётся единственным authority для operational retry approval.

---

## 16. Status output

Расширить:

```powershell
uv run python scripts/agent_cycle.py status PDFTR-45
```

Пример:

```text
Ticket: PDFTR-45
State: STOPPED
Branch: pdftr-45-operational-stopped-retry
HEAD: ...
Review round: 0
Implementation attempt: 1
Operational retries: 0
Stop class: operational
Stop code: implementer_process_failed
Stop reason: implementer exited with code 1
Operational retry eligible: yes
Active agent: none
Working tree: clean
Review valid for HEAD: no
```

Если retry запрещён:

```text
Operational retry eligible: no
Reason: working tree is dirty
```

---

## 17. Idempotency

Повтор одной и той же recovery command не должен:

- дважды append approval;
- дважды increment retry count;
- создавать duplicate attempt;
- дублировать artifacts.

После successful reopen повторный вызов должен deterministic reject или resume уже approved attempt.

---

## 18. Crash safety

Recovery manifest update должен использовать existing atomic-write discipline.

Если runner падает после approval persistence, но до child launch, следующий invocation должен продолжить **тот же approved attempt** без duplicate approval.

---

## 19. Backward compatibility

Existing manifests без новых fields должны оставаться readable.

Допускается:

- безопасно вывести `unknown`;
- не разрешать operational retry автоматически.

Не делать unsafe migration на основании substring matching старого `stop_reason`.

---

## 20. Tests

Добавить deterministic tests минимум для:

### Happy path
- STOPPED operational failure;
- review_round = 0;
- clean tree;
- unchanged HEAD;
- human approval;
- implementer retry;
- successful handoff;
- READY_FOR_REVIEW.

### Attempt accounting
- implementation attempt increments;
- review round unchanged.

### Dirty tree
- retry rejected;
- no manifest mutation.

### HEAD changed
- retry rejected.

### Branch mismatch
- retry rejected.

### Active agent
- retry rejected.

### Unsafe / unknown stop class
- retry rejected.

### Accepted handoff exists
- operational retry not applicable;
- normal resume path retained.

### Audit
- approval persisted;
- previous stop diagnostics retained;
- previous artifacts retained.

### Idempotency
- duplicate recovery invocation does not duplicate approval/count.

### Retry limit
- retries up to configured maximum;
- next retry rejected.

### Crash/resume
- approval persisted;
- crash before child launch;
- next run resumes same attempt.

### Status
- shows stop class/code;
- shows implementation attempt;
- shows retry count;
- shows eligibility and rejection reason.

### Regression
Existing tests for:
- repeated-finding recovery;
- review-round-limit recovery;
- exact-SHA binding;
- process containment;
- Windows Job Object;
- POSIX cleanup;
- strict JSON;
- reviewer read-only;
- PDFTR-44 progress journals;
- PDFTR-43 project tracking/PR integration;

must remain green.

---

## 21. Acceptance criteria

PDFTR-45 is complete when:

- operational STOPPED before review can be retried with explicit human approval;
- no manual `.agent-cycle` rename is required;
- old failed attempt artifacts remain available;
- implementation attempt increments;
- review round does not increment;
- retry requires clean tree;
- retry requires unchanged exact HEAD;
- retry requires correct branch/repo identity;
- unsafe/ambiguous STOPPED reasons fail closed;
- policy uses structured stop classification, not free text;
- duplicate approval is impossible;
- crash between approval and launch is resumable;
- status clearly reports retry eligibility;
- reviewer permissions remain unchanged;
- existing exhausted-review recovery behavior remains unchanged;
- full `scripts/check.ps1` passes;
- Windows and Ubuntu CI pass.

---

## Non-goals

Do not implement in PDFTR-45:

- automatic retry without human approval;
- automatic reset/stash/cleanup of dirty WIP;
- retry of reviewer safety violations;
- provider-specific retry loops;
- exponential backoff service;
- automatic model switching;
- force-rebinding to changed HEAD;
- execution timeout policy;
- automatic merge.

---

## Suggested implementation shape

Предпочтительно разделить policy functions, например:

```python
reopen_review_cycle(...)
retry_operational_cycle(...)
```

вместо расширения одного generic `reopen_cycle()`.

Для classification:

```python
class StopClass(str, Enum):
    OPERATIONAL = "operational"
    REVIEW_EXHAUSTED = "review_exhausted"
    SAFETY = "safety"
    UNKNOWN = "unknown"
```

Stable stop codes:

```text
implementer_process_failed
implementer_terminated
provider_unavailable
operational_retry_limit
repeated_finding
review_round_limit
```

---

## Real regression scenario

Обязательно покрыть точный PDFTR-44 case:

```text
Ticket: PDFTR-44
State: STOPPED
Branch: pdftr-44-agent-progress-journal
HEAD: b2eab35703d461efc5f33cde0c1fe9ecea195936
Review round: 0
Human approvals: 0
Stop reason: implementer exited with code 1
Active agent: none
Working tree: clean
Review valid for HEAD: no
```

После восстановления model limits оператор должен иметь возможность выполнить:

```powershell
uv run python scripts/pi_ticket_cycle.py PDFTR-44 `
  --preset codex-codex `
  --recover-operational `
  --reason "Codex usage limits exhausted; limits reset; retry approved"
```

Без:

- rename `.agent-cycle`;
- manual manifest editing;
- потери diagnostics;
- расходования review budget.
