"""Trusted-parent result service. No CLI, result files, stdin or public callback.

Run deployed, pinned code with protected state/configuration and credentials outside
agent authority. A Protocol is dependency injection, NOT authentication of arbitrary
Python callers. Only the parent may construct/invoke this service or receiver.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.request
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from scripts.cycle_ownership import ticket_ownership
from scripts.github_independent_review import load_cycle
from scripts.github_review_facts import GitHubFactsProvider, NoRedirect
from scripts.github_review_publication import (
    PublicationOutcome,
    ReviewPublisher,
    check_payload,
    publication_identity,
)
from scripts.independent_review import IndependentReviewStore, _unique_object, read_json
from scripts.independent_review_dispatch import DispatchRequest
from scripts.independent_review_policy import (
    IndependentReviewError,
    evaluate_independent_review,
    pass_is_valid,
    record_result,
    refresh_state,
    validate_config,
    validate_result,
)


class IndependentReviewResultReceiver(Protocol):
    def receive(self, external_request_id: str) -> dict: ...


class HTTPSReviewResultReceiver:
    """Authenticated polling of a trusted read-only review connector, never a local artifact.

    Connector GET <endpoint>/<opaque dispatch ID> returns exactly external_request_id
    and result (PDFTR-49 schema). Credentials and endpoint are protected parent inputs.
    No redirects, provider-controlled URLs or unauthenticated repository callbacks.
    """

    def __init__(self, endpoint: str, token: str):
        url = urlsplit(endpoint)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or not token
        ):
            raise IndependentReviewError("invalid_result_transport")
        self.endpoint, self.token = endpoint.rstrip("/"), token

    def receive(self, external_request_id: str) -> dict:
        if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", external_request_id) is None:
            raise IndependentReviewError("invalid_request_id")
        outgoing = urllib.request.Request(
            self.endpoint + "/" + external_request_id,
            headers={"Authorization": "Bearer " + self.token, "Accept": "application/json"},
        )
        try:
            with urllib.request.build_opener(NoRedirect()).open(outgoing, timeout=30) as response:
                body = response.read(1024 * 1024 + 1)
                if response.status != 200 or len(body) > 1024 * 1024:
                    raise IndependentReviewError("result_transport_failed")
            if self.token in body.decode("utf-8"):
                raise IndependentReviewError("result_contains_secret")
            return json.loads(body, object_pairs_hook=_unique_object)
        except (OSError, ValueError) as error:
            raise IndependentReviewError("result_transport_failed") from error


def _atomic_json(root: Path, target: Path, document: dict) -> None:
    temporary = root / "temp" / "independent-review"
    for path in (temporary, *temporary.parents, target, *target.parents):
        if path.is_symlink() or path.is_junction():
            raise IndependentReviewError("symbolic_publication_state")
    temporary.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=temporary, suffix=".json", delete=False
        ) as stream:
            name = Path(stream.name)
            json.dump(document, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        if name is not None:
            name.unlink(missing_ok=True)


class IndependentReviewResultService:
    """One OS ownership scope; result history and side-effect history stay separate.

    initialize() is explicit/exclusive first use only. Missing/corrupt ledger never
    auto-resets. Recovered PENDING is uncertain, not permission to send again.
    """

    def __init__(
        self,
        store: IndependentReviewStore,
        provider: GitHubFactsProvider,
        receiver: IndependentReviewResultReceiver,
        publisher: ReviewPublisher,
        cycle_reader=load_cycle,
        secrets: tuple[str, ...] = (),
    ):
        if provider.config != store.config:
            raise IndependentReviewError("provider_binding")
        self.store, self.provider = store, provider
        self.receiver, self.publisher, self.cycle_reader = receiver, publisher, cycle_reader
        credentials = (
            getattr(receiver, "token", None),
            getattr(publisher, "token", None),
            getattr(provider.read, "token", None),
        )
        self.secrets = tuple(s for s in (*secrets, *credentials) if type(s) is str and s)
        self.path = store.directory / "independent-publications.json"

    def _facts(self) -> dict:
        return self.provider.fetch(self.cycle_reader(self.store.root, self.store.config["ticket"]))

    def initialize(self) -> None:
        self.store._safe_directory()
        with ticket_ownership(self.store.directory):
            self.store.load()
            if self.path.exists() or self.path.is_symlink() or self.path.is_junction():
                raise IndependentReviewError("publication_state_already_exists")
            self._save({"schema_version": "1.0", "config": self.store.config, "publications": []})

    def _save(self, ledger: dict) -> None:
        _atomic_json(self.store.root, self.path, ledger)

    def _load(self, state: dict) -> dict:
        ledger = read_json(self.path)
        validate_config(ledger.get("config"))
        if (
            set(ledger) != {"schema_version", "config", "publications"}
            or ledger["schema_version"] != "1.0"
            or ledger["config"] != self.store.config
            or type(ledger["publications"]) is not list
        ):
            raise IndependentReviewError("publication_state_corrupt")
        generations = set()
        for entry in ledger["publications"]:
            if type(entry) is not dict or set(entry) != {
                "generation",
                "identity",
                "payload",
                "publication_state",
                "github_check_id",
                "continuation",
            }:
                raise IndependentReviewError("publication_state_corrupt")
            generation = entry["generation"]
            if (
                type(generation) is not int
                or not 1 <= generation <= len(state["reviews"])
                or generation in generations
            ):
                raise IndependentReviewError("publication_state_corrupt")
            generations.add(generation)
            review = state["reviews"][generation - 1]
            if (
                review["result"] is None
                or entry["identity"] != publication_identity(self.store.config, review)
                or entry["payload"] != check_payload(self.store.config, review)
                or entry["publication_state"]
                not in {"PENDING", "PUBLISHED", "PUBLICATION_UNCERTAIN", "FAILED_DEFINITE", "STALE"}
            ):
                raise IndependentReviewError("publication_state_corrupt")
            identifier = entry["github_check_id"]
            if (
                (entry["publication_state"] == "PUBLISHED") != (identifier is not None)
                or identifier is not None
                and (type(identifier) is not int or identifier <= 0)
            ):
                raise IndependentReviewError("publication_state_corrupt")
            continuation = entry["continuation"]
            if continuation is not None and (
                entry["publication_state"] != "PUBLISHED"
                or review["result"]["verdict"] != "CHANGES_REQUIRED"
                or json.dumps(continuation, sort_keys=True)
                != json.dumps(self._continuation(review), sort_keys=True)
            ):
                raise IndependentReviewError("publication_state_corrupt")
        return ledger

    def _receipt(self, state: dict, generation: int) -> str:
        if type(generation) is not int or not 1 <= generation <= len(state["reviews"]):
            raise IndependentReviewError("unknown_generation")
        review = state["reviews"][generation - 1]
        receipt = read_json(self.store.directory / f"independent-dispatch-{generation}.json")
        from dataclasses import asdict

        expected = asdict(
            DispatchRequest(
                self.store.config["repository"],
                self.store.config["ticket"],
                self.store.config["pull_request"],
                generation,
                review["requested_sha"],
                review["requested_base_sha"],
            )
        )
        if (
            set(receipt) != set(expected) | {"outcome", "external_request_id"}
            or any(type(receipt[k]) is not type(v) or receipt[k] != v for k, v in expected.items())
            or receipt["outcome"] != "DISPATCHED"
            or type(receipt["external_request_id"]) is not str
            or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", receipt["external_request_id"]) is None
        ):
            raise IndependentReviewError("dispatch_receipt_mismatch")
        return receipt["external_request_id"]

    def _current(self, facts: dict, state: dict, review: dict) -> bool:
        if review["result"]["verdict"] == "PASS":
            return (
                review["status"] == "PASS"
                and review["generation"] == state["current_generation"]
                and pass_is_valid(facts, state, self.store.config)
            )
        decision = evaluate_independent_review(facts, state, self.store.config)
        return (
            decision["decision"] == "ALREADY_REVIEWED"
            and decision["generation"] == review["generation"]
            and review["status"] == "CHANGES_REQUIRED"
        )

    def _continuation(self, review: dict) -> dict:
        return {
            "schema_version": "1.0",
            "ticket": self.store.config["ticket"],
            "source": "independent_review",
            "generation": review["generation"],
            "reviewed_sha": review["requested_sha"],
            "verdict": "CHANGES_REQUIRED",
            "status": "PENDING_HUMAN_OR_POLICY",
        }

    def _finish(self, state: dict, ledger: dict, entry: dict) -> dict:
        facts = self._facts()  # Post-write and every status/restart: readiness is never cached.
        state = refresh_state(facts, state, self.store.config)
        self.store._persist(state)
        review = state["reviews"][entry["generation"] - 1]
        current = self._current(facts, state, review)
        if (
            current
            and entry["publication_state"] == "PUBLISHED"
            and review["result"]["verdict"] == "CHANGES_REQUIRED"
        ):
            entry["continuation"] = self._continuation(review)
        self._save(ledger)
        return {
            "publication": entry,
            "ready_for_human_merge": entry["publication_state"] == "PUBLISHED"
            and current
            and pass_is_valid(facts, state, self.store.config),
            "continuation_eligible": current and entry["continuation"] is not None,
        }

    @staticmethod
    def _outcome(entry: dict, outcome: PublicationOutcome) -> None:
        if (
            outcome.state == "PUBLISHED"
            and type(outcome.github_check_id) is int
            and outcome.github_check_id > 0
        ):
            entry["publication_state"] = "PUBLISHED"
            entry["github_check_id"] = outcome.github_check_id
        elif outcome.state == "FAILED_DEFINITE" and outcome.github_check_id is None:
            entry["publication_state"] = "FAILED_DEFINITE"
        else:
            entry["publication_state"] = "PUBLICATION_UNCERTAIN"

    def receive_and_publish(self, generation: int) -> dict:
        """Trusted harness chooses dispatched generation; only receiver supplies evidence."""
        with ticket_ownership(self.store.directory):
            state = self.store.load()
            ledger = self._load(state)
            request_id = self._receipt(state, generation)
            envelope = self.receiver.receive(request_id)
            if type(envelope) is not dict or set(envelope) != {"external_request_id", "result"}:
                raise IndependentReviewError("invalid_result_envelope")
            if envelope["external_request_id"] != request_id:
                raise IndependentReviewError("dispatch_receipt_mismatch")
            result = envelope["result"]
            validate_result(result, self.store.config)
            if result["generation"] != generation:
                raise IndependentReviewError("result_generation_mismatch")
            if any(secret in json.dumps(envelope, ensure_ascii=False) for secret in self.secrets):
                raise IndependentReviewError("result_contains_secret")
            state = record_result(self._facts(), state, self.store.config, result)
            self.store._persist(state)  # Accepted result MUST be durable before publication intent.
            existing = next(
                (e for e in ledger["publications"] if e["generation"] == generation), None
            )
            if existing is not None:
                if existing["publication_state"] == "PENDING":
                    existing["publication_state"] = "PUBLICATION_UNCERTAIN"
                    self._save(ledger)
                return self._finish(state, ledger, existing)
            # Immediately before intent/mutation, never reuse ingestion facts.
            facts = self._facts()
            state = refresh_state(facts, state, self.store.config)
            self.store._persist(state)
            review = state["reviews"][generation - 1]
            current = self._current(facts, state, review)
            entry = {
                "generation": generation,
                "identity": publication_identity(self.store.config, review),
                "payload": check_payload(self.store.config, review),
                "publication_state": "PENDING" if current else "STALE",
                "github_check_id": None,
                "continuation": None,
            }
            ledger["publications"].append(entry)
            self._save(ledger)  # Durable at-most-once fence BEFORE transport invocation.
            if current:
                try:
                    outcome = self.publisher.publish(
                        self.store.config["repository"], entry["payload"]
                    )
                except Exception:
                    outcome = PublicationOutcome("PUBLICATION_UNCERTAIN")
                self._outcome(entry, outcome)
                self._save(ledger)
            return self._finish(state, ledger, entry)

    def status(self, generation: int, *, reconcile: bool = False) -> dict:
        """Trusted read refresh/reconciliation. Never sends or retries a GitHub mutation.

        continuation_eligible is an advisory exact-context signal for an operator;
        it does not launch an agent, transition the cycle or grant retry/review budgets.
        """
        with ticket_ownership(self.store.directory):
            state = self.store.load()
            if type(generation) is not int or not 1 <= generation <= len(state["reviews"]):
                raise IndependentReviewError("unknown_generation")
            ledger = self._load(state)
            entry = next((e for e in ledger["publications"] if e["generation"] == generation), None)
            if entry is None:
                raise IndependentReviewError("publication_not_requested")
            if entry["publication_state"] == "PENDING":
                entry["publication_state"] = "PUBLICATION_UNCERTAIN"
                self._save(ledger)
            if reconcile and entry["publication_state"] == "PUBLICATION_UNCERTAIN":
                try:
                    outcome = self.publisher.reconcile(
                        self.store.config["repository"], entry["payload"]
                    )
                except Exception:
                    outcome = PublicationOutcome("PUBLICATION_UNCERTAIN")
                # A reconciliation read can prove existence only, not definite rejection.
                if outcome.state == "PUBLISHED":
                    self._outcome(entry, outcome)
                    self._save(ledger)
            return self._finish(state, ledger, entry)
