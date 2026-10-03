"""Real local Git, no model providers, no network; Node is Pi's existing runtime."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests import test_pi_ticket_cycle as cycle_tests
from tests.test_pi_ticket_cycle import REPOSITORY_ROOT, TASK_BRANCH, _git, _inspect_git

git_repo = cycle_tests.git_repo
work_dir = cycle_tests.work_dir


def test_read_operations_and_no_mutation(git_repo: Path) -> None:
    base = _git(git_repo, "rev-parse", "HEAD")
    assert _inspect_git(git_repo, {"operation": "status"}) == ""
    assert _inspect_git(git_repo, {"operation": "head"}) == base
    assert _inspect_git(git_repo, {"operation": "resolve_revision", "revision": base}) == base
    assert _inspect_git(git_repo, {"operation": "current_branch"}).strip() == TASK_BRANCH
    (git_repo / "tracked.txt").write_text("second\n", encoding="utf-8")
    _git(git_repo, "add", "tracked.txt")
    _git(git_repo, "commit", "-m", "second")
    head = _git(git_repo, "rev-parse", "HEAD")
    index = (git_repo / ".git/index").read_bytes()
    config = (git_repo / ".git/config").read_bytes()
    refs = _git(git_repo, "show-ref")
    assert "+second" in _inspect_git(git_repo, {"operation": "diff", "base": base, "head": head})
    shown = _inspect_git(git_repo, {"operation": "show", "commit": head})
    assert head in shown and "second" in shown and "tracked.txt" in shown
    assert (
        _inspect_git(git_repo, {"operation": "merge_base", "base": base, "head": head}).strip()
        == base
    )
    history = _inspect_git(git_repo, {"operation": "log", "base": base, "head": head, "limit": 1})
    assert len(history.splitlines()) == 1 and head in history
    assert _inspect_git(git_repo, {"operation": "status"}) == ""
    assert (git_repo / ".git/index").read_bytes() == index
    assert (git_repo / ".git/config").read_bytes() == config
    assert _git(git_repo, "show-ref") == refs


def test_dirty_staged_unstaged_untracked(git_repo: Path) -> None:
    (git_repo / "tracked.txt").write_text("staged\n", encoding="utf-8")
    _git(git_repo, "add", "tracked.txt")
    (git_repo / "tracked.txt").write_text("unstaged\n", encoding="utf-8")
    (git_repo / "new.txt").write_text("untracked\n", encoding="utf-8")
    index = (git_repo / ".git/index").read_bytes()
    status = _inspect_git(git_repo, {"operation": "status"})
    assert "MM tracked.txt" in status and "?? new.txt" in status
    assert "+staged" in _inspect_git(git_repo, {"operation": "working_diff", "staged": True})
    assert "+unstaged" in _inspect_git(git_repo, {"operation": "working_diff", "staged": False})
    assert (git_repo / ".git/index").read_bytes() == index


@pytest.mark.parametrize(
    "operation",
    [
        "add",
        "commit",
        "checkout",
        "switch",
        "restore",
        "reset",
        "clean",
        "merge",
        "rebase",
        "cherry-pick",
        "revert",
        "tag",
        "branch",
        "push",
        "pull",
        "fetch",
        "stash",
        "config",
        "remote",
        "update-ref",
        "apply",
        "am",
        "bash",
        "powershell",
        "cmd",
        "sh",
        "python",
    ],
)
def test_mutating_or_shell_operations_rejected(git_repo: Path, operation: str) -> None:
    with pytest.raises(RuntimeError, match="unsupported"):
        _inspect_git(git_repo, {"operation": operation})
    assert _git(git_repo, "status", "--porcelain") == ""


@pytest.mark.parametrize(
    "revision",
    [
        "--output=escape",
        "--git-dir=../other",
        "HEAD; echo escape",
        "HEAD && git clean -fd",
        "$(touch escaped)",
        "HEAD^{tree}",
        "HEAD:tracked.txt",
        "HEAD~1",
        "master",
        "../other",
        "a" * 39,
        "z" * 40,
        "a" * 40 + "\n",
        "HEAD\x00",
        42,
    ],
)
def test_revision_injection_rejected(git_repo: Path, revision: object) -> None:
    with pytest.raises(RuntimeError, match="revision must"):
        _inspect_git(git_repo, {"operation": "resolve_revision", "revision": revision})


@pytest.mark.parametrize(
    "field", ["argv", "command", "cwd", "root", "git_dir", "work_tree", "output", "format", "env"]
)
def test_extra_arguments_and_repo_override_rejected(git_repo: Path, field: str) -> None:
    with pytest.raises(RuntimeError, match="unexpected"):
        _inspect_git(git_repo, {"operation": "status", field: "escape"})


@pytest.mark.parametrize("limit", [0, 101, -1, "1", True, 1.5])
def test_log_limit_rejected(git_repo: Path, limit: object) -> None:
    with pytest.raises(RuntimeError, match="log limit"):
        _inspect_git(git_repo, {"operation": "log", "base": "HEAD", "head": "HEAD", "limit": limit})


def test_malicious_git_helpers_not_executed(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = git_repo / "escaped.txt"
    command = f"echo escaped > '{marker.as_posix()}'"
    for key in (
        "diff.external",
        "diff.evil.command",
        "diff.evil.textconv",
        "core.pager",
        "pager.diff",
        "pager.show",
        "core.fsmonitor",
        "credential.helper",
        "core.sshCommand",
    ):
        _git(git_repo, "config", key, command)
    _git(git_repo, "config", "alias.escape", "!" + command)
    _git(git_repo, "config", "alias.diff", "!" + command)
    _git(git_repo, "config", "log.showSignature", "true")
    _git(git_repo, "config", "gpg.program", command)
    (git_repo / ".gitattributes").write_text("tracked.txt diff=evil\n", encoding="utf-8")
    (git_repo / "tracked.txt").write_text("malicious test\n", encoding="utf-8")
    # Positive control: this config genuinely executes a helper with ordinary Git.
    _git(git_repo, "diff")
    assert marker.exists()
    marker.unlink()
    monkeypatch.setenv("GIT_EXTERNAL_DIFF", command)
    monkeypatch.setenv("GIT_PAGER", command)
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.fsmonitor")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", command)
    head = _inspect_git(git_repo, {"operation": "head"})
    for query in [
        {"operation": "status"},
        {"operation": "working_diff", "staged": False},
        {"operation": "diff", "base": head, "head": head},
        {"operation": "show", "commit": head},
        {"operation": "current_branch"},
        {"operation": "log", "base": head, "head": head, "limit": 10},
    ]:
        _inspect_git(git_repo, query)
    assert not marker.exists()
    with pytest.raises(RuntimeError, match="unsupported"):
        _inspect_git(git_repo, {"operation": "escape"})


def test_local_worktree_and_inherited_routing_cannot_escape(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _git(git_repo, "rev-parse", "HEAD")
    _git(git_repo, "config", "core.worktree", str(git_repo.parent))
    monkeypatch.setenv("GIT_DIR", str(git_repo.parent))
    monkeypatch.setenv("GIT_WORK_TREE", str(git_repo.parent))
    monkeypatch.setenv("GIT_INDEX_FILE", str(git_repo / "escaped-index"))
    assert _inspect_git(git_repo, {"operation": "head"}) == expected
    assert _inspect_git(git_repo, {"operation": "status"}) == ""
    assert not (git_repo / "escaped-index").exists()


def test_missing_commit_fails_closed(git_repo: Path) -> None:
    with pytest.raises(RuntimeError, match="Git inspection failed"):
        _inspect_git(git_repo, {"operation": "show", "commit": "0" * 40})


def test_partial_clone_and_alternates_rejected(git_repo: Path) -> None:
    _git(git_repo, "config", "remote.origin.promisor", "true")
    with pytest.raises(RuntimeError, match="partial clone"):
        _inspect_git(git_repo, {"operation": "head"})
    _git(git_repo, "config", "--unset", "remote.origin.promisor")
    (git_repo / ".git/objects/info/alternates").write_text(str(git_repo.parent), encoding="utf-8")
    with pytest.raises(RuntimeError, match="alternate object"):
        _inspect_git(git_repo, {"operation": "head"})


def test_gitfile_redirect_rejected(git_repo: Path) -> None:
    root = git_repo / "nested"
    root.mkdir()
    (root / ".git").write_text(f"gitdir: {git_repo / '.git'}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="physical .git"):
        _inspect_git(root, {"operation": "head"})


@pytest.mark.parametrize("relative_redirect", [False, True])
def test_commondir_foreign_repository_escape_rejected(
    git_repo: Path, work_dir: Path, relative_redirect: bool
) -> None:
    original_head = _inspect_git(git_repo, {"operation": "head"})
    _git(work_dir, "init", "-b", TASK_BRANCH)
    _git(work_dir, "config", "user.name", "Foreign Repository Fixture")
    _git(work_dir, "config", "user.email", "foreign@example.invalid")
    (work_dir / "foreign.txt").write_text("foreign evidence\n", encoding="utf-8")
    _git(work_dir, "add", "foreign.txt")
    _git(work_dir, "commit", "-m", "foreign commit")
    foreign_head = _git(work_dir, "rev-parse", "HEAD")
    assert foreign_head != original_head

    target = work_dir / ".git"
    redirect = (
        Path(os.path.relpath(target, git_repo / ".git")).as_posix()
        if relative_redirect
        else target.as_posix()
    )
    (git_repo / ".git/commondir").write_text(redirect + "\n", encoding="utf-8")
    # Positive control: explicit --git-dir / --work-tree alone follow the foreign store.
    assert (
        _git(
            git_repo,
            f"--git-dir={git_repo / '.git'}",
            f"--work-tree={git_repo}",
            "rev-parse",
            "HEAD",
        )
        == foreign_head
    )
    queries = [
        {"operation": "head"},
        {"operation": "status"},
        {"operation": "current_branch"},
        {"operation": "resolve_revision", "revision": foreign_head},
        {"operation": "show", "commit": foreign_head},
        {"operation": "diff", "base": original_head, "head": foreign_head},
        {"operation": "merge_base", "base": original_head, "head": foreign_head},
        {"operation": "log", "base": original_head, "head": foreign_head, "limit": 1},
        {"operation": "working_diff", "staged": False},
        {"operation": "working_diff", "staged": True},
    ]
    for query in queries:
        with pytest.raises(RuntimeError, match="common-directory redirects.*unsupported"):
            _inspect_git(git_repo, query)


@pytest.mark.parametrize("redirect", [".\n", ""])
def test_commondir_layout_is_explicitly_unsupported(git_repo: Path, redirect: str) -> None:
    (git_repo / ".git/commondir").write_text(redirect, encoding="utf-8")
    with pytest.raises(RuntimeError, match="common-directory redirects.*linked worktrees"):
        _inspect_git(git_repo, {"operation": "head"})


def test_output_limit_fails_closed(git_repo: Path) -> None:
    (git_repo / "large.txt").write_text("a" * (5 * 1024 * 1024) + "\n", encoding="utf-8")
    _git(git_repo, "add", "large.txt")
    _git(git_repo, "commit", "-m", "large patch")
    with pytest.raises(RuntimeError, match="output limit"):
        _inspect_git(git_repo, {"operation": "show", "commit": "HEAD"})


@pytest.mark.parametrize("line_ending", ["\n", "\r\n"])
def test_adapter_has_read_only_runtime_guard_and_fixed_root(line_ending: str) -> None:
    # Execute the actual adapter without Pi/provider dependencies: strip only TS imports/types;
    # a minimal schema stub is enough to capture its registered tool and event handlers.
    script = r"""
import { readFileSync } from 'node:fs';
import { GitReadonlyInspector, OPERATIONS } from './scripts/reviewer_git/inspector.mjs';
let source = readFileSync('./scripts/reviewer_git/extension.ts', 'utf8');
source = source.replace(/\r\n/g, '\n').replace(/\n/g, process.argv[1]);
source = source.replace(/^import .*;\r?\n/gm, '').replace('export default function', 'function')
  .replace(': ExtensionAPI', '').replace(': GitReadonlyInspector', '');
const Type = new Proxy({}, {get: () => (...args) => args});
const handlers = {}; let tool;
const pi = {on: (name, callback) => handlers[name] = callback, registerTool: value => tool = value};
// Invoke the factory defined in source with the fake API.
const factory = new Function('Type', 'GitReadonlyInspector', 'OPERATIONS',
  'return (' + source + ');')
  (Type, GitReadonlyInspector, OPERATIONS);
factory(pi);
for (const name of ['write','edit','bash','powershell','cmd','python']) {
  if (!handlers.tool_call({toolName: name}).block) throw new Error('write/shell allowed');
}
for (const name of ['read','grep','find','ls','git_readonly']) {
  if (handlers.tool_call({toolName: name})) throw new Error('read blocked');
}
let failed = false;
try { await tool.execute('id', {operation:'head'}); } catch { failed = true; }
if (!failed) throw new Error('uninitialized tool did not fail closed');
console.log(tool.name);
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, line_ending],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "git_readonly"


@pytest.mark.parametrize(
    "helper",
    [
        "diff.external",
        "diff.evil.command",
        "diff.evil.textconv",
        "filter.evil.clean",
        "filter.evil.process",
    ],
)
def test_each_configured_helper_is_neutralized(git_repo: Path, helper: str) -> None:
    marker = git_repo / "escaped.txt"
    command = f"echo escaped > '{marker.as_posix()}'"
    (git_repo / ".gitattributes").write_text(
        "tracked.txt diff=evil filter=evil\n", encoding="utf-8"
    )
    (git_repo / "tracked.txt").write_text("dirty helper fixture\n", encoding="utf-8")
    _git(git_repo, "config", helper, command)
    for query in [
        {"operation": "status"},
        {"operation": "working_diff", "staged": False},
        {"operation": "show", "commit": "HEAD"},
    ]:
        output = _inspect_git(git_repo, query)
        assert output
    assert not marker.exists()


def test_repository_executable_cannot_hijack_git(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _git(git_repo, "rev-parse", "HEAD")
    name = "git.exe" if os.name == "nt" else "git"
    (git_repo / name).write_text("not a trusted executable", encoding="utf-8")
    (git_repo / name).chmod(0o755)
    monkeypatch.setenv("PATH", str(git_repo) + os.pathsep + os.environ["PATH"])
    assert _inspect_git(git_repo, {"operation": "head"}) == expected


def test_process_policy_and_validation_before_spawn(git_repo: Path) -> None:
    result = subprocess.run(
        ["node", "tests/reviewer_git_process_test.mjs", str(git_repo)],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "process policy PASS" in result.stdout


def test_real_abort_fails_closed(git_repo: Path) -> None:
    inspector = (REPOSITORY_ROOT / "scripts/reviewer_git/inspector.mjs").as_uri()
    script = (
        f"import {{GitReadonlyInspector}} from '{inspector}';"
        "const controller = new AbortController(); controller.abort();"
        "try { await new GitReadonlyInspector(process.argv[1])"
        ".query({operation:'status'}, controller.signal);"
        "process.exitCode = 1; } catch (error) { console.log(error.message); }"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(git_repo)],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "aborted" in result.stdout.lower()
