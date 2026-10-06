PDFTR-46 — Self-Modifying Runner / Module-Version Skew Safety

Goal

Eliminate orchestration failures caused by the implementer modifying harness modules while
scripts/pi_ticket_cycle.py is still running in the same Python process.

This defect reproduced twice during PDFTR-45.

Observed failures:

1. After implementer updated agent_cycle.py / pi_ticket_cycle.py, reviewer completed,
   but project_tracking.review_without_intent() performed a runtime import of the newer
   pi_ticket_cycle.py.

   The live process still had the older scripts.agent_cycle module cached.

   Result:

   ImportError:
   cannot import name 'OPERATIONAL_CODES' from 'scripts.agent_cycle'

2. After the next implementation changed the harness again, the same pattern reproduced with:

   ImportError:
   cannot import name 'complete_operational_prelaunch' from 'scripts.agent_cycle'

In both cases:
- implementer completed;
- commit was created and pushed;
- handoff was accepted;
- reviewer completed successfully;
- runner crashed only while validating/persisting reviewer output.

The cycle then remained stranded in REVIEWING and required manual review-record recovery.

==================================================
CORE INVARIANT

A running orchestration process must use one internally coherent version of its orchestration code.

Repository modifications made by an implementer during that process must NOT cause the parent
runner to import a mixture of:

- startup-time modules already cached in sys.modules;
- newly modified modules loaded from disk later in the same process.

The current cycle process must either:

A. continue using the coherent startup snapshot until it exits;

or

B. explicitly restart/re-exec at a safe persisted boundary before using newly changed harness code.

It must never silently mix module generations.

==================================================
R1 — Remove runtime circular import/version skew

Current problematic pattern:

scripts.project_tracking.review_without_intent()

runtime imports symbols from:

scripts.pi_ticket_cycle

while pi_ticket_cycle itself already imported project_tracking.

This creates both:
- circular dependency;
- runtime module-generation skew when files change on disk.

Required fix:

Move the shared review-envelope grammar/parsing helpers out of pi_ticket_cycle.py into a small,
stable dependency module.

Suggested shape:

scripts/review_protocol.py
or
scripts/review_envelope.py

Move only shared pure protocol logic, for example:

- REVIEW_SENTINEL_BEGIN
- REVIEW_SENTINEL_END
- JSON fence regex
- strict single-envelope selection
- envelope ambiguity rejection
- any parser-specific exception type needed by both modules

Then:

pi_ticket_cycle.py
    imports review protocol

project_tracking.py
    imports review protocol

project_tracking.py must NOT import pi_ticket_cycle.py at runtime.

Avoid introducing the reverse dependency elsewhere.

==================================================
R2 — Startup-snapshot semantics

Audit the runner for other runtime imports of mutable harness modules.

The parent orchestration process should not dynamically import newly changed runner/state-machine
modules after implementer execution.

Review at least:

- scripts/pi_ticket_cycle.py
- scripts/project_tracking.py
- scripts/tracking_hooks.py
- scripts/agent_cycle.py
- scripts/agent_progress/*
- reviewer helper modules
- any function-local imports used to avoid circular imports

Classify imports as:

1. startup imports — acceptable;
2. runtime imports of immutable stdlib/third-party code — acceptable;
3. runtime imports of repository harness modules that the implementer may edit — unsafe unless
   explicitly protected.

Remove or redesign category 3.

==================================================
R3 — Parent process must not adopt new harness code mid-run

If the implementer modifies:

scripts/agent_cycle.py
scripts/pi_ticket_cycle.py
scripts/project_tracking.py
or related orchestration modules,

the already-running parent process must continue safely using its startup-loaded code.

It is acceptable that the NEW code only becomes active on the next invocation.

This should be documented as intentional behavior.

Do NOT call importlib.reload().

Do NOT attempt partial hot reload.

Do NOT clear sys.modules.

Do NOT dynamically load changed harness files into the existing runner.

Those approaches make version coherence worse.

==================================================
R4 — Safe restart boundary if newer code is required

If some workflow truly requires the newly committed harness implementation before continuing,
do not hot-load it.

Instead use a persisted safe boundary and explicit restart/re-exec semantics.

Example acceptable architecture:

1. current process persists authoritative cycle state;
2. releases child/process ownership;
3. exits with a dedicated restart-required result;
4. operator or wrapper starts a fresh Python process;
5. new process loads one coherent repository version.

However:

Do NOT add automatic restart complexity unless actually required for PDFTR-46.

Preferred minimal solution:
the current process finishes the cycle using its startup snapshot whenever possible.

==================================================
R5 — Review parsing safety must remain unchanged

Moving review parsing logic must preserve all existing strict behavior from PDFTR-35A / PDFTR-43.

Specifically preserve:

- exactly one valid review envelope;
- ambiguity rejection;
- contradictory verdict rejection;
- nested/malformed delimiter rejection;
- metadata intent stripping only outside the selected review envelope;
- reviewer PASS / CHANGES_REQUIRED / BLOCKED schema validation;
- no accidental acceptance of competing verdicts.

The refactor must not weaken strict review validation.

==================================================
R6 — Failure containment

Even if an unexpected module/import error still occurs during post-review processing:

- the original reviewer output must remain preserved;
- reviewer log must remain preserved;
- cycle artifacts must not be deleted;
- no duplicate reviewer execution should occur automatically;
- diagnostics must clearly report the internal runner failure.

Where feasible, a post-review orchestration error should not destroy already completed reviewer
evidence.

Do not silently convert infrastructure failure into PASS.

==================================================
R7 — Regression tests for actual reproduced defect

Add deterministic tests reproducing the PDFTR-45 failure pattern.

Test A — old agent_cycle / new pi_ticket_cycle mismatch simulation

1. Import/start runner modules.
2. Simulate implementer changing on-disk harness modules so newer pi_ticket_cycle expects a symbol
   absent from the already-loaded agent_cycle.
3. Execute review_without_intent / review validation path.
4. Verify no runtime import of pi_ticket_cycle occurs.
5. Verify review is processed using the coherent startup protocol module.

Test B — second-generation symbol mismatch

Repeat with a synthetic newly-added symbol equivalent to:

complete_operational_prelaunch

The test must demonstrate that on-disk modifications cannot cause the live process to import the
new runner generation.

Test C — review PASS survives harness source mutation

1. Start cycle with version A modules.
2. During simulated implementer execution mutate relevant harness source files to version B.
3. Produce valid reviewer PASS.
4. Parent runner validates and records PASS using version A startup snapshot.
5. No ImportError.
6. No manual recovery required.

Test D — CHANGES_REQUIRED survives harness source mutation

Same scenario, but reviewer returns CHANGES_REQUIRED.

Verify normal state transition occurs.

Test E — strict envelope behavior unchanged

Retain/add coverage for:
- competing verdict;
- nested sentinel;
- malformed sentinel;
- intent metadata outside envelope;
- intent-like content inside review envelope.

==================================================
R8 — Import graph regression test

Add a small test or static assertion that:

scripts.project_tracking

does NOT depend on:

scripts.pi_ticket_cycle

directly or through a function-local runtime import.

At minimum:

- inspect source/import behavior deterministically;
- fail if the forbidden dependency is reintroduced.

Prefer architectural dependency enforcement over a fragile string-only assertion if practical.

==================================================
R9 — No state-machine scope expansion

PDFTR-46 is NOT a retry/recovery ticket.

Do not change:

- operational retry semantics from PDFTR-45;
- review-round accounting;
- human approval policy;
- exact-SHA rules;
- STOPPED recovery policy;
- reviewer permissions;
- GitHub/YouTrack behavior.

Only make changes required for coherent module/runtime behavior.

==================================================
R10 — Process ownership / reviewer safety

Preserve:

- reviewer read-only restrictions;
- process containment;
- Windows Job Object behavior;
- POSIX child cleanup;
- runner ownership lock introduced during PDFTR-45;
- progress journals;
- exact-SHA review binding.

No new subprocess should inherit additional write capabilities.

==================================================
EXPECTED ARCHITECTURE

Preferred dependency direction:

    review_protocol.py
          ↑       ↑
          |       |
pi_ticket_cycle   project_tracking

NOT:

pi_ticket_cycle
      ↑
project_tracking
      |
runtime import back into pi_ticket_cycle

Shared protocol modules should contain pure logic only and must not import:

- agent_cycle state mutation APIs;
- tracking hooks;
- provider executors;
- subprocess orchestration.

Keep the shared module small and deterministic.

==================================================
STATUS / OBSERVABILITY

If helpful, emit a startup diagnostic such as:

Runner code snapshot loaded at process start

but do not add noisy per-module logging.

Progress journal semantics from PDFTR-44 must remain unchanged.

==================================================
TESTS

Run focused tests covering:

- review protocol extraction;
- project tracking;
- ticket runner;
- self-modifying harness simulation;
- PASS path;
- CHANGES_REQUIRED path;
- import graph;
- progress integration;
- operational retry regression.

Then run:

scripts/check.ps1

All existing tests must remain green.

==================================================
ACCEPTANCE CRITERIA

PDFTR-46 is complete when:

1. project_tracking no longer runtime-imports pi_ticket_cycle.
2. Shared review-envelope logic lives in a stable independent module.
3. A running runner cannot mix startup-loaded agent_cycle with newly loaded pi_ticket_cycle code.
4. Implementer modifications to harness source do not break post-review processing in the same run.
5. PASS review can be recorded after harness source mutation.
6. CHANGES_REQUIRED review can be recorded after harness source mutation.
7. Strict review ambiguity protections remain unchanged.
8. No hot reload / importlib.reload / sys.modules manipulation is introduced.
9. Reviewer read-only guarantees remain intact.
10. PDFTR-45 operational retry behavior remains unchanged.
11. Process containment and runner ownership protections remain intact.
12. Full scripts/check.ps1 passes.
13. Windows and Ubuntu CI pass.

==================================================
NON-GOALS

Do not implement:

- Python hot reload;
- importlib.reload;
- sys.modules clearing;
- automatic branch switching;
- automatic process restart unless strictly necessary;
- generic plugin reload framework;
- dynamic code patching;
- reviewer retry automation;
- changes to YouTrack integration;
- changes to GitHub PR lifecycle;
- automatic merge.

==================================================
REAL REPRODUCTION EVIDENCE

PDFTR-45 reproduced this twice.

Failure 1:

ImportError:
cannot import name 'OPERATIONAL_CODES' from 'scripts.agent_cycle'

Failure 2:

ImportError:
cannot import name 'complete_operational_prelaunch' from 'scripts.agent_cycle'

Both occurred after reviewer execution when:

project_tracking.review_without_intent()

performed a runtime import of:

scripts.pi_ticket_cycle

from the newly modified working tree while the parent process still held the older:

scripts.agent_cycle

module in memory.

The implementation must include a regression reproducing this exact module-generation mismatch
class and demonstrate that it can no longer occur.

==================================================
IMPLEMENTATION DISCIPLINE

Maintain concise progress journal entries only.

No chain-of-thought.

Run focused validation, then full scripts/check.ps1.

Commit and push.

Final response:

1. new SHA
2. focused test result
3. full scripts/check.ps1 result
4. architecture change summary
5. confirmation runtime pi_ticket_cycle import removed from project_tracking
6. confirmation module-version-skew regression covered
7. progress log path
8. remaining limitations
