# PDFTR-40 implementation plan

1. Add dependency-free fixed-operation Node Git inspector and small Pi TypeScript adapter.
2. Register/load only for reviewer, keep built-in file allowlist, disable extension discovery and require independent exact-SHA/base/branch evidence in prompt.
3. Test real read operations and adversarial config/arguments, bounded failures, all presets and fake cycle evidence.
4. Update contracts, README/CHANGELOG and affected Wiki; run focused and full gates.
5. Report honest limitations, commit/push, write only designated implementer input; no cycle transitions.

State machine, verdict schema, maximum rounds, implementer permissions and human merge ownership remain unchanged. No new dependencies; Node is the existing Pi runtime and is required for its inspector tests.

## P1 follow-up at c7dbc6d

1. Reject any `.git/commondir` entry during inspector construction, before Git subprocesses.
   Common-directory/linked-worktree layouts remain explicitly unsupported; do not resolve redirects.
2. Reproduce absolute and relative foreign-repository redirects with real Git, then assert all
   inspection operations reject them. Cover empty/self redirects and zero subprocess calls.
3. Preserve existing guards/interface/runner/state, update safety docs and affected Wiki, run
   focused security tests and the full PowerShell gate, then commit/push for exact-SHA review.
