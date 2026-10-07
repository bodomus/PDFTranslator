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
