"""Pure exact-SHA independent-review contract; no I/O or event-specific authority.

Inputs are JSON-shaped normalized facts refreshed by a trusted harness. Configuration
is independently trusted. Inspection of user-supplied facts is not merge authorization.
"""

from __future__ import annotations

import copy
import re
from typing import Any

SCHEMA_VERSION = "1.0"
SHA = re.compile(r"[0-9a-f]{40}")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
TICKET = re.compile(r"PDFTR-[1-9][0-9]*[A-Z]?")
ACTIVE = {"REQUESTED", "RUNNING", "DISPATCH_UNCERTAIN"}
VERDICTS = {"PASS", "CHANGES_REQUIRED"}
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


class IndependentReviewError(ValueError):
    """Incomplete, contradictory or unbound independent-review input."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise IndependentReviewError(reason)


def _keys(value: Any, keys: str) -> None:
    _require(type(value) is dict and set(value) == set(keys.split()), "invalid_schema")


def _text(value: Any) -> bool:
    return type(value) is str and bool(value.strip())


def _sha(value: Any) -> bool:
    return type(value) is str and SHA.fullmatch(value) is not None


def validate_config(config: dict) -> None:
    _keys(config, "schema_version repository ticket pull_request required_checks")
    _require(config["schema_version"] == SCHEMA_VERSION, "invalid_schema")
    _require(
        type(config["repository"]) is str
        and REPOSITORY.fullmatch(config["repository"]) is not None,
        "invalid_repository",
    )
    _require(
        type(config["ticket"]) is str and TICKET.fullmatch(config["ticket"]) is not None,
        "invalid_ticket",
    )
    _require(type(config["pull_request"]) is int and config["pull_request"] > 0, "invalid_pr")
    checks = config["required_checks"]
    _require(
        type(checks) is list and bool(checks) and all(_text(c) for c in checks),
        "invalid_required_checks",
    )
    _require(len(set(checks)) == len(checks), "invalid_required_checks")


def _binding(document: dict, config: dict) -> None:
    for key in ("repository", "ticket", "pull_request"):
        _require(
            type(document[key]) is type(config[key]) and document[key] == config[key],
            f"{key}_mismatch",
        )


def validate_facts(facts: dict, config: dict) -> None:
    validate_config(config)
    _keys(
        facts,
        "schema_version repository ticket pull_request pr_exists pr_state pr_draft "
        "head_sha base_sha cycle_state implementation_sha ci_sha checks",
    )
    _require(facts["schema_version"] == SCHEMA_VERSION, "invalid_schema")
    _binding(facts, config)
    _require(type(facts["pr_exists"]) is bool and type(facts["pr_draft"]) is bool, "invalid_facts")
    _require(facts["pr_state"] in ("OPEN", "CLOSED", "MERGED", "UNKNOWN"), "invalid_facts")
    _require(_text(facts["cycle_state"]), "invalid_facts")
    for key in ("head_sha", "base_sha", "implementation_sha", "ci_sha"):
        _require(_sha(facts[key]), "invalid_sha")
    _require(type(facts["checks"]) is dict, "invalid_checks")
    for name, status in facts["checks"].items():
        _require(
            _text(name)
            and type(status) is str
            and status in {"PENDING", "SUCCESS", "FAILURE", "UNKNOWN"},
            "invalid_checks",
        )


def empty_state(config: dict) -> dict:
    validate_config(config)
    return {**copy.deepcopy(config), "current_generation": 0, "reviews": []}


def validate_result(result: dict, config: dict) -> None:
    _keys(
        result,
        "schema_version repository ticket pull_request generation reviewed_sha verdict findings",
    )
    _require(result["schema_version"] == SCHEMA_VERSION, "invalid_schema")
    _binding(result, config)
    _require(type(result["generation"]) is int and result["generation"] > 0, "invalid_generation")
    _require(_sha(result["reviewed_sha"]), "invalid_sha")
    _require(type(result["verdict"]) is str and result["verdict"] in VERDICTS, "invalid_verdict")
    _require(type(result["findings"]) is list, "invalid_findings")
    ids = set()
    for finding in result["findings"]:
        _keys(finding, "id severity file symbol problem required_fix regression_test")
        for field in ("id", "problem", "required_fix"):
            _require(_text(finding[field]), "invalid_findings")
        for field in ("file", "symbol", "regression_test"):
            _require(type(finding[field]) is str, "invalid_findings")
        _require(
            type(finding["severity"]) is str and finding["severity"] in SEVERITIES,
            "invalid_findings",
        )
        _require(finding["id"] not in ids, "invalid_findings")
        ids.add(finding["id"])
    _require(
        bool(result["findings"]) == (result["verdict"] == "CHANGES_REQUIRED"), "invalid_findings"
    )


def validate_state(state: dict, config: dict) -> None:
    validate_config(config)
    _keys(
        state,
        "schema_version repository ticket pull_request required_checks current_generation reviews",
    )
    _require(
        all(type(state[k]) is type(v) and state[k] == v for k, v in config.items()),
        "state_binding_mismatch",
    )
    _require(
        type(state["current_generation"]) is int and type(state["reviews"]) is list, "state_corrupt"
    )
    _require(state["current_generation"] == len(state["reviews"]), "state_corrupt")
    pairs = set()
    for generation, review in enumerate(state["reviews"], 1):
        _keys(review, "generation requested_sha requested_base_sha status result")
        _require(
            type(review["generation"]) is int and review["generation"] == generation,
            "state_corrupt",
        )
        _require(
            _sha(review["requested_sha"]) and _sha(review["requested_base_sha"]), "state_corrupt"
        )
        pair = (review["requested_sha"], review["requested_base_sha"])
        _require(pair not in pairs, "state_corrupt")
        pairs.add(pair)
        status = review["status"]
        _require(type(status) is str and status in ACTIVE | VERDICTS | {"STALE"}, "state_corrupt")
        if generation != state["current_generation"]:
            _require(status == "STALE", "state_corrupt")
        result = review["result"]
        if result is None:
            _require(status in ACTIVE | {"STALE"}, "state_corrupt")
        else:
            validate_result(result, config)
            _require(
                result["generation"] == generation
                and result["reviewed_sha"] == review["requested_sha"],
                "state_corrupt",
            )
            _require(status in {result["verdict"], "STALE"}, "state_corrupt")


def _readiness(facts: dict, config: dict) -> str | None:
    if not facts["pr_exists"]:
        return "pr_missing"
    if facts["pr_state"] != "OPEN":
        return "pr_closed"
    if facts["pr_draft"]:
        return "pr_draft"
    if facts["cycle_state"] != "PASSED":
        return "cycle_not_passed"
    if facts["head_sha"] != facts["implementation_sha"]:
        return "sha_mismatch"
    if facts["ci_sha"] != facts["head_sha"]:
        return "ci_sha_mismatch"
    statuses = [facts["checks"].get(name, "UNKNOWN") for name in config["required_checks"]]
    if "FAILURE" in statuses:
        return "ci_failed"
    if "UNKNOWN" in statuses:
        return "ci_unknown"
    if "PENDING" in statuses:
        return "ci_pending"
    return None


def evaluate_independent_review(facts: dict, state: dict, config: dict) -> dict:
    """Return a stable decision; unchanged inputs always give identical output."""
    try:
        validate_facts(facts, config)
        validate_state(state, config)
    except IndependentReviewError as error:
        return {"decision": "INVALID", "reason": str(error), "generation": None}
    reason = _readiness(facts, config)
    if reason:
        return {"decision": "NOT_ELIGIBLE", "reason": reason, "generation": None}
    for review in state["reviews"]:
        if (
            review["requested_sha"] == facts["head_sha"]
            and review["requested_base_sha"] == facts["base_sha"]
        ):
            status = review["status"]
            decision = (
                "ALREADY_REQUESTED"
                if status in ACTIVE
                else "STALE"
                if status == "STALE"
                else "ALREADY_REVIEWED"
            )
            return {
                "decision": decision,
                "reason": decision.lower(),
                "generation": review["generation"],
            }
    return {
        "decision": "ELIGIBLE",
        "reason": "eligible",
        "generation": state["current_generation"] + 1,
    }


def refresh_state(facts: dict, state: dict, config: dict) -> dict:
    """Revoke old statuses without discarding request identity or result evidence."""
    validate_facts(facts, config)
    validate_state(state, config)
    updated = copy.deepcopy(state)
    for review in updated["reviews"]:
        if (
            review["requested_sha"] != facts["head_sha"]
            or review["requested_base_sha"] != facts["base_sha"]
        ):
            review["status"] = "STALE"
    return updated


def request_review(facts: dict, state: dict, config: dict) -> tuple[dict, dict]:
    """Compute request intent; caller MUST durably persist before any dispatch."""
    updated = refresh_state(facts, state, config)
    decision = evaluate_independent_review(facts, updated, config)
    if decision["decision"] == "ELIGIBLE":
        updated["current_generation"] = decision["generation"]
        updated["reviews"].append(
            {
                "generation": decision["generation"],
                "requested_sha": facts["head_sha"],
                "requested_base_sha": facts["base_sha"],
                "status": "REQUESTED",
                "result": None,
            }
        )
    return updated, decision


def record_result(facts: dict, state: dict, config: dict, result: dict) -> dict:
    """Accept trusted reviewer evidence once, retaining late results as STALE."""
    updated = refresh_state(facts, state, config)
    validate_result(result, config)
    generation = result["generation"]
    _require(generation <= len(updated["reviews"]), "unknown_generation")
    review = updated["reviews"][generation - 1]
    _require(review["requested_sha"] == result["reviewed_sha"], "result_sha_mismatch")
    if review["result"] is not None:
        _require(review["result"] == result, "result_immutable")
        return updated
    review["result"] = copy.deepcopy(result)
    review["status"] = (
        "STALE"
        if review["status"] == "STALE" or facts["head_sha"] != result["reviewed_sha"]
        else result["verdict"]
    )
    return updated


def mark_dispatch(state: dict, config: dict, generation: int, status: str) -> dict:
    """Reserve external dispatch states; uncertainty never authorizes redispatch."""
    validate_state(state, config)
    _require(
        type(generation) is int and 1 <= generation <= len(state["reviews"]), "unknown_generation"
    )
    _require(
        type(status) is str and status in {"RUNNING", "DISPATCH_UNCERTAIN"},
        "invalid_dispatch_status",
    )
    updated = copy.deepcopy(state)
    review = updated["reviews"][generation - 1]
    _require(review["status"] in ACTIVE and review["result"] is None, "invalid_transition")
    _require(
        review["status"] != "DISPATCH_UNCERTAIN" or status == "DISPATCH_UNCERTAIN",
        "dispatch_uncertain",
    )
    review["status"] = status
    return updated


def pass_is_valid(facts: dict, state: dict, config: dict) -> bool:
    """Exact current PASS plus every readiness fact; never a merge grant."""
    decision = evaluate_independent_review(facts, state, config)
    if decision["decision"] != "ALREADY_REVIEWED":
        return False
    review = state["reviews"][decision["generation"] - 1]
    return (
        review["status"] == "PASS"
        and review["result"]["verdict"] == "PASS"
        and review["requested_sha"] == facts["head_sha"]
        and review["result"]["reviewed_sha"] == facts["head_sha"]
        and review["requested_base_sha"] == facts["base_sha"]
    )
