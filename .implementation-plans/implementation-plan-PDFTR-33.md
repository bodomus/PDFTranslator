# PDFTR-33 implementation plan

## 1. Contract and documentation

- Add concise two-agent routing and the PDFTR-33 bootstrap exception to `AGENTS.md` and
  `.codex/PRE_TICKET_WORKFLOW.md`.
- Add a dedicated skill with focused implementer, reviewer, and handoff contracts.
- Document recovery, human merge ownership, and the future-orchestrator boundary.

## 2. State model

- Define strict typed values for manifest state, active role, verdict, handoff sections, findings,
  and the maximum of two review rounds.
- Persist per-ticket state only below `.agent-cycle/<TICKET>/` and ignore the coordination root in Git.

## 3. Git fact collection

- Derive repository root, current branch, HEAD, merge-base, and porcelain status with read-only Git.
- Support optional remote-tip comparison without fetching or making ordinary status network-dependent.

## 4. Transition validator

- Implement initialization, implementer begin/handoff, reviewer begin/record, manual stop, and status.
- Enforce active-role exclusivity, clean-tree gates, branch/HEAD binding, two-round cap, stale review
  invalidation, exact repeated-finding stop, and fail-closed atomic state updates.

## 5. Review artifact and three-section handoff

- Store one strict handoff document with `system`, `implementer`, and `reviewer` sections.
- Keep system-derived facts in the manifest and mirror only validated values into the system section.
- Accept reviewer results from an explicit JSON file and reject wrong ticket, SHA, verdict, shape, or
  round; never let either agent overwrite another section directly.

## 6. Tests

- Use isolated repository-local Git fixtures.
- Cover ticket/path safety, initialization, corrupt JSON, dirty handoff, active-role exclusion,
  exact-SHA review, stale PASS after new commit, invalid verdict, round cap, repeated findings,
  review-time repository mutation, optional remote-tip verification, CLI failure exits, and rejection
  of the legacy product-named section and active-agent values.

## 7. Wiki and user documentation

- Update README, CHANGELOG, the durable development-workflow Wiki page, and Wiki log.
- Run Wiki lint after the Wiki changes.

## 8. Manual pilot and completion

- Exercise an isolated nominal init -> handoff -> exact-SHA PASS cycle.
- Exercise CHANGES_REQUIRED -> second review -> PASSED/STOPPED behavior in disposable fixtures.
- Run focused tests, full pytest, Wiki lint, `scripts/check.ps1`, CRG post-change analysis, and
  `git diff --check`.
- Produce the implementation report and review file, then attach the review to YouTrack and update
  the ticket state when complete.
