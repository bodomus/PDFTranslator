# PDFTR-42 implementation plan

Workflow level 2; initial tree clean on the assigned branch.

## Investigation
The wrapper rejects every state except NEW; its loop unconditionally starts implementation.
The validator binds branch/fingerprint/base/SHA and caps review numbering at two. Source-verified
call chain: run_cycle -> begin_implementation/record_handoff -> begin_review/record_review.
Only orchestration scripts, their tests, and operational documentation are affected; no PDF,
translation, model, dependency or OCR impact.
Graphify query identified both scripts and test modules; source verified the relationships.
CRG update --brief parsed successfully but console output failed with cp1251 UnicodeEncodeError;
retry with PYTHONIOENCODING=utf-8. No Context7 tool is available; no external API changes needed.

## Plan
1. Dispatch idle validated states; reject active/terminal states without guessing ownership.
2. Add explicit reopen/--recover with reason, clean branch/HEAD checks, audit snapshots and a
   HUMAN_APPROVED_REWORK state. Retain cumulative review numbers; each approval authorizes only
   one additional review. Keep MAX_REVIEW_ROUNDS=2 and retain legacy manifest compatibility.
3. Preserve immutable numbered reviews and implementation handoffs, enforce new SHA and existing
   reviewer safeguards. Add deterministic resume/recovery/negative tests.
4. Update README, CHANGELOG, contracts and affected Wiki; run focused tests, Wiki lint and check.ps1.
5. Record report/review, commit/push, supply only designated implementer input to runner.

External ticket attachment/update tooling is unavailable in this session; ticket Markdown already
exists under Tickets/PDFTR-42-resumable-pi-ticket-cycle.md.
