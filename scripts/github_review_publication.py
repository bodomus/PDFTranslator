"""Trusted GitHub App check publication; no retries, comments, reviews or merge API."""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from scripts.github_review_facts import GitHubReader, NoRedirect
from scripts.independent_review_policy import IndependentReviewError

CHECK_NAME = "Independent Review"


def publication_identity(config: dict, review: dict) -> str:
    identity = [
        config["repository"],
        config["pull_request"],
        review["generation"],
        review["requested_sha"],
        review["requested_base_sha"],
        review["result"]["verdict"],
    ]
    return "pdftr-ir-" + hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def check_payload(config: dict, review: dict) -> dict:
    result = review["result"]
    summary = (
        f"Independent review {result['verdict']}\nGeneration: {review['generation']}\n"
        f"Head: {review['requested_sha']}\nBase: {review['requested_base_sha']}\n"
        "Required CI: SUCCESS for exact head at authoritative refresh.\n"
        "Merge remains human-owned.\n"
    )
    rendered = []
    for finding in result["findings"]:
        # Render evidence as inert JSON, not reviewer-controlled GitHub instructions.
        quoted = json.dumps(finding, ensure_ascii=True, sort_keys=True, indent=2)
        block = "```json\n" + quoted.replace("`", "\\u0060") + "\n```"
        if len(rendered) >= 20 or len(summary) + sum(map(len, rendered)) + len(block) > 40000:
            break
        rendered.append(block)
    if len(rendered) != len(result["findings"]):
        summary += (
            f"Additional findings omitted from GitHub rendering "
            f"({len(result['findings']) - len(rendered)}). Full structured result: "
            f"trusted independent-review.json, generation {review['generation']}.\n"
        )
    if rendered:
        summary += "\n" + "\n".join(rendered)
    return {
        "name": CHECK_NAME,
        "head_sha": review["requested_sha"],
        "external_id": publication_identity(config, review),
        "status": "completed",
        "conclusion": "success" if result["verdict"] == "PASS" else "failure",
        "output": {"title": f"Independent Review — {result['verdict']}", "summary": summary},
    }


@dataclass(frozen=True)
class PublicationOutcome:
    state: str
    github_check_id: int | None = None


class ReviewPublisher(Protocol):
    def publish(self, repository: str, payload: dict) -> PublicationOutcome: ...
    def reconcile(self, repository: str, payload: dict) -> PublicationOutcome: ...


class GitHubCheckPublisher:
    """Use a protected GitHub App installation token and its independently configured app ID.

    Reconciliation accepts only complete, unique, exact app/head/identity/output matches.
    Absent/ambiguous/read failures preserve uncertainty; they never grant a retry.
    """

    def __init__(self, token: str, app_id: int):
        if not token or type(app_id) is not int or app_id <= 0:
            raise IndependentReviewError("invalid_publication_credentials")
        self.token, self.app_id = token, app_id
        self.read = GitHubReader(token)

    def _matches(self, run: dict, payload: dict) -> bool:
        return (
            type(run) is dict
            and run.get("app", {}).get("id") == self.app_id
            and all(
                run.get(k) == payload[k]
                for k in ("name", "head_sha", "external_id", "status", "conclusion")
            )
            and run.get("output", {}).get("title") == payload["output"]["title"]
            and run.get("output", {}).get("summary") == payload["output"]["summary"]
            and type(run.get("id")) is int
            and run["id"] > 0
        )

    def publish(self, repository: str, payload: dict) -> PublicationOutcome:
        # Never publish a token supplied by the trusted parent, even in reviewer prose.
        if self.token in json.dumps(payload):
            return PublicationOutcome("FAILED_DEFINITE")
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repository}/check-runs",
            data=json.dumps(payload).encode(),
            method="POST",
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
                body = response.read(256 * 1024 + 1)
                if response.status != 201 or len(body) > 256 * 1024:
                    return PublicationOutcome("PUBLICATION_UNCERTAIN")
            run = json.loads(body)
            if self._matches(run, payload):
                return PublicationOutcome("PUBLISHED", run["id"])
        except urllib.error.HTTPError as error:
            if error.code in {400, 401, 403, 404, 422}:
                return PublicationOutcome("FAILED_DEFINITE")
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return PublicationOutcome("PUBLICATION_UNCERTAIN")

    def reconcile(self, repository: str, payload: dict) -> PublicationOutcome:
        try:
            document = self.read(
                f"/repos/{repository}/commits/{payload['head_sha']}/"
                "check-runs?filter=all&per_page=100"
            )
            runs = document.get("check_runs")
            if (
                type(runs) is list
                and type(document.get("total_count")) is int
                and document["total_count"] == len(runs)
            ):
                candidates = [
                    r
                    for r in runs
                    if type(r) is dict and r.get("external_id") == payload["external_id"]
                ]
                if len(candidates) == 1 and self._matches(candidates[0], payload):
                    return PublicationOutcome("PUBLISHED", candidates[0]["id"])
        except (IndependentReviewError, TypeError, AttributeError):
            pass
        return PublicationOutcome("PUBLICATION_UNCERTAIN")
