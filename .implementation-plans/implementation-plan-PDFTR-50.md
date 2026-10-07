# PDFTR-50 implementation plan

## Investigation (Level 2)
Clean task branch. PDFTR-49 has pure exact-head/base policy and a durable store with
OS-held nonblocking ticket ownership, but no authoritative GitHub adapter or dispatch.
Source verified request_review, mark_dispatch, store.request and cycle _load_cycle.
Graphify query IndependentReviewStore confirmed the policy/store/ownership neighborhood;
source is authoritative. CRG update completed parsing but console output failed cp1251;
rerun with UTF-8. Context7 is not exposed in this session; use documented REST shapes,
strict response validation and deterministic mocked integration tests instead.

## Plan
- Add read-only GitHub REST facts adapter: configured repository/PR, no forks, PR sandwich
  around exact-SHA checks; ambiguous, missing or wrong-SHA evidence fails closed.
- Add immutable transport-neutral dispatch request and HTTPS trusted connector transport.
- Extend store with one serialized fresh-request dispatch operation, persisted intent first;
  no retries; restart REQUESTED conservatively becomes uncertain.
- Add trusted-parent event/manual reevaluation entrypoint; no public webhook server,
  no event authorization, no agent-file facts/config inputs.
- Tests cover normalization, binding, races, serialization, persistence and restart.
- Update README, CHANGELOG, independent review docs and affected Wiki.
- Run focused tests, full check.ps1, Wiki lint, commit and push.

## Boundaries
No policy/result schema changes; no dependencies, PDF/model/OCR changes, YouTrack,
publication, merge or runner phase transitions. Deployment must isolate trusted code,
configuration, cycle state and credentials from agents. External transport is a connector
contract, not an invented ChatGPT Work API. CI exact-SHA results require remote verification.

## Human review correction (2026-10-07)

Reviewed SHA: `81ab41bf5ea6d3b038e1368f4a0970a323cb14a7`; P2 / MEDIUM:
the production entrypoint lacks explicit first initialization. The human supplied the design
and authorized implementation, commit and push in this existing branch/directory.

Investigation: `main` exposes evaluate/signal only; `request_and_dispatch` loads existing
history. `IndependentReviewStore.initialize()` already creates `empty_state(config)` under
the same OS ticket ownership and rejects any existing file without replacing it. Graphify
locates this store/policy/ownership neighborhood; current source confirms the relationships.
CRG refreshed successfully and finds initialize callers only in tests. No PDF/model/OCR,
dependency, policy or state-schema changes are needed. YouTrack reports Issue not found;
no issue is created and no cycle transition is authorized by this correction.

- [x] Write CLI regressions using a real Git repository and harness-created cycle: fresh init,
  second init/unchanged bytes, missing/corrupt history, deleted used history, eligible flow,
  concurrent init, invalid trusted config/cycle, and no transport construction on init.
- [x] Observe RED: the current CLI rejects the requested `init` command.
- [x] Add `init` before transport construction. Reuse protected `PDFTR_REVIEW_CONFIG`, existing
  config/ticket validation, `load_cycle` harness validation and `store.initialize()`.
  Report `state_already_exists` for repeated init without exposing sensitive exceptions.
- [x] Run focused PDFTR-49/PDFTR-50 tests; preserve all existing policy/dispatch regressions.
- [x] Document init and its operator-only first-use boundary in README, CHANGELOG, contract,
  affected Wiki, ticket, report and review. Refresh scoped CRG and lint Wiki.
- [x] Run full `scripts/check.ps1` and record tests/coverage: 1319 passed, 3 skipped, 89.54%.

Final handoff: commit and push this tested correction after versioning the report/review;
the final operator response supplies the exact new SHA and remote verification.

Review focus: init needs no dispatch credentials; invalid or absent cycles/config reject;
existing/corrupt bytes stay unchanged; competing ownership rejects; normal missing-state events
never initialize history. Init performs no dispatch, ingestion, external mutation, merge or
automatic cycle transition. No force/reset/recovery command or implicit initialization is added.
