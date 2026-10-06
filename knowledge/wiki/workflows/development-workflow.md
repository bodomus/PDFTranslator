---
title: Development workflow
type: workflow
status: active
created: 2026-09-17
updated: 2026-10-06
tags:
- development
- tickets
- validation
sources:
- ../../../AGENTS.md
- ../../../.codex/PRE_TICKET_WORKFLOW.md
- ../../../scripts/check.ps1
- ../../../scripts/agent_cycle.py
- ../../../scripts/pi_ticket_cycle.py
- ../../../scripts/agent_progress.py
- ../../../scripts/agent_progress/journal.mjs
- ../../../tests/test_agent_progress.py
- ../../../scripts/project_tracking.py
- ../../../scripts/review_protocol.py
- ../../../tests/test_runner_snapshot.py
- ../../../scripts/tracking_hooks.py
- ../../../project-tracking.toml
- ../../../tests/test_project_tracking.py
- ../../../tests/test_youtrack_validation.py
- ../../../tests/test_pi_ticket_cycle.py
- ../../../tests/test_pi_cycle_resume.py
- ../../../tests/test_operational_retry.py
- ../../../Tickets/PDFTR-42-resumable-pi-ticket-cycle.md
- ../../../scripts/reviewer_git/inspector.mjs
- ../../../.agents/skills/two-agent-ticket-workflow/REVIEWER_GIT_SAFETY.md
- ../../../.agents/skills/two-agent-ticket-workflow/SKILL.md
related:
- ../index.md
- wiki-maintenance.md
- ../testing/wiki-validation.md
---

# Development workflow

Non-trivial work follows the repository intelligence workflow before implementation. The current
source tree, tests, dependency files, runtime evidence, and maintained documentation are
authoritative; Graphify and CRG guide discovery but do not replace source verification.

## Before implementation

1. Read repository and nested instructions, the ticket, and the [Wiki index](../index.md).
2. Record Git branch, commit, working-tree state, Python, and uv baselines.
3. Classify the workflow level and protect unrelated user changes.
4. Query ProjectWiki, Graphify, and CRG as applicable, then verify findings in source.
5. For Level 2 work, write ticket-scoped investigation and implementation-plan artifacts.

## During implementation

- Keep scope ticket-focused and dependencies explicit.
- Add tests for behavior changes and preserve platform/runtime safety constraints.
- Update user documentation and changelog for visible behavior.
- Do not update Wiki pages until implementation knowledge is known.

## Sequential two-agent tickets

Tickets that explicitly use the agent cycle add repository-local coordination under the ignored
`.agent-cycle/<TICKET>/` root. `manifest.json` is authoritative system state. `handoff.json` has
three ownership sections: validator-derived `system`, claims from `implementer`, and an exact-SHA
result from `reviewer`. Concrete LLM products may be assignment metadata but never state-machine
roles or ownership keys.

The implementer is the single repository writer. The reviewer runs only after handoff, checks the
recorded SHA read-only, and returns `PASS`, `CHANGES_REQUIRED`, or `BLOCKED`. A new implementation SHA makes the
earlier result stale. The validator enforces one active role, clean-tree review gates, immutable
review artifacts, exact repeated-finding detection, and at most two automated review rounds.
Round-two changes required stops for human inspection. Final review and merge remain human-owned.

`scripts/agent_cycle.py` validates and records this state; it is not an orchestrator and does not
launch agents, fetch, retry, merge, or create pull requests. PDFTR-33 is the explicit bootstrap
exception in which Codex implemented the validator before the post-ticket role boundary existed.
Recovery is conservative: invalid or corrupt state fails closed rather than being guessed or
silently regenerated.

`scripts/pi_ticket_cycle.py` automates that validated sequence for explicitly assigned tickets. It
imports the validator rather than reimplementing it: it initializes a missing cycle or dispatches
idle `NEW`, `CHANGES_REQUIRED`, `READY_FOR_REVIEW`, and `READY_FOR_REVIEW_2` states, runs
the Pi implementer, validates the handoff and exact SHA from Git plus `agent_cycle`, runs a
technically read-only Pi reviewer on that SHA, and records the reviewer JSON through
`record-review`. It allows one fix/review retry with a required new SHA, stops on abnormal exit,
a dirty tree, or malformed/wrong-SHA output, and returns control to the human after `PASS`,
`BLOCKED`, or the two-round limit. Ownership is explicit: the implementer writes project files and
only its role-owned handoff input, the reviewer returns one structured JSON object on stdout and
never writes an authoritative coordination file, and the runner persists that result into ignored `.agent-cycle`
state. The parser accepts exactly one supported review envelope and fails closed otherwise. The
runner owns every child process tree and terminates descendants through a Windows Job Object or a
saved POSIX process group on success, cancellation, or any post-spawn failure. Provider, model, and
tool names are configuration; deterministic tests replace Pi and never contact providers or the
network.

The parent startup-loads all repository harness dependencies and retains that code generation for
its entire invocation. Implementer source edits activate only on the next process invocation, not
by hot reload or automatic restart. The pure `review_protocol.py` owns shared envelope grammar;
tracking does not import the runner. Before parsing/persisting a successful reviewer result, the
runner saves original stdout to `reviewer-stdout-round-<N>.txt`. Unexpected internal post-review
failures stop explicitly with diagnostics, retaining stdout, logs and cycle artifacts without
rerunning the reviewer. Isolated disk-mutation tests cover both reported missing-symbol generations
and normal PASS/CHANGES_REQUIRED accounting.

Human recovery is explicit: `--recover --reason` on the runner or `agent_cycle.py reopen --reason`
authorizes one further implementation/review pair only from exhausted `STOPPED` review states.
The validator requires the recorded branch, clean tree, unchanged HEAD and repository bindings.
`HUMAN_APPROVED_REWORK` plus strict `human_recoveries` audit entries retain approval reason,
prior stop reason, SHA, round, next attempt and previous handoff. Review numbering is cumulative;
old reviews and numbered implementation snapshots are immutable. MAX_REVIEW_ROUNDS remains two;
a recovery changes-required verdict stops again. `PASSED` reruns only configured external synchronization/PR verification; other terminal
and active-role states never auto-resume except for the proven pre-launch operational case below.
Approval is a human/operator action, not agent authority.

Pre-handoff operational failure has a separate human boundary: `--recover-operational --reason`
(or validator `retry-operational`) requires structured operational stop classification, round zero,
no accepted handoff/review, no active role, clean tree and unchanged exact HEAD plus existing
branch/repository identity. `HUMAN_APPROVED_OPERATIONAL_RETRY` and strict `operational_retries`
history authorize at most three new implementer attempts without granting reviews. Normal invocation
resumes a persisted approval; duplicate approval rejects. Approved operational attempts precede any
accepted handoff/review, so their authorized numbered snapshot inventory is empty. Unexpected
implementation/review snapshots reject before preservation, journal appends or transitions, including
approval-crash normalization. Later review/rework states retain their accounted immutable history.
Atomic manifest approval can safely recover its exact blank handoff projection after interruption
between writes, comparing nested JSON types as well as values; false and 0.0 cannot replace integer 0.
The runner holds an OS ticket lock
and persists an attempt-bound `implementer-launch-attempt-<N>.json` prepared marker before begin.
If it dies during begin's manifest/handoff writes or after begin/tracking but before the launch
fence, normal invocation can resume the same active implementation under exclusive ownership,
clean unchanged HEAD and matching strict approval-bound marker. Before status loading, the runner
atomically completes only the exact blank prior approved handoff projection after validating all
identity/Git bindings and absence of immutable accepted artifacts. Nonblank or other mismatched
projections reject; this does not relax ordinary validator loading or repeat begin/accounting.
Before executor entry the atomic marker becomes launching; uncertainty after that point, concurrent
owners, absent/corrupt/mismatched markers and legacy active states reject without guessing a child.
Historical markers remain available; approval/attempt/round accounting is never repeated.
Attempts add operational retry count
to implementation numbering; accepted handoffs retain their actual number. Partial inputs and prior
reports receive attempt-numbered snapshots, log numbers are unique, journals stay append-only.
Status exposes class/code, count/attempt and eligibility/rejection reason. OS launch failures and
nonzero implementer exits have stable codes; trusted adapters can supply provider codes, but text
messages are never parsed. Legacy text-only operational stops remain unknown; legacy exhausted
review recovery derives classification from validated immutable reviews. No WIP cleanup, automatic
retry, process-ownership guessing or new reviewer authority is introduced.

The runner reports lifecycle boundaries and authoritative handoff/review results with flushed
plain console output. `SubprocessExecutor` retries timed communication and emits an elapsed-time
heartbeat every five minutes; it sends stdin once and retains the same process-tree owner and
cleanup paths. Detailed child output stays in existing diagnostic logs.

Each role receives centralized milestone-only policy and a runner-bound `progress_append` capability
with no path parameter. When enabled, each highest-precedence automated-runner override explicitly
permits only that bound tool as a diagnostic exception, forbids direct journal writes, and preserves
all other role restrictions. Disabled overrides retain the original write prohibitions.
Its append-only `<role>-progress.log` uses `[HH:MM]` UTC and retains prior
history plus attempt/round boundaries across exits, resume and recovery. The reviewer can append
only to its own diagnostic journal, never the implementer's or tracked repository files; this narrow
exception does not replace review JSON or relax Git/SHA gates. No reasoning, prompts or sensitive
content is permitted; tool validation additionally rejects controls, URLs and common credential
patterns. The heartbeat reads a bounded 64-KiB tail locally, skips malformed/partial lines, sanitizes
controls and truncates activity text. Staleness is measured from valid entry changes observed by
heartbeat polling, restarting per execution. Defaults are enabled, 30-minute stale warnings and
180 console characters; CLI flags can configure/disable them. Warnings never kill or auto-recover
the child. Exit/failure/cancellation diagnostics include last activity and relative journal path.
All runner diagnostics, including CLI errors and final reports, retain representable stream text
and replace unsupported characters with `?`; unavailable output cannot fail a child or mask its
original failure. Invalid UTF-8 journal bytes remain non-fatal. Journal mutation uses entry-level
`lstat` checks, rejecting even dangling symbolic links before opening and allowing creation only
when the entry is absent; normal files retain append-only behavior.

Runtime role presets (`deepseek-codex`, `codex-deepseek`, `codex-codex`, `deepseek-deepseek`)
select provider/model pairs. Explicit CLI fields override the corresponding preset fields.
Reviewer tools remain limited to `read,grep,find,ls,git_readonly`, and every role uses a separate process and
context even when provider/model are identical. Presets do not alter the validator state machine.

The reviewer-only Git-read adapter and optional progress tool load explicitly with other extension
discovery disabled.
Its fixed-operation inspector verifies HEAD/status/SHA/branch/diff/show/merge-base/history using
runner-bound cwd, full commit IDs or HEAD, bounded output/time and no shell. It disables executable
Git helper/filter/pager paths, optional index locks and network/submodule traversal. Unsupported
layouts or failed/inconsistent evidence fail closed. Any `.git/commondir` entry is rejected before
a Git subprocess; linked-worktree/common-directory layouts remain unsupported, while ordinary
repositories without redirects remain supported. Reviewers independently verify Git evidence;
`agent_cycle.py` remains the sole state/binding authority. See the source-linked reviewer safety
contract for limits and supported operations. Node 22 tests use local repositories, no providers.

`cycle_status` labels dirty-tree evidence as expected only during IMPLEMENTING with active
implementer. This read-only status projection leaves the manifest untouched, preserves other
binding errors, and does not relax initialization, handoff, review, or terminal validation gates.

Process-tree service fixtures in `tests/test_pi_ticket_cycle.py` clear inherited automatic
coverage startup variables in their test environment. Their temporary child cwd has no coverage
config; pytest-cov 6 would otherwise create statement-only data alongside the parent's branch
data. The module's real child/grandchild diagnostic verifies isolation and unchanged parent
measurement. This test-only exception preserves branch coverage policy and coverage for real
package subprocesses in other test modules.

## External tracking and human handoff

The runner invokes `TrackingHooks` after safe local preflight. `ProjectTracking` bootstraps the
exact Markdown ticket before implementer execution; its narrow YouTrack REST adapter verifies
key/project/configured account before mutations, reads project field cardinality/value bundles,
and uploads the ticket definition. `project-tracking.toml` is canonical, with a credential-free HTTPS
`base_url` and environment-only token. A legacy URL variable must match the configured URL exactly.
Preflight distinguishes disabled, missing credentials, authentication, project and endpoint failures.
Creation is opt-in (shipped `allow_create = false`); definite exact absence differs from transport/auth
failure. Creation responses and read-back must agree with the requested key/project; a differently
allocated YouTrack number requires human reconciliation, never fallback mutation. OS-held local
synchronization locks serialize harness/operator access; ambiguous creates recover through exact
discovery only. Important field/definition updates use read-before-write and semantic read-back.
Assignee resolves an exact API login; estimates, UTC due dates and enums require explicit local values.
The operator `validate-live` command defaults to remote read-only, supports dry-run, explicit creation,
field/state updates and a separate finalization opt-in, and repeats opted-in synchronization to verify
idempotency. No real credentials or remote mutations are required during implementation; deterministic
fakes do not establish live API/mapping compatibility. Only configured schema-valid fields and lifecycle states are
applied. Unsupported fields and outages generate agent-visible warnings without changing verdicts.
Historical PDFTR-38…PDFTR-42 placeholders are excluded.

Optional agent metadata is a separate YouTrack stdout envelope, not a change to strict handoff or
review schemas. The runner applies it only after accepting the relevant local result. The reviewer
keeps its fixed read-only tools. Integration tokens are removed from child environments; categorized, sanitized
external diagnostics avoid server-body/credential disclosure. Invalid metadata is isolated from
an otherwise valid review result. The strict review envelope is selected first and never rewritten
by metadata removal. Nested, overlapping and unmatched intent delimiters, including those inside
fenced JSON, fail closed; metadata cannot hide competing verdicts.
Unavailable or partially malformed field schemas skip unsupported definitions; ticket attachments
and review comments continue independently of custom-field availability.

Runtime `youtrack.json` and JSONL events preserve identities, mutation keys, SHA, action and status.
Mutations are journaled before sending: ambiguous create outcomes use discovery only on resume,
while uncertain comment/attachment mutations require human reconciliation. Concise comments publish
only harness-confirmed SHA/round/action evidence, not agent prose or huge logs. PASS/PASSED target human
review, never Done; only an explicit merged/finalization action may close. REST socket and overall
timeouts bound calls; an uncertain in-flight request is never blindly retried. Socket timeouts,
connection loss and unreadable mutation responses also retain uncertainty: terminated client transport
does not prove server-side failure. Pending/uncertain field/definition writes durably block later
synchronization, including after restart; operator repair
requires proving transport termination and reconciling remote state, not merely a GET or lock release.
Configured field types/estimation/date syntax are checked before bootstrap mutation; failed requested
operator synchronization returns nonzero without an idempotent-completion claim. Implementation reports
are attached after accepted handoff. Configuration/audit failures disable integrations, not safe
local work. Configurable `merged` lifecycle updates support Done without automatic merge polling.

After PASSED, GitHub integration uses the explicit configured repository and head/base. It creates
or reuses one open PR with neutral metadata, checks exact reviewed head, publishes SHA-bound
readiness/review/CI evidence, checks the head again, and includes
local validation/report evidence, persisted role/model provenance, warnings and recovery history.
Exact-head check rollup is classified independently from local validation. A moved head invalidates
readiness and triggers remote replacement with neutral metadata. Uncertain readiness updates also
trigger neutralization. If GitHub is unavailable during cleanup, operator reconciliation is required;
no human handoff is produced and the local verdict remains unchanged.
`human-review.json` records verified SHA, PR/YouTrack URLs, timestamp, CI status and audit
context for independent human/ChatGPT Work review; `github-events.jsonl` records success/failure.
No Work UI automation or automatic merge is implemented. Passed-cycle resume re-verifies external
readiness without rerunning agents, including idempotent YouTrack bootstrap/PASS catch-up for legacy passed
cycles. Existing committed completion summaries under `reviews/` are attached after PASS.

## Completion

1. Run focused validation, then the full `scripts/check.ps1` quality gate.
2. Refresh CRG and inspect the final blast radius; refresh Graphify only for qualifying structural
   architecture changes.
3. Produce the ticket implementation report and review.
4. Update only affected Wiki pages, append a meaningful log entry, and run Wiki lint.
5. Update the external ticket and attach required artifacts when authorized.
