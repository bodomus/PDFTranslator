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
import re
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
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
    reopen_cycle,
    stop_cycle,
    validate_ticket_id,
)
from scripts.project_tracking import (  # noqa: E402
    INTENT_HELP,
    child_environment,
    review_without_intent,
)
from scripts.tracking_hooks import TrackingHooks  # noqa: E402

REVIEW_SENTINEL_BEGIN = "<<<AGENT_CYCLE_REVIEW_JSON>>>"
REVIEW_SENTINEL_END = "<<<END_AGENT_CYCLE_REVIEW_JSON>>>"
_JSON_FENCE = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n?```", re.DOTALL)

# The reviewer is technically read-only: only these tools may ever be granted.
READ_ONLY_TOOLS = frozenset({"read", "grep", "find", "ls", "git_readonly"})
REVIEWER_EXTENSION = Path(__file__).resolve().parent / "reviewer_git" / "extension.ts"

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

_CREATE_SUSPENDED = getattr(subprocess, "CREATE_SUSPENDED", 0x00000004)


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
DEFAULT_REVIEWER = RoleConfig(
    "openai-codex", "gpt-6.1-sol", ("read", "grep", "find", "ls", "git_readonly")
)
HEARTBEAT_SECONDS = 5 * 60


@dataclass(frozen=True)
class RolePreset:
    implementer: RoleConfig
    reviewer: RoleConfig


_CODEX_IMPLEMENTER = RoleConfig(DEFAULT_REVIEWER.provider, DEFAULT_REVIEWER.model)
_DEEPSEEK_REVIEWER = RoleConfig(
    DEFAULT_IMPLEMENTER.provider, DEFAULT_IMPLEMENTER.model, DEFAULT_REVIEWER.tools
)
ROLE_PRESETS = {
    "deepseek-codex": RolePreset(DEFAULT_IMPLEMENTER, DEFAULT_REVIEWER),
    "codex-deepseek": RolePreset(_CODEX_IMPLEMENTER, _DEEPSEEK_REVIEWER),
    "codex-codex": RolePreset(_CODEX_IMPLEMENTER, DEFAULT_REVIEWER),
    "deepseek-deepseek": RolePreset(DEFAULT_IMPLEMENTER, _DEEPSEEK_REVIEWER),
}


def _console_message(message: str) -> None:
    print(message, flush=True)


@dataclass(frozen=True)
class ProgressReporter:
    """Lifecycle only; never receives prompts or captured child output."""

    ticket: str
    emit: Callable[[str], None] = _console_message

    def message(self, message: str) -> None:
        self.emit(f"[{self.ticket}] {message}")

    def heartbeat(self, role: str, elapsed: float) -> None:
        self.message(f"{role} running... {int(elapsed // 60)}m")


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
        heartbeat: Callable[[float], None] | None = None,
    ) -> CommandResult: ...


def validate_reviewer_config(config: RunnerConfig) -> None:
    """Reject any reviewer configuration that is not explicitly read-only."""
    tools = config.reviewer.tools
    if not tools:
        raise RunnerError("reviewer tools must be a non-empty read-only allowlist")
    if "git_readonly" not in tools:
        raise RunnerError("reviewer tools must include git_readonly for independent Git evidence")
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
        return {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | _CREATE_SUSPENDED,
        }
    return {"start_new_session": True}


def _taskkill(pid: int, *, force: bool) -> None:
    arguments = ["taskkill", "/T", "/PID", str(pid)]
    if force:
        arguments.insert(1, "/F")
    subprocess.run(arguments, capture_output=True, text=True, check=False)


def _signal_group(pgid: int, signum: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(pgid, signum)


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


if os.name == "nt":  # pragma: no cover - Windows-only Job Object integration
    import ctypes
    from ctypes import wintypes

    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _JOBOBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _JOBOBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOBOBJECT_BASIC_ACCOUNTING_INFORMATION = 1
    _TH32CS_SNAPTHREAD = 0x00000004
    _THREAD_SUSPEND_RESUME = 0x0002
    _THREAD_RESUME_FAILED = 0xFFFFFFFF
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_void_p),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimitInformation),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _BasicAccountingInformation(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", wintypes.LARGE_INTEGER),
            ("TotalKernelTime", wintypes.LARGE_INTEGER),
            ("ThisPeriodTotalUserTime", wintypes.LARGE_INTEGER),
            ("ThisPeriodTotalKernelTime", wintypes.LARGE_INTEGER),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]

    class _ThreadEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", ctypes.c_long),
            ("tpDeltaPri", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
        ]

    _KERNEL32.CreateJobObjectW.restype = wintypes.HANDLE
    _KERNEL32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    _KERNEL32.SetInformationJobObject.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    )
    _KERNEL32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    _KERNEL32.QueryInformationJobObject.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    _KERNEL32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    _KERNEL32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _KERNEL32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _KERNEL32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    _KERNEL32.Thread32First.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ThreadEntry32))
    _KERNEL32.Thread32Next.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ThreadEntry32))
    _KERNEL32.OpenThread.restype = wintypes.HANDLE
    _KERNEL32.OpenThread.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _KERNEL32.ResumeThread.restype = wintypes.DWORD
    _KERNEL32.ResumeThread.argtypes = (wintypes.HANDLE,)

    def _create_job_object(process: subprocess.Popen[str]) -> int | None:
        job = _KERNEL32.CreateJobObjectW(None, None)
        if not job or job == _INVALID_HANDLE_VALUE:
            return None
        try:
            limit = _ExtendedLimitInformation()
            limit.BasicLimitInformation.LimitFlags = _JOBOBJECT_LIMIT_KILL_ON_JOB_CLOSE
            configured = _KERNEL32.SetInformationJobObject(
                job,
                _JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(limit),
                ctypes.sizeof(limit),
            )
            if not configured:
                _KERNEL32.CloseHandle(job)
                return None
            if not _KERNEL32.AssignProcessToJobObject(job, wintypes.HANDLE(process._handle)):
                _KERNEL32.CloseHandle(job)
                return None
            return job
        except BaseException:
            # A KeyboardInterrupt during setup must not leak the job or its members.
            _KERNEL32.CloseHandle(job)
            raise

    def _job_active_processes(job: int) -> int:
        accounting = _BasicAccountingInformation()
        returned = wintypes.DWORD(0)
        queried = _KERNEL32.QueryInformationJobObject(
            job,
            _JOBOBJECT_BASIC_ACCOUNTING_INFORMATION,
            ctypes.byref(accounting),
            ctypes.sizeof(accounting),
            ctypes.byref(returned),
        )
        if not queried:
            return -1
        return int(accounting.ActiveProcesses)

    def _resume_thread(handle: Any) -> int:
        return int(_KERNEL32.ResumeThread(handle))

    def _resume_suspended_process(pid: int) -> tuple[int, bool]:
        """Resume the suspended thread(s) of a process; return (threads resumed, failed)."""
        snapshot = _KERNEL32.CreateToolhelp32Snapshot(_TH32CS_SNAPTHREAD, 0)
        if not snapshot or snapshot == _INVALID_HANDLE_VALUE:
            return 0, True
        resumed = 0
        failed = False
        try:
            entry = _ThreadEntry32()
            entry.dwSize = ctypes.sizeof(_ThreadEntry32)
            present = _KERNEL32.Thread32First(snapshot, ctypes.byref(entry))
            while present:
                if entry.th32OwnerProcessID == pid:
                    thread = _KERNEL32.OpenThread(_THREAD_SUSPEND_RESUME, False, entry.th32ThreadID)
                    if thread:
                        if _resume_thread(thread) == _THREAD_RESUME_FAILED:
                            failed = True
                        else:
                            resumed += 1
                        _KERNEL32.CloseHandle(thread)
                present = _KERNEL32.Thread32Next(snapshot, ctypes.byref(entry))
        finally:
            _KERNEL32.CloseHandle(snapshot)
        return resumed, failed

    class _WindowsProcessTree:
        def __init__(self, process: subprocess.Popen[str]) -> None:
            self._process = process
            self._job: int | None = None
            try:
                self._job = _create_job_object(process)
                if self._job is None:
                    raise RunnerError(
                        "could not establish a Windows Job Object for process containment; "
                        "refusing to run an uncontrolled child"
                    )
                resumed, failed = _resume_suspended_process(process.pid)
                if failed or resumed == 0:
                    raise RunnerError(
                        "could not resume the suspended Pi process; refusing to treat an "
                        "uncontained child as started"
                    )
            except BaseException:
                # Closing the job terminates a suspended or partially resumed child tree.
                self._close_job()
                raise

        def _close_job(self) -> None:
            if self._job is not None:
                _KERNEL32.CloseHandle(self._job)
                self._job = None

        def terminate(self, grace_seconds: float) -> bool:
            if self._job is None:
                return self._process.poll() is not None
            if _job_active_processes(self._job) == 0:
                return True
            if self._process.poll() is None:
                _taskkill(self._process.pid, force=False)
                if self._wait_until_empty(grace_seconds):
                    return True
            _KERNEL32.TerminateJobObject(self._job, 1)
            return self._wait_until_empty(grace_seconds)

        def close(self) -> None:
            self._close_job()

        def _wait_until_empty(self, timeout: float) -> bool:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                self._process.poll()
                if _job_active_processes(self._job) == 0:
                    return True
                time.sleep(0.05)
            self._process.poll()
            return _job_active_processes(self._job) == 0


class _PosixProcessTree:
    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process
        try:
            self._pgid: int | None = os.getpgid(process.pid)
        except (ProcessLookupError, OSError):
            self._pgid = None

    def terminate(self, grace_seconds: float) -> bool:
        if self._pgid is None:
            return True
        _signal_group(self._pgid, signal.SIGTERM)
        if self._wait_until_empty(grace_seconds):
            return True
        _signal_group(self._pgid, signal.SIGKILL)
        return self._wait_until_empty(grace_seconds)

    def close(self) -> None:
        self._pgid = None

    def _wait_until_empty(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._process.poll()
            if not _group_exists(self._pgid):
                return True
            time.sleep(0.05)
        self._process.poll()
        return not _group_exists(self._pgid)


def _new_process_tree(process: subprocess.Popen[str]) -> Any:
    if os.name == "nt":
        return _WindowsProcessTree(process)
    return _PosixProcessTree(process)


def _terminate_without_tree(process: subprocess.Popen[str], grace_seconds: float) -> None:
    """Best-effort termination when the tree guard could not be established after spawn."""
    if os.name == "nt":
        _taskkill(process.pid, force=True)
    else:
        try:
            pgid = os.getpgid(process.pid)
        except (ProcessLookupError, OSError):
            pgid = None
        if pgid is not None:
            _signal_group(pgid, signal.SIGKILL)
    with contextlib.suppress(OSError):
        process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired, OSError):
        process.wait(timeout=grace_seconds)


@dataclass
class SubprocessExecutor:
    """Standard-library Pi executor with owned process-tree cleanup and diagnostics."""

    executable: str = "pi"
    grace_seconds: float = 10.0
    heartbeat_seconds: float = HEARTBEAT_SECONDS

    def ensure_available(self) -> None:
        resolve_executable(self.executable)

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        log_path: Path,
        stdin_text: str,
        heartbeat: Callable[[float], None] | None = None,
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
            env=child_environment(),
            **_group_popen_kwargs(),
        )
        try:
            tree = _new_process_tree(process)
        except BaseException:
            _terminate_without_tree(process, self.grace_seconds)
            raise
        try:
            stdout, stderr = self._communicate(process, stdin_text, heartbeat)
        except BaseException as error:
            cleanup_error = self._cleanup(tree, process, "failure")
            if cleanup_error is not None:
                raise cleanup_error from error
            if isinstance(error, KeyboardInterrupt):
                raise RunnerCancelled("active Pi child process was cancelled") from error
            raise
        else:
            cleanup_error = self._cleanup(tree, process, "completion")
            if cleanup_error is not None:
                raise cleanup_error
            _write_log(log_path, command, stdout, stderr)
            return CommandResult(process.returncode, stdout, stderr)
        finally:
            tree.close()

    def _communicate(
        self,
        process: subprocess.Popen[str],
        stdin_text: str,
        heartbeat: Callable[[float], None] | None,
    ) -> tuple[str, str]:
        if heartbeat is None:
            return process.communicate(input=stdin_text)
        started = time.monotonic()
        pending_input: str | None = stdin_text
        while True:
            try:
                return process.communicate(input=pending_input, timeout=self.heartbeat_seconds)
            except subprocess.TimeoutExpired:
                # communicate retains partial output and input progress across timeout retries.
                pending_input = None
                if process.poll() is None:
                    heartbeat(time.monotonic() - started)

    def _cleanup(
        self, tree: Any, process: subprocess.Popen[str], context: str
    ) -> RunnerError | None:
        try:
            terminated = tree.terminate(self.grace_seconds)
        except OSError as error:
            return RunnerError(f"failed to terminate the Pi process tree during {context}: {error}")
        try:
            if process.poll() is None:
                process.wait(timeout=self.grace_seconds)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(OSError):
                process.kill()
            process.wait()
        if not terminated:
            return RunnerError(
                f"could not confirm termination of the Pi process tree during {context}"
            )
        return None


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


def _pi_arguments(config: RoleConfig, executable: str, *, reviewer: bool = False) -> list[str]:
    arguments = [executable, "--provider", config.provider, "--model", config.model]
    if reviewer:
        arguments.extend(["--no-extensions", "--extension", str(REVIEWER_EXTENSION)])
    if config.tools:
        arguments.extend(["--tools", ",".join(config.tools)])
    arguments.append("-p")
    return arguments


def extract_review_json(stdout: str) -> dict[str, Any]:
    """Extract exactly one reviewer JSON object from exactly one supported envelope.

    Envelopes are, in priority order: a single ordered sentinel pair, else a single JSON fence,
    else the whole trimmed stdout. The complete envelope body must parse as one JSON object with
    unique member names and no trailing content. Any extra object, duplicate/reversed/unmatched
    delimiter, array, duplicate key, malformed or truncated body fails closed. `agent_cycle`
    remains the authority for validating the object.
    """
    body, outside = _single_envelope(stdout)
    if "{" in outside:
        raise RunnerError("reviewer output contains JSON text outside the result envelope")
    body = body.strip()
    if not body:
        raise RunnerError("reviewer result envelope is empty")
    try:
        document = json.loads(body, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as error:
        raise RunnerError(f"reviewer result is not valid JSON: {error}") from error
    if not isinstance(document, dict):
        raise RunnerError("reviewer result must be a single JSON object")
    return document


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RunnerError(f"reviewer result contains duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _single_envelope(stdout: str) -> tuple[str, str]:
    begin_count = stdout.count(REVIEW_SENTINEL_BEGIN)
    end_count = stdout.count(REVIEW_SENTINEL_END)
    if begin_count or end_count:
        if begin_count != 1 or end_count != 1:
            raise RunnerError("reviewer output has duplicate or unmatched review delimiters")
        begin = stdout.find(REVIEW_SENTINEL_BEGIN)
        end = stdout.find(REVIEW_SENTINEL_END)
        if end < begin:
            raise RunnerError("reviewer output has reversed review delimiters")
        body = stdout[begin + len(REVIEW_SENTINEL_BEGIN) : end]
        outside = stdout[:begin] + stdout[end + len(REVIEW_SENTINEL_END) :]
        return body, outside
    matches = list(_JSON_FENCE.finditer(stdout))
    if matches:
        if len(matches) != 1:
            raise RunnerError("reviewer output has multiple fenced results")
        match = matches[0]
        body = match.group(1)
        outside = stdout[: match.start()] + stdout[match.end() :]
        return body, outside
    return stdout, ""


def _load_ticket_text(repo_root: Path, ticket: str) -> str:
    ticket = validate_ticket_id(ticket)
    directory = repo_root / "Tickets"
    matches: list[Path] = []
    if directory.is_dir():
        matches = sorted(directory.glob(f"{ticket}.md")) + sorted(directory.glob(f"{ticket}-*.md"))
    if len(matches) != 1:
        raise RunnerError(
            f"expected exactly one ticket file for {ticket} under Tickets/, found {len(matches)}"
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
        "- You MAY create or replace only your designated handoff input file:",
        f"    {handoff_path}",
        "- Do NOT modify manifest.json, handoff.json, review-*.json, reviewer-input-*.json, or any",
        "  other file under .agent-cycle/. The runner and validator own all other coordination",
        "  state.",
        "- Only implement, test, commit, push, and prepare that handoff input, then exit.",
        "Any manual transition command or blanket .agent-cycle prohibition in the reference",
        "contract below is superseded by these permissions.",
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
        "5. Write the implementer handoff JSON to exactly the permitted path above",
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
    expected_base: str,
    expected_branch: str,
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
            "- Return only the single JSON object described below on stdout.",
            "- The runner — not you — persists that output into ignored .agent-cycle state and",
            "  records the review. You never write a coordination file.",
            "Any manual transition or file-writing instruction in the reference contract below is",
            "superseded.",
            "",
            f"Exact reviewed SHA: {reviewed_sha}",
            f"Expected base SHA: {expected_base}",
            f"Expected task branch: {expected_branch}",
            "Use git_readonly independently: head, status, resolve_revision of the reviewed SHA,",
            "current_branch, merge_base(base, head), diff(base, head), show(commit), bounded log.",
            "Verify HEAD equals reviewed SHA, status is empty, branch matches, and merge-base",
            "equals expected base. Inspect the exact endpoint diff (or merge-base diff as needed).",
            "Git-read is constrained evidence, NOT shell access or another state machine.",
            "If Git inspection fails or evidence is inconsistent, fail closed with BLOCKED.",
            "Do not return BLOCKED solely because ordinary file tools cannot inspect Git.",
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
    heartbeat: Callable[[float], None],
) -> CommandResult:
    try:
        return executor.run(
            command, cwd=repo_root, log_path=log_path, stdin_text=stdin_text, heartbeat=heartbeat
        )
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
    reporter: ProgressReporter | None = None,
    recover: bool = False,
    reason: str | None = None,
) -> RunOutcome:
    """Drive the sequential Pi cycle for one ticket; return the terminal outcome."""
    active_config = config or RunnerConfig()
    ticket = validate_ticket_id(ticket)
    progress = reporter or ProgressReporter(ticket)
    validate_reviewer_config(active_config)
    repo_root = repo_root.resolve()
    if ticket_text is None:
        ticket_text = _load_ticket_text(repo_root, ticket)
    implementer_contract = _load_contract(
        repo_root, "IMPLEMENTER_CONTRACT.md", IMPLEMENTER_FALLBACK
    )
    reviewer_contract = _load_contract(repo_root, "REVIEWER_CONTRACT.md", REVIEWER_FALLBACK)

    directory = cycle_directory(repo_root, ticket)
    if recover != (reason is not None):
        raise RunnerError("human recovery requires both --recover and --reason")
    if recover and not directory.is_dir():
        raise RunnerError("human recovery requires an existing STOPPED cycle")
    if not directory.is_dir():
        executor.ensure_available()
        initialize_cycle(repo_root, ticket, active_config.base_branch)
        progress.message("cycle initialized")
    if recover:
        try:
            reopen_cycle(repo_root, ticket, reason or "")
        except CycleError as error:
            raise RunnerError(f"human recovery rejected: {error}") from error
    status = cycle_status(repo_root, ticket)
    manifest = _read_manifest(repo_root, ticket)
    diagnostic = (
        f"cycle is {status['state']}: {manifest['stop_reason']}; "
        f"current HEAD={status['head_sha']}; manifest HEAD={manifest['current_head_sha']}; "
        f"review round={manifest['review_round']}; "
        "manual inspection or explicit human-approved recovery is required"
    )
    if status["errors"]:
        raise RunnerError(
            "cycle preflight failed: " + "; ".join(status["errors"]) + "; " + diagnostic
        )
    tracking = TrackingHooks(repo_root, ticket, ticket_text, warn=progress.message)
    if status["state"] == "PASSED":
        tracking.call("bootstrap", manifest)
        tracking.call("lifecycle", "PASS", manifest, "reviewer")
        tracking.call("passed", manifest, active_config)
        return _outcome(manifest, active_config)
    if status["state"] not in {
        "NEW",
        "CHANGES_REQUIRED",
        "HUMAN_APPROVED_REWORK",
        "READY_FOR_REVIEW",
        "READY_FOR_REVIEW_2",
    }:
        raise RunnerError(diagnostic)
    executor.ensure_available()
    progress.message(f"cycle ready: {status['state']}")
    tracking.call("bootstrap", manifest)

    try:
        while True:
            manifest = _read_manifest(repo_root, ticket)
            if manifest["state"] in {"NEW", "CHANGES_REQUIRED", "HUMAN_APPROVED_REWORK"}:
                begin_implementation(repo_root, ticket)
                manifest = _read_manifest(repo_root, ticket)
                tracking.call("role_metadata", "implementer", active_config.implementer)
                tracking.call("lifecycle", "start", manifest)
                attempt = manifest["review_round"] + 1
                findings = _load_findings(repo_root, ticket, manifest["review_round"])
                # Do not accept an input left over from an earlier attempt.
                _handoff_path(directory).unlink(missing_ok=True)
                facts = collect_git_facts(repo_root, manifest["base_branch"])
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
                round_label = f" round {attempt}" if attempt > 1 else ""
                progress.message(
                    f"implementer{round_label} started: "
                    f"{active_config.implementer.provider} / {active_config.implementer.model}"
                )
                implementer_result = _execute_child(
                    executor,
                    _pi_arguments(active_config.implementer, active_config.executable),
                    repo_root=repo_root,
                    ticket=ticket,
                    log_path=directory / f"pi-implementer-round-{attempt}.log",
                    stdin_text=implementer_prompt
                    + INTENT_HELP
                    + "\nInclude integration warnings in your report: "
                    + json.dumps(tracking.data["warnings"]),
                    heartbeat=lambda elapsed: progress.heartbeat("implementer", elapsed),
                )
                progress.message(f"implementer finished: exit {implementer_result.returncode}")
                if implementer_result.returncode != 0:
                    _abort(
                        repo_root,
                        ticket,
                        f"implementer exited with code {implementer_result.returncode}",
                    )
                _require_clean_tree(repo_root, ticket, manifest["base_branch"], "implementer")
                progress.message("validating implementer handoff...")
                try:
                    _record_handoff(repo_root, ticket, directory, manifest["base_branch"])
                except RunnerError:
                    progress.message("handoff rejected")
                    raise
                tracking.call(
                    "lifecycle",
                    "handoff",
                    _read_manifest(repo_root, ticket),
                    "implementer",
                    implementer_result.stdout,
                )

            manifest = _read_manifest(repo_root, ticket)
            reviewed_sha = manifest["current_head_sha"]
            progress.message(f"handoff accepted: {reviewed_sha}")
            begin_review(repo_root, ticket, reviewed_sha)
            manifest = _read_manifest(repo_root, ticket)
            review_round = manifest["review_round"]

            tracking.call("role_metadata", "reviewer", active_config.reviewer)
            reviewer_prompt = _reviewer_prompt(
                ticket=ticket,
                ticket_text=ticket_text,
                contract=reviewer_contract,
                reviewed_sha=reviewed_sha,
                review_round=review_round,
                expected_base=manifest["base_sha"],
                expected_branch=manifest["branch"],
            )
            round_label = f" round {review_round}" if review_round > 1 else ""
            progress.message(
                f"reviewer{round_label} started: "
                f"{active_config.reviewer.provider} / {active_config.reviewer.model}"
            )
            reviewer_result = _execute_child(
                executor,
                _pi_arguments(active_config.reviewer, active_config.executable, reviewer=True),
                repo_root=repo_root,
                ticket=ticket,
                log_path=directory / f"pi-reviewer-round-{review_round}.log",
                stdin_text=reviewer_prompt
                + INTENT_HELP
                + "\nIntegration evidence: "
                + json.dumps(tracking.data["warnings"]),
                heartbeat=lambda elapsed: progress.heartbeat("reviewer", elapsed),
            )
            progress.message(f"reviewer finished: exit {reviewer_result.returncode}")
            if reviewer_result.returncode != 0:
                _abort(
                    repo_root,
                    ticket,
                    f"reviewer exited with code {reviewer_result.returncode}",
                )

            progress.message(f"validating review round {review_round}...")
            try:
                document = extract_review_json(
                    review_without_intent(reviewer_result.stdout, ticket)
                )
            except RunnerError as error:
                progress.message("review output rejected")
                _abort(repo_root, ticket, f"reviewer output rejected: {error}")
            review_input = directory / f"reviewer-input-round-{review_round}.json"
            try:
                _write_json(review_input, document)
            except OSError as error:
                _abort(repo_root, ticket, f"failed to persist reviewer result: {error}")
            try:
                manifest = record_review(repo_root, ticket, review_input)
            except CycleError as error:
                progress.message("review validation rejected")
                _abort(repo_root, ticket, f"review validation failed: {error}")
            progress.message(f"review round {review_round}: {document['verdict']}")
            tracking.call(
                "lifecycle", document["verdict"], manifest, "reviewer", reviewer_result.stdout
            )

            if manifest["state"] == "CHANGES_REQUIRED":
                continue
            tracking.call("passed", manifest, active_config)
            return _outcome(manifest, active_config)
    except KeyboardInterrupt:
        _abort(repo_root, ticket, "cancelled by user")
    except RunnerCancelled as error:
        _abort(repo_root, ticket, f"cancelled: {error}")
    except CycleError as error:
        raise RunnerError(f"agent cycle rejected the operation: {error}") from error
    except OSError as error:
        _abort(repo_root, ticket, f"runner I/O failure: {error}")
    finally:
        # Observe the validator's terminal state; logging does not decide transitions.
        with contextlib.suppress(OSError, json.JSONDecodeError):
            terminal = _read_manifest(repo_root, ticket)["state"]
            if terminal in {"PASSED", "STOPPED"}:
                progress.message(f"cycle {terminal}")


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
    parser.add_argument("--recover", action="store_true", help="explicit human approval of rework")
    parser.add_argument("--reason", help="required human recovery approval reason")
    parser.add_argument("--base-branch", default="master")
    parser.add_argument("--pi-executable", default="pi")
    parser.add_argument("--preset", choices=tuple(ROLE_PRESETS), help="role/provider/model preset")
    parser.add_argument("--implementer-provider")
    parser.add_argument("--implementer-model")
    parser.add_argument("--reviewer-provider")
    parser.add_argument("--reviewer-model")
    parser.add_argument("--reviewer-tools", default=",".join(DEFAULT_REVIEWER.tools))
    parser.add_argument("--ticket-file", type=Path)
    parser.add_argument("--repo-root", type=Path)
    return parser


def _config_from_arguments(arguments: argparse.Namespace) -> RunnerConfig:
    roles = ROLE_PRESETS[arguments.preset or "deepseek-codex"]
    reviewer_tools = tuple(
        tool.strip() for tool in arguments.reviewer_tools.split(",") if tool.strip()
    )
    return RunnerConfig(
        implementer=RoleConfig(
            roles.implementer.provider
            if arguments.implementer_provider is None
            else arguments.implementer_provider,
            roles.implementer.model
            if arguments.implementer_model is None
            else arguments.implementer_model,
        ),
        reviewer=RoleConfig(
            roles.reviewer.provider
            if arguments.reviewer_provider is None
            else arguments.reviewer_provider,
            roles.reviewer.model if arguments.reviewer_model is None else arguments.reviewer_model,
            reviewer_tools,
        ),
        base_branch=arguments.base_branch,
        executable=arguments.pi_executable,
    )


def main(argv: list[str] | None = None, *, repo_root: Path | None = None) -> int:
    arguments = _parser().parse_args(argv)
    root = (repo_root or arguments.repo_root or Path.cwd()).resolve()
    config = _config_from_arguments(arguments)
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
            recover=arguments.recover,
            reason=arguments.reason,
        )
    except (RunnerError, CycleError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    _report(outcome)
    return 0 if outcome.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
