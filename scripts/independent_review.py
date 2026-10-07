"""Read-only independent-review inspection and trusted-harness persistence API.

There is deliberately no result-ingestion or dispatch CLI. Agent-supplied files
must never be promoted to authorization. Deployments must isolate store writes
from agents; this library is not a filesystem permission or identity service.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.cycle_ownership import ticket_ownership
from scripts.independent_review_policy import (
    IndependentReviewError,
    empty_state,
    evaluate_independent_review,
    mark_dispatch,
    record_result,
    request_review,
    validate_config,
    validate_state,
)


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise IndependentReviewError("duplicate_json_key")
        value[key] = item
    return value


def read_json(path: Path) -> dict:
    if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
        raise IndependentReviewError("symbolic_state")
    try:
        document = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, ValueError) as error:
        raise IndependentReviewError("unreadable_json") from error
    if type(document) is not dict:
        raise IndependentReviewError("invalid_schema")
    return document


class IndependentReviewStore:
    """Trusted harness only: serialize read/validate/replace under OS ticket ownership.

    Initialization is explicit and exclusive, never inferred from missing history.
    The default layout is .agent-cycle/<ticket>/independent-review.json. A future
    launcher must invoke this from its trusted parent, never expose it to agents.
    """

    def __init__(self, repository_root: Path, directory: Path, config: dict):
        validate_config(config)
        self.root = repository_root.resolve()
        self.directory = directory.absolute()
        self.config = json.loads(json.dumps(config))
        self.path = self.directory / "independent-review.json"

    def _safe_directory(self) -> None:
        for path in (self.directory, *self.directory.parents):
            if path.is_symlink() or path.is_junction():
                raise IndependentReviewError("symbolic_state")
        self.directory.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        document = read_json(self.path)
        validate_state(document, self.config)
        return document

    def _persist(self, state: dict) -> None:
        validate_state(state, self.config)
        if self.path.is_symlink() or self.path.is_junction():
            raise IndependentReviewError("symbolic_state")
        temporary = self.root / "temp" / "independent-review"
        if any(p.is_symlink() or p.is_junction() for p in (temporary, *temporary.parents)):
            raise IndependentReviewError("symbolic_temporary_directory")
        temporary.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=temporary, suffix=".json", delete=False
            ) as stream:
                name = Path(stream.name)
                json.dump(state, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if name is not None:
                name.unlink(missing_ok=True)

    def initialize(self) -> dict:
        self._safe_directory()
        with ticket_ownership(self.directory):
            if self.path.exists() or self.path.is_symlink() or self.path.is_junction():
                raise IndependentReviewError("state_already_exists")
            state = empty_state(self.config)
            self._persist(state)
            return state

    def request(self, refresh_facts: Callable[[], dict]) -> dict:
        """Refresh under ownership; return one dispatch intent only AFTER persistence.

        Existing REQUESTED after a crash returns ALREADY_REQUESTED, not a new dispatch
        grant. There is no automatic retry, even if dispatch has not yet been invoked.
        """
        self._safe_directory()
        with ticket_ownership(self.directory):
            previous = self.load()
            state, decision = request_review(refresh_facts(), previous, self.config)
            self._persist(state)
            return decision

    def request_and_dispatch(
        self, refresh_facts: Callable[[], dict], dispatch: Callable[[dict], str | None]
    ) -> dict:
        """Trusted parent only: one ownership scope from refresh through delivery.

        None means definite non-delivery, with no automatic retry. A recovered
        REQUESTED is conservatively uncertain (including a crash before send).
        Any ordinary transport exception is uncertainty, never a retry grant.
        """
        self._safe_directory()
        with ticket_ownership(self.directory):
            state, decision = request_review(refresh_facts(), self.load(), self.config)
            generation = decision["generation"]
            if decision["decision"] != "ELIGIBLE":
                if (
                    generation is not None
                    and state["reviews"][generation - 1]["status"] == "REQUESTED"
                ):
                    state = mark_dispatch(state, self.config, generation, "DISPATCH_UNCERTAIN")
                self._persist(state)
                return decision
            self._persist(state)  # Mandatory durable intent BEFORE external side effects.
            review = json.loads(json.dumps(state["reviews"][generation - 1]))
            try:
                status = dispatch(review)
            except Exception:
                # Never persist transport exceptions: they may contain credentials.
                status = "DISPATCH_UNCERTAIN"
            if status not in {None, "RUNNING", "DISPATCH_UNCERTAIN"}:
                status = "DISPATCH_UNCERTAIN"
            if status is not None:
                state = mark_dispatch(state, self.config, generation, status)
                self._persist(state)
            return {**decision, "dispatch_state": status or "DEFINITE_NOT_DISPATCHED"}

    def accept_result(self, refresh_facts: Callable[[], dict], result: dict) -> dict:
        """Only trusted independent reviewer transport may call this, never agents."""
        self._safe_directory()
        with ticket_ownership(self.directory):
            previous = self.load()
            state = record_result(refresh_facts(), previous, self.config, result)
            self._persist(state)
            return state

    def dispatch_status(self, generation: int, status: str) -> dict:
        self._safe_directory()
        with ticket_ownership(self.directory):
            state = mark_dispatch(self.load(), self.config, generation, status)
            self._persist(state)
            return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only independent-review diagnostics")
    parser.add_argument("command", choices=("status", "evaluate"))
    parser.add_argument("ticket")
    parser.add_argument("--config", type=Path, required=True, help="Trusted policy configuration")
    parser.add_argument("--facts", type=Path, help="Normalized facts; inspection only, no dispatch")
    parser.add_argument("--state", type=Path, help="Existing state; never modified")
    args = parser.parse_args(argv)
    try:
        config = read_json(args.config)
        validate_config(config)
        if config["ticket"] != args.ticket:
            raise IndependentReviewError("ticket_mismatch")
        path = args.state or Path(".agent-cycle") / args.ticket / "independent-review.json"
        # Missing default state is displayed as NOT_REQUESTED; explicit missing input rejects.
        state = (
            empty_state(config)
            if args.state is None and not path.exists() and not path.is_symlink()
            else read_json(path)
        )
        validate_state(state, config)
        if args.command == "status":
            output = {"inspection_only": True, "state": state}
        else:
            if args.facts is None:
                raise IndependentReviewError("facts_required")
            output = {
                "inspection_only": True,
                **evaluate_independent_review(read_json(args.facts), state, config),
            }
        print(json.dumps(output, indent=2, sort_keys=True))
        return 1 if output.get("decision") == "INVALID" else 0
    except IndependentReviewError as error:
        print(json.dumps({"inspection_only": True, "decision": "INVALID", "reason": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
