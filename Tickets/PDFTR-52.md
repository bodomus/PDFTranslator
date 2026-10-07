# PDFTR-52 — Safe automatic fix continuation

## Status
Planned (runner-managed implementation attempt 1)

## Ticket text
Implement the trusted continuation layer consuming only a current PDFTR-51 independent-review continuation intent. A current, published, exact-context CHANGES_REQUIRED result may start a new implementation attempt on the same ticket/task branch. Automatic merge remains out of scope.

Required eligibility: exact current independent generation/head/base and immutable findings; authoritative open non-draft PR and required CI success; PASSED local cycle with the reviewed implementation SHA; matching repository/branch/HEAD, clean tree, no active agent or Git operation; no publication/dispatch/launch uncertainty; independent automatic continuation budget available.

Persist authorization and identity before findings preparation and process launch. At most one automatic continuation per generation, maximum two authorizations per ticket lineage, independent of operational/pre-handoff/human review recovery. Restart may resume positively unlaunched preparation using the same identity; uncertain launch never auto-retries. Preserve immutable review history, cumulative attempt numbering, existing hardened process containment, normal Pi reviewer and required CI before a new independent review. Findings must come from accepted PDFTR-49 evidence resolved through PDFTR-51, never comments or arbitrary JSON.

Human intervention is required for uncertainty, stale/corrupt context, unsafe repository state, safety stops and exhausted budgets. YouTrack is non-authoritative and missing issues must not block; do not create issues or merge.

## Acceptance and validation
Focused tests cover authorization, PASS/unpublished/uncertain rejection, stale head/base/older generation, duplicates/concurrent ownership, prelaunch restart, launch uncertainty, repository safety, bounded budgets/recovery isolation, immutable findings, internal reviewer and new independent-review requirements. Full scripts/check.ps1 must pass; exact-SHA Windows/Ubuntu CI remains required before human final approval.

## Runner constraints
Only implementer may mutate, commit or push. Runner owns all agent-cycle transitions and state. Only designated implementer handoff input and bound progress_append diagnostic journal are writable coordination inputs. No manual transitions. Source ticket supplied in the runner assignment is authoritative; this tracked summary retains its operational requirements. Remote attachment capability is not exposed in this session.
