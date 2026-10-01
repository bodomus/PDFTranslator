"""Validate and record sequential implementer/reviewer ticket-cycle state."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, NoReturn

SCHEMA_VERSION = "1.0"
MAX_REVIEW_ROUNDS = 2
TICKET_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*-[1-9][0-9]*[A-Z]*$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
COORDINATION_DIRECTORY = ".agent-cycle"


class CycleError(RuntimeError):
    """A fail-closed coordination or validation error."""


class CycleState(StrEnum):
    NEW = "NEW"
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
    coordination_root = (repo_root.resolve() / COORDINATION_DIRECTORY).resolve()
    candidate = (coordination_root / ticket).resolve()
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
    if state not in {CycleState.NEW, CycleState.CHANGES_REQUIRED}:
        raise CycleError(f"cannot begin implementation from {state.value}")
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
    if manifest["review_round"]:
        previous = _load_json(directory / f"review-{manifest['review_round']}.json")
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
    if manifest["review_round"] >= MAX_REVIEW_ROUNDS:
        raise CycleError(f"maximum review rounds is {MAX_REVIEW_ROUNDS}")
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
    manifest["review_started_head"] = None
    manifest["review_started_status"] = None
    handoff["reviewer"] = review_document
    _sync_system(handoff, manifest)
    _atomic_write_json(artifact_path, review_document)
    _write_cycle(directory, manifest, handoff)
    return manifest


def stop_cycle(repo_root: Path, ticket: str, reason: str) -> dict[str, Any]:
    reason = reason.strip()
    if not reason or any(ord(character) < 32 for character in reason) or len(reason) > 200:
        raise CycleError("stop reason must be 1-200 printable characters")
    directory, manifest, handoff, _facts = _load_cycle(repo_root, ticket)
    if CycleState(manifest["state"]) in {CycleState.PASSED, CycleState.BLOCKED}:
        raise CycleError(f"cannot stop terminal state {manifest['state']}")
    manifest["state"] = CycleState.STOPPED.value
    manifest["active_agent"] = None
    manifest["stop_reason"] = reason
    manifest["review_started_head"] = None
    manifest["review_started_status"] = None
    _sync_system(handoff, manifest)
    _write_cycle(directory, manifest, handoff)
    return manifest


def cycle_status(
    repo_root: Path, ticket: str, *, verify_remote: str | None = None
) -> dict[str, Any]:
    _directory, manifest, handoff, facts = _load_cycle(repo_root, ticket)
    errors: list[str] = []
    if facts.head_sha != manifest["current_head_sha"]:
        errors.append("Git HEAD differs from manifest current_head_sha")
    if facts.clean != manifest["working_tree_clean"]:
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
        "active_agent": manifest["active_agent"],
        "working_tree_clean": facts.clean,
        "review_valid_for_head": review_valid,
        "remote_tip": remote_tip,
        "errors": errors,
    }


def _load_cycle(
    repo_root: Path, ticket: str
) -> tuple[Path, dict[str, Any], dict[str, Any], GitFacts]:
    ticket = validate_ticket_id(ticket)
    requested = repo_root.resolve()
    actual = Path(_run_git(requested, "rev-parse", "--show-toplevel")).resolve()
    if actual != requested:
        raise CycleError(f"run from repository root: expected {actual}, got {requested}")
    directory = cycle_directory(requested, ticket)
    if not directory.is_dir():
        raise CycleError(f"ticket cycle does not exist: {ticket}")
    manifest = _load_json(directory / "manifest.json")
    _validate_manifest(manifest, ticket)
    handoff = _load_json(directory / "handoff.json")
    _validate_handoff(handoff, manifest)
    facts = collect_git_facts(requested, manifest["base_branch"])
    if facts.repository_fingerprint != manifest["repository_fingerprint"]:
        raise CycleError("cycle belongs to a different Git repository")
    if facts.branch != manifest["branch"]:
        raise CycleError(
            f"wrong task branch: expected {manifest['branch']!r}, found {facts.branch!r}"
        )
    if facts.base_sha != manifest["base_sha"]:
        raise CycleError("merge base differs from the initialized ticket cycle")
    return directory, manifest, handoff, facts


def _validate_manifest(document: dict[str, Any], ticket: str) -> None:
    _require_exact_keys(document, MANIFEST_KEYS, "manifest")
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
    if not 0 <= document["review_round"] <= MAX_REVIEW_ROUNDS:
        raise CycleError(f"manifest review_round exceeds {MAX_REVIEW_ROUNDS}")
    try:
        CycleState(document["state"])
    except (TypeError, ValueError) as error:
        raise CycleError(f"invalid manifest state: {document['state']!r}") from error
    if document["active_agent"] not in {None, *(agent.value for agent in ActiveAgent)}:
        raise CycleError(f"invalid active_agent: {document['active_agent']!r}")
    if not isinstance(document["working_tree_clean"], bool):
        raise CycleError("manifest working_tree_clean must be boolean")
    started_head = document["review_started_head"]
    if started_head is not None:
        _validated_sha(started_head, "manifest review_started_head")
    started_status = document["review_started_status"]
    if started_status is not None and not _is_string_list(started_status):
        raise CycleError("manifest review_started_status must be null or a string list")
    stop_reason = document["stop_reason"]
    if stop_reason is not None and not isinstance(stop_reason, str):
        raise CycleError("manifest stop_reason must be null or a string")


def _validate_handoff(document: dict[str, Any], manifest: dict[str, Any]) -> None:
    _require_exact_keys(document, HANDOFF_KEYS, "handoff")
    _require_schema(document, "handoff")
    system = document["system"]
    if not isinstance(system, dict):
        raise CycleError("handoff system section must be an object")
    _require_exact_keys(system, SYSTEM_KEYS, "handoff system")
    expected_system = _system_from_manifest(manifest)
    if system != expected_system:
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
    expected_attempt = manifest["review_round"] + 1
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
    if not 1 <= review_round <= MAX_REVIEW_ROUNDS:
        raise CycleError(f"review_round must be between 1 and {MAX_REVIEW_ROUNDS}")
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


def _load_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
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
    print(f"Ticket: {status['ticket']}")
    print(f"State: {status['state']}")
    print(f"Branch: {status['branch']}")
    print(f"HEAD: {status['head_sha']}")
    print(f"Review round: {status['review_round']} / {status['max_review_rounds']}")
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
