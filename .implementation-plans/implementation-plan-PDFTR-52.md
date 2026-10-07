# PDFTR-52 implementation plan

## Investigation (Level 2)
Clean baseline on the expected task branch. PDFTR-51 persists validated publications and pending continuation intent but does not launch fixes. PDFTR-49 supplies immutable exact head/base generation results. The Pi runner already serializes tickets, fences every implementer launch, and contains/reaps process trees. Source verified: IndependentReviewResultService._load/_receipt, IndependentReviewStore.load, run_cycle/_run_cycle, agent_cycle implementation_attempt and record_review.

Graphify query identified the expected runner/result/test neighborhood; source is authoritative. CRG update parsed successfully but console rendering failed with a cp1251 UnicodeEncodeError; repeat with UTF-8. Context7 is not exposed in this session; no external APIs/dependencies are introduced.

## Plan
- Add pure fail-closed continuation policy with independent limit two.
- Add trusted-parent-only service resolving publication/receipt/result, separate durable lineage ledger and immutable findings input, exclusive ticket ownership, prelaunch refresh and uncertain-launch fence.
- Project a policy-approved state into the existing cycle and reuse its implementer and reviewer, retaining cumulative attempts/reviews and all retry histories. Give each continuation the normal two-review budget without granting operational/pre-handoff recovery.
- Add focused policy, restart, duplicate, integrity and real runner integration tests.
- Update README, changelog, independent-review documentation and affected Wiki page; lint Wiki and run focused/full PowerShell gate.

No PDF, translation, model, OCR, dependencies or merge changes. Protected deployment state/code remains mandatory, as in PDFTR-51. Agent-authored local JSON and GitHub comments are never authorization sources. Optional ticket updates remain outside policy; attachments are unavailable through this runner.
