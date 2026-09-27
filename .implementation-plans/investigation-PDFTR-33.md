# PDFTR-33 investigation

## Baseline and scope

- Workflow level: 2 (durable development-workflow and cross-platform tooling change).
- Task branch: `codex/PDFTR-33-two-agent-ticket-handoff-contract`.
- Actual base and starting HEAD: `35c8f698de1370484af8fc73f77518c104efb1e0`.
- Pre-existing user change: deleted `temp/.agents.zip`; it is unrelated and remains untouched.
- PDF extraction, translation, rendering, OCR, cache, schemas, and production CLI are unaffected.
- PDFTR-33 is a documented bootstrap exception: Codex may implement this ticket because the
  coordination contract does not exist yet. After completion, ordinary agent-cycle tickets use
  DeepSeek as the only project-file writer and Codex as an exact-SHA, read-only reviewer.

## Source-verified findings

1. Repository implementation and review are currently governed by `AGENTS.md`,
   `.codex/PRE_TICKET_WORKFLOW.md`, `knowledge/AGENTS.md`, `scripts/check.ps1`, and ticket-local
   instructions. None defines machine-readable inter-agent ownership or SHA-bound review state.
2. Durable coordination belongs in one dedicated skill plus a small routing section in `AGENTS.md`.
   Repository investigation remains in `PRE_TICKET_WORKFLOW`; duplicating it would create drift.
3. Existing standalone scripts use `argparse` and direct `main(argv)` entry points. A standard-library
   script is the smallest cross-platform fit and keeps this workflow outside the production Typer CLI.
4. The smallest safe cycle consists of `.agent-cycle/<TICKET>/manifest.json` and
   `.agent-cycle/<TICKET>/handoff.json`, with optional immutable reviewer input files. The manifest
   owns derived Git/runtime state; the handoff has exactly three ownership sections: `shared`,
   `deepseek`, and `codex`.
5. System-derived facts are repository root, branch, HEAD, merge-base, tracked/untracked clean state,
   review round, workflow state, active role, and the reviewed-SHA validity decision. Agent prose is
   never authoritative for those values.
6. Safe local Git reads are `git rev-parse --show-toplevel`, `git branch --show-current`,
   `git rev-parse HEAD`, `git merge-base master HEAD`, and `git status --porcelain`. Optional push
   verification compares local HEAD with `refs/remotes/<remote>/<branch>`; it is opt-in because normal
   status must work offline and must not fetch.
7. Required transitions are NEW -> IMPLEMENTING -> READY_FOR_REVIEW -> REVIEWING, then PASS -> PASSED,
   BLOCKED -> BLOCKED, or CHANGES_REQUIRED -> IMPLEMENTING for round one and STOPPED for round two.
8. `active_agent` is `null`, `deepseek`, or `codex`. A begin action fails if another role is active.
9. A review applies only when `codex.reviewed_sha` equals the system-derived HEAD captured for that
   review. A later HEAD causes status validation to report the prior result as stale, never PASS.
10. Repeated findings use the exact tuple `(id, file, symbol)` after normalizing absent optional
    values to empty strings. An unresolved key repeated in consecutive rounds stops for human review.
11. Standard-library dataclasses plus strict, explicit key/type validation are sufficient. They avoid
    coupling this repository tool to application models while still rejecting unknown or missing fields.
12. Git behavior is tested in isolated repositories created below repository-local `temp/`; tests do
    not mutate the developer checkout and require no network.
13. The durable Wiki change fits `knowledge/wiki/workflows/development-workflow.md`; no ticket-specific
    Wiki page is needed. `knowledge/wiki/log.md` records the change.
14. Bootstrap limitation: PDFTR-33 cannot begin under tooling that it creates. Its final manual pilot
    can exercise initialized state and synthetic exact-SHA reviews, but the initial implementation
    phase is recorded as the explicit exception rather than fabricated as self-hosted.
15. A future orchestrator needs stable JSON sections, deterministic transitions, non-zero fail-closed
    exits, and machine-readable status. It does not need process spawning, automatic prompts, fetching,
    retries, merging, or agent-product APIs in this ticket.

## Graph evidence and source verification

- Existing Graphify data connected repository instructions, the development workflow, Wiki tooling,
  and direct script tests; current source confirmed `argparse`, importable functions, and the quality gate.
- CRG was updated to HEAD (`1620` nodes, `14510` edges, low pre-change risk). It has limited file lookup
  coverage for the standalone Wiki scripts, so source inspection remains authoritative.
- This change is isolated from production pipeline flows. Expected blast radius is repository workflow
  docs, the new standalone validator, its tests, and Wiki metadata only.

## Safety conclusions

- Ticket IDs accept only `[A-Z][A-Z0-9]*-[1-9][0-9]*`; path separators, traversal, controls, absolute
  paths, empty strings, and zero identifiers fail before path construction.
- All coordination files resolve below the repository `.agent-cycle` root.
- State writes use a same-directory temporary file and atomic replacement; corrupt or unexpected JSON
  is never discarded or guessed back into validity.
- No destructive Git command, network call, model download, PDF mutation, or new dependency is required.
