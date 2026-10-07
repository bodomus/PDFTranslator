# PDFTR-48 investigation and implementation plan

## Investigation (Level 2)
Baseline: clean, branch `pdrtr-48-human-approved`. Existing `retry_operational_cycle`
checks hardened `_load_cycle` Git bindings but only accepts structured operational stops.
The runner already serializes ownership and persists prepared/launching retry markers.
Initial executions do not yet persist positive exited-process evidence. Tracking stores
write-ahead mutation outcomes in `youtrack.json` and preserves success idempotency keys.

Graphify query `retry_operational_cycle run_cycle` identifies validator, runner and retry
tests; source confirms those boundaries. CRG `update --brief` updated successfully but
its console panel failed cp1251 encoding; rerun with UTF-8. Context7 is unavailable in
this tool session. No new dependencies or external library APIs are needed.

## Plan
1. Add separate human pre-handoff approval state/history and deterministic eligibility.
2. Require positive runner exit evidence, clean unchanged Git bindings, no accepted
   handoff/review or uncertain mutations; serialize operator approval with runner lock.
3. Preserve a byte-exact attempt snapshot before approval; validate persisted history.
4. Reuse existing prepared/launching crash fencing, never resume a dispatched process.
5. Expose dedicated validator command (approval only; normal runner dispatches it).
6. Add adversarial/restart tests, update docs and affected Wiki, run focused/full gates.

Blast radius: harness only; no PDF, translation, model, CUDA, OCR or dependency changes.
Operational eligibility and review-exhaustion recovery remain separate policies.
