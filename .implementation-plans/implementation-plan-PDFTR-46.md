# PDFTR-46 investigation and implementation plan

Level 2; initial tree clean on pdftr-46-self-modifying-runner.

## Investigation
The CLI loads pi_ticket_cycle as __main__, not scripts.pi_ticket_cycle. Tracking's function-local import can therefore load changed disk source after implementation against cached agent_cycle. Graphify query identified the runner/tracking/test neighborhood; source confirms the circular edge. CRG update completed parsing but its brief panel failed with CP1251 UnicodeEncodeError; retry with UTF-8 diagnostics planned. No PDF, translation, models, OCR, dependencies or public schemas are affected.

## Plan
1. Extract the unchanged sentinel/fence selection grammar and a pure protocol exception into review_protocol; startup-import it from both callers and translate errors at existing boundaries.
2. Audit all parent harness imports (including progress and reviewer helpers); retain only startup repository imports and runtime stdlib imports. Document next-invocation activation, without reload/restart.
3. Preserve raw reviewer stdout before validation and contain unexpected post-review failures with explicit internal diagnostics, retaining evidence and never rerunning reviewers automatically.
4. Add isolated on-disk mutation regressions for both missing-symbol generations, PASS and CHANGES_REQUIRED, plus AST dependency enforcement. Retain strict parsing tests and ownership/retry checks.
5. Run focused tests, Wiki lint and scripts/check.ps1; update README, changelog, affected Wiki, report and completion review; commit/push and supply only designated implementer input.

External tracking attachments are runner-owned; no direct API access. Integration warning: YouTrack credentials unavailable.
