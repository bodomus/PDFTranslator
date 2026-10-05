# PDFTR-43 investigation and implementation plan

## Investigation (Level 2)
Baseline: clean tree, ticket branch, Python 3.12.10, uv 0.5.26. Existing runner owns process sequencing; agent_cycle owns strict SHA-bound state. No external tracking exists. Graphify query `pi_ticket_cycle run_cycle` located runner/validator/tests, verified in source. CRG `update --brief` completed indexing but console failed cp1251 Unicode output; retry with UTF-8. Context7 is unavailable in this session; use official YouTrack REST and GitHub CLI documentation as API references. No translation/PDF/model/OCR changes.

## Plan
1. Add dependency-free project tracking adapter with configured YouTrack schema mapping, identity verification, audit/idempotency and GitHub PR exact-SHA checks.
2. Bootstrap before child execution; lifecycle hooks only after validated local transitions. Optional agent intent stdout envelope separate from strict role contracts.
3. Strip integration credentials from child environments. Keep reviewer allowlist unchanged.
4. Deterministic fake-transport tests plus runner regression tests, full check.ps1, Wiki lint.
5. Update README, CHANGELOG, affected Wiki, report. Commit/push and write designated implementer input only.

## Safety
No remote calls during tests; no historical backfill; no automatic merge; external errors do not alter verdicts. Ambiguous create outcomes are journaled before mutation and never blindly retried. External identity mismatch disables further YouTrack mutation. Coordination artifacts are runtime-owned, not authored in this implementation session.

## Human-approved interrupted-process recovery (2026-10-05)
- Resume the existing dirty implementation from HEAD `4e250091f2632630c31e0871a3f2e401e0c944c5`.
- Existing adapters, runner hooks, deterministic tests and documentation already cover the core scope.
- Inspect remaining isolation/non-blocking gaps: metadata must not hide another reviewer verdict;
  unavailable or malformed custom-field schemas must not prevent safe ticket attachments/comments.
- Reproduce focused tests and the full quality gate; replace inherited validation claims with
  current evidence. Preserve all existing agent-cycle history and run no manual transitions.
- Keep operational milestones in `.agent-cycle/PDFTR-43/implementer-progress.log`, archive the
  existing WIP patch under ignored `temp/pdftr43/`, then commit/push intended ticket files.
- Exact live YouTrack mappings remain deployment configuration, never a completion prerequisite.

## Human-approved R1/R2 recovery after independent review
- Start from reviewed SHA `6e09414901cb631b4abe34d77d249ddcdcc38746`; retain the existing branch,
  implementation, validator, reviewer capabilities and historical coordination artifacts.
- R1: select the existing strict review envelope before metadata removal; remove only external
  metadata and reject nested/overlapping/malformed boundaries and hidden competing verdicts.
- R2: create/update neutral PR metadata, verify exact head, publish SHA-bound readiness/review/CI,
  reverify and revoke published claims after movement or uncertain publication.
- Exercise tracking/parser/races plus reviewer/validator/resume regressions, run full check.ps1,
  update the report and docs, commit/push and preserve a clean working tree. Append only factual
  milestones to the existing implementer-progress.log; run no cycle transitions.
