"""Exercise real disk mutations in disposable repositories and fresh Python processes."""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests import test_pi_ticket_cycle as cycle_tests
from tests.test_pi_ticket_cycle import (
    REPOSITORY_ROOT,
    TICKET,
    FakePi,
    _config,
    _git,
    _state,
)

# Reuse existing repository-local fixtures without importing shadowed names.
git_repo = cycle_tests.git_repo
work_dir = cycle_tests.work_dir

HARNESS = (
    "agent_cycle",
    "agent_progress",
    "pi_ticket_cycle",
    "project_tracking",
    "tracking_hooks",
    "review_protocol",
    "pre_handoff_retry_policy",
    "independent_review_policy",
    "independent_review_continuation_policy",
    "cycle_ownership",
)


def _copy_harness(root: Path) -> None:
    (root / "scripts").mkdir()
    (root / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    for name in HARNESS:
        shutil.copyfile(REPOSITORY_ROOT / "scripts" / f"{name}.py", root / "scripts" / f"{name}.py")


def _child(root: Path, source: str, *args: str) -> None:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COV_CORE_", "COVERAGE_PROCESS_")) and key != "PYTHONPATH"
    }
    result = subprocess.run(
        [sys.executable, "-c", source, *args],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("symbol", ["OPERATIONAL_CODES", "complete_operational_prelaunch"])
def test_tracking_never_imports_new_runner_generation(work_dir: Path, symbol: str) -> None:
    _copy_harness(work_dir)
    # Simulate an older state module with neither later-generation symbol.
    (work_dir / "scripts/agent_cycle.py").write_text("GENERATION = 'A'\n", encoding="utf-8")
    _child(
        work_dir,
        """
import json
import sys
from pathlib import Path
from scripts import agent_cycle, project_tracking, review_protocol
assert not hasattr(agent_cycle, sys.argv[1])
assert 'scripts.pi_ticket_cycle' not in sys.modules
original = review_protocol.single_envelope
Path('scripts/pi_ticket_cycle.py').write_text(
    'from scripts.agent_cycle import ' + sys.argv[1] + '\\n', encoding='utf-8')
Path('scripts/review_protocol.py').write_text(
    "raise RuntimeError('new generation')", encoding='utf-8')
body = json.dumps({'verdict': 'PASS'})
stdout = review_protocol.REVIEW_SENTINEL_BEGIN + body + review_protocol.REVIEW_SENTINEL_END
assert project_tracking.review_without_intent(stdout, 'PDFTR-46') == stdout
assert project_tracking.single_envelope is original
assert review_protocol.single_envelope(stdout)[0] == body
assert 'scripts.pi_ticket_cycle' not in sys.modules
# Counterfactual: loading the on-disk runner really reproduces the reported ImportError.
try:
    __import__('scripts.pi_ticket_cycle')
except ImportError as error:
    assert sys.argv[1] in str(error)
else:
    raise AssertionError('mismatch was not reproduced')
""",
        symbol,
    )


@pytest.mark.parametrize("verdict", ["PASS", "CHANGES_REQUIRED"])
def test_cli_snapshot_records_review_after_source_mutation(git_repo: Path, verdict: str) -> None:
    _copy_harness(git_repo)
    (git_repo / ".gitignore").write_text("/.agent-cycle/\n__pycache__/\n", encoding="utf-8")
    _git(git_repo, "add", ".")
    _git(git_repo, "commit", "-m", "startup harness snapshot")
    _child(
        git_repo,
        """
import json
import runpy
import subprocess
import sys
from pathlib import Path
# Like direct CLI execution, this does not register scripts.pi_ticket_cycle.
runner = runpy.run_path('scripts/pi_ticket_cycle.py', run_name='snapshot_runner')
assert 'scripts.pi_ticket_cycle' not in sys.modules
from scripts import agent_cycle, review_protocol
original_protocol = review_protocol.single_envelope
root = Path.cwd()
ticket = 'PDFTR-35'

def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()

class Pi:
    implementations = 0
    reviews = 0
    def ensure_available(self):
        pass
    def run(self, command, *, cwd, log_path, stdin_text, heartbeat=None):
        log_path.write_text('preserved reviewer/implementer log', encoding='utf-8')
        directory = root / '.agent-cycle' / ticket
        if stdin_text.startswith('You are the implementer'):
            self.implementations += 1
            # Version B expects a symbol absent from the startup agent_cycle.
            assert not hasattr(agent_cycle, 'pdftr46_new_prelaunch')
            Path('scripts/pi_ticket_cycle.py').write_text(
                'from scripts.agent_cycle import pdftr46_new_prelaunch\\n', encoding='utf-8')
            for name in ('agent_cycle', 'project_tracking', 'tracking_hooks',
                         'agent_progress', 'review_protocol', 'pre_handoff_retry_policy',
                         'independent_review_policy', 'independent_review_continuation_policy',
                         'cycle_ownership'):
                Path('scripts/' + name + '.py').write_text(
                    "raise RuntimeError('adopted new harness generation')\\n", encoding='utf-8')
            Path('tracked.txt').write_text('attempt ' + str(self.implementations), encoding='utf-8')
            git('add', '.')
            git('commit', '-m', 'mutate harness attempt ' + str(self.implementations))
            handoff = dict(schema_version='1.0', ticket=ticket,
                implementation_attempt=self.implementations, status='COMPLETE',
                implementation_report='.implementation-reports/implementation-report-PDFTR-35.md',
                focused_tests='PASS', full_tests='PASS', check_ps1='PASS',
                known_limitations=[], notes=[])
            (directory / 'implementer.json').write_text(json.dumps(handoff), encoding='utf-8')
            return runner['CommandResult'](0, '', '')
        self.reviews += 1
        verdict = sys.argv[1] if self.reviews == 1 else 'PASS'
        finding = dict(id='R1', severity='HIGH', file='tracked.txt', symbol='example',
            problem='defect', required_fix='fix', regression_test='test')
        document = dict(schema_version='1.0', ticket=ticket, review_round=self.reviews,
            reviewed_sha=git('rev-parse', 'HEAD'), verdict=verdict,
            findings=[finding] if verdict == 'CHANGES_REQUIRED' else [], blocked_reason=None)
        stdout = (review_protocol.REVIEW_SENTINEL_BEGIN + json.dumps(document)
            + review_protocol.REVIEW_SENTINEL_END)
        return runner['CommandResult'](0, stdout, '')

pi = Pi()
result = runner['run_cycle'](root, ticket, executor=pi,
    config=runner['RunnerConfig'](base_branch='master'))
assert result.state == 'PASSED'
assert pi.reviews == pi.implementations == (1 if sys.argv[1] == 'PASS' else 2)
directory = root / '.agent-cycle' / ticket
first = json.loads((directory / 'review-1.json').read_text(encoding='utf-8'))
assert first['verdict'] == sys.argv[1]
manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
assert not manifest.get('human_recoveries')
assert 'scripts.pi_ticket_cycle' not in sys.modules
assert review_protocol.single_envelope is original_protocol
assert (directory / 'reviewer-stdout-round-1.txt').read_text(encoding='utf-8')
assert (directory / 'pi-reviewer-round-1.log').read_text(encoding='utf-8')
""",
        verdict,
    )


def test_harness_dependency_graph_is_startup_only() -> None:
    edges: dict[str, set[str]] = {}
    for name in HARNESS:
        tree = ast.parse((REPOSITORY_ROOT / "scripts" / f"{name}.py").read_text(encoding="utf-8"))
        startup = {id(node) for node in tree.body}
        edges[name] = set()
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0, "audit relative harness imports explicitly"
                modules = (
                    [f"scripts.{alias.name}" for alias in node.names]
                    if node.module == "scripts"
                    else [node.module or ""]
                )
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.Call):
                # No dynamic harness imports/hot-loading in the parent.
                function = ast.unparse(node.func)
                assert function not in {
                    "__import__",
                    "importlib.import_module",
                    "importlib.reload",
                    "runpy.run_path",
                    "runpy.run_module",
                }
            for module in modules:
                if module.startswith("scripts."):
                    assert id(node) in startup, f"late harness import in {name}: {module}"
                    edges[name].add(module.split(".")[1])
    reachable: set[str] = set()
    pending = list(edges["project_tracking"])
    while pending:
        name = pending.pop()
        if name not in reachable:
            reachable.add(name)
            pending.extend(edges.get(name, set()))
    assert "pi_ticket_cycle" not in reachable
    assert edges["review_protocol"] == set()


@pytest.mark.parametrize("stage", ["review_without_intent", "record_review"])
def test_internal_post_review_error_retains_evidence(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    import scripts.pi_ticket_cycle as runner

    fake = FakePi(git_repo)

    def fail(*args: object) -> None:
        raise ImportError("synthetic harness mismatch")

    monkeypatch.setattr(runner, stage, fail)
    with pytest.raises(runner.RunnerError, match="internal runner failure.*ImportError"):
        runner.run_cycle(git_repo, TICKET, executor=fake, config=_config())
    assert _state(git_repo) == "STOPPED"
    directory = git_repo / ".agent-cycle" / TICKET
    assert '"verdict": "PASS"' in (directory / "reviewer-stdout-round-1.txt").read_text("utf-8")
    assert (directory / "pi-reviewer-round-1.log").read_text("utf-8") == "fake pi log\n"
    assert (directory / "handoff.json").is_file()
    assert not (directory / "review-1.json").exists()
    with pytest.raises(runner.RunnerError):
        runner.run_cycle(git_repo, TICKET, executor=fake, config=_config())
    assert fake.reviewer_runs == 1
