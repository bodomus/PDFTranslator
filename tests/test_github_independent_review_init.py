"""Explicit trusted first-use initialization through the production CLI."""

from __future__ import annotations

import io
import json
import subprocess
import threading

import pytest
from scripts import github_independent_review as review_cli
from scripts.agent_cycle import (
    begin_implementation,
    begin_review,
    initialize_cycle,
    record_handoff,
    record_review,
)
from scripts.github_review_facts import GitHubFactsProvider
from scripts.independent_review import IndependentReviewStore
from scripts.independent_review_dispatch import DispatchReceipt

TICKET = "PDFTR-50"


def git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()


@pytest.fixture
def cli_cycle(tmp_path, monkeypatch):
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init", "-b", "master")
    git(root, "config", "user.name", "Independent Review Tests")
    git(root, "config", "user.email", "review@example.invalid")
    (root / ".gitignore").write_text("/.agent-cycle/\n/temp/\n", encoding="utf-8")
    git(root, "add", ".gitignore")
    git(root, "commit", "-m", "fixture")
    git(root, "switch", "-c", "task")
    initialize_cycle(root, TICKET)
    config = {
        "schema_version": "1.0",
        "repository": "owner/repo",
        "ticket": TICKET,
        "pull_request": 123,
        "required_checks": ["windows", "ubuntu"],
    }
    config_path = tmp_path / "protected-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.chdir(root)
    monkeypatch.setenv("PDFTR_REVIEW_CONFIG", str(config_path))
    for name in ("GITHUB_TOKEN", "PDFTR_REVIEW_ENDPOINT", "PDFTR_REVIEW_TOKEN"):
        monkeypatch.delenv(name, raising=False)

    def forbidden(*_args):
        pytest.fail("initialization must not construct GitHub/provider review transports")

    monkeypatch.setattr(review_cli, "GitHubFactsProvider", forbidden)
    monkeypatch.setattr(review_cli, "HTTPSReviewDispatcher", forbidden)
    store = IndependentReviewStore(root, root / ".agent-cycle" / TICKET, config)
    return root, config_path, store


@pytest.fixture
def eligible_cli(cli_cycle, monkeypatch):
    root, _, store = cli_cycle
    begin_implementation(root, TICKET)
    implementer = store.directory / "implementer-input.json"
    implementer.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "ticket": TICKET,
                "implementation_attempt": 1,
                "status": "COMPLETE",
                "implementation_report": (
                    ".implementation-reports/implementation-report-PDFTR-50.md"
                ),
                "focused_tests": "PASS",
                "full_tests": "PASS",
                "check_ps1": "PASS",
                "known_limitations": [],
                "notes": [],
            }
        ),
        encoding="utf-8",
    )
    record_handoff(root, TICKET, implementer)
    head = git(root, "rev-parse", "HEAD")
    begin_review(root, TICKET, head)
    reviewer = store.directory / "reviewer-input.json"
    reviewer.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "ticket": TICKET,
                "review_round": 1,
                "reviewed_sha": head,
                "verdict": "PASS",
                "findings": [],
                "blocked_reason": None,
            }
        ),
        encoding="utf-8",
    )
    record_review(root, TICKET, reviewer)
    reads, calls = [], []

    def read(path):
        reads.append(path)
        if "/pulls/" in path:
            return {
                "number": 123,
                "draft": False,
                "merged": False,
                "state": "open",
                "head": {"sha": head, "ref": "task", "repo": {"full_name": "owner/repo"}},
                "base": {"sha": "b" * 40, "repo": {"full_name": "owner/repo"}},
            }
        if "/check-runs" in path:
            return {
                "total_count": 2,
                "check_runs": [
                    {"name": name, "head_sha": head, "status": "completed", "conclusion": "success"}
                    for name in ("windows", "ubuntu")
                ],
            }
        return {"full_name": "owner/repo"}

    provider = GitHubFactsProvider(store.config, read)

    class Dispatcher:
        def dispatch(self, request):
            assert store.load()["reviews"][request.generation - 1]["status"] == "REQUESTED"
            calls.append(request)
            return DispatchReceipt("DISPATCHED", "opaque-123")

    monkeypatch.setattr(review_cli, "GitHubFactsProvider", lambda *_: provider)
    monkeypatch.setattr(review_cli, "HTTPSReviewDispatcher", lambda *_: Dispatcher())
    monkeypatch.setenv("GITHUB_TOKEN", "unused-test-token")
    monkeypatch.setenv("PDFTR_REVIEW_ENDPOINT", "https://connector.example.test")
    monkeypatch.setenv("PDFTR_REVIEW_TOKEN", "unused-test-token")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "check_run")
    monkeypatch.setattr(review_cli.sys, "stdin", io.TextIOWrapper(io.BytesIO(b"{}")))
    return reads, calls


def test_cli_fresh_init_without_transport_credentials(cli_cycle, capsys):
    root, _, store = cli_cycle
    before = {p.name: p.read_bytes() for p in store.directory.iterdir()}
    head = git(root, "rev-parse", "HEAD")
    assert review_cli.main(["init", TICKET]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["decision"] == "INITIALIZED"
    state = store.load()
    assert state["current_generation"] == 0
    assert state["reviews"] == []
    assert state["ticket"] == TICKET
    assert state["repository"] == "owner/repo"
    assert state["pull_request"] == 123
    assert output["state"] == state
    assert {p.name: p.read_bytes() for p in store.directory.iterdir() if p.name in before} == before
    assert not list(store.directory.glob("independent-dispatch-*.json"))
    assert git(root, "rev-parse", "HEAD") == head
    assert git(root, "status", "--porcelain") == ""


def test_cli_second_init_rejects_without_changing_bytes(cli_cycle, capsys):
    _, _, store = cli_cycle
    assert review_cli.main(["init", TICKET]) == 0
    capsys.readouterr()
    before = store.path.read_bytes()
    assert review_cli.main(["init", TICKET]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "decision": "INVALID",
        "reason": "state_already_exists",
    }
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("command", ["evaluate", "signal"])
def test_cli_event_without_init_fails_closed(cli_cycle, eligible_cli, capsys, command):
    _, _, store = cli_cycle
    _, calls = eligible_cli
    assert review_cli.main([command, TICKET]) == 1
    assert json.loads(capsys.readouterr().out)["decision"] == "INVALID"
    assert not store.path.exists()
    assert calls == []


def test_cli_initialized_eligible_flow_dispatches_once(cli_cycle, eligible_cli, capsys):
    root, _, store = cli_cycle
    reads, calls = eligible_cli
    assert review_cli.main(["init", TICKET]) == 0
    capsys.readouterr()
    assert reads == [] and calls == []
    assert review_cli.main(["signal", TICKET]) == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "ELIGIBLE"
    assert review_cli.main(["evaluate", TICKET]) == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "ALREADY_REQUESTED"
    state = store.load()
    assert state["current_generation"] == 1
    assert len(state["reviews"]) == len(calls) == 1
    assert state["reviews"][0]["status"] == "RUNNING"
    assert calls[0].head_sha == git(root, "rev-parse", "HEAD")
    assert calls[0].base_sha == "b" * 40


@pytest.mark.parametrize("command", ["evaluate", "signal"])
def test_cli_deleted_used_history_never_reinitialized(cli_cycle, eligible_cli, capsys, command):
    _, _, store = cli_cycle
    _, calls = eligible_cli
    assert review_cli.main(["init", TICKET]) == 0
    assert review_cli.main(["signal", TICKET]) == 0
    assert len(calls) == 1
    capsys.readouterr()
    store.path.unlink()
    assert review_cli.main([command, TICKET]) == 1
    assert json.loads(capsys.readouterr().out)["decision"] == "INVALID"
    assert not store.path.exists()
    assert len(calls) == 1


@pytest.mark.parametrize("corrupt", [b"{malformed", b"{}"])
def test_cli_init_preserves_corrupt_history(cli_cycle, capsys, corrupt):
    _, _, store = cli_cycle
    store.path.write_bytes(corrupt)
    assert review_cli.main(["init", TICKET]) == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "state_already_exists"
    assert store.path.read_bytes() == corrupt


@pytest.mark.parametrize("change", ["absent", "ticket", "checks", "malformed"])
def test_cli_init_rejects_invalid_trusted_configuration(cli_cycle, capsys, change):
    _, config_path, store = cli_cycle
    if change == "absent":
        config_path.unlink()
    elif change == "malformed":
        config_path.write_text("{credential-sentinel", encoding="utf-8")
    else:
        config = dict(store.config)
        config["ticket" if change == "ticket" else "required_checks"] = (
            "PDFTR-49" if change == "ticket" else []
        )
        config_path.write_text(json.dumps(config), encoding="utf-8")
    assert review_cli.main(["init", TICKET]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "decision": "INVALID",
        "reason": "trusted_evaluation_failed",
    }
    assert not store.path.exists()


@pytest.mark.parametrize("change", ["absent", "branch", "dirty", "head", "repository", "handoff"])
def test_cli_init_rejects_invalid_harness_context(cli_cycle, capsys, change):
    root, _, store = cli_cycle
    manifest_path = store.directory / "manifest.json"
    if change == "absent":
        manifest_path.unlink()
    elif change == "branch":
        git(root, "switch", "master")
    elif change == "dirty":
        (root / ".gitignore").write_text("dirty\n", encoding="utf-8")
    elif change == "head":
        git(root, "commit", "--allow-empty", "-m", "unexpected head")
    elif change == "repository":
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["repository_fingerprint"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    else:
        (store.directory / "handoff.json").write_text("{}", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in store.directory.iterdir()}
    assert review_cli.main(["init", TICKET]) == 1
    assert json.loads(capsys.readouterr().out)["decision"] == "INVALID"
    assert not store.path.exists()
    assert {p.name: p.read_bytes() for p in store.directory.iterdir()} == before


def test_cli_concurrent_init_has_one_complete_state(cli_cycle, monkeypatch):
    _, _, store = cli_cycle
    entered, release = threading.Event(), threading.Event()
    persist = IndependentReviewStore._persist

    def blocked(self, state):
        entered.set()
        assert release.wait(10)
        persist(self, state)

    monkeypatch.setattr(IndependentReviewStore, "_persist", blocked)
    results, errors = [], []

    def worker():
        try:
            results.append(review_cli.main(["init", TICKET]))
        except Exception as error:
            errors.append(error)

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        assert entered.wait(10)
        assert not store.path.exists()
        assert review_cli.main(["init", TICKET]) == 1
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive() and not errors
    assert results == [0]
    assert store.load()["current_generation"] == 0
    assert store.load()["reviews"] == []
    assert list((store.root / "temp" / "independent-review").iterdir()) == []
