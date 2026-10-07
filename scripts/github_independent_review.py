"""Trusted-parent GitHub wake-up integration; never expose this CLI to agents."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.agent_cycle import CycleError, _load_cycle
from scripts.cycle_ownership import CycleOwnershipError
from scripts.github_review_facts import GitHubFactsProvider, GitHubReader
from scripts.independent_review import IndependentReviewStore, read_json
from scripts.independent_review_dispatch import (
    DispatchRequest,
    HTTPSReviewDispatcher,
    IndependentReviewDispatcher,
    persist_receipt,
)
from scripts.independent_review_policy import IndependentReviewError

SUPPORTED_EVENTS = frozenset(
    {
        "opened",
        "reopened",
        "ready_for_review",
        "synchronize",
        "edited",
        "check_run",
        "check_suite",
        "status",
        "workflow_run",
        "manual",
    }
)


def github_event_signal(event_name: str, payload: dict) -> str:
    """Normalize GitHub notification names/actions, not their authorization claims."""
    if type(payload) is not dict:
        raise IndependentReviewError("invalid_event")
    signal = payload.get("action") if event_name == "pull_request" else event_name
    if type(signal) is not str or signal not in SUPPORTED_EVENTS:
        raise IndependentReviewError("unsupported_event")
    return signal


def load_cycle(root: Path, ticket: str) -> dict:
    """Existing harness validation proves ticket, Git repository and branch binding."""
    _, manifest, _, git = _load_cycle(root, ticket)
    if git.head_sha != manifest["current_head_sha"] or not git.clean:
        raise IndependentReviewError("cycle_git_mismatch")
    return manifest


def handle_signal(
    event_type: str,
    payload: dict,
    store: IndependentReviewStore,
    provider: GitHubFactsProvider,
    dispatcher: IndependentReviewDispatcher,
    cycle_reader=load_cycle,
) -> dict:
    """Payload is intentionally unused: configured target, never event authorization.

    A trusted event connector can route all supported PR/CI notifications here.
    No public webhook receiver is provided. Duplicate notifications are safe.
    """
    if event_type not in SUPPORTED_EVENTS:
        raise IndependentReviewError("unsupported_event")
    if provider.config != store.config:
        raise IndependentReviewError("provider_binding")

    def refresh() -> dict:
        return provider.fetch(cycle_reader(store.root, store.config["ticket"]))

    def dispatch(review: dict) -> str | None:
        request = DispatchRequest(
            repository=store.config["repository"],
            ticket=store.config["ticket"],
            pull_request=store.config["pull_request"],
            generation=review["generation"],
            head_sha=review["requested_sha"],
            base_sha=review["requested_base_sha"],
        )
        receipt = dispatcher.dispatch(request)
        # Only the typed outcome and bounded opaque identifier may leave transport.
        if receipt.outcome not in {"DISPATCHED", "DEFINITE_NOT_DISPATCHED", "DISPATCH_UNCERTAIN"}:
            raise IndependentReviewError("invalid_dispatch_receipt")
        if receipt.external_request_id is not None:
            import re

            if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", receipt.external_request_id) is None:
                raise IndependentReviewError("invalid_dispatch_receipt")
        if receipt.outcome == "DISPATCHED" and not receipt.external_request_id:
            raise IndependentReviewError("invalid_dispatch_receipt")
        persist_receipt(store.root, store.directory, request, receipt)
        return {
            "DISPATCHED": "RUNNING",
            "DISPATCH_UNCERTAIN": "DISPATCH_UNCERTAIN",
            "DEFINITE_NOT_DISPATCHED": None,
        }[receipt.outcome]

    return {"event_type": event_type, **store.request_and_dispatch(refresh, dispatch)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trusted independent-review reevaluation/dispatch")
    parser.add_argument("command", choices=("evaluate", "signal"))
    parser.add_argument("ticket")
    parser.add_argument("--event", choices=sorted(SUPPORTED_EVENTS), default="manual")
    args = parser.parse_args(argv)
    try:
        # Trusted service environment, never repository/agent-supplied CLI files.
        config = read_json(Path(os.environ["PDFTR_REVIEW_CONFIG"]))
        if config.get("ticket") != args.ticket:
            raise IndependentReviewError("ticket_mismatch")
        root = Path.cwd()
        store = IndependentReviewStore(root, root / ".agent-cycle" / args.ticket, config)
        provider = GitHubFactsProvider(config, GitHubReader(os.environ["GITHUB_TOKEN"]))
        dispatcher = HTTPSReviewDispatcher(
            os.environ["PDFTR_REVIEW_ENDPOINT"], os.environ["PDFTR_REVIEW_TOKEN"]
        )
        event = args.event
        if args.command == "signal":
            body = sys.stdin.buffer.read(1024 * 1024 + 1)
            if len(body) > 1024 * 1024:
                raise IndependentReviewError("event_size_limit")
            event = github_event_signal(os.environ["GITHUB_EVENT_NAME"], json.loads(body))
        output = handle_signal(event, {}, store, provider, dispatcher)
        print(json.dumps(output, sort_keys=True))
        return 0
    except (IndependentReviewError, CycleError, CycleOwnershipError, OSError, KeyError, ValueError):
        # No exceptions or environment values: URLs/auth can appear in library errors.
        print(json.dumps({"decision": "INVALID", "reason": "trusted_evaluation_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
