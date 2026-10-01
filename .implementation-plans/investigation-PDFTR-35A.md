# Investigation — PDFTR-35A Orchestrator safety follow-up

## Ticket

PDFTR-35A fixes the four high-severity findings from the PDFTR-35 round-2 review for SHA
`1e3a3a78712ebb4f1e91f8090377759930e1546c`: R2 contradictory handoff write permissions, R4
incomplete process-tree cancellation, R5 permissive reviewer JSON extraction, R6 missing child
cleanup on post-spawn I/O failure.

## Workflow

- Level 2 (orchestration safety, process lifecycle, reviewer trust boundary).
- Branch `pdftr-35a-orchestrator-safety-follow-up` created from the PDFTR-35 implementation SHA
  `1e3a3a7` (the findings live in code that only exists there). PDFTR-35 history is untouched.
- Graphify/CRG: the affected symbols are the same isolated `scripts` community; the CRG graph is
  reused. Source is authoritative.

## Integration defect found during preflight

`scripts/agent_cycle.py::validate_ticket_id` rejected the canonical follow-up ID `PDFTR-35A`
because `TICKET_PATTERN` allowed only `<LETTERS>-<digits>`, even though the repository already
contains `PDFTR-9A`, `PDFTR-10A`, `PDFTR-14A`, and `PDFTR-16A` artifacts. This blocked cycle
initialization for the ticket's own ID. Fixed minimally by allowing an optional uppercase suffix
(`^[A-Z][A-Z0-9]*-[1-9][0-9]*[A-Z]*$`) with the error text updated; path safety is unchanged. No
state-machine behavior changed.

## Investigation answers (ticket questions 1–12)

1. **Contradictory write instructions.**
   - `scripts/pi_ticket_cycle.py::_implementer_prompt`: "- Do NOT modify anything under
     .agent-cycle/." conflicts with required action 5, which demands writing
     `.agent-cycle/<TICKET>/implementer.json` (validated by `_handoff_path`/`_record_handoff`).
   - `.agents/skills/two-agent-ticket-workflow/REVIEWER_CONTRACT.md`: tells the reviewer to create
     the ignored coordination input itself ("The only permitted result is a structured reviewer
     input for the validator…"), while the runner grants only `read,grep,find,ls` and denies write.
   - `IMPLEMENTER_CONTRACT.md` and `REVIEWER_CONTRACT.md` also instruct agents to call
     `begin-implementation`, `handoff`, `begin-review`, and `record-review` manually, which the
     automated runner owns.

2. **Who writes reviewer JSON.** The runner does: `run_cycle` parses stdout, writes
   `reviewer-input-round-<n>.json`, then calls `record_review`. The reviewer only prints JSON.
   Runtime is correct; the prose contracts contradict it.

3. **How Pi is spawned.** `SubprocessExecutor.run` uses `subprocess.Popen(..., shell=False)`;
   `_platform_command` launches `.cmd`/`.bat` via `cmd.exe /c` and `.ps1` via `powershell -File`;
   the prompt is delivered on stdin; children start in a new process group/session.

4. **Can the current API terminate descendants reliably?** No. On Windows `taskkill /T /PID`
   traverses from the direct parent; once the parent exits it cannot find descendants. On POSIX
   `_signal_group` re-resolves `os.getpgid(pid)` after `process.wait()` reaps the parent, gets
   `ProcessLookupError`, and never sends `SIGKILL`. Both leave a descendant alive.

5. **Per-platform strategy.** Windows: create a Job Object with
   `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and assign the spawned process immediately; terminate with
   `TerminateJobObject`; closing the last handle also kills survivors. A local ctypes probe
   confirmed a grandchild survives the direct parent's exit yet dies when the job is terminated.
   POSIX: capture `os.getpgid(pid)` at spawn (parent is a session/group leader) and signal that
   saved group with `SIGTERM` then `SIGKILL`, polling `killpg(pgid, 0)` until the group is gone.

6. **Exception paths that bypass cleanup.** `SubprocessExecutor.run` only cleans up on
   `KeyboardInterrupt`. An `OSError`/`BrokenPipeError` from `communicate`, any failure while
   parsing/capturing output, or a failure writing the diagnostic log propagates without terminating
   the child; `_execute_child` then calls `stop_cycle` and clears the active role while the child
   (and descendants) may still run.

7. **How the parser locates JSON today.** `extract_review_json` compares sentinel *counts*, then
   `_json_objects` scans for every `{` and `json.JSONDecoder.raw_decode`s decodable objects, and
   accepts when exactly one dict was found anywhere in the text.

8. **Why contradictory/malformed output passes.** Scavenging accepts a valid nested object inside a
   malformed outer object and a valid object inside a top-level array. Reversed sentinel order is
   accepted because only counts are compared. A second object in a different envelope can be
   ignored.

9. **Minimum fail-closed parser change.** Choose exactly one supported envelope (a single ordered
   sentinel pair, else a single JSON fence, else the whole trimmed stdout); parse the *complete*
   envelope body with `json.loads` as exactly one object; reject arrays, trailing content,
   duplicate/unmatched/reversed delimiters, and any JSON object outside the envelope. `agent_cycle`
   remains the schema/verdict authority.

10. **Minimum child+descendant fixture.** A real Python parent that spawns a sleeping Python
    grandchild, writes the grandchild PID, and either keeps running (Ctrl+C case) or exits early
    (the bug case). Start it through the same group/job primitives and assert both PIDs are gone
    after cleanup. No LLM provider is involved.

11. **Dependency-free.** Yes. `ctypes`, `subprocess`, `os`, `signal`, `time`, and `json` are all
    standard library.

12. **Files that must change.**
    - `scripts/pi_ticket_cycle.py` (prompts, process tree, extraction, cleanup).
    - `tests/test_pi_ticket_cycle.py` (four findings' regression tests).
    - `.agents/skills/two-agent-ticket-workflow/IMPLEMENTER_CONTRACT.md`,
      `REVIEWER_CONTRACT.md`, `SKILL.md` (ownership consistency).
    - `README.md`, `CHANGELOG.md`, affected Wiki pages and log.
    - `scripts/agent_cycle.py` + `tests/test_agent_cycle.py` (suffixed-ID integration defect).

## Scope guard

No package/PDF/translation/render/OCR/model/cache code changes. No new dependency. No redesign of
`scripts/agent_cycle.py` beyond the suffixed-ID pattern fix.
