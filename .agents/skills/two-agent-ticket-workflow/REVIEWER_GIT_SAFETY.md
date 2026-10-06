# Reviewer Git-read capability (PDFTR-40)

The Pi runner grants reviewers `read,grep,find,ls,git_readonly` for every role/model preset.
Implementer permissions are unchanged. Git-read is **not shell access** and cannot mutate the
working tree, index, refs, branches, tags, remotes, commits, stash or configuration.

The runner disables extension discovery and explicitly loads its trusted Git-read adapter plus,
when progress is enabled, the trusted `progress_append` extension. This diagnostic-only tool accepts
one short milestone, no paths, and appends only to the runner-bound reviewer journal. It rejects
redirected/hard-linked journals, controls and common credential patterns. It grants no repository
writes or shell access; operational policy forbids reasoning and sensitive content.
The adapter also blocks non-allowlisted tool calls. Pi still runs as its OS user: this is a
model-callable capability boundary, not a sandbox against compromised Pi/Node/Git binaries or
concurrent external writers. Existing file-reading tools are not a repository filesystem sandbox.

## Interface

Call `git_readonly` with exactly the fields for one operation:

| operation | Additional required fields |
| --- | --- |
| `status`, `head`, `current_branch` | none |
| `resolve_revision` | `revision` |
| `show` | `commit` |
| `diff`, `merge_base` | `base`, `head` |
| `log` | `base`, `head`, `limit` (integer 1–100) |
| `working_diff` | `staged` (boolean; false = unstaged, true = index) |

Revisions accept only literal `HEAD` or a full hexadecimal commit SHA (40 or 64 characters),
resolved and verified as a commit. No branch-name/revision expressions, custom argv, paths,
formats, environment overrides or output files are accepted. Unknown operations/fields fail.
`diff` compares exact endpoints, not an implicit three-dot range: query `merge_base` first and
use that result as `base` when the review calls for merge-base semantics. `show` provides fixed
metadata, file statistics and patch; `log` gives fixed SHA/parents/subject records.

Root comes exclusively from the runner-bound cwd at session start. Git receives explicit fixed
`--git-dir` and `--work-tree`. Redirecting gitfiles, symlinked Git directories, alternate object
stores and partial clones are unsupported and fail closed. Any `.git/commondir` entry is rejected
before a Git subprocess, even if empty or self-referential: linked-worktree/common-directory
layouts are intentionally unsupported. The guard checks the entry itself without following it
or reading the redirected store. Ordinary repositories without `commondir` remain supported.
Submodules are not traversed.

## Hardening and bounds

- Direct Node `execFile` invocation with `shell=false`; no model-provided executable or argv.
  Resolve Git to an absolute executable from absolute PATH entries outside the repository,
  preventing current-directory/relative-PATH executable hijacking.
- No pager, external diff, textconv or signature verification programs.
- No fsmonitor, hooks, recursive submodules, optional index locks or network protocols.
- All configured clean/smudge/process filter drivers are disabled, with `required=false`;
  unsupported filter names fail closed. Required-filter content can therefore appear dirty:
  do not execute a filter to repair the evidence; return `BLOCKED` if it prevents verification.
- Inherited `GIT_*` routing/config/helper/trace variables are stripped. Replacement objects and
  lazy fetch are disabled; promisor config/objects are rejected even on older Git versions.
- Built-in commands cannot be replaced by aliases. Credentials/transport helpers have no reachable
  network operation; credential helper is explicitly cleared and protocols denied.
- Local/system/global configuration is read to preserve legitimate Windows line-ending semantics,
  but executable mechanisms are neutralized by fixed flags and overrides. Config reading itself
  never executes aliases or helpers.
- Each Git subprocess has a 30-second timeout and 4-MiB stdout/stderr cap; cancellation propagates.
  Exceeding bounds returns an error, never a silently truncated patch or an output file.

Reviewers must independently verify current HEAD, clean porcelain status, requested SHA,
expected branch, base/head diff and merge-base relationship using this capability. Failed or
inconsistent evidence means `BLOCKED`; missing ordinary shell access alone is not a blocker.
The validator remains the only cycle state/exact-SHA authority; verdict and two-round semantics
are unchanged. Final review and merge remain human decisions.

Tests use small local repositories and Node 22 (Pi's existing runtime), with no model or network.
CI explicitly installs Node for the deterministic inspector tests on Windows and Ubuntu.
