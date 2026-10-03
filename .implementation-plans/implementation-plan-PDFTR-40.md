# PDFTR-40 implementation plan

1. Add dependency-free fixed-operation Node Git inspector and small Pi TypeScript adapter.
2. Register/load only for reviewer, keep built-in file allowlist, disable extension discovery and require independent exact-SHA/base/branch evidence in prompt.
3. Test real read operations and adversarial config/arguments, bounded failures, all presets and fake cycle evidence.
4. Update contracts, README/CHANGELOG and affected Wiki; run focused and full gates.
5. Report honest limitations, commit/push, write only designated implementer input; no cycle transitions.

State machine, verdict schema, maximum rounds, implementer permissions and human merge ownership remain unchanged. No new dependencies; Node is the existing Pi runtime and is required for its inspector tests.
