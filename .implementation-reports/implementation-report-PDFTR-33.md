# PDFTR-33 implementation report

## Outcome

Implemented a repository-local, fail-closed contract for strictly sequential implementation and
exact-SHA, read-only review. The tool records workflow state only; it
does not launch agents, call model APIs, fetch, retry, merge, create pull requests, or supervise
processes.

PDFTR-33 is explicitly documented as the bootstrap exception authorized by the user: Codex
implemented the infrastructure before its post-ticket role controls existed. For ordinary later
agent-cycle tickets, the implementer is the only project-file writer and the reviewer is read-only.
DeepSeek/Codex may be assigned by orchestration metadata, but product names are not validator roles.

## Contract and state

- `.agent-cycle/` is ignored persistent local coordination state, distinct from disposable `temp/`.
- Each ticket has strict `manifest.json` authoritative state and `handoff.json` with exactly three
  ownership sections: `system`, `implementer`, and `reviewer`.
- `system` is derived by the validator; the two agents provide only their role-specific inputs.
- Normalized `review-1.json` and `review-2.json` artifacts are immutable once recorded.
- Ticket IDs, JSON fields, schema version, enum values, Git SHAs, review rounds, findings, and paths
  are validated explicitly; unknown/missing fields and corrupt state fail closed.
- Legacy product-named handoff sections and `active_agent` values are rejected explicitly.

## Validator behavior

`scripts/agent_cycle.py` provides:

- `init`;
- `begin-implementation`;
- `handoff`;
- `begin-review --sha`;
- `record-review --file`;
- `status [--json] [--verify-remote REMOTE]`;
- `stop --reason`.

It derives repository root, branch, HEAD, merge-base, root-commit fingerprint, and porcelain status
through read-only Git. It enforces the expected branch, clean transition gates, exact review SHA,
one active role, no repository mutation during review, a new implementation SHA after requested
changes, stale-review invalidation, exact repeated finding keys, and exactly two automated review
rounds. Optional remote verification compares an existing remote-tracking ref and never fetches.

## Documentation

- Added the concise root routing rules and minimal PRE_TICKET coordination overlay.
- Added `.agents/skills/two-agent-ticket-workflow/` with progressive role and handoff contracts.
- Updated README, CHANGELOG, ProjectWiki development workflow, and Wiki log.
- Documented conservative recovery and human ownership of final review/merge.

## Tests and validation

- Focused validator tests: `29 passed`.
- New deterministic coverage includes safe ticket IDs, isolated initialization, strict three-section
  handoff, dirty-tree rejection, exact SHA binding, stale PASS after a new commit, two-round stop,
  repeated findings, review-time mutation, invalid verdict, active-role exclusion, corrupt JSON,
  new-SHA requirement, wrong repository root, manual commit between phases, local remote-tip
  verification, and non-zero CLI failure.
- Full pytest: `385 passed, 1 skipped`; coverage `89.10%`.
- `scripts/check.ps1`: passed (Wiki lint, Ruff format/check, mypy, full pytest).
- Standalone strict mypy for the new script: passed.
- Skill `quick_validate.py`: passed.
- ProjectWiki lint: `15` pages, `107` links, `0` errors, `0` warnings.
- `git diff --check`: passed.

The first sandboxed full pytest attempts could not access the configured global `A:\Temp`; no test
body failure caused those results. The authoritative rerun outside that sandbox restriction and
the final `scripts/check.ps1` run both passed completely.

## Manual pilot evidence and bootstrap limits

The ticket could not initialize its own cycle before the validator existed and before its changes
were committed cleanly. That bootstrap phase is not represented as a fabricated self-hosted run.

The repository-local isolated Git fixtures exercised the complete nominal sequence through exact-SHA
`PASS`, verified that a later commit makes that PASS stale, and separately exercised round-one
`CHANGES_REQUIRED` followed by a new implementation SHA and round-two `PASSED`/`STOPPED` behavior.
They also exercised exact repeated-finding stop and immutable review artifacts. These fixtures use
real Git commands, no developer-checkout mutation, no network, and no LLM/model call.

## Scope and risk

- No production PDFTranslate CLI, PDF processing, translation, rendering, OCR, cache, or serialized
  document contract changed.
- No dependency or lockfile changed.
- Windows and Linux behavior uses Python 3.12 standard-library APIs plus Git; CI needs no model or
  external service.
- The pre-existing deletion `temp/.agents.zip` was preserved and is not part of PDFTR-33.

## Final status

READY FOR REVIEW. A human still owns final review and merge.
