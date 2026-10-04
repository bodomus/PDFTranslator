# PDFTR-43 — GitHub PR / ChatGPT Work Integration and YouTrack Agent Ownership

## Goal

После успешного agent cycle связать наш harness с внешним workflow:

1. YouTrack становится рабочим источником состояния тикета.
2. Implementer и reviewer поддерживают тикет актуальным в ходе работы.
3. После `PASSED` harness создаёт или обновляет GitHub PR.
4. PR содержит exact implementation SHA, validation evidence и review status.
5. Финальный human / ChatGPT Work review получает готовый PR и полный audit context.
6. Ошибка YouTrack или внешней интеграции не должна блокировать основную реализацию, если локальный repository workflow может продолжаться безопасно.

PDFTR-38…PDFTR-42 были выполнены без полноценного YouTrack tracking. Пользователь вручную создаёт placeholder tickets для восстановления последовательности. Начиная с PDFTR-43 новые задачи должны синхронизироваться с YouTrack автоматически.

---

# Architectural decision

## Do not give raw YouTrack mutation responsibility directly to arbitrary agent shell/tool access

Implementer и reviewer должны **управлять содержанием тикета**, но mutation boundary должен оставаться в harness.

Предпочтительная модель:

```text
Tickets/PDFTR-43.md
        ↓
Pi harness / YouTrack adapter
        ↓
ensure/create/sync issue
        ↓
implementer
        ↓
structured YouTrack update request
        ↓
harness validates + applies
        ↓
reviewer
        ↓
structured YouTrack review update
        ↓
harness validates + applies
```

Agent решает **что написать и какие значения предложить**.

Harness решает:

- можно ли выполнить mutation;
- какой именно issue разрешено менять;
- какие поля разрешены;
- как сделать update idempotent;
- как обработать API failure;
- как сохранить audit trail.

Это сохраняет role isolation и уменьшает риск того, что coding agent случайно изменит другой YouTrack issue.

---

# 1. YouTrack ticket bootstrap

## Source

Canonical local task definition до создания remote issue:

```text
Tickets/PDFTR-XX.md
```

Harness должен уметь прочитать ticket file до запуска implementer.

## Ensure issue

Перед первой implementation attempt выполнить:

```text
ensure_youtrack_issue(ticket)
```

### If issue already exists

Например:

```text
PDFTR-43
```

Harness:

- читает issue;
- не создаёт duplicate;
- синхронизирует разрешённые поля;
- сохраняет remote issue ID / URL в coordination metadata.

### If issue does not exist

Harness создаёт новый issue из `Tickets/PDFTR-XX.md`.

Минимально:

- Project: PDFTR
- Summary: title из Markdown
- Description: task body из Markdown
- Assignee: `bodomus`
- Estimation: agent/harness-derived estimate
- Due date: agent/harness-derived target date
- State: project default / Open

После создания harness обязан проверить, что созданный issue имеет ожидаемый key.

Если созданный key отличается от ожидаемого `PDFTR-XX`:

```text
fail YouTrack synchronization
continue local implementation
record diagnostic
```

Нельзя переименовывать или удалять чужие issues для восстановления номера.

---

# 2. Bootstrap ownership

Создание remote ticket должно происходить **до implementer execution**, как orchestration preflight.

Не делать создание issue скрытым side effect внутри coding implementation.

Причины:

- implementer может завершиться до создания тикета;
- повторный запуск может создать duplicate;
- ticket identity нужна до handoff;
- reviewer должен видеть тот же issue;
- external mutation должна иметь audit trail отдельно от code mutation.

Implementer остаётся первым **рабочим agent**, но YouTrack bootstrap выполняет harness непосредственно перед ним.

---

# 3. Automatic field selection

Для нового тикета система должна попытаться заполнить:

- Assignee = `bodomus`
- Estimation
- Due date
- State
- Type, если поле существует и значение можно определить безопасно
- Priority, если поле существует и значение можно определить безопасно

## Estimation

Implementer может предложить estimation на основе ticket scope.

Не требовать ложной точности.

Предпочтительно выбирать из существующей схемы проекта YouTrack.

Если schema неизвестна:

- inspect project fields;
- попытаться сопоставить;
- при невозможности не блокировать работу.

## Due date

Due date должен определяться консервативно из:

- estimation;
- task complexity;
- текущей даты;
- dependency/blocker information.

Не ставить просроченную дату.

Если уверенного значения нет — поле можно оставить пустым и записать diagnostic.

---

# 4. Unknown / unsupported YouTrack fields

YouTrack integration является **best effort**, а не hard dependency implementation pipeline.

Если agent или adapter не знает, как заполнить поле:

```text
do not guess invalid field/value
do not stop coding cycle
```

Записать проблему в implementation/review evidence.

Пример:

```text
YouTrack sync warning:
Could not map project field "Estimation" to a supported value.
Implementation continued.
```

Проблема также должна попасть в соответствующий report:

```text
.implementation-reports/...
reviews/...
```

если report создаётся данным role.

---

# 5. YouTrack state lifecycle

Harness должен поддерживать понятный lifecycle.

Рекомендуемая логика:

```text
ticket created / discovered
        ↓
Open

implementer starts
        ↓
In Progress

implementation handoff accepted
        ↓
Ready for Review

reviewer CHANGES_REQUIRED
        ↓
In Progress
+ review findings comment

reviewer PASS
        ↓
Ready for Human Review

PR merged
        ↓
Done
```

Названия состояний должны introspect-иться из реальной YouTrack project schema.

Не hardcode состояние, если project использует другое имя.

Допускается configurable mapping.

---

# 6. Implementer YouTrack responsibilities

Implementer должен формировать structured update intent.

Пример artifact:

```json
{
  "ticket": "PDFTR-43",
  "role": "implementer",
  "summary": "Implemented GitHub PR and YouTrack orchestration integration.",
  "proposed_fields": {
    "estimation": "1d",
    "due_date": "2026-10-05",
    "assignee": "bodomus"
  },
  "comment": "Implementation complete at <sha>. Validation: ..."
}
```

Harness:

1. validates schema;
2. restricts update to current ticket;
3. applies allowed fields;
4. stores result;
5. logs failure non-fatally unless ticket identity itself is unsafe.

Implementer must not be able to mutate arbitrary YouTrack issues.

---

# 7. Reviewer YouTrack responsibilities

Reviewer remains code read-only.

Reviewer may propose YouTrack metadata updates through structured output only.

Reviewer must NOT receive generic direct YouTrack write capability.

For `CHANGES_REQUIRED`:

- add concise review comment;
- include exact reviewed SHA;
- include actionable findings;
- transition ticket back to mapped `In Progress`, if available.

For `PASS`:

- add review PASS comment;
- include exact reviewed SHA;
- update state to mapped `Ready for Human Review`.

Failure to update YouTrack must not change review verdict.

---

# 8. YouTrack audit artifacts

Add coordination artifact(s), for example:

```text
.agent-cycle/PDFTR-43/youtrack.json
.agent-cycle/PDFTR-43/youtrack-events.jsonl
```

`youtrack.json` may contain:

```json
{
  "ticket": "PDFTR-43",
  "issue_id": "...",
  "issue_url": "...",
  "last_sync_role": "reviewer",
  "last_sync_sha": "...",
  "last_sync_status": "success"
}
```

Event log should preserve:

- timestamp;
- role;
- requested action;
- issue identity;
- success/failure;
- remote response identity where safe;
- error class/message;
- exact local SHA associated with update.

Do not store authentication tokens.

---

# 9. Idempotency

Every YouTrack operation must be safe under runner restart/resume.

Examples:

- rerunning `ensure_youtrack_issue` must not create another issue;
- the same implementation SHA must not add the same completion comment repeatedly;
- the same review verdict must not produce duplicate comments on resume;
- state transitions already applied should be treated as success.

Use deterministic idempotency keys derived from:

```text
ticket + role + round/attempt + SHA + action
```

Store them locally in the audit artifact.

---

# 10. Failure policy

## Non-blocking failures

These must normally produce warning + audit event and continue:

- YouTrack temporarily unavailable;
- field does not exist;
- unsupported estimation value;
- due-date update rejected;
- comment creation failed;
- state transition unavailable;
- assignee field mapping unavailable.

## Fail closed

These should prevent remote mutation and may stop YouTrack sync:

- issue identity ambiguity;
- attempting to mutate a different ticket;
- project mismatch;
- authentication points to unexpected YouTrack project/account;
- returned issue key does not match expected ticket;
- malformed response that makes target identity uncertain.

Local implementation/review may still continue when safe.

---

# 11. Backfill policy for PDFTR-38…PDFTR-42

PDFTR-38…PDFTR-42 are historical exceptions.

User creates placeholder YouTrack issues manually.

PDFTR-43 implementation must NOT rewrite their history automatically.

Optional documentation/backfill tooling may later:

- attach title;
- add final SHA;
- mark resolved;
- add concise completion note.

That is outside the core PDFTR-43 path unless trivial and explicitly safe.

---

# 12. GitHub PR integration

After agent cycle reaches:

```text
PASSED
```

harness should ensure a PR exists from ticket branch to configured base branch.

Default:

```text
head = current ticket branch
base = master
```

Behavior must be idempotent:

```text
existing PR -> update/reuse
no PR      -> create
```

Do not create duplicate PRs on rerun.

---

# 13. PR content

PR title should include ticket ID and concise task title.

Example:

```text
PDFTR-43: GitHub PR / ChatGPT Work integration
```

PR body should include:

- ticket ID;
- YouTrack link when available;
- implementation SHA;
- branch/base;
- implementer provider/model;
- reviewer provider/model;
- review rounds;
- final automated verdict;
- focused validation summary;
- full validation summary;
- coverage where available;
- known warnings;
- human recovery history, if any;
- note that merge remains human-owned.

Do not claim CI success unless exact-SHA CI evidence exists.

---

# 14. Exact-SHA PR binding

PR metadata must explicitly identify:

```text
Implementation SHA: <exact SHA>
```

Before updating PR as ready for human review verify:

```text
PR head SHA == cycle implementation/reviewed SHA
```

If PR head moved unexpectedly:

```text
fail closed for PR readiness
do not claim reviewed status
```

---

# 15. GitHub Actions / CI

When PR exists:

- inspect exact PR head SHA checks;
- collect workflow/check status;
- distinguish:
  - pending;
  - passed;
  - failed;
  - unavailable.

CI availability must not be fabricated from local `scripts/check.ps1`.

If checks are pending, PR may exist but must not be labelled as CI-passed.

---

# 16. ChatGPT Work handoff

PDFTR-43 should establish a deterministic handoff package for final review.

Minimum handoff metadata:

```json
{
  "ticket": "PDFTR-43",
  "youtrack_url": "...",
  "github_pr_url": "...",
  "head_sha": "...",
  "base_branch": "master",
  "cycle_state": "PASSED",
  "automated_review": "PASS",
  "ci_status": "passed|pending|failed|unavailable"
}
```

Store as, for example:

```text
.agent-cycle/PDFTR-43/human-review.json
```

The handoff must be sufficient for ChatGPT Work or a human reviewer to open the PR and perform independent review without reconstructing state manually.

If direct ChatGPT Work invocation is not available through a stable supported interface, generating the verified handoff artifact + PR URL is acceptable for PDFTR-43.

Do not implement brittle UI automation solely to claim Work integration.

---

# 17. Human review boundary

Automated agent `PASS` must continue to mean:

```text
READY FOR HUMAN REVIEW
```

not:

```text
MERGED
```

PDFTR-43 must not automatically merge the PR.

Merge remains explicitly human-owned.

---

# 18. Security / permissions

YouTrack credentials must come from secure configuration/environment.

Never:

- commit API tokens;
- write tokens to `.agent-cycle`;
- include tokens in logs;
- expose credentials to reviewer prompts.

Prefer a narrow YouTrack adapter/API layer.

GitHub operations must preserve existing repository safety constraints.

---

# 19. Configuration

Prefer project configuration instead of scattered constants.

Example:

```toml
[project_tracking.youtrack]
enabled = true
project = "PDFTR"
assignee = "bodomus"

[project_tracking.github]
base_branch = "master"
create_pr_on_pass = true
```

Actual configuration format may follow existing repository conventions.

Secrets remain outside repository config.

---

# 20. Tests

Add deterministic tests for at least:

## YouTrack bootstrap

- existing issue is reused;
- missing issue is created;
- wrong returned issue key fails remote sync;
- duplicate create is prevented on resume;
- Markdown title/body are mapped correctly.

## Fields

- assignee `bodomus`;
- valid estimation update;
- unsupported estimation is non-blocking;
- due date update;
- missing custom field is non-blocking.

## Lifecycle

- implementer start -> In Progress;
- handoff -> Ready for Review;
- CHANGES_REQUIRED -> In Progress;
- PASS -> Ready for Human Review;
- merge event/update -> Done where supported.

## Reviewer isolation

- reviewer cannot directly mutate YouTrack;
- reviewer structured update applies only through harness;
- verdict is unaffected by YouTrack outage.

## Idempotency

- resume does not duplicate issue;
- resume does not duplicate comments;
- resume does not duplicate PR;
- repeated state update succeeds idempotently.

## GitHub

- create PR after PASSED;
- reuse existing PR;
- exact head SHA verification;
- changed PR head fails readiness;
- CI pending/pass/fail/unavailable handled separately.

## Failure handling

- YouTrack timeout does not kill safe local implementation;
- GitHub PR API failure leaves cycle PASSED but reports integration warning;
- identity ambiguity fails remote mutation.

---

# Acceptance criteria

- New tickets can be bootstrapped from `Tickets/PDFTR-XX.md`.
- Existing YouTrack tickets are detected and reused.
- Assignee defaults to `bodomus`.
- Estimation and due date are populated when safely derivable.
- Unsupported YouTrack fields are reported but do not block implementation.
- Implementer and reviewer keep the current ticket updated through structured harness-controlled mutations.
- Reviewer remains read-only with respect to repository and direct external mutation.
- YouTrack updates are idempotent and auditable.
- After `PASSED`, a GitHub PR is created or reused.
- PR is bound to the exact reviewed SHA.
- Exact-SHA CI state is represented accurately.
- A deterministic human/ChatGPT Work handoff artifact is produced.
- No automatic merge occurs.
- Existing PDFTR-35A / PDFTR-40 / PDFTR-42 safety guarantees remain intact.
- `scripts/check.ps1` passes.
- Windows and Ubuntu CI pass.

---

# Non-goals

Do not implement in PDFTR-43:

- automatic PR merge;
- arbitrary YouTrack bulk edits;
- historical reconstruction of PDFTR-38…PDFTR-42;
- unrestricted YouTrack access for coding/reviewer agents;
- brittle browser automation for ChatGPT Work;
- changes to PDF translation/layout behavior.

---

# Follow-up candidates

Possible later tickets:

- automatic close/Done transition after confirmed GitHub merge;
- richer YouTrack ↔ PR bidirectional links;
- SLA / estimation calibration from historical tickets;
- Work-trigger integration if/when a stable supported programmatic interface is available;
- reusable project-management adapter so the same harness can support YouTrack, GitHub Issues, Linear, Jira, etc.
