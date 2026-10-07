# Agent-cycle handoff contract

Schema version `1.0` uses `.agent-cycle/<TICKET>/`:

```text
manifest.json       system-owned authoritative state
handoff.json        validated system/implementer/reviewer sections
review-1.json       immutable normalized reviewer result, when recorded
review-2.json       immutable normalized reviewer result, when recorded
```

The entire `.agent-cycle/` root is local runtime state and is ignored by Git.

`implementer-progress.log` and `reviewer-progress.log` are append-only diagnostic evidence, not
schema fields or authoritative state. The runner supplies each role's fixed path and
`progress_append` capability, preserves history across exits/resume/recovery, and appends UTC
attempt/round boundaries. Journals never replace handoff claims or SHA-bound review JSON.

## Ownership

- `system`: validator-written projection of ticket, branch, merge base, current HEAD, review round,
  and state. Agents cannot supply this section.
- `implementer`: implementation claims accepted only during `handoff`.
- `reviewer`: SHA-bound review result accepted only during `record-review`.

The complete top-level shape is exactly
`{"schema_version":"1.0","system":{},"implementer":{},"reviewer":{}}`, with the role sections
containing the fields documented below when populated. Product names may appear only as external
assignment metadata; they are not schema keys, enum values, transitions, or ownership domains.

The validator writes `handoff.json` atomically after validating the role-specific input. An agent
must never replace the whole handoff or edit another owner's section.

## Implementer input

```json
{
  "schema_version": "1.0",
  "ticket": "PDFTR-34",
  "implementation_attempt": 1,
  "status": "COMPLETE",
  "implementation_report": ".implementation-reports/implementation-report-PDFTR-34.md",
  "focused_tests": "PASS",
  "full_tests": "PASS",
  "check_ps1": "PASS",
  "known_limitations": [],
  "notes": []
}
```

Check values are `PASS`, `FAIL`, or `NOT_RUN`. Unknown and missing fields fail closed.

## Reviewer input

```json
{
  "schema_version": "1.0",
  "ticket": "PDFTR-34",
  "review_round": 1,
  "reviewed_sha": "0123456789abcdef0123456789abcdef01234567",
  "verdict": "CHANGES_REQUIRED",
  "findings": [
    {
      "id": "R1",
      "severity": "HIGH",
      "file": "src/example.py",
      "symbol": "example",
      "problem": "Concrete defect",
      "required_fix": "Concrete correction",
      "regression_test": "Required regression coverage"
    }
  ],
  "blocked_reason": null
}
```

Severity is `CRITICAL`, `HIGH`, `MEDIUM`, or `LOW` and never decides merge automatically. `PASS`
requires an empty findings list; `CHANGES_REQUIRED` requires at least one finding; `BLOCKED`
requires `blocked_reason`. Exact repeated findings use `(id, file, symbol)`.

## Recovery

- Agent crash: use `status`; do not guess the missing transition.
- Invalid input: correct the role-owned input and retry; authoritative files remain unchanged.
- Manual commit or branch change: return to the recorded branch and explicitly re-enter the valid
  phase; do not edit manifest JSON by hand.
- Deleted ticket directory: initialize a new cycle only after a human confirms the prior local state
  is intentionally abandoned.
- Corrupt authoritative JSON: stop for human inspection. The validator never recreates it silently.
- Usage or external budget stop: `stop <TICKET> --reason usage_limit` (or another explicit reason).

- Human-approved exhausted-review recovery: an operator may run `agent_cycle.py reopen <TICKET>
  --reason <APPROVAL>` or `pi_ticket_cycle.py <TICKET> --recover --reason <APPROVAL>`. Agents must
  not self-approve recovery. Only STOPPED after exhausted reviews with repeated_finding or
  review_round_limit is eligible. Clean tree, recorded branch and unchanged manifest HEAD are
  required. HUMAN_APPROVED_REWORK resumes implementation with the next cumulative attempt.
- The optional strict manifest `human_recoveries` list contains exactly `reason`, `stop_reason`,
  `review_round`, `reviewed_sha`, `implementation_attempt`, and `previous_handoff` for each approval.
  Legacy manifests without this field remain supported. Each entry authorizes only one new review;
  MAX_REVIEW_ROUNDS stays two. New reviews use cumulative immutable filenames (review-3.json etc.).
  Accepted handoffs are retained as immutable implementation-<attempt>.json snapshots; legacy
  last handoffs are also captured in the approval audit. No historical reviews are superseded or
  considered valid for the new SHA. Recovery still requires a new implementation SHA.

- Separate operational retry: `pi_ticket_cycle.py <TICKET> --recover-operational --reason <APPROVAL>`
  or `agent_cycle.py retry-operational <TICKET> --reason <APPROVAL>` is human/operator-only.
  Eligibility requires STOPPED with structured operational class/recognized code, round zero,
  no accepted implementation or review, no active agent, clean tree, unchanged exact HEAD and
  existing ticket/repository/branch bindings. Unknown/safety failures and legacy text-only
  operational stops cannot be inferred from free text. No WIP cleanup or reviewer powers are added.
- Optional strict manifest fields: positive integer `implementation_attempt`,
  `stop_class` (operational, review_exhausted, safety, unknown),
  `stop_code` (stable string or null), and `operational_retries` (list). Each approval entry has
  exactly `type=operational_retry`, `reason`, `previous_stop_code`, `previous_stop_reason`,
  `head_sha`, `branch`, `review_round=0`, and `implementation_attempt`. Attempts are
  `review_round + 1 + len(operational_retries)` during implementation. Existing accepted handoffs
  retain their actual attempt. Review grants remain controlled only by `human_recoveries`.
- `HUMAN_APPROVED_OPERATIONAL_RETRY` resumes the approved attempt via a normal runner invocation;
  duplicate approval rejects. Atomic manifest persistence is the approval commit point; a crash
  before its blank handoff projection is refreshed is safely completed in memory during loading
  only for the exact previous blank projection, including nested JSON types. Boolean/float rounds
  cannot replace integer zero. This pre-first-handoff state authorizes no numbered accepted
  implementation/review snapshots: unexpected snapshots reject before normalization or any resume
  mutation. Later review/rework history and failed-attempt diagnostics remain preserved.
  Three retries maximum; further operational failure records `operational_retry_limit`.
- Runner ownership is serialized by an OS-held `.agent-cycle/<TICKET>.runner.lock`, automatically
  released on process death. An atomic `implementer-launch-attempt-<N>.json` binds an operational
  approval, repository fingerprint, ticket, branch, exact HEAD and attempt to `prepared`/`launching`.
  A matching `prepared` record permits normal resume of pre-launch IMPLEMENTING only under the
  exclusive lock and clean unchanged Git facts; no new approval or begin transition is performed.
  If begin crashed between replacing manifest and handoff, the runner validates identity, approval,
  strict prepared marker and absence of accepted artifacts before atomically completing only the
  exact blank prior HUMAN_APPROVED_OPERATIONAL_RETRY projection. Nonblank/other contradictory
  handoffs reject before mutation. Ordinary validator loading remains strict.
  The runner persists `launching` before entering the executor. From that fence onward child
  ownership is uncertain after a crash and active-phase resume rejects. Missing, corrupt or
  contradictory records, legacy active phases and competing runners fail closed. These files are
  runner-owned; neither role may mutate them. Historical attempt markers are retained.
- Retry preserves cumulative implementer logs, append-only progress, rejected/partial input as
  `implementer-attempt-<previous>.json`, and previous report as
  `implementation-report-attempt-<previous>.md`. Nothing silently truncates old diagnostics.
  Legacy exhausted-review recovery is classified from validated immutable reviews, not stop text.

- Separate clean pre-handoff recovery: operator-only `agent_cycle.py retry-pre-handoff <TICKET>`
  approves `HUMAN_APPROVED_PRE_HANDOFF_RETRY`; normal runner invocation dispatches that attempt.
  STOPPED/round-zero/no accepted handoff or review, clean unchanged HEAD, branch/repository bindings,
  no active owner, strict exited launch evidence and no pending/uncertain tracking mutation are
  independently checked. Stop prose does not grant authority; legacy unknown stops lacking positive
  process evidence reject. Safety-class stops and exhausted operational limits cannot use this path.
- Optional strict `pre_handoff_retries` records contain `retry_kind=pre_handoff`,
  `approved_by=human`, UTC `approved_at`, `implementation_attempt`, `previous_attempt_id`,
  `source_head`, `branch`, `repository_identity`, previous stop class/code/reason and `evidence`
  filename-to-SHA256 bindings. Prior top-level execution artifacts are exclusively snapshotted into
  `attempts/<previous_attempt_id>/`; history, blank prior handoff and exited marker are validated on
  every load. Missing/changed history or inconsistent mixed retry numbering fails closed.
  Attempt numbering includes both retry histories; review authorization remains unchanged.
- All implementer executions now persist prepared/launching/exited markers. Exited is written only
  after owned process-tree cleanup returns. Approval shares the OS ticket lock with runner dispatch.
  The existing exact blank-projection and prepared-marker crash repair applies to either approved
  retry kind. Launching uncertainty never permits active-phase redispatch; repeated approvals reject.
  Tracking successful mutation keys/identity are retained, and uncertainty is rechecked at dispatch.
  Approval metadata and historical artifacts are harness-owned, never agent handoff fields.

- Separate trusted independent continuation (PDFTR-52) consumes only the protected PDFTR-51
  publication intent and exact PDFTR-49 result/receipt. It does not add agent input fields. A durable
  `independent-continuations.json` authorization precedes immutable structured findings preparation,
  `POLICY_APPROVED_CONTINUATION` projection and existing runner launch fences. One generation may
  authorize one attempt; two authorizations maximum per ticket lineage. The optional strict manifest
  `independent_continuations` list binds continuation ID, source generation/round/head/base and findings
  digest. Cumulative attempts/review filenames and retry histories are retained; a correction gets the
  normal two internal reviews. Ordinary runner commands cannot dispatch the policy-approved state
  without the protected parent hook. Positive prelaunch preparation may resume the same identity;
  launch uncertainty requires human inspection. See `docs/independent-review.md` for deployment,
  rejection codes and restart constraints. Neither role may mutate continuation authority or findings.

Do not delete or rewrite immutable review artifacts as recovery. Human final review and merge remain
outside the state machine.
