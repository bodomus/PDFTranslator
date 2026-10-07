"""Validate and record sequential implementer/reviewer ticket-cycle state."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, NoReturn

if __package__ in {None, ""}:  # pragma: no cover - script entry point
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.cycle_ownership import CycleOwnershipError, ticket_ownership  # noqa: E402
from scripts.pre_handoff_retry_policy import evaluate_pre_handoff_retry  # noqa: E402

SCHEMA_VERSION = "1.0"
MAX_REVIEW_ROUNDS = 2
MAX_OPERATIONAL_RETRIES = 3
OPERATIONAL_CODES = {
    "implementer_process_failed",
    "implementer_terminated",
    "provider_usage_limit",
    "provider_unavailable",
    "implementer_runtime_failed",
    "network_auth_failed",
}


class StopClass(StrEnum):
    OPERATIONAL = "operational"
    REVIEW_EXHAUSTED = "review_exhausted"
    SAFETY = "safety"
    UNKNOWN = "unknown"


TICKET_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*-[1-9][0-9]*[A-Z]*$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
COORDINATION_DIRECTORY = ".agent-cycle"


class CycleError(RuntimeError):
    """A fail-closed coordination or validation error."""


class CycleState(StrEnum):
    NEW = "NEW"
    HUMAN_APPROVED_REWORK = "HUMAN_APPROVED_REWORK"
    HUMAN_APPROVED_OPERATIONAL_RETRY = "HUMAN_APPROVED_OPERATIONAL_RETRY"
    HUMAN_APPROVED_PRE_HANDOFF_RETRY = "HUMAN_APPROVED_PRE_HANDOFF_RETRY"
    IMPLEMENTING = "IMPLEMENTING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    REVIEWING = "REVIEWING"
    CHANGES_REQUIRED = "CHANGES_REQUIRED"
    READY_FOR_REVIEW_2 = "READY_FOR_REVIEW_2"
    PASSED = "PASSED"
    BLOCKED = "BLOCKED"
    STOPPED = "STOPPED"


class ActiveAgent(StrEnum):
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"


class ReviewVerdict(StrEnum):
    PASS = "PASS"
    CHANGES_REQUIRED = "CHANGES_REQUIRED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class GitFacts:
    root: Path
    branch: str
    head_sha: str
    base_sha: str
    status: tuple[str, ...]
    repository_fingerprint: str

    @property
    def clean(self) -> bool:
        return not self.status


@dataclass(frozen=True)
class Finding:
    id: str
    severity: str
    problem: str
    required_fix: str
    file: str = ""
    symbol: str = ""
    regression_test: str = ""

    @property
    def stable_key(self) -> tuple[str, str, str]:
        return (self.id, self.file, self.symbol)


@dataclass(frozen=True)
class ReviewInput:
    schema_version: str
    ticket: str
    review_round: int
    reviewed_sha: str
    verdict: ReviewVerdict
    findings: tuple[Finding, ...]
    blocked_reason: str | None


MANIFEST_KEYS = {
    "schema_version",
    "ticket",
    "repository_fingerprint",
    "branch",
    "base_branch",
    "base_sha",
    "current_head_sha",
    "review_round",
    "state",
    "active_agent",
    "working_tree_clean",
    "review_started_head",
    "review_started_status",
    "stop_reason",
}
HANDOFF_KEYS = {"schema_version", "system", "implementer", "reviewer"}
SYSTEM_KEYS = {
    "ticket",
    "branch",
    "base_sha",
    "current_head_sha",
    "review_round",
    "state",
}
IMPLEMENTER_KEYS = {
    "schema_version",
    "ticket",
    "implementation_attempt",
    "status",
    "implementation_report",
    "focused_tests",
    "full_tests",
    "check_ps1",
    "known_limitations",
    "notes",
}
REVIEW_KEYS = {
    "schema_version",
    "ticket",
    "review_round",
    "reviewed_sha",
    "verdict",
    "findings",
    "blocked_reason",
}
FINDING_KEYS = {
    "id",
    "severity",
    "file",
    "symbol",
    "problem",
    "required_fix",
    "regression_test",
}
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
CHECK_RESULTS = {"PASS", "FAIL", "NOT_RUN"}


def validate_ticket_id(ticket: str) -> str:
    """Return a safe canonical ticket ID or fail before path construction."""
    if not isinstance(ticket, str) or not TICKET_PATTERN.fullmatch(ticket):
        raise CycleError(
            "invalid ticket ID; expected conservative form such as PDFTR-33, ABC-123, or PDFTR-35A"
        )
    return ticket


def cycle_directory(repo_root: Path, ticket: str) -> Path:
    ticket = validate_ticket_id(ticket)
    root_entry = repo_root.resolve() / COORDINATION_DIRECTORY
    ticket_entry = root_entry / ticket
    if (
        root_entry.is_symlink()
        or ticket_entry.is_symlink()
        or root_entry.is_junction()
        or ticket_entry.is_junction()
    ):
        raise CycleError("coordination directory must not be a symbolic link")
    coordination_root = root_entry.resolve()
    candidate = ticket_entry.resolve()
    if candidate.parent != coordination_root:
        raise CycleError("ticket coordination path escapes .agent-cycle")
    return candidate


def _run_git(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise CycleError(f"git {' '.join(arguments)} failed: {detail}")
    return result.stdout.strip()


def collect_git_facts(repo_root: Path, base_branch: str = "master") -> GitFacts:
    """Derive authoritative state using read-only Git commands."""
    requested = repo_root.resolve()
    actual = Path(_run_git(requested, "rev-parse", "--show-toplevel")).resolve()
    if actual != requested:
        raise CycleError(f"run from repository root: expected {actual}, got {requested}")
    branch = _run_git(actual, "branch", "--show-current")
    if not branch:
        raise CycleError("detached HEAD is not a valid ticket branch")
    head_sha = _validated_sha(_run_git(actual, "rev-parse", "HEAD"), "Git HEAD")
    base_sha = _validated_sha(_run_git(actual, "merge-base", base_branch, "HEAD"), "merge base")
    status_text = _run_git(actual, "status", "--porcelain", "--untracked-files=all")
    status = tuple(line for line in status_text.splitlines() if line)
    roots = _run_git(actual, "rev-list", "--max-parents=0", "HEAD").splitlines()
    if not roots:
        raise CycleError("repository has no root commit")
    fingerprint = hashlib.sha256("\n".join(sorted(roots)).encode()).hexdigest()
    return GitFacts(actual, branch, head_sha, base_sha, status, fingerprint)


def initialize_cycle(repo_root: Path, ticket: str, base_branch: str = "master") -> dict[str, Any]:
    ticket = validate_ticket_id(ticket)
    facts = collect_git_facts(repo_root, base_branch)
    if facts.branch == base_branch:
        raise CycleError(f"ticket cycle cannot initialize on base branch {base_branch!r}")
    _require_clean(facts, "initialization")
    directory = cycle_directory(facts.root, ticket)
    if directory.exists():
        raise CycleError(f"ticket cycle already exists: {directory.relative_to(facts.root)}")
    directory.mkdir(parents=True)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "ticket": ticket,
        "repository_fingerprint": facts.repository_fingerprint,
        "branch": facts.branch,
        "base_branch": base_branch,
        "base_sha": facts.base_sha,
        "current_head_sha": facts.head_sha,
        "review_round": 0,
        "state": CycleState.NEW.value,
        "active_agent": None,
        "working_tree_clean": True,
        "review_started_head": None,
        "review_started_status": None,
        "stop_reason": None,
        "stop_class": StopClass.UNKNOWN.value,
        "stop_code": None,
        "operational_retries": [],
        "implementation_attempt": 1,
    }
    handoff = _blank_handoff(manifest)
    _atomic_write_json(directory / "manifest.json", manifest)
    _atomic_write_json(directory / "handoff.json", handoff)
    return manifest


def begin_implementation(repo_root: Path, ticket: str) -> dict[str, Any]:
    directory, manifest, handoff, facts = _load_cycle(repo_root, ticket)
    _require_no_active_agent(manifest)
    _require_clean(facts, "begin implementation")
    if facts.head_sha != manifest["current_head_sha"]:
        raise CycleError("Git HEAD changed outside a validated implementation phase")
    state = CycleState(manifest["state"])
    if state not in {
        CycleState.NEW,
        CycleState.CHANGES_REQUIRED,
        CycleState.HUMAN_APPROVED_REWORK,
        CycleState.HUMAN_APPROVED_OPERATIONAL_RETRY,
        CycleState.HUMAN_APPROVED_PRE_HANDOFF_RETRY,
    }:
        raise CycleError(f"cannot begin implementation from {state.value}")
    manifest["implementation_attempt"] = implementation_attempt(manifest)
    manifest["state"] = CycleState.IMPLEMENTING.value
    manifest["active_agent"] = ActiveAgent.IMPLEMENTER.value
    manifest["current_head_sha"] = facts.head_sha
    manifest["working_tree_clean"] = True
    manifest["review_started_head"] = None
    manifest["review_started_status"] = None
    handoff["reviewer"] = None
    _sync_system(handoff, manifest)
    _write_cycle(directory, manifest, handoff)
    return manifest


def record_handoff(repo_root: Path, ticket: str, input_file: Path) -> dict[str, Any]:
    directory, manifest, handoff, facts = _load_cycle(repo_root, ticket)
    if manifest["active_agent"] != ActiveAgent.IMPLEMENTER.value:
        raise CycleError("handoff requires implementer to be the active agent")
    if manifest["state"] != CycleState.IMPLEMENTING.value:
        raise CycleError("handoff requires IMPLEMENTING state")
    _require_clean(facts, "handoff")
    for previous_round in range(1, manifest["review_round"] + 1):
        previous = _load_json(directory / f"review-{previous_round}.json")
        if previous.get("reviewed_sha") == facts.head_sha:
            raise CycleError("a changes-required handoff must point to a new implementation SHA")
    implementer = _validate_implementer_input(_load_json(input_file), ticket, manifest)
    manifest["current_head_sha"] = facts.head_sha
    manifest["working_tree_clean"] = True
    manifest["active_agent"] = None
    manifest["state"] = (
        CycleState.READY_FOR_REVIEW.value
        if manifest["review_round"] == 0
        else CycleState.READY_FOR_REVIEW_2.value
    )
    attempt_path = directory / f"implementation-{implementer['implementation_attempt']}.json"
    if attempt_path.exists():
        raise CycleError(f"immutable implementation artifact already exists: {attempt_path.name}")
    _atomic_write_json(attempt_path, implementer)
    handoff["implementer"] = implementer
    handoff["reviewer"] = None
    _sync_system(handoff, manifest)
    _write_cycle(directory, manifest, handoff)
    return manifest


def begin_review(repo_root: Path, ticket: str, expected_sha: str) -> dict[str, Any]:
    directory, manifest, handoff, facts = _load_cycle(repo_root, ticket)
    _require_no_active_agent(manifest)
    _require_clean(facts, "begin review")
    expected_sha = _validated_sha(expected_sha, "expected review SHA")
    state = CycleState(manifest["state"])
    if state not in {CycleState.READY_FOR_REVIEW, CycleState.READY_FOR_REVIEW_2}:
        raise CycleError(f"cannot begin review from {state.value}")
    if manifest["review_round"] >= _authorized_review_limit(manifest):
        raise CycleError("review limit reached; explicit human-approved recovery is required")
    if expected_sha != facts.head_sha or expected_sha != manifest["current_head_sha"]:
        raise CycleError("expected review SHA must match both current Git HEAD and manifest HEAD")
    manifest["review_round"] += 1
    manifest["state"] = CycleState.REVIEWING.value
    manifest["active_agent"] = ActiveAgent.REVIEWER.value
    manifest["review_started_head"] = facts.head_sha
    manifest["review_started_status"] = list(facts.status)
    manifest["working_tree_clean"] = True
    handoff["reviewer"] = None
    _sync_system(handoff, manifest)
    _write_cycle(directory, manifest, handoff)
    return manifest


def record_review(repo_root: Path, ticket: str, input_file: Path) -> dict[str, Any]:
    directory, manifest, handoff, facts = _load_cycle(repo_root, ticket)
    if manifest["active_agent"] != ActiveAgent.REVIEWER.value:
        raise CycleError("record-review requires reviewer to be the active agent")
    if manifest["state"] != CycleState.REVIEWING.value:
        raise CycleError("record-review requires REVIEWING state")
    if facts.head_sha != manifest["review_started_head"]:
        raise CycleError("repository HEAD changed during the read-only review window")
    if list(facts.status) != manifest["review_started_status"]:
        raise CycleError("repository working tree changed during the read-only review window")
    review = _validate_review_input(_load_json(input_file), ticket, manifest)
    artifact_path = directory / f"review-{review.review_round}.json"
    if artifact_path.exists():
        raise CycleError(f"immutable review artifact already exists: {artifact_path.name}")

    repeated = _repeated_finding_keys(directory, review)
    stop_reason: str | None = None
    if review.verdict == ReviewVerdict.PASS:
        next_state = CycleState.PASSED
    elif review.verdict == ReviewVerdict.BLOCKED:
        next_state = CycleState.BLOCKED
        stop_reason = review.blocked_reason
    elif repeated:
        next_state = CycleState.STOPPED
        stop_reason = "repeated_finding"
    elif review.review_round >= MAX_REVIEW_ROUNDS:
        next_state = CycleState.STOPPED
        stop_reason = "review_round_limit"
    else:
        next_state = CycleState.CHANGES_REQUIRED

    review_document = _review_to_dict(review)
    manifest["state"] = next_state.value
    manifest["active_agent"] = None
    manifest["working_tree_clean"] = True
    manifest["stop_reason"] = stop_reason
    manifest["stop_class"] = (
        StopClass.REVIEW_EXHAUSTED.value
        if stop_reason in {"repeated_finding", "review_round_limit"}
        else StopClass.UNKNOWN.value
    )
    manifest["stop_code"] = (
        stop_reason if manifest["stop_class"] == StopClass.REVIEW_EXHAUSTED.value else None
    )
    manifest["review_started_head"] = None
    manifest["review_started_status"] = None
    handoff["reviewer"] = review_document
    _sync_system(handoff, manifest)
    _atomic_write_json(artifact_path, review_document)
    _write_cycle(directory, manifest, handoff)
    return manifest


def _authorized_review_limit(manifest: dict[str, Any]) -> int:
    return MAX_REVIEW_ROUNDS + len(manifest.get("human_recoveries", []))


def reopen_cycle(repo_root: Path, ticket: str, reason: str) -> dict[str, Any]:
    """Explicit human approval of ONE additional implementation/exact-SHA review pair."""
    directory, manifest, handoff, facts = _load_cycle(repo_root, ticket)
    diagnostic = (
        f"state={manifest['state']}; current HEAD={facts.head_sha}; "
        f"manifest HEAD={manifest['current_head_sha']}; review round={manifest['review_round']}; "
        f"stop reason={manifest['stop_reason']}; "
        "human must inspect the cycle and explicitly approve recovery with a reason"
    )
    if (
        not isinstance(reason, str)
        or not reason.strip()
        or len(reason) > 200
        or any(ord(character) < 32 for character in reason)
    ):
        raise CycleError(f"recovery reason must be 1-200 printable characters; {diagnostic}")
    # Legacy review recovery is reconstructed only from validated immutable review
    # evidence, never from free-text stop reasons. Legacy operational stops stay unknown.
    if "stop_class" not in manifest and manifest["review_round"] == _authorized_review_limit(
        manifest
    ):
        previous_review = _validate_review_input(
            _load_json(directory / f"review-{manifest['review_round']}.json"),
            ticket,
            manifest,
            persisted=True,
        )
        if previous_review.verdict == ReviewVerdict.CHANGES_REQUIRED:
            manifest["stop_class"] = StopClass.REVIEW_EXHAUSTED.value
            manifest["stop_code"] = (
                "repeated_finding"
                if _repeated_finding_keys(directory, previous_review)
                else "review_round_limit"
            )
    if (
        manifest["state"] != CycleState.STOPPED.value
        or manifest.get("stop_class") != StopClass.REVIEW_EXHAUSTED.value
        or manifest.get("stop_code") not in {"repeated_finding", "review_round_limit"}
        or manifest["review_round"] != _authorized_review_limit(manifest)
    ):
        raise CycleError(f"recovery requires STOPPED after exhausted review rounds; {diagnostic}")
    _require_no_active_agent(manifest)
    if not facts.clean or facts.head_sha != manifest["current_head_sha"]:
        raise CycleError(f"recovery requires a clean working tree and unchanged HEAD; {diagnostic}")
    # Validate the last immutable review before authorizing new work.
    previous = _load_json(directory / f"review-{manifest['review_round']}.json")
    _validate_review_input(previous, ticket, manifest, persisted=True)
    recoveries = list(manifest.get("human_recoveries", []))
    recoveries.append(
        {
            "reason": reason.strip(),
            "stop_reason": manifest["stop_code"],
            "review_round": manifest["review_round"],
            "reviewed_sha": manifest["current_head_sha"],
            "implementation_attempt": implementation_attempt(manifest),
            "previous_handoff": handoff,
        }
    )
    manifest["human_recoveries"] = recoveries
    manifest["implementation_attempt"] = implementation_attempt(manifest)
    manifest["state"] = CycleState.HUMAN_APPROVED_REWORK.value
    manifest["stop_reason"] = None
    manifest["stop_class"] = StopClass.UNKNOWN.value
    manifest["stop_code"] = None
    # Snapshot must not alias the mutable current handoff.
    handoff = json.loads(json.dumps(handoff))
    _sync_system(handoff, manifest)
    _write_cycle(directory, manifest, handoff)
    return manifest


def implementation_attempt(manifest: dict[str, Any]) -> int:
    """Implementation numbering is independent of the review budget."""
    return manifest["review_round"] + 1 + len(retry_approvals(manifest))


def retry_approvals(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        manifest.get("operational_retries", []) + manifest.get("pre_handoff_retries", []),
        key=lambda entry: entry["implementation_attempt"],
    )


def retry_state(manifest: dict[str, Any]) -> str:
    approvals = retry_approvals(manifest)
    if approvals and approvals[-1].get("retry_kind") == "pre_handoff":
        return CycleState.HUMAN_APPROVED_PRE_HANDOFF_RETRY.value
    return CycleState.HUMAN_APPROVED_OPERATIONAL_RETRY.value


def is_retry_approved(manifest: dict[str, Any]) -> bool:
    return manifest["state"] in {
        CycleState.HUMAN_APPROVED_OPERATIONAL_RETRY.value,
        CycleState.HUMAN_APPROVED_PRE_HANDOFF_RETRY.value,
    }


def _operational_rejection(
    manifest: dict[str, Any],
    handoff: dict[str, Any],
    facts: GitFacts,
    directory: Path,
) -> str | None:
    if manifest["state"] != CycleState.STOPPED.value:
        return "operational retry requires STOPPED"
    if manifest.get("stop_code") == "operational_retry_limit":
        return "operational_retry_limit"
    if manifest.get("stop_class", "unknown") != StopClass.OPERATIONAL.value:
        return "stop class is not operational"
    if manifest.get("stop_code") not in OPERATIONAL_CODES:
        return "stop code is not a recognized operational failure"
    if manifest["active_agent"] is not None:
        return "an agent is active"
    if not facts.clean:
        return "working tree is dirty"
    if facts.head_sha != manifest["current_head_sha"]:
        return "operational retry requires unchanged exact HEAD"
    if not manifest["working_tree_clean"]:
        return "repository safety error: recorded working tree is dirty"
    if manifest["review_round"] != 0 or handoff["implementer"] is not None:
        return "an implementation handoff or review was already accepted"
    if handoff["reviewer"] is not None or any(directory.glob("review-*.json")):
        return "accepted or contradictory review artifacts exist"
    if any(directory.glob("implementation-*.json")):
        return "accepted or contradictory implementation artifacts exist"
    if len(manifest.get("operational_retries", [])) >= MAX_OPERATIONAL_RETRIES:
        return "operational_retry_limit"
    return None


def implementer_launch_record(manifest: dict[str, Any], phase: str) -> dict[str, Any]:
    approvals = retry_approvals(manifest)
    return {
        "ticket": manifest["ticket"],
        "repository_fingerprint": manifest["repository_fingerprint"],
        "branch": manifest["branch"],
        "head_sha": manifest["current_head_sha"],
        "implementation_attempt": implementation_attempt(manifest),
        "approval": approvals[-1] if approvals else None,
        "phase": phase,
    }


def _pre_handoff_rejection(
    manifest: dict[str, Any], handoff: dict[str, Any], facts: GitFacts, directory: Path
) -> str | None:
    rejection = evaluate_pre_handoff_retry(manifest, handoff, facts, directory)
    if rejection:
        return rejection
    if manifest.get("implementation_attempt") != implementation_attempt(manifest):
        return "retry_attempt_metadata_inconsistent"
    marker = directory / f"implementer-launch-attempt-{implementation_attempt(manifest)}.json"
    try:
        actual = _load_json(marker)
    except CycleError:
        return "retry_process_outcome_unproven"
    if json.dumps(actual, sort_keys=True) != json.dumps(
        implementer_launch_record(manifest, "exited"), sort_keys=True
    ):
        return "retry_process_outcome_unproven"
    return _tracking_retry_rejection(manifest, directory)


def _tracking_retry_rejection(manifest: dict[str, Any], directory: Path) -> str | None:
    tracking = directory / "youtrack.json"
    if tracking.exists():
        try:
            data = _load_json(tracking)
            operations = data["operations"]
            if not isinstance(operations, dict) or data.get("ticket") != manifest["ticket"]:
                return "retry_state_corrupt"
            if data.get("identity_unsafe"):
                return "retry_remote_mutation_uncertain"
            for key, operation in operations.items():
                if (
                    not isinstance(key, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", key)
                    or not isinstance(operation, dict)
                    or not isinstance(operation.get("status"), str)
                    or operation["status"] not in {"success", "failed", "pending", "uncertain"}
                ):
                    return "retry_state_corrupt"
                expected_keys = (
                    {"status", "result"}
                    if operation["status"] == "success"
                    else {"status", "conflicting_write"}
                )
                if operation.keys() != expected_keys or (
                    "conflicting_write" in operation
                    and type(operation["conflicting_write"]) is not bool
                ):
                    return "retry_state_corrupt"
                if operation["status"] in {"pending", "uncertain"}:
                    return "retry_remote_mutation_uncertain"
        except (CycleError, KeyError):
            return "retry_state_corrupt"
    return None


def retry_pre_handoff_cycle(repo_root: Path, ticket: str) -> dict[str, Any]:
    """Operator-only approval; dispatch remains owned by the locked runner."""
    try:
        with ticket_ownership(cycle_directory(repo_root.resolve(), validate_ticket_id(ticket))):
            try:
                directory, manifest, handoff, facts = _load_cycle(repo_root, ticket)
            except CycleError as error:
                code = "retry_state_corrupt"
                if str(error).startswith("wrong task branch:"):
                    code = "retry_branch_mismatch"
                elif str(error).startswith("cycle belongs to a different Git repository"):
                    code = "retry_repository_identity_mismatch"
                raise CycleError(f"{code}: {error}") from error
            rejection = _pre_handoff_rejection(manifest, handoff, facts, directory)
            if rejection:
                raise CycleError(rejection)
            previous = implementation_attempt(manifest)
            archive = directory / "attempts" / str(previous)
            for parent in (archive.parent, archive):
                if parent.is_symlink() or parent.is_junction():
                    raise CycleError("retry_state_corrupt")
                parent.mkdir(exist_ok=True)
            evidence = {}
            for source in directory.iterdir():
                if not source.is_file():
                    continue
                content = source.read_bytes()
                target = archive / source.name
                if target.is_symlink() or target.is_junction():
                    raise CycleError("retry_state_corrupt")
                if target.exists():
                    if target.read_bytes() != content:
                        raise CycleError("retry_attempt_metadata_inconsistent")
                else:
                    # Exclusive creation: existing evidence is never rewritten.
                    with target.open("xb") as stream:
                        stream.write(content)
                evidence[source.name] = hashlib.sha256(content).hexdigest()
            entry = {
                "retry_kind": "pre_handoff",
                "approved_by": "human",
                "approved_at": datetime.now(UTC).isoformat(),
                "implementation_attempt": previous + 1,
                "previous_attempt_id": previous,
                "source_head": facts.head_sha,
                "branch": facts.branch,
                "repository_identity": facts.repository_fingerprint,
                "previous_stop_class": manifest.get("stop_class", "unknown"),
                "previous_stop_code": manifest.get("stop_code"),
                "previous_stop_reason": manifest["stop_reason"],
                "evidence": evidence,
            }
            manifest.setdefault("pre_handoff_retries", []).append(entry)
            manifest.update(
                state=CycleState.HUMAN_APPROVED_PRE_HANDOFF_RETRY.value,
                implementation_attempt=previous + 1,
                stop_reason=None,
                stop_class="unknown",
                stop_code=None,
            )
            _sync_system(handoff, manifest)
            _write_cycle(directory, manifest, handoff)
            return manifest
    except CycleOwnershipError as error:
        raise CycleError("retry_agent_still_active") from error


def retry_operational_cycle(repo_root: Path, ticket: str, reason: str) -> dict[str, Any]:
    """Human approval of one pre-handoff implementer attempt, never a review grant."""
    directory, manifest, handoff, facts = _load_cycle(repo_root, ticket)
    if (
        not isinstance(reason, str)
        or not reason.strip()
        or len(reason) > 200
        or any(ord(character) < 32 for character in reason)
    ):
        raise CycleError("recovery reason must be 1-200 printable characters")
    rejection = _operational_rejection(manifest, handoff, facts, directory)
    if rejection:
        raise CycleError(rejection)
    approvals = list(manifest.get("operational_retries", []))
    approvals.append(
        {
            "type": "operational_retry",
            "reason": reason.strip(),
            "previous_stop_code": manifest["stop_code"],
            "previous_stop_reason": manifest["stop_reason"],
            "head_sha": facts.head_sha,
            "branch": facts.branch,
            "review_round": 0,
            "implementation_attempt": implementation_attempt(manifest) + 1,
        }
    )
    manifest["operational_retries"] = approvals
    manifest["implementation_attempt"] = implementation_attempt(manifest)
    manifest["state"] = CycleState.HUMAN_APPROVED_OPERATIONAL_RETRY.value
    manifest["stop_reason"] = None
    manifest["stop_class"] = StopClass.UNKNOWN.value
    manifest["stop_code"] = None
    _sync_system(handoff, manifest)
    _write_cycle(directory, manifest, handoff)
    return manifest


def stop_cycle(
    repo_root: Path,
    ticket: str,
    reason: str,
    *,
    stop_class: StopClass = StopClass.UNKNOWN,
    stop_code: str | None = None,
) -> dict[str, Any]:
    reason = reason.strip()
    if not reason or any(ord(character) < 32 for character in reason) or len(reason) > 200:
        raise CycleError("stop reason must be 1-200 printable characters")
    directory, manifest, handoff, _facts = _load_cycle(repo_root, ticket)
    if CycleState(manifest["state"]) in {CycleState.PASSED, CycleState.BLOCKED}:
        raise CycleError(f"cannot stop terminal state {manifest['state']}")
    manifest["state"] = CycleState.STOPPED.value
    manifest["active_agent"] = None
    if stop_class == StopClass.OPERATIONAL and stop_code not in OPERATIONAL_CODES:
        raise CycleError("unrecognized operational stop code")
    if (
        stop_class == StopClass.OPERATIONAL
        and len(manifest.get("operational_retries", [])) >= MAX_OPERATIONAL_RETRIES
    ):
        stop_class = StopClass.UNKNOWN
        stop_code = "operational_retry_limit"
    manifest["stop_reason"] = reason
    manifest["stop_class"] = stop_class.value
    manifest["stop_code"] = stop_code
    manifest["review_started_head"] = None
    manifest["review_started_status"] = None
    _sync_system(handoff, manifest)
    _write_cycle(directory, manifest, handoff)
    return manifest


def cycle_status(
    repo_root: Path, ticket: str, *, verify_remote: str | None = None
) -> dict[str, Any]:
    _directory, manifest, handoff, facts = _load_cycle(repo_root, ticket)
    rejection = _operational_rejection(manifest, handoff, facts, _directory)
    errors: list[str] = []
    if facts.head_sha != manifest["current_head_sha"]:
        errors.append("Git HEAD differs from manifest current_head_sha")
    expected_dirty = (
        manifest["state"] == CycleState.IMPLEMENTING.value
        and manifest["active_agent"] == ActiveAgent.IMPLEMENTER.value
        and not facts.clean
    )
    if facts.clean != manifest["working_tree_clean"] and not expected_dirty:
        errors.append("working-tree cleanliness differs from manifest")
    reviewer = handoff["reviewer"]
    review_valid = bool(
        reviewer is not None
        and reviewer["reviewed_sha"] == facts.head_sha
        and reviewer["reviewed_sha"] == manifest["current_head_sha"]
    )
    remote_tip: str | None = None
    if verify_remote is not None:
        remote_ref = f"refs/remotes/{verify_remote}/{manifest['branch']}"
        try:
            remote_tip = _validated_sha(
                _run_git(facts.root, "rev-parse", "--verify", remote_ref), "remote branch tip"
            )
        except CycleError as error:
            errors.append(str(error))
        else:
            if remote_tip != facts.head_sha:
                errors.append("local HEAD is not the expected remote branch tip")
    return {
        "ticket": ticket,
        "state": manifest["state"],
        "branch": facts.branch,
        "head_sha": facts.head_sha,
        "review_round": manifest["review_round"],
        "max_review_rounds": MAX_REVIEW_ROUNDS,
        "authorized_review_limit": _authorized_review_limit(manifest),
        "human_recovery_count": len(manifest.get("human_recoveries", [])),
        "stop_reason": manifest["stop_reason"],
        "stop_class": manifest.get("stop_class", "unknown"),
        "stop_code": manifest.get("stop_code"),
        "implementation_attempt": manifest.get(
            "implementation_attempt",
            (
                handoff["implementer"]["implementation_attempt"]
                if handoff["implementer"] is not None
                else implementation_attempt(manifest)
            ),
        ),
        "expected_head_sha": manifest["current_head_sha"],
        "pre_handoff_retry_eligible": _pre_handoff_rejection(manifest, handoff, facts, _directory)
        is None,
        "pre_handoff_retry_rejection": _pre_handoff_rejection(manifest, handoff, facts, _directory),
        "operational_retry_count": len(manifest.get("operational_retries", [])),
        "operational_retry_eligible": rejection is None,
        "operational_retry_rejection": rejection,
        "active_agent": manifest["active_agent"],
        "working_tree_clean": facts.clean,
        "working_tree_dirty_expected": expected_dirty,
        "review_valid_for_head": review_valid,
        "remote_tip": remote_tip,
        "errors": errors,
    }


def complete_operational_prelaunch(repo_root: Path, ticket: str) -> None:
    """Complete only a proven blank begin projection; caller must hold runner ownership."""
    directory, manifest, handoff, _facts = _load_cycle(
        repo_root, ticket, prepared_operational_resume=True
    )
    if (
        manifest["state"] == CycleState.IMPLEMENTING.value
        and _load_json(directory / "handoff.json") != handoff
    ):
        _atomic_write_json(directory / "handoff.json", handoff)


def _load_cycle(
    repo_root: Path, ticket: str, *, prepared_operational_resume: bool = False
) -> tuple[Path, dict[str, Any], dict[str, Any], GitFacts]:
    ticket = validate_ticket_id(ticket)
    requested = repo_root.resolve()
    actual = Path(_run_git(requested, "rev-parse", "--show-toplevel")).resolve()
    if actual != requested:
        raise CycleError(f"run from repository root: expected {actual}, got {requested}")
    directory = cycle_directory(requested, ticket)
    if not directory.is_dir():
        raise CycleError(f"ticket cycle does not exist: {ticket}")
    for entry in directory.iterdir():
        if entry.is_symlink() or entry.is_junction():
            raise CycleError("cycle artifacts must not be symbolic links or junctions")
    manifest = _load_json(directory / "manifest.json")
    _validate_manifest(manifest, ticket)
    for approval in manifest.get("pre_handoff_retries", []):
        archive = directory / "attempts" / str(approval["previous_attempt_id"])
        for parent in (archive.parent, archive):
            if parent.is_symlink() or parent.is_junction() or not parent.is_dir():
                raise CycleError("retry_attempt_metadata_inconsistent")
        for name, digest in approval["evidence"].items():
            path = archive / name
            if path.is_symlink() or path.is_junction() or not path.is_file():
                raise CycleError("retry_attempt_metadata_inconsistent")
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise CycleError("retry_attempt_metadata_inconsistent")
        prior = _load_json(archive / "manifest.json")
        if (
            prior.get("state") != "STOPPED"
            or prior.get("review_round") != 0
            or prior.get("implementation_attempt") != approval["previous_attempt_id"]
            or prior.get("current_head_sha") != approval["source_head"]
            or prior.get("repository_fingerprint") != approval["repository_identity"]
            or prior.get("branch") != approval["branch"]
            or prior.get("stop_class", "unknown") != approval["previous_stop_class"]
            or prior.get("stop_code") != approval["previous_stop_code"]
            or prior.get("stop_reason") != approval["previous_stop_reason"]
        ):
            raise CycleError("retry_attempt_metadata_inconsistent")
        _validate_manifest(prior, ticket)
        prior_handoff = _load_json(archive / "handoff.json")
        if json.dumps(prior_handoff, sort_keys=True) != json.dumps(
            _blank_handoff(prior), sort_keys=True
        ):
            raise CycleError("retry_handoff_already_accepted")
        old_marker = f"implementer-launch-attempt-{approval['previous_attempt_id']}.json"
        if old_marker not in approval["evidence"] or json.dumps(
            _load_json(archive / old_marker), sort_keys=True
        ) != json.dumps(implementer_launch_record(prior, "exited"), sort_keys=True):
            raise CycleError("retry_process_outcome_unproven")
    # Operational approval requires round zero and no human review recoveries. Its
    # audit accounts only for failed pre-handoff attempts, so no numbered accepted
    # implementation/review snapshots are authorized. Other states keep legitimate
    # immutable history; failed-attempt diagnostics are unaffected.
    if is_retry_approved(manifest) and (
        any(directory.glob("review-*.json")) or any(directory.glob("implementation-*.json"))
    ):
        raise CycleError("operational retry resume has contradictory handoff/review artifacts")
    handoff = _load_json(directory / "handoff.json")
    # Approval commits the manifest first. Only the blank pre-handoff projection can
    # be completed in memory after a crash between the two atomic replacements.
    if is_retry_approved(manifest):
        previous = dict(manifest, state=CycleState.STOPPED.value)
        if json.dumps(handoff, sort_keys=True) == json.dumps(
            _blank_handoff(previous), sort_keys=True
        ):
            handoff = _blank_handoff(manifest)
    facts = collect_git_facts(requested, manifest["base_branch"])
    if facts.repository_fingerprint != manifest["repository_fingerprint"]:
        raise CycleError("cycle belongs to a different Git repository")
    if facts.branch != manifest["branch"]:
        raise CycleError(
            f"wrong task branch: expected {manifest['branch']!r}, found {facts.branch!r}; "
            f"state={manifest['state']}; current HEAD={facts.head_sha}; "
            f"manifest HEAD={manifest['current_head_sha']}; "
            f"review round={manifest['review_round']}; stop reason={manifest['stop_reason']}; "
            "human must return to the recorded ticket branch"
        )
    if facts.base_sha != manifest["base_sha"]:
        raise CycleError("merge base differs from the initialized ticket cycle")
    if (
        prepared_operational_resume
        and manifest["state"] == CycleState.IMPLEMENTING.value
        and manifest["active_agent"] == ActiveAgent.IMPLEMENTER.value
        and manifest["review_round"] == 0
        and retry_approvals(manifest)
        and json.dumps(handoff, sort_keys=True)
        == json.dumps(
            _blank_handoff(dict(manifest, state=retry_state(manifest))),
            sort_keys=True,
        )
    ):
        expected = {
            "ticket": manifest["ticket"],
            "repository_fingerprint": manifest["repository_fingerprint"],
            "branch": manifest["branch"],
            "head_sha": manifest["current_head_sha"],
            "implementation_attempt": implementation_attempt(manifest),
            "approval": retry_approvals(manifest)[-1],
            "phase": "prepared",
        }
        marker = directory / f"implementer-launch-attempt-{implementation_attempt(manifest)}.json"
        if json.dumps(_load_json(marker), sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise CycleError("operational launch ownership is uncertain")
        _require_clean(facts, "pre-launch resume")
        if facts.head_sha != manifest["current_head_sha"]:
            raise CycleError("pre-launch resume requires unchanged exact HEAD")
        if any(directory.glob("review-*.json")) or any(directory.glob("implementation-*.json")):
            raise CycleError("pre-launch resume has contradictory handoff/review artifacts")
        handoff = _blank_handoff(manifest)
    _validate_handoff(handoff, manifest)
    if is_retry_approved(manifest) and (
        handoff["implementer"] is not None or handoff["reviewer"] is not None
    ):
        raise CycleError("operational approval cannot contain an accepted handoff/review")
    return directory, manifest, handoff, facts


def _validate_pre_handoff_fields(document: dict[str, Any]) -> None:
    entries = document.get("pre_handoff_retries", [])
    if not isinstance(entries, list):
        raise CycleError("retry_attempt_metadata_inconsistent")
    keys = {
        "retry_kind",
        "approved_by",
        "approved_at",
        "implementation_attempt",
        "previous_attempt_id",
        "source_head",
        "branch",
        "repository_identity",
        "previous_stop_class",
        "previous_stop_code",
        "previous_stop_reason",
        "evidence",
    }
    for entry in entries:
        if not isinstance(entry, dict):
            raise CycleError("retry_attempt_metadata_inconsistent")
        _require_exact_keys(entry, keys, "pre-handoff approval")
        if (
            entry["retry_kind"] != "pre_handoff"
            or entry["approved_by"] != "human"
            or type(entry["implementation_attempt"]) is not int
            or type(entry["previous_attempt_id"]) is not int
            or entry["implementation_attempt"] != entry["previous_attempt_id"] + 1
            or entry["previous_attempt_id"] < 1
            or entry["branch"] != document["branch"]
            or entry["repository_identity"] != document["repository_fingerprint"]
            or not isinstance(entry["previous_stop_class"], str)
            or entry["previous_stop_class"] not in {"unknown", "operational"}
            or not isinstance(entry["previous_stop_reason"], str)
            or not isinstance(entry["approved_at"], str)
            or not re.fullmatch(
                r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?\+00:00", entry["approved_at"]
            )
            or not isinstance(entry["evidence"], dict)
            or not {"manifest.json", "handoff.json"} <= entry["evidence"].keys()
        ):
            raise CycleError("retry_attempt_metadata_inconsistent")
        try:
            datetime.fromisoformat(entry["approved_at"])
        except ValueError as error:
            raise CycleError("retry_attempt_metadata_inconsistent") from error
        _validated_sha(entry["source_head"], "retry source HEAD")
        code = entry["previous_stop_code"]
        if code is not None and (not isinstance(code, str) or not re.fullmatch(r"[a-z_]+", code)):
            raise CycleError("retry_attempt_metadata_inconsistent")
        for name, digest in entry["evidence"].items():
            if (
                not isinstance(name, str)
                or Path(name).name != name
                or name in {".", ".."}
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
            ):
                raise CycleError("retry_attempt_metadata_inconsistent")
    if entries:
        operational = document.get("operational_retries", [])
        if not isinstance(operational, list) or any(
            not isinstance(e, dict) or type(e.get("implementation_attempt")) is not int
            for e in operational
        ):
            raise CycleError("retry_attempt_metadata_inconsistent")
        numbers = [e["implementation_attempt"] for e in entries]
        if (
            numbers != sorted(numbers)
            or any(e["source_head"] != entries[0]["source_head"] for e in entries)
            or any(e.get("head_sha") != entries[0]["source_head"] for e in operational)
        ):
            raise CycleError("retry_attempt_metadata_inconsistent")
        # This also proves mixed operational/pre-handoff attempts have no gaps/duplicates.
        attempts = [e["implementation_attempt"] for e in retry_approvals(document)]
        if attempts != list(range(2, len(attempts) + 2)):
            raise CycleError("retry_attempt_metadata_inconsistent")
    if document["state"] == CycleState.HUMAN_APPROVED_PRE_HANDOFF_RETRY.value and (
        not entries
        or retry_state(document) != document["state"]
        or document["review_round"] != 0
        or document["active_agent"] is not None
        or document["current_head_sha"] != entries[-1]["source_head"]
        or document["stop_reason"] is not None
        or document.get("stop_code") is not None
        or document.get("stop_class") != "unknown"
        or document.get("implementation_attempt") != implementation_attempt(document)
    ):
        raise CycleError("retry_attempt_metadata_inconsistent")


def _validate_operational_fields(document: dict[str, Any]) -> None:
    classification = document.get("stop_class", "unknown")
    if not isinstance(classification, str) or classification not in set(StopClass):
        raise CycleError("invalid stop_class")
    code = document.get("stop_code")
    if code is not None and (not isinstance(code, str) or not re.fullmatch(r"[a-z_]+", code)):
        raise CycleError("invalid stop_code")
    if classification == StopClass.OPERATIONAL.value and code not in OPERATIONAL_CODES:
        raise CycleError("invalid operational stop code")
    approvals = document.get("operational_retries", [])
    if not isinstance(approvals, list) or len(approvals) > MAX_OPERATIONAL_RETRIES:
        raise CycleError("invalid operational retry history")
    for index, entry in enumerate(approvals):
        if not isinstance(entry, dict):
            raise CycleError("operational approval must be an object")
        _require_exact_keys(
            entry,
            {
                "type",
                "reason",
                "previous_stop_code",
                "previous_stop_reason",
                "head_sha",
                "branch",
                "review_round",
                "implementation_attempt",
            },
            "operational approval",
        )
        for field in ("reason", "previous_stop_reason", "branch"):
            value = entry[field]
            if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
                raise CycleError(f"invalid operational approval {field}")
        if len(entry["reason"]) > 200 or len(entry["previous_stop_reason"]) > 200:
            raise CycleError("invalid operational approval reason length")
        if (
            entry["type"] != "operational_retry"
            or not isinstance(entry["previous_stop_code"], str)
            or entry["previous_stop_code"] not in OPERATIONAL_CODES
            or type(entry["review_round"]) is not int
            or entry["review_round"] != 0
            or type(entry["implementation_attempt"]) is not int
            or entry["implementation_attempt"]
            != index
            + 2
            + sum(
                1
                for prior in document.get("pre_handoff_retries", [])
                if prior["implementation_attempt"] < entry["implementation_attempt"]
            )
            or entry["branch"] != document["branch"]
        ):
            raise CycleError("contradictory operational approval")
        _validated_sha(entry["head_sha"], "operational approval HEAD")
        if index and entry["head_sha"] != approvals[0]["head_sha"]:
            raise CycleError("operational approval HEAD changed")
    if document["state"] == CycleState.HUMAN_APPROVED_OPERATIONAL_RETRY.value and (
        retry_state(document) != document["state"]
        or not approvals
        or document["review_round"] != 0
        or document["active_agent"] is not None
        or document["current_head_sha"] != approvals[-1]["head_sha"]
        or document.get("stop_class", "unknown") != StopClass.UNKNOWN.value
        or document.get("stop_code") is not None
        or document["stop_reason"] is not None
    ):
        raise CycleError("operational retry state requires an unused approval")


def _validate_manifest(document: dict[str, Any], ticket: str) -> None:
    optional = {
        "human_recoveries",
        "stop_class",
        "stop_code",
        "operational_retries",
        "pre_handoff_retries",
        "implementation_attempt",
    }
    expected = MANIFEST_KEYS | (optional & document.keys())
    _require_exact_keys(document, expected, "manifest")
    _validate_pre_handoff_fields(document)
    _validate_operational_fields(document)
    recoveries = document.get("human_recoveries", [])
    if not isinstance(recoveries, list):
        raise CycleError("manifest human_recoveries must be a list")
    for index, recovery in enumerate(recoveries):
        if not isinstance(recovery, dict):
            raise CycleError("human recovery must be an object")
        _require_exact_keys(
            recovery,
            {
                "reason",
                "stop_reason",
                "review_round",
                "reviewed_sha",
                "implementation_attempt",
                "previous_handoff",
            },
            "human recovery",
        )
        if (
            not isinstance(recovery["reason"], str)
            or not recovery["reason"].strip()
            or len(recovery["reason"]) > 200
            or any(ord(character) < 32 for character in recovery["reason"])
        ):
            raise CycleError("human recovery requires a printable 1-200 character reason")
        if not isinstance(recovery["stop_reason"], str) or recovery["stop_reason"] not in {
            "repeated_finding",
            "review_round_limit",
        }:
            raise CycleError("invalid human recovery stop reason")
        expected_round = MAX_REVIEW_ROUNDS + index
        if (
            type(recovery["review_round"]) is not int
            or recovery["review_round"] != expected_round
            or type(recovery["implementation_attempt"]) is not int
            or recovery["implementation_attempt"]
            != expected_round + 1 + len(retry_approvals(document))
        ):
            raise CycleError("invalid human recovery round/attempt")
        _validated_sha(recovery["reviewed_sha"], "human recovery reviewed_sha")
        historical = dict(document)
        historical.update(
            {
                "review_round": expected_round,
                "current_head_sha": recovery["reviewed_sha"],
                "state": CycleState.STOPPED.value,
            }
        )
        _validate_handoff(recovery["previous_handoff"], historical)
    _require_schema(document, "manifest")
    if document["ticket"] != ticket:
        raise CycleError("manifest belongs to a different ticket")
    _validated_sha(document["base_sha"], "manifest base_sha")
    _validated_sha(document["current_head_sha"], "manifest current_head_sha")
    if not isinstance(document["repository_fingerprint"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", document["repository_fingerprint"]
    ):
        raise CycleError("invalid manifest repository_fingerprint")
    for field in ("branch", "base_branch"):
        if not isinstance(document[field], str) or not document[field].strip():
            raise CycleError(f"manifest {field} must be a non-empty string")
    if not isinstance(document["review_round"], int) or isinstance(document["review_round"], bool):
        raise CycleError("manifest review_round must be an integer")
    if not 0 <= document["review_round"] <= _authorized_review_limit(document):
        raise CycleError("manifest review_round exceeds human-authorized limit")
    if recoveries and document["review_round"] < MAX_REVIEW_ROUNDS + len(recoveries) - 1:
        raise CycleError("manifest round predates human recovery")
    if document["state"] == CycleState.HUMAN_APPROVED_REWORK.value and (
        not recoveries or document["review_round"] != _authorized_review_limit(document) - 1
    ):
        raise CycleError("HUMAN_APPROVED_REWORK requires an unused explicit human approval")
    try:
        CycleState(document["state"])
    except (TypeError, ValueError) as error:
        raise CycleError(f"invalid manifest state: {document['state']!r}") from error
    if document["active_agent"] is not None and (
        not isinstance(document["active_agent"], str)
        or document["active_agent"] not in {agent.value for agent in ActiveAgent}
    ):
        raise CycleError(f"invalid active_agent: {document['active_agent']!r}")
    if not isinstance(document["working_tree_clean"], bool):
        raise CycleError("manifest working_tree_clean must be boolean")
    started_head = document["review_started_head"]
    if started_head is not None:
        _validated_sha(started_head, "manifest review_started_head")
    started_status = document["review_started_status"]
    if started_status is not None and not _is_string_list(started_status):
        raise CycleError("manifest review_started_status must be null or a string list")
    attempt = document.get("implementation_attempt")
    if "implementation_attempt" in document and (
        type(attempt) is not int
        or not max(1, document["review_round"] + len(retry_approvals(document)))
        <= attempt
        <= implementation_attempt(document)
    ):
        raise CycleError("invalid manifest implementation_attempt")
    stop_reason = document["stop_reason"]
    if stop_reason is not None and not isinstance(stop_reason, str):
        raise CycleError("manifest stop_reason must be null or a string")


def _validate_handoff(document: dict[str, Any], manifest: dict[str, Any]) -> None:
    if not isinstance(document, dict):
        raise CycleError("handoff must be an object")
    _require_exact_keys(document, HANDOFF_KEYS, "handoff")
    _require_schema(document, "handoff")
    system = document["system"]
    if not isinstance(system, dict):
        raise CycleError("handoff system section must be an object")
    _require_exact_keys(system, SYSTEM_KEYS, "handoff system")
    expected_system = _system_from_manifest(manifest)
    if json.dumps(system, sort_keys=True) != json.dumps(expected_system, sort_keys=True):
        raise CycleError("handoff system section does not match authoritative manifest state")
    implementer = document["implementer"]
    if implementer is not None:
        _validate_implementer_input(implementer, manifest["ticket"], manifest, persisted=True)
    reviewer = document["reviewer"]
    if reviewer is not None:
        _validate_review_input(reviewer, manifest["ticket"], manifest, persisted=True)


def _validate_implementer_input(
    document: dict[str, Any],
    ticket: str,
    manifest: dict[str, Any],
    *,
    persisted: bool = False,
) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise CycleError("implementer handoff must be a JSON object")
    _require_exact_keys(document, IMPLEMENTER_KEYS, "implementer handoff")
    _require_schema(document, "implementer handoff")
    if document["ticket"] != ticket:
        raise CycleError("implementer handoff belongs to a different ticket")
    expected_attempt = implementation_attempt(manifest)
    if (
        type(document["implementation_attempt"]) is not int
        or document["implementation_attempt"] < 1
    ):
        raise CycleError("implementation_attempt must be a positive integer")
    if document["implementation_attempt"] != expected_attempt:
        if not persisted:
            raise CycleError(f"implementation_attempt must be {expected_attempt}")
        if not isinstance(document["implementation_attempt"], int):
            raise CycleError("invalid persisted implementation_attempt")
    if document["status"] != "COMPLETE":
        raise CycleError("implementer status must be COMPLETE")
    report = document["implementation_report"]
    expected_report = f".implementation-reports/implementation-report-{ticket}.md"
    if report != expected_report:
        raise CycleError(f"implementation_report must be {expected_report}")
    for field in ("focused_tests", "full_tests", "check_ps1"):
        if document[field] not in CHECK_RESULTS:
            raise CycleError(f"invalid {field}: {document[field]!r}")
    for field in ("known_limitations", "notes"):
        if not _is_string_list(document[field]):
            raise CycleError(f"implementer {field} must be a string list")
    return document


def _validate_review_input(
    document: dict[str, Any],
    ticket: str,
    manifest: dict[str, Any],
    *,
    persisted: bool = False,
) -> ReviewInput:
    if not isinstance(document, dict):
        raise CycleError("reviewer input must be a JSON object")
    _require_exact_keys(document, REVIEW_KEYS, "reviewer input")
    _require_schema(document, "reviewer input")
    if document["ticket"] != ticket:
        raise CycleError("review artifact belongs to a different ticket")
    review_round = document["review_round"]
    if not isinstance(review_round, int) or isinstance(review_round, bool):
        raise CycleError("review_round must be an integer")
    if not 1 <= review_round <= _authorized_review_limit(manifest):
        raise CycleError("review_round exceeds human-authorized limit")
    if review_round != manifest["review_round"]:
        raise CycleError("review artifact round does not match manifest review_round")
    reviewed_sha = _validated_sha(document["reviewed_sha"], "reviewed_sha")
    expected_sha = manifest["current_head_sha"] if persisted else manifest["review_started_head"]
    if reviewed_sha != expected_sha:
        raise CycleError("reviewed_sha does not match the exact SHA under review")
    try:
        verdict = ReviewVerdict(document["verdict"])
    except (TypeError, ValueError) as error:
        raise CycleError(f"invalid review verdict: {document['verdict']!r}") from error
    raw_findings = document["findings"]
    if not isinstance(raw_findings, list):
        raise CycleError("review findings must be a list")
    findings = tuple(_validate_finding(item) for item in raw_findings)
    blocked_reason = document["blocked_reason"]
    if blocked_reason is not None and (
        not isinstance(blocked_reason, str) or not blocked_reason.strip()
    ):
        raise CycleError("blocked_reason must be null or a non-empty string")
    if verdict == ReviewVerdict.PASS and findings:
        raise CycleError("PASS requires findings = []")
    if verdict == ReviewVerdict.CHANGES_REQUIRED and not findings:
        raise CycleError("CHANGES_REQUIRED requires at least one finding")
    if verdict == ReviewVerdict.BLOCKED and blocked_reason is None:
        raise CycleError("BLOCKED requires blocked_reason")
    return ReviewInput(
        SCHEMA_VERSION, ticket, review_round, reviewed_sha, verdict, findings, blocked_reason
    )


def _validate_finding(document: object) -> Finding:
    if not isinstance(document, dict):
        raise CycleError("each finding must be a JSON object")
    _require_exact_keys(document, FINDING_KEYS, "review finding")
    for field in ("id", "problem", "required_fix"):
        if not isinstance(document[field], str) or not document[field].strip():
            raise CycleError(f"finding {field} must be a non-empty string")
    if document["severity"] not in SEVERITIES:
        raise CycleError(f"invalid finding severity: {document['severity']!r}")
    for field in ("file", "symbol", "regression_test"):
        if not isinstance(document[field], str):
            raise CycleError(f"finding {field} must be a string")
    return Finding(**document)


def _repeated_finding_keys(directory: Path, review: ReviewInput) -> set[tuple[str, str, str]]:
    if review.review_round <= 1:
        return set()
    previous_document = _load_json(directory / f"review-{review.review_round - 1}.json")
    manifest = _load_json(directory / "manifest.json")
    previous_manifest = dict(manifest)
    previous_manifest["review_round"] = review.review_round - 1
    previous_manifest["current_head_sha"] = previous_document.get("reviewed_sha")
    previous = _validate_review_input(
        previous_document, review.ticket, previous_manifest, persisted=True
    )
    previous_keys = {finding.stable_key for finding in previous.findings}
    current_keys = {finding.stable_key for finding in review.findings}
    return previous_keys & current_keys


def _review_to_dict(review: ReviewInput) -> dict[str, Any]:
    return {
        "schema_version": review.schema_version,
        "ticket": review.ticket,
        "review_round": review.review_round,
        "reviewed_sha": review.reviewed_sha,
        "verdict": review.verdict.value,
        "findings": [asdict(finding) for finding in review.findings],
        "blocked_reason": review.blocked_reason,
    }


def _blank_handoff(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "system": _system_from_manifest(manifest),
        "implementer": None,
        "reviewer": None,
    }


def _system_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticket": manifest["ticket"],
        "branch": manifest["branch"],
        "base_sha": manifest["base_sha"],
        "current_head_sha": manifest["current_head_sha"],
        "review_round": manifest["review_round"],
        "state": manifest["state"],
    }


def _sync_system(handoff: dict[str, Any], manifest: dict[str, Any]) -> None:
    handoff["system"] = _system_from_manifest(manifest)


def _write_cycle(directory: Path, manifest: dict[str, Any], handoff: dict[str, Any]) -> None:
    _validate_manifest(manifest, manifest["ticket"])
    _validate_handoff(handoff, manifest)
    _atomic_write_json(directory / "manifest.json", manifest)
    _atomic_write_json(directory / "handoff.json", handoff)


def _atomic_write_json(path: Path, document: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        temporary.replace(path)
    except (OSError, UnicodeError) as error:
        temporary.unlink(missing_ok=True)
        raise CycleError(f"cannot write {path.name}: {error}") from error


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CycleError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except FileNotFoundError as error:
        raise CycleError(f"required JSON file is missing: {path}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CycleError(f"cannot read valid JSON from {path}: {error}") from error
    if not isinstance(document, dict):
        raise CycleError(f"JSON root must be an object: {path}")
    return document


def _require_exact_keys(document: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(document)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown: {', '.join(unknown)}")
        raise CycleError(f"invalid {label} fields ({'; '.join(details)})")


def _require_schema(document: dict[str, Any], label: str) -> None:
    if document["schema_version"] != SCHEMA_VERSION:
        raise CycleError(f"unsupported {label} schema_version: {document['schema_version']!r}")


def _validated_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not SHA_PATTERN.fullmatch(value):
        raise CycleError(f"{label} must be a 40-character lowercase Git SHA")
    return value


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _require_clean(facts: GitFacts, operation: str) -> None:
    if not facts.clean:
        raise CycleError(f"{operation} requires a clean working tree")


def _require_no_active_agent(manifest: dict[str, Any]) -> None:
    if manifest["active_agent"] is not None:
        raise CycleError(f"another agent is already active: {manifest['active_agent']}")


def _print_status(status: dict[str, Any]) -> None:
    active = status["active_agent"] or "none"
    tree = "clean" if status["working_tree_clean"] else "dirty"
    if status["working_tree_dirty_expected"]:
        tree += " (expected during implementation)"
    print(f"Ticket: {status['ticket']}")
    print(f"State: {status['state']}")
    print(f"Branch: {status['branch']}")
    print(f"HEAD: {status['head_sha']}")
    print(f"Expected HEAD: {status['expected_head_sha']}")
    print(f"Pre-handoff retry eligible: {'yes' if status['pre_handoff_retry_eligible'] else 'no'}")
    if status["pre_handoff_retry_rejection"]:
        print(f"Rejection code: {status['pre_handoff_retry_rejection']}")
    print(
        f"Review round: {status['review_round']} (automatic limit: {status['max_review_rounds']})"
    )
    print(f"Human approvals: {status['human_recovery_count']}")
    print(f"Implementation attempt: {status['implementation_attempt']}")
    print(f"Operational retries: {status['operational_retry_count']}")
    print(f"Stop class: {status['stop_class']}")
    print(f"Stop code: {status['stop_code'] or 'none'}")
    print(f"Operational retry eligible: {'yes' if status['operational_retry_eligible'] else 'no'}")
    if status["operational_retry_rejection"]:
        print(f"Reason: {status['operational_retry_rejection']}")
    if status["stop_reason"]:
        print(f"Stop reason: {status['stop_reason']}")
    print(f"Active agent: {active}")
    print(f"Working tree: {tree}")
    print(f"Review valid for HEAD: {'yes' if status['review_valid_for_head'] else 'no'}")
    for error in status["errors"]:
        print(f"ERROR: {error}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init", help="initialize a clean ticket cycle")
    init.add_argument("ticket")
    init.add_argument("--base-branch", default="master")
    begin = subparsers.add_parser("begin-implementation", help="grant implementer write ownership")
    begin.add_argument("ticket")
    handoff = subparsers.add_parser("handoff", help="record a validated implementer handoff")
    handoff.add_argument("ticket")
    handoff.add_argument("--file", type=Path, required=True)
    review = subparsers.add_parser("begin-review", help="begin exact-SHA read-only reviewer phase")
    review.add_argument("ticket")
    review.add_argument("--sha", required=True)
    record = subparsers.add_parser("record-review", help="record immutable reviewer result")
    record.add_argument("ticket")
    record.add_argument("--file", type=Path, required=True)
    status = subparsers.add_parser("status", help="validate and display current state")
    status.add_argument("ticket")
    status.add_argument("--json", action="store_true")
    status.add_argument("--verify-remote", metavar="REMOTE")
    reopen = subparsers.add_parser("reopen", help="human approval of one follow-up review pair")
    reopen.add_argument("ticket")
    reopen.add_argument("--reason", required=True)
    retry = subparsers.add_parser("retry-operational", help="human approval of pre-handoff retry")
    retry.add_argument("ticket")
    retry.add_argument("--reason", required=True)
    pre_handoff = subparsers.add_parser(
        "retry-pre-handoff", help="human approval of a proven unchanged pre-handoff attempt"
    )
    pre_handoff.add_argument("ticket")
    stop = subparsers.add_parser("stop", help="record an external/manual stop")
    stop.add_argument("ticket")
    stop.add_argument("--reason", required=True)
    return parser


def main(argv: list[str] | None = None, *, repo_root: Path | None = None) -> int:
    arguments = _parser().parse_args(argv)
    root = (repo_root or Path.cwd()).resolve()
    try:
        if arguments.command == "init":
            initialize_cycle(root, arguments.ticket, arguments.base_branch)
        elif arguments.command == "begin-implementation":
            begin_implementation(root, arguments.ticket)
        elif arguments.command == "handoff":
            record_handoff(root, arguments.ticket, arguments.file)
        elif arguments.command == "begin-review":
            begin_review(root, arguments.ticket, arguments.sha)
        elif arguments.command == "record-review":
            record_review(root, arguments.ticket, arguments.file)
        elif arguments.command == "reopen":
            reopen_cycle(root, arguments.ticket, arguments.reason)
        elif arguments.command == "retry-operational":
            retry_operational_cycle(root, arguments.ticket, arguments.reason)
        elif arguments.command == "retry-pre-handoff":
            # The approval loader reports a structured rejection on binding/corrupt state.
            with contextlib.suppress(CycleError):
                _print_status(cycle_status(root, arguments.ticket))
            retry_pre_handoff_cycle(root, arguments.ticket)
        elif arguments.command == "stop":
            stop_cycle(root, arguments.ticket, arguments.reason)
        elif arguments.command == "status":
            status = cycle_status(root, arguments.ticket, verify_remote=arguments.verify_remote)
            if arguments.json:
                print(json.dumps(status, indent=2, sort_keys=True))
            else:
                _print_status(status)
            return 1 if status["errors"] else 0
        else:
            _unreachable(arguments.command)
        status = cycle_status(root, arguments.ticket)
        _print_status(status)
        return 1 if status["errors"] else 0
    except CycleError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


def _unreachable(command: object) -> NoReturn:
    raise AssertionError(f"unhandled command: {command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
