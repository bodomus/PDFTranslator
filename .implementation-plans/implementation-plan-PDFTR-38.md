# PDFTR-38 plan — blocker-only outcome

Investigation is complete in `investigation-PDFTR-38.md` before tracked test/documentation changes.

1. Add deterministic saved-PDF capability tests for native decimal/letter/bullet markers, unsupported
   custom string and pseudo-element markers, and ignored inline span padding. Native positive controls
   ensure failures are not merely caused by a missing font or a failed HTML insertion.
2. Characterize existing plain-paragraph geometry at narrow/wide requested marker-content gaps and
   confirm semantic lookalikes remain intact during extraction/reconstruction. Tests must not claim
   these are production list support. Retain all current production paths unchanged.
3. Document the unsupported boundary in README, CHANGELOG and the affected reflow Wiki page only.
4. Run focused typography/reconstruction/inline/reflow tests, full pytest, Wiki lint and check.ps1;
   keep temporary output under `temp/`. Inspect the final diff, produce report and review summary.
5. Commit/push this investigation and blocker evidence. Query CI when available; do not claim a CI or
   product completion without evidence. Prepare only the designated runner handoff input, clearly
   identifying the unmet product requirements in `known_limitations`.

No schema/dependency/module-boundary change is proposed. No workaround renderer or planner is added.
The proposed source-owned structural extension requires a human-approved next step and a verified
shared layout primitive; it is not implemented speculatively in this attempt.
