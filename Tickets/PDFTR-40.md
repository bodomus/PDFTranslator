# PDFTR-40 — Reviewer read-only Git inspection

## Summary

Extend the reviewer capability so an exact-SHA read-only review can independently verify Git state and diffs without granting general shell access.

PDFTR-39 exposed a workflow defect: the reviewer could inspect repository files but could not independently verify:

```text
git status / cleanliness
exact diff against base
reviewed SHA binding
merge-base / branch relationship
```

The reviewer therefore returned `BLOCKED` despite being able to inspect the implementation itself.

PDFTR-40 adds a narrowly scoped **read-only Git capability** for reviewers.

This is workflow infrastructure only.

Do not change product behavior.
Do not grant reviewer write access.
Do not replace the existing `read,grep,find,ls` allowlist with unrestricted shell access.

---

# Goal

Allow the reviewer to independently verify the Git facts required by the existing exact-SHA review contract while preserving technical read-only enforcement.

Conceptually:

```text
reviewer tools =
read
grep
find
ls
git-readonly
```

The reviewer must be able to inspect repository state, history, and diffs, but must not be able to mutate:

```text
working tree
index
refs
branches
tags
remotes
commits
stash
repository config
```

---

# Required reviewer Git operations

At minimum support read-only equivalents of:

```text
git status --porcelain
git diff
git diff <base>..<head>
git show <sha>
git rev-parse
git log
git merge-base
git branch --show-current
```

The exact implementation does not need to expose raw arbitrary Git command execution.

Prefer a constrained capability that models allowed operations explicitly.

---

# Forbidden Git operations

The reviewer must not be able to execute mutating operations such as:

```text
git add
git commit
git checkout
git switch
git restore
git reset
git clean
git merge
git rebase
git cherry-pick
git revert
git tag
git branch -D
git push
git pull
git fetch
git stash
git config
git remote
git update-ref
git apply
git am
```

Also forbid arbitrary shell command composition around Git.

The reviewer must not gain access to:

```text
bash
powershell
cmd
sh
python execution
arbitrary subprocess
```

through this ticket.

---

# Security model

The capability must be fail-closed.

Do not implement this as:

```text
allow "git" binary with arbitrary argv
```

because Git has command families and configuration/environment features that can execute helpers or mutate repository state.

The implementation must explicitly constrain both:

```text
operation
arguments
```

Prefer one of these designs:

```text
A. dedicated GitReadonly tool with explicit operations

or

B. internal wrapper that maps an enum/subcommand to pre-approved argv
```

Do not pass arbitrary reviewer-supplied command strings directly to `subprocess`.

---

# Required read-only queries

## 1. Working-tree status

Reviewer must be able to verify:

```text
working tree clean / dirty
staged changes
unstaged changes
untracked files
```

A porcelain status representation is sufficient.

Example semantic operation:

```text
status
```

Mapped internally to something equivalent to:

```text
git status --porcelain=v1
```

---

## 2. Exact SHA

Reviewer must independently resolve and verify the requested review SHA.

Required operations:

```text
rev-parse HEAD
rev-parse <sha>
```

The wrapper must validate revision arguments before invoking Git.

Do not permit revision syntax that can trigger filesystem writes or external helpers.

---

## 3. Diff against base

Reviewer must be able to inspect the exact implementation diff.

Required semantic operation:

```text
diff(base, head)
```

Use explicit validated commit-ish inputs.

Support the workflow's normal comparison semantics, including merge-base where required.

Do not allow reviewer-controlled diff output paths or external diff tools.

Disable external diff helpers/config where necessary.

---

## 4. Commit inspection

Reviewer must be able to inspect:

```text
commit metadata
changed files
patch
```

for an exact SHA.

Equivalent to a constrained `git show`.

No custom format string capable of invoking unexpected behavior is needed.

---

## 5. History / merge-base

Reviewer must be able to inspect enough history to answer:

```text
what is the base?
is head descended from expected base?
what changed between base and head?
```

Required semantic operations:

```text
merge_base(base, head)
log(base, head, bounded_count)
```

History output must be bounded.

---

# Environment hardening

Git read-only execution must neutralize mechanisms that could escape the intended capability.

Investigate and explicitly address at least:

```text
external diff drivers
GIT_EXTERNAL_DIFF
diff.external
textconv filters
pager execution
credential helpers
hooks where relevant
aliases
core.fsmonitor
SSH / transport helpers
submodules
repository-local config effects
```

The wrapper should use hardened environment/config flags where appropriate.

Examples to investigate:

```text
--no-pager
GIT_PAGER=
GIT_EXTERNAL_DIFF=
config overrides disabling external diff/textconv
no network operations
no repository mutation
```

Do not assume "read-only Git command" automatically means "safe process".

---

# Repository boundary

All Git inspection must remain inside the current repository root already bound to the ticket cycle.

Reviewer must not be able to point the wrapper at an arbitrary repository path.

The wrapper should receive the repository root from the runner/workflow, not from reviewer-controlled free-form input.

Do not support arbitrary:

```text
-C <path>
--git-dir
--work-tree
```

arguments.

---

# Integration with reviewer role

Existing reviewer safety remains:

```text
read,grep,find,ls
```

Add only the new Git-read capability.

Role/model presets from PDFTR-37 must continue to work:

```text
deepseek-codex
codex-deepseek
codex-codex
deepseek-deepseek
```

The reviewer gets Git-read capability regardless of provider/model identity.

The implementer must not be restricted by this reviewer-only tool policy.

---

# Exact-SHA review prompt integration

Update the reviewer prompt/contract so it explicitly requires independent verification of:

```text
current HEAD
working-tree cleanliness
exact reviewed SHA
diff against expected base
branch relationship / merge base
```

The reviewer should no longer return `BLOCKED` merely because ordinary file tools cannot perform Git inspection.

If Git-read capability itself fails or returns inconsistent state, reviewer should fail closed.

---

# State-machine behavior

Do not change:

```text
MAX_REVIEW_ROUNDS = 2
state transitions
handoff semantics
review verdict semantics
human merge ownership
```

PDFTR-40 only expands safe reviewer observability.

`agent_cycle.py` remains the authority for state and exact-SHA binding.

The Git-read tool is evidence for the reviewer, not a second state machine.

---

# Investigation

Before implementation, create:

```text
.implementation-plans/investigation-PDFTR-40.md
```

Answer at least:

1. How are Pi reviewer tools currently passed and enforced?
2. Can Pi expose a dedicated custom tool, or must the capability be represented through an existing mechanism?
3. What is the smallest integration point for a reviewer-only Git-read capability?
4. Which exact Git facts does the reviewer need beyond existing `agent_cycle.py` validation?
5. Why is arbitrary `git <argv>` unsafe even if intended as read-only?
6. Which Git read commands can trigger external helpers, filters, pagers, or repository-configured executables?
7. How will those execution paths be neutralized?
8. How will revision arguments be validated?
9. How will repository path escape be prevented?
10. How will output size be bounded?
11. How will Windows and POSIX invocation differ, if at all?
12. How will the tool remain provider/model independent?
13. Which files must change?
14. How will tests prove that mutating and escape attempts are rejected?
15. How will the reviewer prompt change?

Do not implement before investigation is complete.

---

# Preferred implementation shape

Prefer a small explicit interface such as:

```text
GitReadonlyInspector
```

with operations conceptually equivalent to:

```text
status()
head()
resolve_revision(revision)
diff(base, head)
show(commit)
merge_base(base, head)
log(base, head, limit)
current_branch()
```

Exact names are implementation-defined.

Do not build a generic command runner.

---

# Required tests

Add deterministic tests for successful read operations:

```text
status reports clean tree
status reports dirty/untracked tree
HEAD resolution
exact SHA resolution
current branch
base/head diff
commit show
merge-base
bounded log
```

Add rejection tests for attempts equivalent to:

```text
git add
git commit
git checkout
git reset
git clean
git push
git fetch
git config
git remote
git apply
git stash
arbitrary argv injection
repository path override
shell metacharacters
external diff execution
textconv execution
pager execution
alias-based escape
```

Also test:

```text
reviewer receives Git-read capability for every preset
implementer permissions unchanged
same-model Codex/Codex still uses separate contexts
reviewer remains unable to write files
existing read,grep,find,ls remain available
```

No real network access in tests.

---

# Security regression requirement

Add at least one test repository with malicious/local Git configuration attempting to execute a helper during a read operation.

The reviewer wrapper must neutralize it.

Examples worth covering:

```text
diff.external
custom diff driver
textconv
pager
alias
```

The test must prove the helper is not executed.

---

# Reviewer workflow regression

Add an end-to-end fake-cycle test where the reviewer can now obtain:

```text
HEAD
clean status
base/head diff
merge-base
```

and therefore does not need to return `BLOCKED` for missing Git observability.

Do not call a real model provider.

---

# Documentation

Update:

```text
README
CHANGELOG
two-agent workflow documentation
reviewer tool/safety documentation
```

Document clearly that:

```text
Git-read capability is constrained
it is not shell access
it cannot mutate the repository
it is reviewer-only
```

---

# Non-goals

Do not add:

```text
general shell access
GitHub API review integration
ChatGPT Work integration
automatic PR creation
automatic merge
single-agent mode
JEV
Pi-Harness
dynamic model routing
token/cost accounting
network Git operations
reviewer write permissions
```

---

# Quality gate

Run focused tests first, then:

```powershell
uv run pytest tests/test_pi_ticket_cycle.py tests/test_agent_cycle.py
uv run pytest
uv run python scripts/project_wiki/wiki_lint.py
.\scripts\check.ps1
```

Required:

```text
ruff format/check: PASS
mypy: PASS
full pytest: PASS
coverage threshold: PASS
Windows CI: PASS
Ubuntu CI: PASS
working tree: clean
```

---

# Workflow

For this ticket:

```text
implementer = Codex
reviewer    = Codex
```

Separate processes/contexts.

Recommended:

```powershell
uv run python scripts/pi_ticket_cycle.py PDFTR-40 --preset codex-codex
```

Maximum automatic review rounds remain 2.

No auto-merge.

---

# Reviewer checklist

Reviewer must explicitly verify:

```text
1. No arbitrary shell access was introduced.
2. No arbitrary Git argv execution exists.
3. Mutating Git operations are impossible through the new interface.
4. Repository path cannot be overridden.
5. External diff/textconv/pager/helper execution is neutralized.
6. HEAD/status/diff/show/merge-base/log work as intended.
7. Output is bounded where necessary.
8. Reviewer gets the capability for all presets.
9. Implementer behavior remains unchanged.
10. State machine and review-round semantics remain unchanged.
11. Existing process-safety guarantees remain intact.
12. Exact-SHA review can now independently verify Git state without BLOCKED due solely to missing Git inspection.
```

Any capability that permits repository mutation or generic command execution is `CHANGES_REQUIRED`.

---

# Completion criteria

PDFTR-40 is complete when:

```text
reviewer can independently inspect required Git facts
reviewer can verify exact SHA and clean state
reviewer can inspect exact diff and merge-base
capability is explicit and bounded
arbitrary shell is unavailable
mutating Git operations are unavailable
Git helper/config escape paths are neutralized
repository root is fixed
all role/model presets preserve reviewer safety
state machine remains unchanged
full local gate passes
Windows CI passes
Ubuntu CI passes
exact-SHA review returns PASS
```

Final merge remains a human decision.
