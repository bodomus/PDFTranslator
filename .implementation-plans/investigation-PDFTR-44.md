# PDFTR-44 investigation

- Workflow: Level 2; initial tree clean on expected task branch, Python 3.12.10 / uv.
- Current behavior: `SubprocessExecutor._communicate` polls every five minutes and invokes
  `ProgressReporter.heartbeat` with elapsed time only. Reviewer runtime guard permits file reads
  and constrained Git evidence, not shell or writes. Prompts prohibit all coordination writes
  except the implementer handoff input.
- Expected: bounded factual milestone journal, separate role paths, last meaningful activity and
  configurable stale warnings; diagnostic-only, no execution timeout or authoritative state changes.
- Missing boundary: reviewers need a fixed-path append-only tool, not an arbitrary write tool.
- Minimal scope: runner prompt/child wrapper, standalone Python diagnostic module, small Pi
  progress extension and its filesystem helper, one reviewer allowlist exception, tests/docs.
- Call flow source-verified: `run_cycle` constructs role prompts/commands, `_execute_child`
  delegates to the executor, heartbeat is a local callback; role exit/cancellation unwinds through
  existing cleanup and validator STOPPED paths. No changes to the validator or process tree owners.
- Compatibility: handoff/review JSON schemas and exact SHA gates unchanged. Journals are ignored
  runtime artifacts; resume/recovery appends and never deletes them. Stale clocks are per execution.
- No effects on PDFs, translation quality, segmentation, models, GPU, OCR or application caches.
- Graphify query/affected neighborhood source verified. CRG UTF-8 update works after cp1251
  console failure; test-gap heuristic under-reports indirect FakePi/heartbeat tests. Installed Pi
  extension docs/examples/types provide the API reference; Context7 is not available in this harness.
- Validation: parser/heartbeat/capability/resume/failure tests, existing process cleanup and SHA
  regressions, Node extension loading, Wiki lint, full PowerShell quality gate. No model downloads.
