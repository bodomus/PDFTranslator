# Agent-cycle handoff contract

Schema version `1.0` uses `.agent-cycle/<TICKET>/`:

```text
manifest.json       system-owned authoritative state
handoff.json        validated shared/deepseek/codex sections
review-1.json       immutable normalized Codex result, when recorded
review-2.json       immutable normalized Codex result, when recorded
```

The entire `.agent-cycle/` root is local runtime state and is ignored by Git.

## Ownership

- `shared`: validator-written projection of ticket, branch, merge base, current HEAD, review round,
  and state. Agents cannot supply this section.
- `deepseek`: implementation claims supplied by DeepSeek and accepted only during `handoff`.
- `codex`: SHA-bound review result supplied by Codex and accepted only during `record-review`.

The validator writes `handoff.json` atomically after validating the role-specific input. An agent
must never replace the whole handoff or edit another owner's section.

## DeepSeek input

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

## Codex input

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

Do not delete or rewrite immutable review artifacts as recovery. Human final review and merge remain
outside the state machine.
