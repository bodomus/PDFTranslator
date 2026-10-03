# PDFTR-40 investigation (complete before implementation)

Level 2; baseline task branch matches supplied context, tree initially clean. Python/uv workflow unchanged. Ticket already exists at Tickets/PDFTR-40.md. No ticket-service or Context7 tool is exposed in this session; external documentation is verified against the installed Pi docs/source and Git help instead. No product/PDF/model/OCR changes.

## Findings and design answers

1. `scripts/pi_ticket_cycle.py` passes `--tools` to each reviewer child; `validate_reviewer_config` rejects anything outside read/grep/find/ls. Installed Pi `dist/cli/args.js` documents that the allowlist applies to custom tools too.
2. Pi supports `registerTool`, TypeBox parameters and explicit `--extension`. Installed `docs/extensions.md`, packages/configuration/settings docs and `examples/extensions/hello.ts` verify this. `--no-extensions` suppresses discovery but preserves explicit extensions.
3. Smallest integration: reviewer-only explicit extension, registered `git_readonly` tool with fixed operation enum. Disable other extension discovery for reviewer only. Retain file tools; implementer invocation unchanged. Separate dependency-free Node inspector module makes real Git security tests provider-free.
4. Reviewer needs independently observed HEAD, full requested SHA resolution, clean/staged/unstaged/untracked status, branch, exact base/head diff, commit show, merge-base and bounded history. Validator still owns all cycle state.
5. Arbitrary git argv permits write commands, output files, config overrides, path overrides and helper execution. Shell strings compound this risk.
6. Diff/show can invoke external diff and textconv; pagers can execute commands; status can invoke fsmonitor; lazy object fetch can invoke transports/credentials; aliases can execute shell; submodule recursion can inspect other repositories. Local core.worktree/config and inherited GIT_* can redirect the repository.
7. Fixed argv, shell=false, no pager, no external diff/textconv, fsmonitor=false, optional locks off, ignore submodules, hooks disabled, protocol.allow=never, credential.helper cleared, lazy fetch disabled. Strip inherited GIT_* and constrain executable config effects. Initial design considered disabling system/global config; experiments below explain why safe line-ending semantics must instead be preserved. Use explicit trusted --git-dir and --work-tree. Only built-in operations (aliases cannot replace them). Reject promisor repositories to avoid implicit fetch even on older Git; reject redirected/symlink .git and alternates. Config remains readable for Git repository format, but executable paths are neutralized by flags and overrides.
8. Revisions are only literal HEAD or a full 40/64 hex object ID; resolve to a commit before diff/show/log/merge-base. No free refs, revision expressions, options, pathspecs or format strings.
9. Capture runner cwd as repository root at session start; it is not a tool parameter. Require physical .git under that root, reject gitfiles/symlinks/alternates. Explicit fixed git-dir/work-tree defeats local core.worktree. Unsupported layouts fail closed rather than follow an arbitrary path.
10. Every process has a timeout and maxBuffer; overflow fails (never silently truncates evidence). Log count is integer 1..100, fixed metadata format. No output files.
11. Node execFile invokes git directly on Windows and POSIX; shell=false on both. OS null-device config uses NUL or /dev/null. Abort signal propagates to bounded child execution; runner's existing process-tree containment stays unchanged.
12. Extension is selected by role, not provider/model, for all four presets. Separate child contexts persist, including Codex/Codex.
13. Runner, reviewer extension/inspector, focused tests, reviewer contract/skill, README, CHANGELOG, affected workflow Wiki, plan/report/review.
14. Tests use repository-local temp fixtures, real small Git repos and Node (no provider/network). Exercise successful operations, reject unknown operations/extra keys/revision/shell/path injection, malicious helper configuration and unchanged tree/index/refs. Fake cycle independently queries evidence before PASS; all presets assert extension/tool routing and unchanged implementer policy.
15. Prompt supplies expected base/branch and SHA, explicitly requires independent git_readonly evidence and BLOCKED on failures/inconsistency, not merely absence of shell.

## Source/graph validation

ProjectWiki search `agent cycle` points to workflow page; source confirms run_cycle -> _pi_arguments -> executor and _reviewer_prompt; agent_cycle owns transitions and MAX_REVIEW_ROUNDS. Existing FakePi tests provide separate sequential contexts and permission regression points. Graphify query `pi_ticket_cycle` identified the runner, FakePi and validator/test neighborhood, alongside broad shared-import neighbors; source confirms only workflow scripts are relevant (existing graph not authoritative). `code-review-graph update --brief` rebuilt the FTS index but output failed with cp1251 UnicodeEncodeError; retry with PYTHONIOENCODING=utf-8 planned. Scope is workflow scripts only, not translation modules. No important implementation claims rely on graph results.

## Validation

Focused inspector and runner tests, requested runner/validator tests, full pytest, Wiki lint, scripts/check.ps1. Remote CI and exact-SHA review are subsequent runner/human evidence, not claims this implementation can make in advance.

## Experimental refinements

- Windows Git stores `core.autocrlf=true` in system configuration on this host. Disabling system config falsely marked CRLF fixtures dirty. Preserve system/global/local non-executable semantics, override executable paths, and read effective config only through fixed internal config queries (not a reviewer config operation).
- Status and working-tree diff can invoke clean/process filters while hashing files. Discover configured filter names using NUL-delimited name-only output, reject unsupported names, and explicitly disable clean/smudge/process plus required flags for every driver. Malicious filter regressions pass.
- CRG retry with `PYTHONIOENCODING=utf-8 code-review-graph update --brief` succeeded. It identifies runner/config/prompt changes; its reported test gaps are false negatives verified against preset, unsafe-tool, prompt and fake-cycle tests.
- Installed Pi `--no-extensions --extension ./scripts/reviewer_git/extension.ts --offline --help` loaded without errors, confirming adapter imports/API against the actual runtime without a provider call.
