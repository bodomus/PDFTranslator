"""Run a sequential Pi implementer/reviewer cycle over scripts.agent_cycle.

This module owns process sequencing only. `scripts/agent_cycle.py` remains the sole authority
for ticket/branch/HEAD binding, ownership, review rounds, exact-SHA review, and fail-closed
state. Concrete provider and model names are configuration, never workflow concepts.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, Protocol

if __package__ in {None, ""}:  # pragma: no cover - supports `python scripts/pi_ticket_cycle.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.agent_cycle import (  # noqa: E402
    CycleError,
    begin_implementation,
    begin_review,
    collect_git_facts,
    cycle_directory,
    cycle_status,
    initialize_cycle,
    record_handoff,
    record_review,
    stop_cycle,
    validate_ticket_id,
)

REVIEW_SENTINEL_BEGIN = "<<<AGENT_CYCLE_REVIEW_JSON>>>"
REVIEW_SENTINEL_END = "<<<END_AGENT_CYCLE_REVIEW_JSON>>>"

# The reviewer is technically read-only: only these tools may ever be granted.
READ_ONLY_TOOLS = frozenset({"read", "grep", "find", "ls"})

IMPLEMENTER_FALLBACK = (
    "The implementer is the only repository writer. Implement the ticket, add tests, run the "
    "quality gate, commit, push, and prepare the handoff input. Never claim checks passed unless "
    "they actually ran."
)
REVIEWER_FALLBACK = (
    "The reviewer is strictly read-only. Do not modify, create, delete, commit, or push anything. "
    "Inspect the exact reviewed SHA and return one JSON verdict: PASS, CHANGES_REQUIRED, or "
    "BLOCKED. PASS has no findings; CHANGES_REQUIRED has findings; BLOCKED has a reason."
)
CONTRACT_DIRECTORY = Path(".agents") / "skills" / "two-agent-ticket-workflow"


class RunnerError(RuntimeError):
    """A fail-closed runner error; the cycle stops and control returns to the human."""


class RunnerCancelled(RunnerError):
    """The user cancelled an active Pi child process."""


@dataclass(frozen=True)
class RoleConfig:
    provider: str
    model: str
    tools: tuple[str, ...] = ()


DEFAULT_IMPLEMENTER = RoleConfig("deepseek", "deepseek-v4-pro")
DEFAULT_REVIEWER = RoleConfig("openai-codex", "gpt-6.1-sol", ("read", "grep", "find", "ls"))


@dataclass(frozen=True)
class RunnerConfig:
    implementer: RoleConfig = DEFAULT_IMPLEMENTER
    reviewer: RoleConfig = DEFAULT_REVIEWER
    base_branch: str = "master"
    executable: str = "pi"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class RunOutcome:
    ticket: str
    state: str
    branch: str
    implementation_sha: str
    review_rounds: int
    implementer: RoleConfig
    reviewer: RoleConfig
    stop_reason: str | None = None

    @property
    def passed(self) -> bool:
        return self.state == "PASSED"


class PiExecutor(Protocol):
    """Runs one Pi child process and returns its captured result."""

    def ensure_available(self) -> None: ...

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        log_path: Path,
        stdin_text: str,
    ) -> CommandResult: ...


def validate_reviewer_config(config: RunnerConfig) -> None:
    """Reject any reviewer configuration that is not explicitly read-only."""
    tools = config.reviewer.tools
    if not tools:
        raise RunnerError("reviewer tools must be a non-empty read-only allowlist")
    unknown = sorted(set(tools) - READ_ONLY_TOOLS)
    if unknown:
        raise RunnerError(
            f"reviewer tools must stay within {sorted(READ_ONLY_TOOLS)}; rejected: {unknown}"
        )


def resolve_executable(name: str) -> str:
    """Resolve a configured executable through PATH or fail with actionable guidance."""
    if os.path.dirname(name):
        candidate = Path(name)
        if candidate.is_file():
            return str(candidate.resolve())
    resolved = shutil.which(name)
    if resolved is None:
        raise RunnerError(
            f"Pi executable {name!r} was not found on PATH. Install Pi or pass --pi-executable."
        )
    return resolved


def _platform_command(executable: str, arguments: Sequence[str]) -> list[str]:
    suffix = Path(executable).suffix.lower()
    if suffix in {".cmd", ".bat"}:
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", executable, *arguments]
    if suffix == ".ps1":
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            executable,
            *arguments,
        ]
    return [executable, *arguments]


def _group_popen_kwargs() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _taskkill(pid: int, *, force: bool) -> None:
    arguments = ["taskkill", "/T", "/PID", str(pid)]
    if force:
        arguments.insert(1, "/F")
    subprocess.run(arguments, capture_output=True, text=True, check=False)


def _signal_group(pid: int, signum: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(os.getpgid(pid), signum)


def _terminate_process_tree(process: subprocess.Popen[str], grace_seconds: float) -> None:
    """Terminate an entire owned process tree with bounded terminate/kill escalation."""
    if os.name == "nt":
        _taskkill(process.pid, force=False)
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            _taskkill(process.pid, force=True)
            process.wait()
        else:
            _taskkill(process.pid, force=True)
        return
    _signal_group(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        _signal_group(process.pid, signal.SIGKILL)
        process.wait()
    else:
        _signal_group(process.pid, signal.SIGKILL)


@dataclass
class SubprocessExecutor:
    """Standard-library Pi executor with tree cancellation and diagnostic logging."""

    executable: str = "pi"
    grace_seconds: float = 10.0

    def ensure_available(self) -> None:
        resolve_executable(self.executable)

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        log_path: Path,
        stdin_text: str,
    ) -> CommandResult:
        resolved = resolve_executable(command[0])
        actual = _platform_command(resolved, list(command[1:]))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        process = subprocess.Popen(
            actual,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            **_group_popen_kwargs(),
        )
        try:
            stdout, stderr = process.communicate(input=stdin_text)
        except KeyboardInterrupt as error:
            _terminate_process_tree(process, self.grace_seconds)
            raise RunnerCancelled("active Pi child process was cancelled") from error
        _write_log(log_path, command, stdout, stderr)
        return CommandResult(process.returncode, stdout, stderr)


def _describe_command(command: Sequence[str]) -> str:
    described: list[str] = []
    redact_next = False
    for part in command:
        if redact_next:
            described.append(f"<{len(part)} chars>")
            redact_next = False
        elif part == "-p":
            described.append(part)
            redact_next = True
        else:
            described.append(part)
    return " ".join(described)


def _write_log(log_path: Path, command: Sequence[str], stdout: str, stderr: str) -> None:
    content = (
        f"$ {_describe_command(command)}\n\n"
        f"----- stdout -----\n{stdout}\n"
        f"----- stderr -----\n{stderr}\n"
    )
    log_path.write_text(content, encoding="utf-8")


def _pi_arguments(config: RoleConfig, executable: str) -> list[str]:
    arguments = [executable, "--provider", config.provider, "--model", config.model]
    if config.tools:
        arguments.extend(["--tools", ",".join(config.tools)])
    arguments.append("-p")
    return arguments


def extract_review_json(stdout: str) -> dict[str, Any]:
    """Extract exactly one unambiguous reviewer JSON object or fail closed.

    The prompt is delivered on stdin and Pi may wrap the result; accept exactly one JSON
    object anywhere in the output. Any second object, or an unmatched review delimiter,
    fails closed so a contradictory verdict can never be recorded.
    """
    if stdout.count(REVIEW_SENTINEL_BEGIN) != stdout.count(REVIEW_SENTINEL_END):
        raise RunnerError("reviewer output has unmatched review delimiters")
    objects = _json_objects(stdout)
    if len(objects) != 1:
        raise RunnerError(f"expected exactly one reviewer JSON result, found {len(objects)}")
    return objects[0]


def _json_objects(text: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    index = 0
    while index < len(text):
        start = text.find("{", index)
        if start < 0:
            break
        try:
            value, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            index = start + 1
            continue
        if isinstance(value, dict):
            objects.append(value)
        index = end
    return objects


def _load_ticket_text(repo_root: Path, ticket: str) -> str:
    directory = repo_root / "Tickets"
    matches = sorted(directory.glob(f"{ticket}*.md")) if directory.is_dir() else []
    if len(matches) != 1:
        raise RunnerError(
            f"expected exactly one ticket file matching Tickets/{ticket}*.md, found {len(matches)}"
        )
    return matches[0].read_text(encoding="utf-8")


def _load_contract(repo_root: Path, filename: str, fallback: str) -> str:
    path = repo_root / CONTRACT_DIRECTORY / filename
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return fallback


def _handoff_path(directory: Path) -> Path:
    return directory / "implementer.json"


def _read_manifest(repo_root: Path, ticket: str) -> dict[str, Any]:
    path = cycle_directory(repo_root, ticket) / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_findings(repo_root: Path, ticket: str, review_round: int) -> list[dict[str, Any]]:
    if review_round <= 0:
        return []
    artifact = cycle_directory(repo_root, ticket) / f"review-{review_round}.json"
    if not artifact.is_file():
        raise RunnerError(f"review artifact is missing: {artifact.name}")
    document = json.loads(artifact.read_text(encoding="utf-8"))
    findings = document.get("findings")
    return list(findings) if isinstance(findings, list) else []


def _implementer_prompt(
    *,
    ticket: str,
    ticket_text: str,
    contract: str,
    context: dict[str, Any],
    attempt: int,
    findings: list[dict[str, Any]],
    handoff_path: Path,
) -> str:
    sections = [
        f"You are the implementer for ticket {ticket} (attempt {attempt}).",
        "You are the only role permitted to modify project files, commit, or push.",
        "",
        "## Automated runner override (takes precedence over the contract below)",
        "The runner has already entered the implementer phase via scripts/agent_cycle.py.",
        "- Do NOT run scripts/agent_cycle.py or any begin-implementation, handoff, begin-review,",
        "  record-review, or stop transition. The runner owns every phase transition.",
        "- Do NOT modify anything under .agent-cycle/.",
        "- Only implement, test, commit, push, and prepare your handoff input, then exit.",
        "Any manual transition command in the reference contract below is superseded.",
        "",
        "## Ticket",
        ticket_text.strip(),
        "",
        "## Repository rules",
        "Follow AGENTS.md and .codex/PRE_TICKET_WORKFLOW.md. Preserve unrelated user changes.",
        "Keep scope ticket-focused and add or update tests for every behavior change.",
        "",
        "## Implementer contract (reference; manual transition steps are superseded)",
        contract.strip(),
        "",
        "## Current cycle context",
        f"branch: {context['branch']}",
        f"base_sha: {context['base_sha']}",
        f"head_sha: {context['head_sha']}",
        f"review_round: {context['review_round']}",
        "",
        "## Required actions",
        "1. Investigate and implement the smallest coherent change for this ticket.",
        "2. Run the focused tests and the repository quality gate.",
        "3. Commit the change with a clear message and push the task branch.",
        "4. Leave a clean working tree.",
        "5. Write the implementer handoff JSON to exactly this path:",
        f"   {handoff_path}",
        "   with exactly these keys:",
        json.dumps(
            {
                "schema_version": "1.0",
                "ticket": ticket,
                "implementation_attempt": attempt,
                "status": "COMPLETE",
                "implementation_report": (
                    f".implementation-reports/implementation-report-{ticket}.md"
                ),
                "focused_tests": "PASS",
                "full_tests": "PASS",
                "check_ps1": "PASS",
                "known_limitations": [],
                "notes": [],
            },
            indent=2,
        ),
        "The runner validates this file with scripts/agent_cycle.py; do not invent fields.",
        "Set focused_tests, full_tests, and check_ps1 honestly to PASS, FAIL, or NOT_RUN.",
    ]
    if attempt > 1:
        sections.extend(
            [
                "",
                "## Reviewer findings to address",
                "Produce a new commit (new SHA) that resolves these findings:",
                json.dumps(findings, indent=2),
            ]
        )
    return "\n".join(sections)


def _reviewer_prompt(
    *,
    ticket: str,
    ticket_text: str,
    contract: str,
    reviewed_sha: str,
    review_round: int,
) -> str:
    schema = {
        "schema_version": "1.0",
        "ticket": ticket,
        "review_round": review_round,
        "reviewed_sha": reviewed_sha,
        "verdict": "PASS",
        "findings": [],
        "blocked_reason": None,
    }
    return "\n".join(
        [
            f"You are the read-only reviewer for ticket {ticket}, review round {review_round}.",
            "",
            "## Automated runner override (takes precedence over the contract below)",
            "The runner has already entered the review phase via scripts/agent_cycle.py and owns",
            "record-review. You are strictly read-only and must not run any transition.",
            "- Do NOT run scripts/agent_cycle.py or any begin-review, record-review, or stop.",
            "- Do NOT modify, create, delete, commit, push, or run any command that writes.",
            "- Return only the single JSON object described below.",
            "Any manual transition command in the reference contract below is superseded.",
            "",
            f"Exact reviewed SHA: {reviewed_sha}",
            "",
            "## Ticket and acceptance criteria",
            ticket_text.strip(),
            "",
            "## Reviewer contract (reference; manual transition steps are superseded)",
            contract.strip(),
            "",
            "## Required output",
            "Return exactly one JSON object between these delimiters, with nothing outside them:",
            REVIEW_SENTINEL_BEGIN,
            json.dumps(schema, indent=2),
            REVIEW_SENTINEL_END,
            "Allowed verdicts: PASS, CHANGES_REQUIRED, BLOCKED.",
            "PASS has findings = []. CHANGES_REQUIRED has at least one finding.",
            "BLOCKED has a non-empty blocked_reason.",
            f"reviewed_sha must equal {reviewed_sha}.",
        ]
    )


def _sanitize_reason(reason: str) -> str:
    printable = "".join(character for character in reason if ord(character) >= 32)
    collapsed = " ".join(printable.split())
    return (collapsed or "runner stopped")[:200]


def _abort(repo_root: Path, ticket: str, reason: str) -> NoReturn:
    message = _sanitize_reason(reason)
    try:
        stop_cycle(repo_root, ticket, message)
    except CycleError as error:
        raise RunnerError(f"{message} (failed to record stop: {error})") from error
    raise RunnerError(message)


def _execute_child(
    executor: PiExecutor,
    command: Sequence[str],
    *,
    repo_root: Path,
    ticket: str,
    log_path: Path,
    stdin_text: str,
) -> CommandResult:
    try:
        return executor.run(command, cwd=repo_root, log_path=log_path, stdin_text=stdin_text)
    except RunnerCancelled:
        raise
    except Exception as error:  # noqa: BLE001 - normalize any operational failure into a clean stop
        _abort(repo_root, ticket, f"Pi process failure: {error}")


def _require_clean_tree(repo_root: Path, ticket: str, base_branch: str, role: str) -> None:
    facts = collect_git_facts(repo_root, base_branch)
    manifest = _read_manifest(repo_root, ticket)
    if facts.branch != manifest["branch"]:
        _abort(repo_root, ticket, f"unexpected branch after {role}: {facts.branch}")
    if not facts.clean:
        _abort(repo_root, ticket, f"{role} left a dirty working tree")


def _record_handoff(repo_root: Path, ticket: str, directory: Path, base_branch: str) -> None:
    handoff_file = _handoff_path(directory)
    if not handoff_file.is_file():
        _abort(repo_root, ticket, f"implementer did not produce {handoff_file.name}")
    try:
        manifest = record_handoff(repo_root, ticket, handoff_file)
    except CycleError as error:
        _abort(repo_root, ticket, f"handoff validation failed: {error}")
    facts = collect_git_facts(repo_root, base_branch)
    if manifest["current_head_sha"] != facts.head_sha:
        _abort(repo_root, ticket, "cycle HEAD does not match Git HEAD after handoff")


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")


def _outcome(manifest: dict[str, Any], config: RunnerConfig) -> RunOutcome:
    return RunOutcome(
        ticket=manifest["ticket"],
        state=manifest["state"],
        branch=manifest["branch"],
        implementation_sha=manifest["current_head_sha"],
        review_rounds=manifest["review_round"],
        implementer=config.implementer,
        reviewer=config.reviewer,
        stop_reason=manifest.get("stop_reason"),
    )


def run_cycle(
    repo_root: Path,
    ticket: str,
    *,
    executor: PiExecutor,
    config: RunnerConfig | None = None,
    ticket_text: str | None = None,
) -> RunOutcome:
    """Drive the sequential Pi cycle for one ticket; return the terminal outcome."""
    active_config = config or RunnerConfig()
    ticket = validate_ticket_id(ticket)
    validate_reviewer_config(active_config)
    repo_root = repo_root.resolve()
    executor.ensure_available()
    if ticket_text is None:
        ticket_text = _load_ticket_text(repo_root, ticket)
    implementer_contract = _load_contract(
        repo_root, "IMPLEMENTER_CONTRACT.md", IMPLEMENTER_FALLBACK
    )
    reviewer_contract = _load_contract(repo_root, "REVIEWER_CONTRACT.md", REVIEWER_FALLBACK)

    directory = cycle_directory(repo_root, ticket)
    if not directory.is_dir():
        initialize_cycle(repo_root, ticket, active_config.base_branch)
    status = cycle_status(repo_root, ticket)
    if status["errors"]:
        raise RunnerError("cycle preflight failed: " + "; ".join(status["errors"]))
    if status["state"] != "NEW":
        raise RunnerError(
            f"runner expects a NEW cycle but found {status['state']}; recover manually"
        )

    try:
        while True:
            begin_implementation(repo_root, ticket)
            manifest = _read_manifest(repo_root, ticket)
            attempt = manifest["review_round"] + 1
            findings = _load_findings(repo_root, ticket, manifest["review_round"])

            facts = collect_git_facts(repo_root, active_config.base_branch)
            implementer_prompt = _implementer_prompt(
                ticket=ticket,
                ticket_text=ticket_text,
                contract=implementer_contract,
                context={
                    "branch": facts.branch,
                    "base_sha": facts.base_sha,
                    "head_sha": facts.head_sha,
                    "review_round": manifest["review_round"],
                },
                attempt=attempt,
                findings=findings,
                handoff_path=_handoff_path(directory),
            )
            implementer_result = _execute_child(
                executor,
                _pi_arguments(active_config.implementer, active_config.executable),
                repo_root=repo_root,
                ticket=ticket,
                log_path=directory / f"pi-implementer-round-{attempt}.log",
                stdin_text=implementer_prompt,
            )
            if implementer_result.returncode != 0:
                _abort(
                    repo_root,
                    ticket,
                    f"implementer exited with code {implementer_result.returncode}",
                )
            _require_clean_tree(repo_root, ticket, active_config.base_branch, "implementer")
            _record_handoff(repo_root, ticket, directory, active_config.base_branch)

            manifest = _read_manifest(repo_root, ticket)
            reviewed_sha = manifest["current_head_sha"]
            begin_review(repo_root, ticket, reviewed_sha)
            manifest = _read_manifest(repo_root, ticket)
            review_round = manifest["review_round"]

            reviewer_prompt = _reviewer_prompt(
                ticket=ticket,
                ticket_text=ticket_text,
                contract=reviewer_contract,
                reviewed_sha=reviewed_sha,
                review_round=review_round,
            )
            reviewer_result = _execute_child(
                executor,
                _pi_arguments(active_config.reviewer, active_config.executable),
                repo_root=repo_root,
                ticket=ticket,
                log_path=directory / f"pi-reviewer-round-{review_round}.log",
                stdin_text=reviewer_prompt,
            )
            if reviewer_result.returncode != 0:
                _abort(
                    repo_root,
                    ticket,
                    f"reviewer exited with code {reviewer_result.returncode}",
                )

            try:
                document = extract_review_json(reviewer_result.stdout)
            except RunnerError as error:
                _abort(repo_root, ticket, f"reviewer output rejected: {error}")
            review_input = directory / f"reviewer-input-round-{review_round}.json"
            _write_json(review_input, document)
            try:
                manifest = record_review(repo_root, ticket, review_input)
            except CycleError as error:
                _abort(repo_root, ticket, f"review validation failed: {error}")

            if manifest["state"] == "CHANGES_REQUIRED":
                continue
            return _outcome(manifest, active_config)
    except KeyboardInterrupt:
        _abort(repo_root, ticket, "cancelled by user")
    except RunnerCancelled as error:
        _abort(repo_root, ticket, f"cancelled: {error}")
    except CycleError as error:
        raise RunnerError(f"agent cycle rejected the operation: {error}") from error


def _report(outcome: RunOutcome) -> None:
    if outcome.passed:
        print("AGENT CYCLE PASSED")
        print()
        print(f"Ticket: {outcome.ticket}")
        print(f"State: {outcome.state}")
        print(f"Implementation SHA: {outcome.implementation_sha}")
        print(f"Review rounds: {outcome.review_rounds}")
        print(f"Implementer: {outcome.implementer.provider} / {outcome.implementer.model}")
        print(f"Reviewer: {outcome.reviewer.provider} / {outcome.reviewer.model}")
        print()
        print("READY FOR HUMAN REVIEW")
        return
    print(f"AGENT CYCLE STOPPED: {outcome.state}")
    print()
    print(f"Ticket: {outcome.ticket}")
    print(f"Implementation SHA: {outcome.implementation_sha}")
    print(f"Review rounds: {outcome.review_rounds}")
    if outcome.stop_reason:
        print(f"Stop reason: {outcome.stop_reason}")
    print()
    print("HUMAN REVIEW REQUIRED")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticket")
    parser.add_argument("--base-branch", default="master")
    parser.add_argument("--pi-executable", default="pi")
    parser.add_argument("--implementer-provider", default=DEFAULT_IMPLEMENTER.provider)
    parser.add_argument("--implementer-model", default=DEFAULT_IMPLEMENTER.model)
    parser.add_argument("--reviewer-provider", default=DEFAULT_REVIEWER.provider)
    parser.add_argument("--reviewer-model", default=DEFAULT_REVIEWER.model)
    parser.add_argument("--reviewer-tools", default=",".join(DEFAULT_REVIEWER.tools))
    parser.add_argument("--ticket-file", type=Path)
    parser.add_argument("--repo-root", type=Path)
    return parser


def main(argv: list[str] | None = None, *, repo_root: Path | None = None) -> int:
    arguments = _parser().parse_args(argv)
    root = (repo_root or arguments.repo_root or Path.cwd()).resolve()
    reviewer_tools = tuple(
        tool.strip() for tool in arguments.reviewer_tools.split(",") if tool.strip()
    )
    config = RunnerConfig(
        implementer=RoleConfig(arguments.implementer_provider, arguments.implementer_model),
        reviewer=RoleConfig(arguments.reviewer_provider, arguments.reviewer_model, reviewer_tools),
        base_branch=arguments.base_branch,
        executable=arguments.pi_executable,
    )
    ticket_text: str | None = None
    if arguments.ticket_file is not None:
        ticket_text = arguments.ticket_file.read_text(encoding="utf-8")
    try:
        outcome = run_cycle(
            root,
            arguments.ticket,
            executor=SubprocessExecutor(arguments.pi_executable),
            config=config,
            ticket_text=ticket_text,
        )
    except RunnerError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    _report(outcome)
    return 0 if outcome.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
