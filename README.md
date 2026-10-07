# PDFTranslate

PDFTranslate is a Windows-first Python command-line application for translating English PDF
content into Russian. It can inspect text-based PDFs, extract layout-aware text blocks into a
stable JSON intermediate format, translate those blocks locally with NLLB, and render Russian text
into a validated copy of the source PDF. Optional OCRmyPDF/Tesseract preprocessing supports
scanned and mixed documents.

## Prerequisites

- Windows 11 is the primary development platform; Linux is also validated in CI.
- Python 3.12 (the project intentionally supports `>=3.12,<3.13`).
- [uv](https://docs.astral.sh/uv/) on `PATH`.
- Git, required for pre-commit hooks.
- Optional for scanned PDFs: OCRmyPDF, 64-bit Tesseract with English (`eng`) data, and
  Ghostscript when required by the installed OCRmyPDF version.

No CUDA toolkit, NVIDIA GPU, model download, or administrator privileges are required for tests.
PyMuPDF is the PDF backend; PyTorch and Transformers provide local inference. NLLB weights are
downloaded only when translation runs without an already cached model.

On Windows, the committed uv configuration installs the official CUDA 13.0 PyTorch build so the
same environment supports both explicit CPU inference and NVIDIA GPU inference. CUDA execution
requires a compatible NVIDIA GPU and driver, but not a separately installed CUDA Toolkit. Linux CI
continues to resolve Torch from PyPI and does not require GPU hardware.

Performance and memory measurements are available through the standalone benchmark script. It
supports deterministic model-free checks plus strict-offline real NLLB CPU/CUDA runs without
adding benchmark commands to the production CLI. See
[docs/performance-benchmark.md](docs/performance-benchmark.md) for scenarios, commands, metrics,
and interpretation limits.

## Project knowledge

The repository includes a small Git-tracked ProjectWiki for durable architecture, workflow,
decision, constraint, failure-mode, integration, and testing knowledge. Start with the curated
[knowledge index](knowledge/wiki/index.md); source code, tests, current configuration, canonical
reports, and runtime evidence remain authoritative.

Search and validate the Wiki without network access or extra dependencies:

```powershell
uv run python scripts/project_wiki/wiki_search.py "PDF extraction"
uv run python scripts/project_wiki/wiki_lint.py
```

Read [knowledge/AGENTS.md](knowledge/AGENTS.md) before maintaining the Wiki. Existing files under
`knowledge/raw/` are immutable evidence during normal maintenance, and only pages affected by
durable new knowledge should change after a non-trivial ticket.

## Two-agent ticket cycles

Tickets that explicitly opt into the repository agent cycle use local ignored state under
`.agent-cycle/<TICKET>/`. The implementer is the only writer; after it commits and pushes, the
reviewer checks one exact SHA read-only. The validator enforces sequential ownership, strict
`system`/`implementer`/`reviewer` handoff sections, stale-review invalidation, and a maximum of two
review rounds. Concrete agent products are optional orchestration metadata, not contract roles.
Final merge remains a human decision.

```powershell
uv run python scripts/agent_cycle.py init PDFTR-34
uv run python scripts/agent_cycle.py begin-implementation PDFTR-34
uv run python scripts/agent_cycle.py handoff PDFTR-34 --file .agent-cycle/PDFTR-34/implementer.json
uv run python scripts/agent_cycle.py begin-review PDFTR-34 --sha <FULL-40-CHARACTER-SHA>
uv run python scripts/agent_cycle.py record-review PDFTR-34 --file .agent-cycle/PDFTR-34/reviewer.json
uv run python scripts/agent_cycle.py status PDFTR-34
```

See [the two-agent workflow skill](.agents/skills/two-agent-ticket-workflow/SKILL.md) for role and
recovery contracts. The tool records workflow state only; it does not launch agents, fetch, merge,
or create pull requests. PDFTR-33 itself is the one explicitly authorized bootstrap exception.

### External tracking and human review (PDFTR-43 / PDFTR-47)

`project-tracking.toml` controls the harness-owned YouTrack and GitHub adapters. Before launching
an implementer, the runner reads the exact ticket Markdown, preflights credentials/project/endpoints,
looks up only its exact YouTrack key, verifies ticket/project/account identity, synchronizes summary/body,
and attaches the definition. Missing issues are not created by default (`allow_create = false`).
The canonical configuration is `[youtrack]` in `project-tracking.toml`, including HTTPS `base_url`;
set only `YOUTRACK_TOKEN` securely in the parent environment. Legacy `YOUTRACK_URL`, if present,
must exactly match the configured URL; it cannot override the host. Configure `expected_login` for
the authorized account. Tokens are excluded from child environments and audit logs.
For GitHub, install/authenticate `gh`; the repository and base branch are explicit config.
Disable either integration with `enabled = false` / `create_pr_on_pass = false`.

Project field names and lifecycle state values are configurable, but mutations use inspected schema
and existing bundle values, not guessed IDs. Assignee defaults to `bodomus`, resolved by exact API
login and checked against the project's allowed user bundle. Estimation, due date, type and priority
are never invented: set them explicitly under `[youtrack.defaults]`. Periods preserve units (e.g.
`4h`, `1d 2h`); due dates require ISO `YYYY-MM-DD`, encoded as midnight UTC milliseconds. Important
writes are re-read and semantically verified; HTTP success alone is not synchronization success.
Unknown fields, unsupported values, API failures and unavailable credentials generate warnings,
not a failed implementation/review. Identity mismatch prevents further YouTrack mutations.
Historical PDFTR-38…PDFTR-42 placeholders are excluded from automatic synchronization.

Agents may optionally emit a separate `<<<YOUTRACK_UPDATE_JSON>>>` / `<<<END_YOUTRACK_UPDATE_JSON>>>`
stdout envelope containing exactly `ticket`, `role`, `summary`, `proposed_fields`, and `comment`.
Proposed fields permit only string-valued `assignee`, `estimation`, `due_date`, `type`, `priority`.
The harness supplies state and exact SHA, validates the current ticket/role, and applies updates.
Reviewer tools remain read-only; malformed metadata does not change a valid review verdict.
The strict review envelope is selected before metadata removal. Only separate external metadata
may be removed; nested, overlapping or unmatched intent delimiters and competing verdicts fail
closed, including those inside fenced review JSON. Unavailable or partially malformed project
schemas skip unsupported fields while safe ticket attachments and review comments continue.

Ignored runtime artifacts include `youtrack.json`, `youtrack-events.jsonl`, `github-events.jsonl`,
and `human-review.json`. Mutation keys bind ticket/role/round/SHA/action. Intent is journaled before
mutation: an uncertain create is recovered by exact-key discovery, never by blind re-creation;
failed reconciliation reads preserve the original uncertain mutation and its non-repeatable guard.
Secondary reconciliation diagnostics are best-effort: warning-sink failures preserve the original
mutation uncertainty and evidence across restart.
Only verified exact ticket/project discovery resolves that create, including after restart;
identity mismatches retain the safety fence and unrelated mutation fences remain intact.
Uncertain comments/attachments require human reconciliation rather than automatic duplicate retries.
Fields/definitions are read before writing and re-verified on resume; identical values generate no
extra update. Pending or uncertain field/definition operations durably fence further YouTrack synchronization,
even across restart. There is no automatic fence reset: an operator must establish that the old
transport has terminated and reconcile remote state before repairing its operation evidence. A GET
or lock release alone cannot establish this. Malformed configured field values fail validation before
bootstrap mutations; requested synchronization failures return nonzero without an idempotency claim. Comments remain concise SHA/round/action evidence; unverified agent prose and huge
validation dumps are not published. Warnings are passed to agent reports; the implementation report
is attached. Synchronization is locally OS-lock serialized; conflicts/uncertain creates permit only
exact discovery, never another creation. Each REST call has a 5-second socket timeout and 10-second
overall bound, with no automatic mutation retry loop. Mutation socket/overall timeouts, connection loss,
HTTP 408/5xx mutation errors (including gateway 504), and unreadable mutation responses are uncertain even if the client transport has terminated: the server
may still complete the write. Durable create/comment and field/definition fences require reconciliation.
Read-only request timeouts are ordinary read failures. Every mutation operation explicitly prepares
identity checks, discovery, duplicate checks and payloads before mutation journaling, including issue
creation, lifecycle comments, attachments, PR cross-links and field/definition updates. Failed
preparation creates only diagnostic events, without reserving a non-repeatable mutation key or
creating a pending/uncertain mutation or conflicting-write fence; the same action can retry after
restart. Pending intent is persisted immediately before mutation execution. A verification GET
timeout after a dispatched write still preserves that operation's mutation fence.
An existing committed `reviews/review-<TICKET>.md` completion summary is attached after PASS.

#### Explicit operator validation (no agent cycle)

```powershell
uv run python scripts/project_tracking.py validate-live PDFTR-47 --dry-run
uv run python scripts/project_tracking.py validate-live PDFTR-47
# Explicit create / definition / configured-default updates, then idempotent second sync:
uv run python scripts/project_tracking.py validate-live PDFTR-47 --allow-create
# Existing issue fields and an explicitly chosen lifecycle state:
uv run python scripts/project_tracking.py validate-live PDFTR-47 --apply-fields --state start
# Done is human-owned, never implied by PASS:
uv run python scripts/project_tracking.py validate-live PDFTR-47 --state merged --finalize
```

Default validation and dry-run do not mutate the remote issue. They inspect credentials, project,
exact identity, discovered fields/states and assignee; evidence/warnings are recorded locally.
`--allow-create`, `--apply-fields` or `--state` explicitly opt into remote synchronization (definition,
attachment and configured defaults); state changes require `--state`. Validation exits nonzero when
credentials/identity/issue or a requested semantic write cannot be verified. Partial field availability
is diagnosed without blocking the local agent cycle. Inspect `youtrack.json` and append-only events;
`success`, `partial` and `failed` distinguish actual results. If an issue is definitely absent without
permission, the warning explicitly says remote create is unavailable. Network/auth/server failures
never authorize creation. YouTrack allocates issue numbers: if creation returns a different key, it
is recorded for human reconciliation and **no further mutation** is allowed; a requested key is never
guessed or substituted. Do not enable creation to backfill historical keys. Live access is not needed
for implementation/testing; live API formats/mappings must still be confirmed by an operator.

After `PASSED`, GitHub readiness remains independent of the YouTrack uncertainty fence: under the
shared synchronization lock, PR processing continues while the YouTrack cross-link is skipped with
an explicit warning. Stale local readiness is still revoked if GitHub's head has moved.
The runner creates or reuses a PR with neutral metadata, verifies its head against
the reviewed SHA, publishes SHA-bound review/readiness/CI evidence, and verifies the head again.
Detected movement or an uncertain readiness update triggers replacement with neutral metadata.
A moved head prevents the human-review artifact; an external failure leaves the local cycle
`PASSED` with a warning. The PR includes role/model provenance,
validation evidence, warnings and human recovery history. Exact-head checks are represented as
`pending`, `passed`, `failed` or `unavailable` in `human-review.json`; local `check.ps1` is never CI
evidence. Rerunning a passed cycle safely catches up YouTrack bootstrap/PASS synchronization
and refreshes PR/check evidence without rerunning agents.
Give the PR URL and this deterministic handoff to a human or ChatGPT Work for independent review.
If GitHub is unavailable during neutralization, remote cleanup requires operator reconciliation;
the failed integration still produces no handoff and does not change the local cycle verdict.
No browser automation, historical backfill, automatic merge, or automatic merged-event polling is
implemented. Human review and merge remain human-owned.

### One-command Pi runner

`scripts/pi_ticket_cycle.py` automates the same sequence without changing the validator's
authority:

```powershell
uv run python scripts/pi_ticket_cycle.py PDFTR-36
```

It imports `scripts/agent_cycle.py`, initializes a missing cycle or resumes an idle cycle, runs a Pi implementer
(default `deepseek / deepseek-v4-pro`), validates the handoff and exact SHA deterministically,
starts a read-only Pi reviewer (default `openai-codex / gpt-6.1-sol` with `read,grep,find,ls,git_readonly`), and
records the reviewer JSON through the validator. The implementer may write project files and only
its own handoff input; the reviewer returns one structured JSON object on stdout and never writes a
coordination file — the runner persists that output into ignored `.agent-cycle` state. Reviewer tool
configuration must stay within the fixed read-only allowlist and is rejected before any cycle state
changes; prompts are delivered on stdin so large multilingual prompts are not limited by Windows
command lines; and the runner requires exactly one unambiguous reviewer result, rejecting malformed,
truncated, array-wrapped, extra, reversed-delimiter, or duplicate-key output. It supports at most
one fix/review retry, requires a new SHA, and stops on abnormal exit, a dirty tree, a missing
executable, cancellation, malformed/ambiguous/wrong-SHA output, or any post-spawn I/O failure. The
Windows child is created suspended and joined to its Job Object before it can run, and a Job Object
(Windows) or process group (POSIX) guarantees no Pi descendant survives the runner, on success or
failure. Ticket files match the exact ID boundary, so `PDFTR-35` never selects `PDFTR-35A`. It never
merges. After `PASSED`, the configured harness integration creates/reuses a PR.
Provider, model, and tool names are configuration;
`agent_cycle.py` remains the workflow authority, and the tests never invoke Pi, providers, or the
network.

The parent runner uses the harness modules loaded at process startup for the entire invocation.
Implementer edits to orchestration source take effect only on the next invocation; no hot reload or
automatic restart is performed. Runner and tracking share the pure `scripts/review_protocol.py`
envelope grammar, with no tracking import back into the runner. Original reviewer stdout is saved
as `reviewer-stdout-round-<N>.txt` before validation, alongside the existing reviewer log. Unexpected
post-review internal failures stop with diagnostics and retain evidence; they never imply PASS or
automatically repeat the reviewer.

Rerun the same command to resume `READY_FOR_REVIEW` or `READY_FOR_REVIEW_2` directly with
its exact-SHA reviewer, or `CHANGES_REQUIRED` with the next implementation attempt and previous
findings. `PASSED` reruns only external synchronization/PR verification, never agents; `BLOCKED`, `STOPPED`, and active `IMPLEMENTING` /
`REVIEWING` states fail closed without launching a child. Active phases require human inspection;
the runner does not guess whether another process is still running.

After exhausted reviews, a human may explicitly approve **one** additional implementation/review
pair (not an automatic retry budget):

```powershell
uv run python scripts/pi_ticket_cycle.py PDFTR-XX --recover --reason "human-approved follow-up for R1"
# Alternatively approve now, then run the normal runner command:
uv run python scripts/agent_cycle.py reopen PDFTR-XX --reason "human-approved follow-up for R1"
```

Approval is accepted only for `STOPPED` with `repeated_finding` or `review_round_limit` after the
review budget is exhausted, on the recorded branch with a clean tree and unchanged manifest HEAD.
`HUMAN_APPROVED_REWORK` and `human_recoveries` audit metadata record the reason, old stop reason,
SHA, round, attempt and prior handoff. Reviews retain cumulative numbers (`review-3.json`, etc.);
earlier artifacts are never overwritten. Numbered `implementation-<attempt>.json` snapshots retain
accepted handoffs. A new implementation SHA and independent exact-SHA review remain mandatory.
Any recovery review requesting changes stops again and needs another explicit human approval.
Agents must never request their own recovery; this command is a human/operator approval boundary,
not an authenticated identity service. Corrupt state and unclassified stops cannot be reopened.

For a **clean pre-handoff stop** (including a clean clarification exit), the human operator can
approve another attempt without renaming or deleting the cycle directory:

```powershell
uv run python scripts/agent_cycle.py retry-pre-handoff PDFTR-XX
uv run python scripts/pi_ticket_cycle.py PDFTR-XX
```

The first command approves only; the second dispatches the persisted attempt. Status reports
eligibility, attempt, expected/actual HEAD, branch, clean-tree evidence and rejection codes.
Approval requires STOPPED, round zero, no accepted implementation/review, unchanged clean HEAD,
recorded branch/repository identity, exclusive runner ownership, positive exited-process evidence,
and no pending/uncertain YouTrack mutations. Unknown stop prose never grants eligibility. Legacy
stops without runner exit evidence fail closed; operational retry remains a separate policy.
Structured `stop_class=operational` stops are rejected by `retry-pre-handoff` and must use the
PDFTR-45 operational retry path, including its retry budget; stop prose cannot bypass that rule.
Each approval snapshots previous execution artifacts byte-for-byte under `attempts/<N>/`, records
human approval time and source bindings in `pre_handoff_retries`, and persists
`HUMAN_APPROVED_PRE_HANDOFF_RETRY` before dispatch. Attempts are monotonic; review budget is unchanged.
A crash before the launch fence resumes only the same prepared attempt; a crash after the fence
requires inspection and cannot launch another implementer. Historical evidence is hash-checked.
Normal run/status never approves retries. Agents must not invoke this operator command or modify
approval metadata. Existing tracking identities and successful mutation keys are retained.

For a **pre-handoff operational failure**, a human can approve a separate implementer retry:

```powershell
uv run python scripts/pi_ticket_cycle.py PDFTR-45 --preset codex-codex `
  --recover-operational --reason "Usage limits reset; retry approved"
# Or persist approval now and resume with the normal runner command:
uv run python scripts/agent_cycle.py retry-operational PDFTR-45 --reason "Retry approved"
```

This requires `STOPPED`, structured `stop_class=operational` and a recognized `stop_code`,
round zero, no accepted implementation/review, no active agent, a clean tree, unchanged exact
HEAD, and the recorded branch/repository. It never stashes, resets, cleans or rebinds HEAD.
`HUMAN_APPROVED_OPERATIONAL_RETRY` persists one approval and resumes the same approved attempt
if interrupted before execution. Repeating the approval command rejects without mutation; use
normal resume after approval. An approved operational retry still precedes any accepted handoff or
review: unexpected numbered implementation/review snapshots reject before journal appends,
preservation or transitions, including an interrupted approval write. Accounted history in later
review/rework states remains valid. Approval-crash reconciliation requires equal JSON types as well
as values; Boolean or floating-point review rounds cannot substitute for integer zero.
For operational approvals the runner also resumes a pre-launch
`IMPLEMENTING` phase only with a matching atomic `prepared` attempt marker, clean unchanged Git
facts, and an exclusive OS-held ticket lock. If begin persisted the manifest but not its blank
handoff projection, normal resume atomically completes only the exact previous approved blank
projection after validating that same ownership and Git evidence. Contradictory handoffs reject.
The lock is released on runner death. Before entering
the child executor the marker becomes `launching`; crashes after this fence, missing/corrupt markers
and other active phases require inspection. Process ownership is never guessed.

At most **three** operational retries are allowed. `implementation_attempt` increases independently
of `review_round`; approval grants no extra review budget. The strict `operational_retries` audit
retains each human reason, prior stop code/reason, HEAD, branch and attempt. Previous logs keep
unique cumulative implementer numbers (`pi-implementer-round-2.log` is attempt 2), progress journals
remain append-only, partial inputs are archived as `implementer-attempt-1.json`, and previous
reports as `implementation-report-attempt-1.md`. `status` shows classification, attempt/count and
eligibility/rejection reason. Retry exhaustion records `operational_retry_limit`.

Nonzero implementer exits, termination and OS launch/runtime errors have structured classification.
Trusted adapters may explicitly supply quota, unavailable-provider or network/auth codes; provider
message text is never parsed for safety decisions. Uncertain errors, safety violations and legacy
text-only operational manifests (including an already-created PDFTR-44 stop) remain **unknown** and
require manual intervention: they cannot be safely auto-migrated from `stop_reason`. Legacy exhausted
review recovery instead uses validated immutable review evidence. Reviewer permissions are unchanged.

The runner prints flushed lifecycle messages for phase starts/exits, handoff validation, review
verdicts, and the validator's terminal state. A running child produces a heartbeat every five
minutes. Prompts, reasoning, and child stdout/stderr stay out of lifecycle output; existing
`.agent-cycle/<TICKET>/pi-*-round-*.log` files remain the detailed diagnostic source.

Each role receives a harness-bound `progress_append(message)` tool and its own append-only
`.agent-cycle/<TICKET>/<role>-progress.log`. Entries use `[HH:MM]` in **UTC** and contain only
short factual milestones (major steps, tests/results, blockers, commit/push/completion), usually
5–20 per execution; reviewer logs are shorter. Never log reasoning, prompts, secrets, credentials,
auth headers, OAuth codes, environment dumps or secret-bearing URLs. Summarize external failures;
the tool additionally rejects common credential patterns, all HTTP URLs and control characters.
It accepts no path parameter; reviewers cannot append to the implementer journal or mutate the
repository. This is a diagnostic exception only, not a review verdict or authoritative cycle state.
Journal writes inspect the directory entry itself and reject symbolic links, including dangling
links, before opening; an absent entry can be created and regular journals remain append-only.
When enabled, both automated-runner prompt overrides explicitly authorize only this bound tool
as a diagnostic write exception; direct journal writes remain prohibited. Disabled progress retains
the original role write restrictions. The reviewer loads only the trusted Git-read and progress extensions.

Heartbeats read the latest valid complete line locally, for example:
`[PDFTR-45] implementer attempt 2 running... 95m - last: [19:42] Running focused tests`.
Missing/empty/unreadable journals keep the old heartbeat format. Parsing reads at most the last
64 KiB, skips malformed/partial lines, sanitizes controls and truncates console activity to 180
characters. A warning appears after 30 minutes without a newly observed valid entry (including
when none is reported); the stale clock restarts per execution and updates at heartbeat polling.
This is **not a timeout** and never kills or recovers a process. No model status requests or periodic
agent-generated heartbeats are used; token overhead is limited to the short policy/tool and milestones.
Console diagnostics preserve characters supported by the stream and replace unsupported characters
with `?`, retaining display limits on CP1251/ASCII consoles. Invalid UTF-8 journal bytes are decoded
with replacement. Unavailable diagnostic output cannot interrupt execution or mask its original failure.

Configure via `--progress-stale-minutes 30`, `--progress-max-console-chars 180` (20–2000), or
`--no-agent-progress` to disable journals/policy/diagnostics. Defaults need no project configuration.
Existing journals survive success, failure, cancellation, STOPPED, resume and human recovery;
the runner appends UTC attempt/round boundaries instead of truncating. At role exit, including
cancellation or failure, it prints `Last activity:` and the relative `Progress log:` path.

Use a preset to change the provider/model assigned to each role:

| Preset | Implementer | Reviewer |
| --- | --- | --- |
| `deepseek-codex` (default) | `deepseek / deepseek-v4-pro` | `openai-codex / gpt-6.1-sol` |
| `codex-deepseek` | `openai-codex / gpt-6.1-sol` | `deepseek / deepseek-v4-pro` |
| `codex-codex` | `openai-codex / gpt-6.1-sol` | `openai-codex / gpt-6.1-sol` |
| `deepseek-deepseek` | `deepseek / deepseek-v4-pro` | `deepseek / deepseek-v4-pro` |

```powershell
uv run python scripts/pi_ticket_cycle.py PDFTR-38 --preset codex-codex
uv run python scripts/pi_ticket_cycle.py PDFTR-38 --preset codex-deepseek --reviewer-model custom-model
```

Each explicit `--implementer-provider`, `--implementer-model`, `--reviewer-provider`, or
`--reviewer-model` overrides that preset field; unspecified fields use the preset or existing
defaults. Unknown presets fail before cycle initialization. Reviewers retain the independent
`read,grep,find,ls,git_readonly` allowlist regardless of model identity. Same-model roles still use separate
Pi child processes and separate role prompts/contexts.

Reviewer-only `git_readonly` exposes explicit status, HEAD/SHA resolution, branch, endpoint diff,
working/index diff, commit show, merge-base and bounded history operations. It is not shell access
or arbitrary Git argv and cannot mutate the repository. The runner fixes the repository root and
loads its trusted Git-read adapter (plus the bound progress tool when enabled); helpers, filters,
pagers and network transports are
neutralized. Only HEAD/full commit IDs are accepted; each subprocess is capped at 30 seconds and
4 MiB (errors fail closed rather than truncate evidence). Reviewers independently verify Git
state and base relationships; `agent_cycle.py` still owns exact-SHA binding and all state.
See [reviewer Git safety](.agents/skills/two-agent-ticket-workflow/REVIEWER_GIT_SAFETY.md) for
operations and unsupported layouts. Inspector tests require Node 22, Pi's existing runtime;
CI installs it explicitly. Implementer permissions and human merge ownership are unchanged.
Linked-worktree/common-directory layouts, including any `.git/commondir` entry, are rejected
before inspection; ordinary repositories with a physical `.git` and no redirect remain supported.

`agent_cycle.py status` reports a dirty tree during `IMPLEMENTING` with active `implementer` as
`dirty (expected during implementation)`; JSON includes `working_tree_dirty_expected`.
Status does not mutate the manifest or hide HEAD/branch errors. Initialization, handoff, review
start, review ownership, and terminal cleanliness checks remain strict.


Source-backed paragraph typography can be inspected without translation or rendering. The
standalone developer command reports occurrence identity, role, dominant source style,
confidence/provenance, geometry inference, and mixed-style flags; optional JSON output belongs
under `temp/` during local investigation:

```powershell
uv run python -m scripts.typography_inspect SOURCE.pdf --pages 1,3-4
uv run python -m scripts.typography_inspect SOURCE.pdf --occurrences 38-42 `
  --output .\temp\pdftr27\typography.json
uv run python -m scripts.typography_inspect SOURCE.pdf --pages 1,3-4 --resolved `
  --output .\temp\pdftr28\resolved-styles.json
```

See [typography evidence](docs/typography-evidence.md) for the typed contract, confidence rules,
Robitzsch verification, and current limitations. See
[style reconstruction](docs/style-reconstruction.md) for role baselines, deterministic precedence,
fallback metadata, and the production paragraph/inline rendering boundary.

## Production body and footnote reflow

Schema 1.3 rendering automatically uses production reflow for confidently classified
single-column book pages. Body prose, headings, and footnotes use their occurrence-indexed
reconstructed typography. Body/heading content flows through the existing source body region,
then through bounded blank continuation pages inserted immediately after the source page. Ordered
footnotes use the same role-aware typography contract in their separate source lower-page region,
followed by bounded dedicated continuation pages. For each source page, body continuation pages
precede footnote continuation pages, followed by the next original page. Headers, page numbers, images, drawings,
and captions remain anchored or on the fixed-layout path. Ambiguous, multi-column, intersecting,
and otherwise unsafe pages never enter reflow automatically.

Mixed-style paragraphs retain the resolved paragraph style as their base. Source-backed inline
font-size and RGB-color differences are applied only when the exact source substring survives in
the translation with a unique, order-preserving mapping. Ambiguous, missing, overlapping, or
unsupported runs are deferred and reported; source offsets are never reused as translated offsets,
and bold/italic/font-family evidence remains diagnostic rather than synthesizing an unsafe face.

Each continuation is recorded as an exact occurrence-backed segment and validated after save in a
padded clip around its own target rectangle. Any unplaced text, fixed-layout overflow, or missing
saved segment prevents atomic publication. Source footnote separators are preserved; blank
continuation pages do not synthesize separators, running headers, or source page numbers.

Source-confirmed lists preserve `•`, `-`, `–`, `*`, numeric (`1.`, `2)`) and letter (`a)`, `A.`)
markers through the shared reflow path. Detection requires independently bounded source spans on
the same physical line; MuPDF marker/content lines in one source block can also supply that evidence.
Letter-dot markers additionally need prose content and an adjacent sequential list with matching
origins; name-shaped prefixes such as adjacent `A. Smith` / `B. Jones` remain semantic text,
including surname qualifiers (`A. Smith (editor)`) and particles (`A. van Smith`). Qualifiers
and name particles do not provide prose evidence for separating a letter marker. Lowercase
apostrophe components (`d'Angelo`, `l’Ouverture`) also remain semantic; an ambiguous neighboring
name cannot confirm a prose letter item. Geometrically proven letter prefixes retain their complete
source text even when list evidence is rejected.
Same-block source continuation lines join their item only with matching content origins, compatible
styles and close line geometry. Unresolved tails retain fallback instead of flowing a partial item.
A combined marker/content span or ambiguous geometry also keeps the existing fallback behavior.

The provider receives semantic content only. For a confirmed source item `1. Configure project`,
provider output `2. Настройте проект` becomes `1. Настройте проект`. Ordinary text and semantic
prefixes such as `A. Smith`, `1.5 mm` and `3.14` remain intact. Source marker and content origins
populate the existing list-layout contract: wrapped content stays at `content_x`, the marker stays
at `marker_x`, and continuation pages carry semantic text only. Saved validation rejects locally
missing, duplicate and continuation markers throughout each local placement, accounting for
legitimate marker tokens in planned semantic text. Explicit list-layout contract markers are
validated independently of automatic detection's vocabulary. Semantic inline styles remain
independent of marker offsets. Artifact versions and the global translation-cache revision are unchanged; translated
JSON retains the canonical marker for compatibility with fixed-layout fallback.

## Reflow architecture proof of concept

PDFTR-22 also provides an isolated historical body-text reflow demonstrator under
`scripts/reflow_poc/`. It consumes a completed schema 1.3 artifact, an explicit reviewed body region,
and explicit paragraph occurrence indexes; it emits a selectable diagnostic PDF plus a typed JSON
layout plan without changing the normal renderer.

```powershell
uv run python -m scripts.reflow_poc SOURCE.pdf TRANSLATED.json `
  --source-page 3 `
  --occurrences 38-41 `
  --allow-ambiguous-occurrences 38-41 `
  --region 67.35,53.78,378.32,463.23 `
  --output .\temp\pdftr22\reflow-poc.pdf `
  --plan .\temp\pdftr22\layout-plan.json `
  --debug-output .\temp\pdftr22\reflow-debug.pdf
```

This command is intentionally fail-closed and limited to reviewed single-column body prose. Normal
production rendering does not import it; see
[`docs/reflow-architecture.md`](docs/reflow-architecture.md) for the production boundary, evidence,
and unsupported layouts.

## Windows setup

From PowerShell, clone or open the repository and run:

```powershell
.\scripts\bootstrap.ps1
```

The script resolves the repository from its own location, so it can also be launched from another
working directory. It verifies Python 3.12 through uv, creates/synchronizes `.venv`, installs
pre-commit hooks, and runs a CLI smoke test.

The equivalent manual environment command is:

```powershell
uv sync --frozen --all-groups
```

## CLI

Basic diagnostics:

```powershell
uv run pdftranslate --version
uv run pdftranslate doctor
uv run python -m pdftranslate --version
```

Inspect a PDF as a Rich table or clean machine-readable JSON:

```powershell
uv run pdftranslate inspect .\manual.pdf
uv run pdftranslate inspect .\manual.pdf --json
```

Extract all pages or a validated one-based page selection:

```powershell
uv run pdftranslate extract .\manual.pdf --output .\manual.document.json
uv run pdftranslate extract .\manual.pdf --pages 1,3-5 --output .\selected.json
uv run pdftranslate extract .\manual.pdf --output .\manual.document.json --compact --overwrite
```

Extraction writes schema 1.2. It preserves typed physical blocks, source lines, span typography,
geometry, and original/normalized order, then adds logical paragraphs with reversible source-block
and line mappings. Conservative reconstruction uses page, column, alignment, gap, indentation,
font/style, width, punctuation, list/heading/caption/footnote, repeated-margin, and strong cross-page
signals. It never merges columns, headings into body text, or separate list items by default;
uncertain boundaries remain separate and are recorded as ambiguous diagnostics. Use
`--paragraph-reconstruction off` for one logical unit per physical block.

Document-level repeated-element analysis runs before paragraph reconstruction. It conservatively
classifies body blocks, sequential page numbers, running headers/footers, repeated boilerplate,
watermark candidates, and uncertain repeated content using position, normalized text, geometry,
font similarity, recurrence, parity, numeric sequences, and first/last-page exceptions. Every
source block remains in schema 1.2/1.3 JSON with confidence, a stable group ID, policy, ambiguity,
and reasons. Confirmed repeated elements form separate logical units and cannot merge into body
paragraphs or across pages.

The default `--repeated-elements auto` preserves page numbers, translates repeated headers and
legal text once per unique source text through the normal cache, skips translation/rendering of
watermark candidates without erasing the source PDF content, and preserves uncertain groups. The
classifier never selects the destructive `remove` policy automatically. Use
`--repeated-elements off` on root, batch, or extract commands to classify all blocks as body. Fine
tuning is available through `PDFTRANSLATE_REPEATED_*` settings; defaults are conservative and
short documents do not receive confirmed header/footer classifications.

Optional strict EN-to-RU terminology is supplied with `--glossary PATH` on the normal PDF,
`batch`, and direct `translate` workflows. Glossaries are versioned UTF-8 JSON and operate on
logical paragraphs, after repeated-element policy selection. Fixed translations and preserved
terms use collision-safe protected placeholders; final outputs fail closed if a preferred target
or placeholder is missing. The semantic glossary fingerprint participates in cache and resume
identity, and batch loads it once for all files:

```powershell
uv run pdftranslate .\manual.pdf --glossary .\docs\glossary.example.json
uv run pdftranslate batch .\manuals --glossary .\docs\glossary.example.json
```

See [docs/glossary.md](docs/glossary.md) for schema, precedence, matching, privacy, and limitations.
Independently of an optional glossary, translation conservatively preserves confidently identified
Latin or Greek quotation paragraphs verbatim. In otherwise translatable prose, Greek-script spans
and a small set of academic foreign terms stay outside model inference and are restored exactly.
Ambiguous Latin-script text remains on the normal translation path; an explicit glossary `translate` match takes
precedence over automatic whole-paragraph preservation. Preservation classifications and counts
are serialized into translation metadata and exposed in privacy-safe reports.

JSON is written as UTF-8 through an atomic sibling file; existing output and the source PDF are
protected unless the applicable explicit option is supplied.

Encrypted PDFs can be identified by `inspect`, but `extract` rejects password-required documents
because password input is outside this ticket. The standalone `extract` command does not run OCR;
use the root one-command workflow for scanned documents.

## One-command translation

Run the complete local pipeline with a PDF path as the first argument:

```powershell
uv run pdftranslate .\manual.pdf
uv run pdftranslate .\manual.pdf --output .\manual.ru.pdf
uv run pdftranslate .\manual.pdf --pages 1-20
uv run pdftranslate .\manual.pdf --device cuda
uv run pdftranslate .\manual.pdf --offline
uv run pdftranslate .\manual.pdf --resume
```

Without `--output`, the destination is a sibling named `<input-stem>.ru.pdf`. The root command
runs and reports six stages:

```text
1/6 Inspect
2/6 OCR
3/6 Extract
4/6 Translate
5/6 Render
6/6 Validate
```

Translation also reports completed blocks and translation-memory hits/misses. The existing
`inspect`, `extract`, `translate`, and `render` subcommands remain available for advanced or
diagnostic workflows.

Pipeline artifacts are stored outside the repository under the platform application cache:

```text
<cache>/workspaces/<run-id>/
  inspection.json
  ocr.pdf           # present when OCR ran
  ocr.log           # retained OCRmyPDF command/output
  ocr.txt           # OCR sidecar when produced
  extracted.json
  translated.json
  rendered.pdf
  manifest.json
  pipeline.log
  failure.json       # present after a failed or interrupted run
```

The stable run ID includes the immutable source fingerprint/path and behavior-affecting options.
`--resume` requires that exact identity, validates each completed artifact, reports reused stages,
and continues a translation checkpoint without repeating completed model translations. A changed
source or relevant option is rejected rather than consuming stale state. Normal translation-memory
cache reuse remains active without `--resume`.

Rendering targets the workspace candidate first. Validation reopens the candidate, copies it to a
temporary sibling of the requested destination, validates that copy, and only then atomically
publishes the final filename. Failures retain intermediate artifacts and detailed diagnostics but
never publish a partial PDF under the final name. Existing output is protected unless
`--overwrite` is explicit; `--overwrite` and `--resume` are mutually exclusive.

Preview the selected pages and expected work without constructing or downloading a model:

```powershell
uv run pdftranslate .\manual.pdf --pages 1-20 --dry-run
```

Dry-run reports page classifications, estimated blocks, the OCR decision/pages, backend, requested
device, output path, and expected stages without launching OCR or loading the translation model.

### OCR preprocessing

The root command defaults to conservative automatic OCR:

```powershell
uv run pdftranslate .\scanned.pdf --ocr auto
uv run pdftranslate .\mixed.pdf --ocr on --ocr-language eng
uv run pdftranslate .\text.pdf --ocr off
```

- `--ocr auto` runs only when selected pages are classified as scanned. Normal text PDFs skip the
  external process. Mixed pages retain their reliable existing text.
- `--ocr on` invokes OCRmyPDF for selected pages with `--mode skip`, so pages that already contain
  text are preserved.
- `--ocr off` never launches OCR and returns exit code 4 when selected scanned pages need it.
- `--ocr-force` requires `--ocr on` and deliberately uses OCRmyPDF force mode, which rasterizes
  selected pages. Use it only for known-bad text layers.
- `--ocr-deskew`, `--ocr-clean`, and `--ocr-rotate-pages` opt into corresponding conservative
  OCRmyPDF preprocessing. `--ocr-clean` also requires the external `unpaper` tool.

OCR writes only inside the deterministic run workspace and never overwrites the source. The result
is reopened, checked for page-count and page-geometry changes, reclassified, and warned about when
little or no text was recovered. Compatible `ocr.pdf` artifacts are reused by `--resume`; changing
the source or any OCR setting selects a different workspace.

`pdftranslate doctor` reports resolved OCRmyPDF, Tesseract, and Ghostscript paths and versions plus
English language-data availability. It provides guidance only and never installs system software.
On Windows, follow the [OCRmyPDF installation guide](https://ocrmypdf.readthedocs.io/en/latest/installation.html);
Tesseract can be installed with `winget install -e --id UB-Mannheim.TesseractOCR`, while Ghostscript
requires its own 64-bit installation when needed. Ensure `ocrmypdf`, `tesseract`, and the `eng`
trained-data file are discoverable before processing scans.

## Directory batch translation

Translate every selected PDF below a directory while keeping one NLLB model and one translation
memory open for the whole batch:

```powershell
uv run pdftranslate batch "J:\Books" --recursive
uv run pdftranslate batch .\manuals --output-dir .\manuals_ru --exclude "**/drafts/**"
uv run pdftranslate batch .\manuals --resume --ocr auto --device cuda
```

The available options are:

```text
--output-dir PATH
--recursive
--glob PATTERN
--exclude PATTERN          # repeatable
--overwrite
--resume
--continue-on-error
--ocr auto|on|off
--device auto|cpu|cuda
--report PATH
```

Without `--output-dir`, results are written under the sibling `<input-dir>_ru`. Relative
subdirectories are preserved and each output is named `<input-stem>.ru.pdf`, so equal filenames in
different source folders do not collide. Discovery is deterministically sorted, treats `.pdf`
case-insensitively, skips `.ru.pdf` files, and excludes a nested output tree. `--glob` and every
repeatable `--exclude` match both normalized relative paths and filenames case-insensitively.

Processing is sequential. The translation backend is initialized lazily at most once and the same
open SQLite translation cache is shared by every document. Each PDF still receives its own
source/options-derived workspace, so `--resume` validates and reuses stages independently.

The default failure policy is fail-fast: the failed PDF is recorded and remaining files are marked
as not processed. `--continue-on-error` instead attempts the remaining files. Any file failure
returns exit code 10 after the report is written; Ctrl+C remains exit code 130. Existing outputs are
reported as skipped unless `--overwrite` or `--resume` is explicit.

An atomic UTF-8 JSON report is always written to `<output-dir>/batch-report.json`, or to `--report`
when supplied. The terminal prints a human-readable summary plus successful output paths, skip
reasons, and errors. The versioned report contains start/finish time, roots, every discovered file,
success/failure/skip records, output and diagnostic paths, pages, OCR pages, translated blocks,
cache hits, elapsed time, and the final exit code.

### Exit codes

The root pipeline command uses centralized stable categories:

| Code | Category |
| ---: | --- |
| 0 | Success |
| 2 | Invalid arguments or incompatible resume state |
| 3 | Unsupported, missing, encrypted, empty, or corrupt PDF |
| 4 | OCR required |
| 5 | Local model unavailable |
| 6 | Translation failure |
| 7 | Rendering failure |
| 8 | Output validation/publication failure |
| 9 | OCR dependency, subprocess, timeout, or output-validation failure |
| 10 | One or more batch files failed |
| 11 | Requested diagnostic artifacts could not be published |
| 130 | Ctrl+C or simulated interruption |

## Local translation

Translate extracted JSON while retaining every original block:

```powershell
uv run pdftranslate translate .\manual.document.json `
  --output .\manual.ru.json `
  --from en `
  --to ru `
  --backend nllb `
  --device auto
```

The default backend is `facebook/nllb-200-distilled-600M` with `eng_Latn` to `rus_Cyrl`.
The model loads once per process. `--device auto` uses CUDA only after availability and allocation
probes succeed; `--device cpu` forces CPU, while explicit `--device cuda` fails clearly when CUDA
is unavailable. Automatic CUDA out-of-memory recovery is bounded and can fall back to CPU once;
explicit CUDA failures are not hidden.

Useful runtime options:

```text
--model
--device auto|cpu|cuda
--batch-size
--max-input-tokens
--cache-dir
--overwrite
--offline
--resume
--ocr auto|on|off
--ocr-language eng
--ocr-deskew
--ocr-clean
--ocr-rotate-pages
--ocr-force
--repeated-elements auto|off
```

Normal mode may download missing model files and reports this before loading. `--offline` resolves
the model to an existing local directory or Hugging Face cache snapshot before importing
Transformers, loads configuration/tokenizer/model with `local_files_only=True`, and scopes the Hub
offline environment to component loading. It never falls back to the remote model ID and fails with
the checked cache path and recovery guidance when local files are absent. The upstream model repository was
approximately 2.5 GB when this documentation was written; cache size, RAM, and VRAM requirements
vary by revision and precision. The [NLLB model card](https://huggingface.co/facebook/nllb-200-distilled-600M) identifies
the checkpoint as CC-BY-NC-4.0, so
confirm that license fits the intended use.

The cache root defaults to the platform application cache and can be changed with
`PDFTRANSLATE_CACHE_DIR` or `--cache-dir`. Model files live below `models`; translation memory is a
SQLite database in the same root. Default runtime data is not written into the repository.

The translator skips whitespace, standalone page numbers, obvious code, measurement-only values,
and numeric identifiers. Embedded URLs, email addresses, file paths, measurements, and identifiers
are protected and must be restored exactly. Long blocks split at paragraph/sentence boundaries
where possible; forced splits produce warnings instead of silent truncation.

New extracted output uses schema 1.2 and translated output uses schema 1.3. Translation runs once
per logical paragraph while raw blocks and mapping evidence remain immutable. Rendering redacts
every mapped source fragment and inserts the translated paragraph once on its anchor page, including
cross-page continuations without duplicate insertion. Legacy schema 1.0/1.1 JSON remains readable.
Atomic checkpoints validate the source fingerprint, paragraph structure, backend, model, language
pair, batch size, and token limit.

## Translation quality benchmark

Run the repository-safe 61-sample English-to-Russian benchmark without extracting or rendering a
PDF:

```powershell
uv run pdftranslate benchmark-translation `
  .\benchmarks\translation-en-ru-v1.json `
  --output .\temp\benchmark\nllb.json `
  --device cpu `
  --offline
```

Use `--baseline <prior.json>` to compare sample status and finding identities with an earlier run.
The JSON and sibling Markdown report record the application version, commit, dataset version,
backend, model/tokenizer identity, effective device, segmentation settings, elapsed time, and
in-run exact-source cache hits/misses. One translator instance is reused for the whole dataset.
The in-run cache stores only model-execution artifacts; protected-token declarations, human scores,
historical traces, findings, and status are recalculated independently for every sample, including
cache hits. Normal tests substitute a fake translator and never download NLLB.

The versioned dataset contains prose, technical text, headings, captions, lists, warnings, labels,
long sentences, abbreviations, units, URLs, paths, commands, code, product names, repeated terms,
hyphenated breaks, and multi-sentence paragraphs. It also retains the PDFTR-8 `1900-1` protected-
token failure and page-7 number/date corruption with `F￾` as explicit historical stage traces.
Findings identify `current_run` versus `historical_trace`; only current-run errors determine the
sample pass/fail status, so preserved defect evidence cannot masquerade as a new regression.

Findings are attributed to one of six boundaries:

- `extraction`: source and extracted snapshots differ;
- `segmentation`: forced or missing/duplicated segment evidence;
- `protected_token`: declared values or internal placeholders are damaged;
- `model`: inference output loses numeric/structural content, remains untranslated, or contains
  suspicious characters;
- `terminology`: explicitly low human terminology score;
- `rendering`: rendered text differs from the clean translated-text snapshot.

This attribution is diagnostic: a final-PDF symptom is not automatically a model defect. PDFTR-9
does not change PDF appearance or rendering behavior. Automated checks cover structural integrity,
not semantic adequacy or fluency. Optional human scores use a documented 1–5 scale: 1 unacceptable,
2 major problems, 3 usable with edits, 4 good, and 5 excellent.

## Render translated PDFs

Render a completed schema 1.1 or schema 1.3 translation into a new PDF:

```powershell
uv run pdftranslate render .\manual.pdf .\manual.ru.json `
  --output .\manual.ru.pdf `
  --allow-expand
```

The renderer validates the source SHA-256 and file size, page count and dimensions, source page
indexes, block IDs, original text, bounding boxes, completed translation state, and translated
text before publication. `--force-source-mismatch` bypasses only the size/fingerprint comparison;
layout and block validation still run. The source PDF is never overwritten. Output is saved to a
temporary sibling, reopened and checked, then atomically published.

Use `--font PATH` to select a TrueType or OpenType font. Without it, PDFTranslate searches Windows
fonts (Segoe UI, Arial, then Calibri) and common DejaVu/Liberation locations on Linux. The selected
font is loaded before rendering and every required Cyrillic glyph is validated. No font files are
bundled in this repository.

Layout options are:

```text
--min-font-size
--font-size-step
--line-height
--redaction-padding
--allow-expand
--debug-layout
--force-source-mismatch
--overwrite
```

Text is wrapped inside the extracted block rectangle and reduced in deterministic steps. Optional
expansion stops at the page edge or the next horizontally overlapping text block. For schema 1.3,
every logical paragraph receives an explicit terminal state. Unresolved required overflow fails
the render before any incomplete PDF is published; the error identifies each paragraph occurrence
and its layout evidence. `PRESERVE`, `SKIP`, and `REMOVE` units are accounted for by policy rather
than treated as missing translations. `--debug-layout` writes `<output-stem>.debug.pdf` after a
successful render; a completeness failure instead writes `<output-stem>.failed-render.pdf` with
the source and planned rectangles when debug mode is enabled.

Original text regions are redacted while PyMuPDF is instructed to retain overlapping image and
vector objects. A median color sampled from the source rectangle is used instead of assuming a
white page. This is conservative: complex gradients, patterned backgrounds, text intersecting
line art, and unusually dense layouts may still require manual review. OCR and text inside images
are not rendered by this stage.

## Page classification

Each page is classified as `text`, `scanned`, `mixed`, or `empty`. The deterministic defaults are:

| Environment setting | Default | Meaning |
| --- | ---: | --- |
| `PDFTRANSLATE_CLASSIFICATION_MIN_TEXT_CHARACTERS` | `20` | Minimum meaningful extracted characters |
| `PDFTRANSLATE_CLASSIFICATION_MAX_INCIDENTAL_TEXT_BLOCKS` | `1` | Maximum block count still considered incidental |
| `PDFTRANSLATE_CLASSIFICATION_MIXED_IMAGE_AREA_RATIO` | `0.15` | Image coverage that makes a meaningful-text page mixed |
| `PDFTRANSLATE_CLASSIFICATION_SCANNED_IMAGE_AREA_RATIO` | `0.65` | Expected coverage for a strong scanned-page signal |
| `PDFTRANSLATE_PARAGRAPH_RECONSTRUCTION_MODE` | `conservative` | `conservative` reconstruction or physical-block `off` mode |
| `PDFTRANSLATE_PARAGRAPH_LEFT_ALIGNMENT_TOLERANCE` | `8.0` | Maximum aligned-left difference in PDF points |
| `PDFTRANSLATE_PARAGRAPH_INDENTATION_TOLERANCE` | `14.0` | Maximum continuation indentation difference |
| `PDFTRANSLATE_PARAGRAPH_MAX_VERTICAL_GAP_RATIO` | `0.75` | Maximum line gap relative to line height |
| `PDFTRANSLATE_PARAGRAPH_MIN_WIDTH_RATIO` | `0.72` | Similar-width evidence threshold |
| `PDFTRANSLATE_PARAGRAPH_COLUMN_GUTTER_RATIO` | `0.08` | Minimum two-column gutter ratio |
| `PDFTRANSLATE_PARAGRAPH_CROSS_PAGE_EDGE_RATIO` | `0.18` | Top/bottom region required for cross-page merging |

Image coverage is the sum of actual image-placement bounding-box areas divided by visible page
area, capped at 1. Image-only pages remain `scanned` below the strong threshold and receive a
warning. Settings use the standard `PDFTRANSLATE_` environment prefix.

## Reading-order limitation

Extraction preserves PyMuPDF's `sort=False` block order, removes empty blocks, normalizes line
whitespace, and exposes both original and normalized indexes. It deliberately does not merge or
geometrically reorder unrelated columns. Complex multi-column reading order may therefore need a
later, document-specific stage.

## Real-PDF validation

Run the opt-in, source-preserving compatibility harness against a private local corpus:

```powershell
.\scripts\validate-real-pdfs.ps1 `
  -CorpusRoot "J:\PdfTestCorpus" `
  -OutputRoot "J:\PdfValidationResults" `
  -DryRun
```

Dry-run classifies pages, plans OCR, hashes every source before and after inspection, and generates
the complete JSON/Markdown report structure without loading a model or invoking OCR. Remove
`-DryRun` only for an explicit real-model run; use `-Offline` when the required model is already
cached. Manifest categories and `-Subset` support text-heavy books, technical manuals, columns,
tables, images/captions, scanned/mixed files, long PDFs, and paths with spaces or Cyrillic text.

Results include `validation-summary.json`, `validation-summary.md`, per-document JSON, copied logs,
translated outputs, and a PDF-XChange manual-review template. Source SHA-256 and size are verified
after every success or failure, stage timing and cache/resume evidence are recorded, and failures
become severity/stage/root-cause/follow-up defect entries. See
[`docs/real-pdf-validation.md`](docs/real-pdf-validation.md) for the private-corpus manifest,
manual checklist, opt-in OCR/model workflow, and reproduction commands.

A title fragment or intentional blank-page label is not positive translation evidence. A real-model
proof must include at least one coherent source paragraph and verify the rendered Russian text,
absence of the source English paragraph, placement, search, selection, and copy behavior.

## Translation diagnostics

Request structured diagnostics on the normal end-to-end command:

```powershell
uv run pdftranslate input.pdf --report --report-format both --report-dir .\reports --debug-layout
```

Each execution reserves a unique `run-<UTC timestamp>-<workspace prefix>-<execution id>` directory
below `--report-dir` (or the output PDF directory), then writes `translation-report.json`, a
self-contained `translation-report.html`, and optionally `debug-layout.pdf` inside it. Existing
diagnostic files are never replaced. Reports contain run/page/block IDs, classifications, bounding
boxes, cache and
OCR status, font fitting, expansion/overflow, validation findings, elapsed time, file sizes, and
measurable Python peak memory. Fresh translation stages record exact per-block segmentation counts
and cache status. Repeated-element evidence adds document counts plus per-block classification,
confidence, group ID, policy, and ambiguity; ambiguous groups produce the stable
`REPEATED_ELEMENT_AMBIGUOUS` finding. Reused historical stages and unavailable VRAM remain
`null`/`unknown`, never guessed.
The report also records the renderer's selected font and promotes renderer warnings to stable
`RENDER_WARNING` findings. The HTML summary additionally surfaces the document inline-style totals
— candidate, applied, deferred, and applied-character counts — directly from `ReportSummary`, so
mixed-style evidence is readable without opening the embedded JSON.

Source and translated text are excluded by default. Use `--include-report-text` only for explicit
local debugging; it requires `--report`. The HTML file embeds its CSS and uses no network assets.
Failure reports are written when the workspace was initialized and reporting remains possible,
without replacing the primary pipeline error. If success-report or debug-layout publication fails
after the normal PDF was validated and published, the command returns exit code 11 and explicitly
reports that the translated PDF remains available; it never relabels that PDF as invalid.

## Quality and tests

Run the complete local quality gate:

```powershell
.\scripts\check.ps1
```

Or run individual checks:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

The suite generates small PDF fixtures at runtime for extraction, translation, rendering,
image/vector preservation, fitting, overflow, source mismatch, debug layout, Unicode paths, and batch discovery/orchestration/reporting.
Translation tests use deterministic fake backends and never load or download NLLB. No binary
fixtures are committed.

Run the coverage-oriented test helper:

```powershell
.\scripts\test.ps1
```

## Roadmap

Future work is tracked in the PDFTranslate YouTrack project.

Large models, generated PDFs, extracted document JSON, and local model caches must remain outside
version control.
