# PDFTR-33 — Follow-up fix: generic agent roles

## Goal

Remove product-specific agent names from the low-level agent-cycle contract. The validator and
state schema model roles rather than specific LLM products. `opencode.json` remains unchanged.

## Required role names

- `deepseek` becomes `implementer`;
- `codex` becomes `reviewer`;
- `shared` becomes `system`.

The handoff top-level sections are exactly `schema_version`, `system`, `implementer`, and
`reviewer`. `active_agent` accepts only `implementer`, `reviewer`, or null. Product names may be
assignment metadata but must not be schema keys, enum values, transitions, or ownership domains.

Preserve the single-writer rule, read-only exact-SHA review, clean-tree gates, stale-review
invalidation, two-round cap, repeated-finding stop, active-role exclusivity, atomic writes, safety,
optional remote validation, and human merge ownership. Add regressions for the generic PASS flow,
second-round `CHANGES_REQUIRED`, and rejection of the former product-specific names.

Update the validator, tests, workflow skill, repository instructions, README, CHANGELOG,
ProjectWiki, implementation report, and review artifact. Run focused tests, the full suite,
ProjectWiki lint, and `scripts/check.ps1`. Final status: `READY FOR REVIEW`.
