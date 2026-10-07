# Implementation report — PDFTR-48

## Workflow and investigation
- Level 2; initial working tree clean on the supplied ticket branch.
- Graphify queried `retry_operational_cycle run_cycle`, then refreshed with
  `graphify update . --no-cluster`. Sources confirm validator policy, runner dispatch,
  process ownership and tracking mutation boundaries. Graphify reported four JSON files
  producing no nodes; none owns retry execution.
- CRG `update --brief` refreshed structural relationships. Initial console rendering failed
  cp1251 encoding; `PYTHONIOENCODING=utf-8` succeeded. Graph test-gap hints were verified
  against executable tests, not treated as authoritative missing coverage. Final CRG refresh
  confirmed scope remained confined to the harness and its tests; Graphify reverse traversal
  confirmed the validator CLI entry point, with remaining relationships verified in source.
- Context7 unavailable in this session. Existing Python/Git/process APIs reused; no dependencies added.

## Scope and changes
The former operational policy correctly refused clean unknown stops. The new dedicated
`retry-pre-handoff` command approves only a provably unchanged pre-first-handoff STOPPED cycle;
normal runner invocation dispatches the already-approved attempt.

- Independent deterministic policy rejects accepted handoffs, review evidence, active ownership,
  dirty/changed Git state, safety stops and exhausted operational limits. Stop prose is irrelevant.
- Existing hardened Git inspection supplies repository, branch, merge-base, HEAD and tree bindings.
- Every implementer execution records prepared/launching/exited evidence. Positive exit proof is
  written only after process-tree cleanup; legacy unknown stops without proof remain ineligible.
- `HUMAN_APPROVED_PRE_HANDOFF_RETRY` and strict `pre_handoff_retries` history persist human UTC
  approval, previous stop facts, monotonic attempt identity and repository/source bindings.
- Prior top-level execution artifacts are byte-exact snapshots under `attempts/<N>/`, with SHA256
  bindings checked on load. Prior stopped manifests, blank handoffs and exit markers are verified.
- Shared OS ticket ownership moved unchanged into startup-loaded `cycle_ownership.py`; both
  operator approval and runner dispatch use it. No late runner import or harness hot reload.
- Existing exact blank-projection repair and prepared/launching crash fencing handle the new
  approval without repeating accounting. Uncertain dispatched attempts cannot resume automatically.
- Pending/uncertain tracking mutations fence approval and dispatch. Tracking identities and definite
  successful mutation keys survive retries unchanged; no tracking issue creation is implied.
- Operational retry keeps its recognized-class/code predicates and three-retry limit. Exhausted
  review recovery and review authorization remain separate. Reviewer capabilities are unchanged.

No PDF/translation/model/device/OCR/dependency behavior changed. Handoff schemas remain unchanged.

## Validation
- Focused recovery, operational-retry, startup-snapshot, review-resume and validator suites: PASS.
- `scripts/check.ps1`: PASS (Windows Python 3.12); full pytest, Wiki lint, Ruff formatting/lint and mypy.
- Final full gate: 1,143 passed, 3 skipped in 408.98 seconds; coverage 89.54%.
  This rerun includes extra reviewer-evidence and crash-boundary regressions.
- CLI `--help` smoke test: PASS; dedicated command registered. No real retry or state transition
  was invoked on this ticket; transition tests use disposable repositories under `temp/`.
- Adversarial tests cover dirty/untracked changes, HEAD/branch/repository mismatch, accepted or
  contradictory artifacts, active ownership, missing/launching process proof, arbitrary stop text,
  corrupted history, malformed tracking data, uncertainty, duplicate approval, mixed retry numbering,
  definite tracking success, historical byte preservation and pre/post-dispatch restart boundaries.
- Existing startup disk-mutation tests now include both new shared modules and prove startup-only
  behavior through PASS and CHANGES_REQUIRED source replacement.
- CI configuration retains Windows/Ubuntu Python 3.12. Hosted CI results are not claimed locally.
- No live provider, YouTrack mutation, model download, GPU or OCR integration validation performed.

## Documentation and completion
Updated README, CHANGELOG, handoff contract and affected development-workflow Wiki/log.
Ticket plan and implementer completion review are stored in their required ticket-specific paths.
The runner owns external attachments, tracking lifecycle and final review coordination.

## Integration warnings
["YouTrack identity mismatch; remote mutation refused", "YouTrack authentication failed"]

## Remaining boundaries
Approval is the existing human/operator operational boundary, not an authenticated identity service.
Legacy stops lacking positive process evidence and uncertain launches require human inspection;
no unsafe migration, cleanup, generic force retry or automatic retry is introduced.
