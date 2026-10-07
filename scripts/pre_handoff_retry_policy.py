"""Human recovery policy; no stop prose, agent claims, or Git subprocesses."""

from pathlib import Path
from typing import Any


def evaluate_pre_handoff_retry(
    manifest: dict[str, Any], handoff: dict[str, Any], facts: Any, directory: Path
) -> str | None:
    if manifest["state"] != "STOPPED":
        return "retry_not_stopped"
    if (
        manifest["review_round"] != 0
        or manifest.get("human_recoveries")
        or manifest["review_started_head"] is not None
        or manifest["review_started_status"] is not None
        or handoff["reviewer"] is not None
        or any(directory.glob("review-*.json"))
        or any(directory.glob("reviewer-*.json"))
        or any(directory.glob("reviewer-stdout-*.txt"))
        or any(directory.glob("pi-reviewer-round-*.log"))
        or (directory / "reviewer-progress.log").exists()
    ):
        return "retry_review_already_started"
    if handoff["implementer"] is not None or any(directory.glob("implementation-*.json")):
        return "retry_handoff_already_accepted"
    if manifest["active_agent"] is not None:
        return "retry_agent_still_active"
    if not facts.clean or not manifest["working_tree_clean"]:
        return "retry_dirty_tree"
    if facts.head_sha != manifest["current_head_sha"]:
        return "retry_head_mismatch"
    # Safety-class stops are not an operator escape hatch for a known safety failure.
    # Operational stops must use PDFTR-45's budgeted retry path.
    if manifest.get("stop_class", "unknown") != "unknown":
        return "retry_stop_class_ineligible"
    if manifest.get("stop_code") == "operational_retry_limit":
        return "retry_operational_limit"
    return None
