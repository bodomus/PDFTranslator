# PDFTR-5 Implementation Plan

1. Mirror the attached ticket under `Tickets/`, assign ChatGPT, and move it to `In Progress`.
2. Add centralized stable exit codes and typed pipeline contracts.
3. Implement deterministic run identity and an application-cache workspace with atomic manifests,
   logs, failure state, and strict resume validation.
4. Implement inspect, extract, translate, render-to-candidate, validate, and atomic publication.
5. Reuse validated stages only with `--resume`; retain normal translation-memory caching.
6. Add dry-run inspection without constructing a model backend or writing translated output.
7. Add root PDF-path dispatch while preserving existing Typer subcommands.
8. Add generated-PDF/fake-backend tests for all ticket acceptance and failure scenarios.
9. Update README and CHANGELOG with usage, artifacts, resume, progress, and exit codes.
10. Run focused tests, full checks, CLI smoke tests, CRG update, and Graphify refresh.
11. Create `reviews/review-PDFTR-5.md`, commit ticket scope, comment, and move to `In Review`.
