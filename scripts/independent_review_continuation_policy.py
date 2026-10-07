"""Pure trusted continuation eligibility. No I/O and no agent execution."""

from scripts.independent_review_policy import (
    IndependentReviewError,
    evaluate_independent_review,
    validate_state,
)

MAX_INDEPENDENT_CONTINUATIONS = 2


def evaluate_continuation(
    cycle: dict,
    independent: dict,
    publication: dict,
    history: list[dict],
    facts: dict,
    safety: dict,
) -> dict:
    """All inputs are normalized by the trusted parent, never agent assertions."""

    def reject(reason):
        return {"decision": "REJECTED", "reason": "continuation_" + reason}

    try:
        config = {
            k: independent[k]
            for k in ("schema_version", "repository", "ticket", "pull_request", "required_checks")
        }
        validate_state(independent, config)
        intent = publication.get("continuation")
        if publication.get("publication_state") in {"PENDING", "PUBLICATION_UNCERTAIN"}:
            return reject("publication_uncertain")
        if publication.get("publication_state") != "PUBLISHED":
            return reject("not_published")
        if type(intent) is not dict:
            return reject("intent_missing")
        generation = intent.get("generation")
        if type(generation) is not int or generation != independent["current_generation"]:
            return reject("generation_mismatch")
        if generation < 1:
            return reject("generation_mismatch")
        review = independent["reviews"][generation - 1]
        expected = {
            "schema_version": "1.0",
            "ticket": config["ticket"],
            "source": "independent_review",
            "generation": generation,
            "reviewed_sha": review["requested_sha"],
            "verdict": "CHANGES_REQUIRED",
            "status": "PENDING_HUMAN_OR_POLICY",
        }
        if intent != expected or publication.get("generation") != generation:
            return reject("generation_mismatch")
        if review["status"] == "DISPATCH_UNCERTAIN":
            return reject("dispatch_uncertain")
        if not review["result"] or review["result"]["verdict"] != "CHANGES_REQUIRED":
            return reject("not_changes_required")
        if review["status"] != "CHANGES_REQUIRED":
            return reject("stale")
        if facts.get("head_sha") != review["requested_sha"]:
            return reject("head_mismatch")
        if facts.get("base_sha") != review["requested_base_sha"]:
            return reject("base_mismatch")
        if cycle.get("state") != "PASSED" or cycle.get("human_recoveries"):
            return reject("cycle_state_invalid")
        if cycle.get("current_head_sha") != review["requested_sha"]:
            return reject("cycle_sha_mismatch")
        if cycle.get("active_agent") is not None:
            return reject("agent_active")
        for field, reason in (
            ("repository_matches", "repository_mismatch"),
            ("branch_matches", "branch_mismatch"),
            ("head_matches", "head_mismatch"),
            ("clean", "dirty_tree"),
            ("no_operation", "repository_operation"),
            ("no_active_agent", "agent_active"),
            ("publication_resolved", "publication_uncertain"),
        ):
            if safety.get(field) is not True:
                return reject(reason)
        if type(history) is not list or any(
            type(e) is not dict
            or type(e.get("source_generation")) is not int
            or e["source_generation"] < 1
            for e in history
        ):
            return reject("state_corrupt")
        if any(e.get("source_generation") == generation for e in history):
            return reject("already_used")
        if len(history) >= MAX_INDEPENDENT_CONTINUATIONS:
            return reject("budget_exhausted")
        decision = evaluate_independent_review(facts, independent, config)
        if decision["decision"] != "ALREADY_REVIEWED" or decision["generation"] != generation:
            return reject("reference_facts_invalid")
        return {"decision": "AUTHORIZED", "reason": "continuation_authorized"}
    except (IndependentReviewError, KeyError, TypeError, IndexError):
        return reject("state_corrupt")
