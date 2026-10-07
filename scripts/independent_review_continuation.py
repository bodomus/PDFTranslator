"""Trusted-parent-only correction service; no CLI, comments or agent-authored inputs.

Deploy pinned code and protect all authority ledgers from agent writes, as for
PDFTR-49/51. Python dependency injection is not authentication. This service holds
existing ticket ownership throughout the existing Pi runner; it never spawns agents.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from scripts import agent_cycle as cycle
from scripts.cycle_ownership import ticket_ownership
from scripts.independent_review import read_json
from scripts.independent_review_continuation_policy import (
    MAX_INDEPENDENT_CONTINUATIONS,
    evaluate_continuation,
)
from scripts.independent_review_policy import IndependentReviewError
from scripts.independent_review_result import IndependentReviewResultService, _atomic_json


def digest(document: dict) -> str:
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()


def findings_input(review: dict) -> dict:
    return {
        "schema_version": "1.0",
        "source": "independent_review",
        "generation": review["generation"],
        "reviewed_sha": review["requested_sha"],
        "requested_base_sha": review["requested_base_sha"],
        "findings": copy.deepcopy(review["result"]["findings"]),
    }


class IndependentReviewContinuationService:
    """Explicit initialization, bounded durable authorizations, no uncertain retry.

    AUTHORIZED/PREPARED may resume the SAME identity after fresh eligibility checks.
    LAUNCHING or RUNNING without terminal evidence requires human inspection; lack
    of a handoff never grants another spawn. Normal runner recovery stays separate.
    """

    def __init__(self, results: IndependentReviewResultService):
        self.results = results
        self.store = results.store
        self.path = self.store.directory / "independent-continuations.json"
        if self.store.directory != cycle.cycle_directory(
            self.store.root, self.store.config["ticket"]
        ):
            raise IndependentReviewError("continuation_repository_mismatch")

    def initialize(self) -> None:
        with ticket_ownership(self.store.directory):
            self.store.load()
            self.results._load(self.store.load())
            manifest = cycle._load_json(self.store.directory / "manifest.json")
            if manifest.get("independent_continuations") or any(
                self.store.directory.glob("independent-findings-*.json")
            ):
                raise IndependentReviewError("continuation_state_corrupt")
            if self.path.exists() or self.path.is_symlink() or self.path.is_junction():
                raise IndependentReviewError("continuation_state_already_exists")
            self._save({"schema_version": "1.0", "config": self.store.config, "continuations": []})

    def _save(self, ledger: dict) -> None:
        _atomic_json(self.store.root, self.path, ledger)

    def _passed_evidence(self, manifest: dict, handoff: dict) -> None:
        review, implementer = handoff["reviewer"], handoff["implementer"]
        if (
            type(review) is not dict
            or review["verdict"] != "PASS"
            or review["reviewed_sha"] != manifest["current_head_sha"]
            or type(implementer) is not dict
            or read_json(self.store.directory / f"review-{manifest['review_round']}.json") != review
            or read_json(
                self.store.directory
                / f"implementation-{implementer['implementation_attempt']}.json"
            )
            != implementer
        ):
            raise IndependentReviewError("continuation_state_corrupt")

    def _load(self, independent: dict) -> dict:
        ledger = read_json(self.path)
        if (
            set(ledger) != {"schema_version", "config", "continuations"}
            or ledger["schema_version"] != "1.0"
            or ledger["config"] != self.store.config
            or type(ledger["continuations"]) is not list
            or len(ledger["continuations"]) > MAX_INDEPENDENT_CONTINUATIONS
        ):
            raise IndependentReviewError("continuation_state_corrupt")
        generations = set()
        for number, entry in enumerate(ledger["continuations"], 1):
            if type(entry) is not dict or set(entry) != {
                "continuation_id",
                "source_generation",
                "source_head_sha",
                "source_base_sha",
                "approved_by",
                "state",
                "findings_sha256",
                "result_sha256",
                "previous_manifest",
                "previous_handoff",
                "implementation_attempt",
                "resulting_implementation_sha",
            }:
                raise IndependentReviewError("continuation_state_corrupt")
            generation = entry["source_generation"]
            if (
                type(entry["continuation_id"]) is not int
                or entry["continuation_id"] != number
                or type(generation) is not int
                or not 1 <= generation <= len(independent["reviews"])
                or generation in generations
                or entry["approved_by"] != "policy"
                or entry["state"]
                not in {
                    "AUTHORIZED",
                    "PREPARED",
                    "LAUNCHING",
                    "RUNNING",
                    "COMPLETED",
                    "LAUNCH_UNCERTAIN",
                    "STALE",
                    "REJECTED",
                }
            ):
                raise IndependentReviewError("continuation_state_corrupt")
            generations.add(generation)
            review = independent["reviews"][generation - 1]
            previous = entry["previous_manifest"]
            cycle._validate_manifest(previous, self.store.config["ticket"])
            cycle._validate_handoff(entry["previous_handoff"], previous)
            self._passed_evidence(previous, entry["previous_handoff"])
            if (
                previous["state"] != "PASSED"
                or previous["active_agent"] is not None
                or previous["current_head_sha"] != review["requested_sha"]
                or entry["source_head_sha"] != review["requested_sha"]
                or entry["source_base_sha"] != review["requested_base_sha"]
                or review["result"] is None
                or review["result"]["verdict"] != "CHANGES_REQUIRED"
                or entry["result_sha256"] != digest(review["result"])
                or entry["findings_sha256"] != digest(findings_input(review))
                or type(entry["implementation_attempt"]) is not int
                or entry["implementation_attempt"] != cycle.implementation_attempt(previous)
                or len(previous.get("independent_continuations", [])) != number - 1
            ):
                raise IndependentReviewError("continuation_state_corrupt")
            artifact_path = self._input_path(entry)
            if (
                entry["state"] not in {"AUTHORIZED", "STALE", "REJECTED"} or artifact_path.exists()
            ) and read_json(artifact_path) != findings_input(review):
                raise IndependentReviewError("continuation_findings_mismatch")
            resulting = entry["resulting_implementation_sha"]
            if entry["state"] == "COMPLETED":
                cycle._validated_sha(resulting, "continuation result")
                if resulting == entry["source_head_sha"]:
                    raise IndependentReviewError("continuation_state_corrupt")
            elif resulting is not None:
                raise IndependentReviewError("continuation_state_corrupt")
        return ledger

    def _input_path(self, entry: dict) -> Path:
        return self.store.directory / f"independent-findings-{entry['continuation_id']}.json"

    @staticmethod
    def _approval(entry: dict) -> dict:
        return {
            k: entry[k]
            for k in (
                "continuation_id",
                "source_generation",
                "source_head_sha",
                "source_base_sha",
                "findings_sha256",
            )
        } | {"source_round": entry["previous_manifest"]["review_round"]}

    def _safety(self, previous: dict) -> dict:
        facts = cycle.collect_git_facts(self.store.root, previous["base_branch"])
        operations = (
            "MERGE_HEAD",
            "REBASE_HEAD",
            "CHERRY_PICK_HEAD",
            "REVERT_HEAD",
            "rebase-merge",
            "rebase-apply",
            "sequencer",
            "BISECT_LOG",
        )
        no_operation = all(
            not Path(
                cycle._run_git(
                    self.store.root, "rev-parse", "--path-format=absolute", "--git-path", name
                )
            ).exists()
            for name in operations
        )
        return {
            "repository_matches": facts.repository_fingerprint
            == previous["repository_fingerprint"],
            "branch_matches": facts.branch == previous["branch"],
            "head_matches": facts.head_sha == previous["current_head_sha"],
            "clean": facts.clean,
            "no_operation": no_operation,
            "no_active_agent": True,  # Exclusive OS lock; projection owner checked separately.
            "publication_resolved": True,
        }

    def _evaluate(self, previous, publication, ledger, *, resume=None):
        independent = self.store.load()
        publications = self.results._load(independent)
        if any(
            e["publication_state"] in {"PENDING", "PUBLICATION_UNCERTAIN"}
            for e in publications["publications"]
        ):
            return {"decision": "REJECTED", "reason": "continuation_publication_uncertain"}
        generation = publication["generation"]
        current_publication = next(
            (e for e in publications["publications"] if e["generation"] == generation), None
        )
        if current_publication != publication:
            return {"decision": "REJECTED", "reason": "continuation_stale"}
        self.results._receipt(
            independent, generation
        )  # Accepted authenticated receipt correlation.
        facts = self.results.provider.fetch(previous)
        history = [e for e in ledger["continuations"] if e is not resume]
        return evaluate_continuation(
            previous, independent, publication, history, facts, self._safety(previous)
        )

    def _project(self, entry: dict) -> None:
        """Idempotent prelaunch projection; no process may exist in these states."""
        previous = entry["previous_manifest"]
        target = copy.deepcopy(previous)
        target.setdefault("independent_continuations", []).append(self._approval(entry))
        target.update(
            state="POLICY_APPROVED_CONTINUATION",
            implementation_attempt=entry["implementation_attempt"],
            review_started_head=None,
            review_started_status=None,
        )
        handoff = copy.deepcopy(entry["previous_handoff"])
        handoff["reviewer"] = None
        cycle._sync_system(handoff, target)
        actual = cycle._load_json(self.store.directory / "manifest.json")
        actual_handoff = cycle._load_json(self.store.directory / "handoff.json")
        active = dict(target, state="IMPLEMENTING", active_agent="implementer")
        active_handoff = copy.deepcopy(handoff)
        cycle._sync_system(active_handoff, active)
        if actual == active:
            marker = (
                self.store.directory
                / f"implementer-launch-attempt-{entry['implementation_attempt']}.json"
            )
            if read_json(marker) != cycle.implementer_launch_record(target, "prepared"):
                raise IndependentReviewError("continuation_launch_uncertain")
        elif actual not in (previous, target):
            raise IndependentReviewError("continuation_cycle_state_invalid")
        if actual_handoff not in (entry["previous_handoff"], handoff, active_handoff):
            raise IndependentReviewError("continuation_state_corrupt")
        if (
            self.store.directory / f"implementation-{entry['implementation_attempt']}.json"
        ).exists():
            raise IndependentReviewError("continuation_already_used")
        cycle._validate_manifest(target, self.store.config["ticket"])
        cycle._write_cycle(self.store.directory, target, handoff)

    def receive_and_continue(self, generation: int, **runner_options) -> dict:
        """Protected parent return path: authenticated evidence, publication, then policy.

        Locks are reacquired rather than nested. All facts are independently refreshed
        during continuation, so the publication signal itself grants no launch authority.
        """
        self.results.receive_and_publish(generation)
        return self.continue_cycle(expected_generation=generation, **runner_options)

    def continue_cycle(
        self, *, executor, config=None, ticket_text=None, reporter=None, expected_generation=None
    ) -> dict:
        """Called only by the protected parent after PDFTR-51; never by reviewer tools.

        Returning rejection is a human-intervention signal, not a recovery grant.
        Repeated/concurrent events cannot allocate or launch another attempt.
        """
        from scripts.pi_ticket_cycle import RunnerConfig, _run_cycle, validate_reviewer_config

        validate_reviewer_config(config or RunnerConfig())
        with ticket_ownership(self.store.directory):
            independent = self.store.load()
            ledger = self._load(independent)
            publications = self.results._load(independent)
            generation = independent["current_generation"]
            if expected_generation is not None and (
                type(expected_generation) is not int or expected_generation != generation
            ):
                return {"decision": "REJECTED", "reason": "continuation_generation_mismatch"}
            publication = next(
                (e for e in publications["publications"] if e["generation"] == generation), None
            )
            if publication is None:
                return {"decision": "REJECTED", "reason": "continuation_not_published"}
            entry = next(
                (e for e in ledger["continuations"] if e["source_generation"] == generation), None
            )
            if entry is not None and entry["state"] not in {"AUTHORIZED", "PREPARED"}:
                if entry["state"] in {"LAUNCHING", "RUNNING"}:
                    current = cycle.cycle_status(self.store.root, self.store.config["ticket"])
                    manifest = cycle._load_json(self.store.directory / "manifest.json")
                    marker_path = self.store.directory / (
                        f"implementer-launch-attempt-{entry['implementation_attempt']}.json"
                    )
                    expected = dict(
                        entry["previous_manifest"],
                        implementation_attempt=entry["implementation_attempt"],
                    )
                    exited = marker_path.exists() and read_json(
                        marker_path
                    ) == cycle.implementer_launch_record(expected, "exited")
                    bound = self._approval(entry) in manifest.get("independent_continuations", [])
                    if (
                        exited
                        and bound
                        and not current["errors"]
                        and current["state"] == "PASSED"
                        and current["head_sha"] != entry["source_head_sha"]
                    ):
                        entry["state"] = "COMPLETED"
                        entry["resulting_implementation_sha"] = current["head_sha"]
                    elif (
                        exited
                        and bound
                        and not current["errors"]
                        and current["state"] in {"STOPPED", "BLOCKED"}
                    ):
                        entry["state"] = "REJECTED"
                    else:
                        entry["state"] = "LAUNCH_UNCERTAIN"
                    self._save(ledger)
                return {
                    "decision": "REJECTED",
                    "reason": "continuation_launch_uncertain"
                    if entry["state"] == "LAUNCH_UNCERTAIN"
                    else "continuation_already_used",
                }
            if entry is None:
                previous = read_json(self.store.directory / "manifest.json")
                handoff = read_json(self.store.directory / "handoff.json")
                cycle._validate_manifest(previous, self.store.config["ticket"])
                cycle._validate_handoff(handoff, previous)
            else:
                previous, handoff = entry["previous_manifest"], entry["previous_handoff"]
            decision = self._evaluate(previous, publication, ledger, resume=entry)
            if decision["decision"] != "AUTHORIZED":
                if entry is not None:
                    entry["state"] = (
                        "STALE"
                        if decision["reason"]
                        in {
                            "continuation_head_mismatch",
                            "continuation_base_mismatch",
                            "continuation_generation_mismatch",
                            "continuation_stale",
                        }
                        else "REJECTED"
                    )
                    self._save(ledger)
                return decision
            if entry is None:
                cycle._load_cycle(self.store.root, self.store.config["ticket"])
                self._passed_evidence(previous, handoff)
            executor.ensure_available()
            review = independent["reviews"][generation - 1]
            if entry is None:
                entry = {
                    "continuation_id": len(ledger["continuations"]) + 1,
                    "source_generation": generation,
                    "source_head_sha": review["requested_sha"],
                    "source_base_sha": review["requested_base_sha"],
                    "approved_by": "policy",
                    "state": "AUTHORIZED",
                    "findings_sha256": digest(findings_input(review)),
                    "result_sha256": digest(review["result"]),
                    "previous_manifest": previous,
                    "previous_handoff": handoff,
                    "implementation_attempt": cycle.implementation_attempt(previous),
                    "resulting_implementation_sha": None,
                }
                ledger["continuations"].append(entry)
                self._save(ledger)  # Authorization/budget commit point BEFORE any cycle mutation.
            path = self._input_path(entry)
            artifact = findings_input(review)
            if path.exists():
                if read_json(path) != artifact:
                    raise IndependentReviewError("continuation_findings_mismatch")
            else:
                _atomic_json(self.store.root, path, artifact)
            entry["state"] = "PREPARED"
            self._save(ledger)
            self._project(entry)
            launch = _ContinuationLaunch(self, ledger, entry, publication)
            outcome = _run_cycle(
                self.store.root,
                self.store.config["ticket"],
                executor=executor,
                config=config,
                ticket_text=ticket_text,
                reporter=reporter,
                continuation=launch,
            )
            if outcome.state == "PASSED" and outcome.implementation_sha != entry["source_head_sha"]:
                entry["state"] = "COMPLETED"
                entry["resulting_implementation_sha"] = outcome.implementation_sha
                self._save(ledger)
            return {"decision": entry["state"], "continuation_id": entry["continuation_id"]}


class _ContinuationLaunch:
    def __init__(self, service, ledger, entry, publication):
        self.service, self.ledger, self.entry, self.publication = (
            service,
            ledger,
            entry,
            publication,
        )

    def prompt(self) -> str:
        independent = self.service.store.load()
        self.service._load(independent)  # Tampered findings/result reject even after preparation.
        artifact = read_json(self.service._input_path(self.entry))
        return (
            "\nThis is an independent-review correction cycle.\n"
            f"Source independent generation: {artifact['generation']}\n"
            f"Reviewed HEAD: {artifact['reviewed_sha']}\n"
            f"Reviewed BASE: {artifact['requested_base_sha']}\n"
            "Fix only the actionable structured findings below. "
            "Do not change unrelated architecture.\n"
            "Do not rewrite independent review evidence or modify continuation authorization. "
            "Do not merge.\n"
            "Run focused tests and the full gate. Commit and push.\n"
            + json.dumps(artifact, indent=2)
            + "\n"
        )

    def before_launch(self) -> None:
        self.service._load(self.service.store.load())
        _, manifest, _, _ = cycle._load_cycle(
            self.service.store.root, self.service.store.config["ticket"]
        )
        if (
            manifest["state"] != "IMPLEMENTING"
            or manifest["active_agent"] != "implementer"
            or manifest.get("independent_continuations", [])[-1:]
            != [self.service._approval(self.entry)]
            or manifest["current_head_sha"] != self.entry["source_head_sha"]
            or manifest["review_round"] != self.entry["previous_manifest"]["review_round"]
        ):
            raise IndependentReviewError("continuation_cycle_state_invalid")
        decision = self.service._evaluate(
            self.entry["previous_manifest"], self.publication, self.ledger, resume=self.entry
        )
        if decision["decision"] != "AUTHORIZED":
            self.entry["state"] = (
                "STALE"
                if "mismatch" in decision["reason"] or decision["reason"] == "continuation_stale"
                else "REJECTED"
            )
            self.service._save(self.ledger)
            raise IndependentReviewError(decision["reason"])
        self.entry["state"] = "LAUNCHING"
        self.service._save(self.ledger)  # Irreversible fence before the runner's own launch marker.

    def process_exited(self) -> None:
        self.entry["state"] = (
            "RUNNING"  # Owned child has exited; internal review remains mandatory.
        )
        self.service._save(self.ledger)
