# PDFTR-47 investigation

- Workflow: Level 2, clean baseline, expected task branch, Python 3.12.10 via uv.
- Entry path: pi_ticket_cycle.run_cycle -> TrackingHooks -> ProjectTracking.bootstrap/lifecycle;
  startup module coherence, local cycle transitions and reviewer capabilities remain unchanged.
- Existing behavior: exact identity checks and write-ahead operation journal existed, but creation
  was implicitly allowed, estimates/dates/enums were inferred and writes lacked semantic read-back.
- Missing capabilities: explicit categorized preflight, canonical host binding, read-only/dry-run
  validator, API login resolution, non-ambiguous missing-issue policy and local sync serialization.
- Scope: scripts/project_tracking.py, project-tracking.toml, tracking tests and documentation.
  No PDF, translation, OCR, model/cache, dependency or agent-cycle schema changes.
- Graphify query and affected traversal identified hooks and tests; source verified those paths.
  Its `translate_paragraphs -> ProjectTracking` association is a false positive: translation source
  does not import tracking. Source wins. Graph refresh uses no LLM and excludes .agent-cycle.
- CRG incremental update succeeds under PYTHONIOENCODING=utf-8; initial cp1251 summary printing
  failed after parsing. Dynamic REST fake relationships are incomplete, so pytest is authoritative.
- Context7 is not exposed by this harness; no external library or SDK has been introduced.
  YouTrack REST shape, project mappings and number allocation still need operator live validation.
- YouTrack token presence check confirmed credentials unavailable; no live API was contacted.
- Validation: focused tracking, validator and runner safety regressions, then scripts/check.ps1,
  Wiki lint and source/diff review. Temporary outputs stay under temp/.
