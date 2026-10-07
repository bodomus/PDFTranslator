"""Authoritative read-only GitHub REST facts; event claims never enter this module."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from urllib.parse import quote

from scripts.independent_review_policy import (
    IndependentReviewError,
    validate_config,
    validate_facts,
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubReader:
    """Fixed GitHub host, bounded reads, no redirects or mutation operations."""

    def __init__(self, token: str):
        self.token = token

    def __call__(self, path: str) -> dict:
        request = urllib.request.Request(
            "https://api.github.com" + path,
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
                body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024:
                raise IndependentReviewError("github_response_limit")
            value = json.loads(body)
            if type(value) is not dict:
                raise IndependentReviewError("github_invalid_response")
            return value
        except (OSError, ValueError) as error:
            raise IndependentReviewError("github_read_failed") from error


def normalize_checks(document: dict, head: str, required: list[str]) -> dict:
    """Exactly one observation per required name; duplicate/rerun ambiguity is UNKNOWN."""
    runs = document.get("check_runs")
    if (
        type(runs) is not list
        or type(document.get("total_count")) is not int
        or document["total_count"] != len(runs)
    ):
        raise IndependentReviewError("incomplete_checks")
    result = {}
    for name in required:
        matches = [run for run in runs if type(run) is dict and run.get("name") == name]
        status = "UNKNOWN"
        if len(matches) == 1 and matches[0].get("head_sha") == head:
            run = matches[0]
            if type(run.get("status")) is not str:
                result[name] = status
                continue
            if run.get("status") in {"queued", "waiting", "in_progress", "pending", "requested"}:
                status = "PENDING"
            elif run.get("status") == "completed":
                conclusion = run.get("conclusion")
                if conclusion == "success":
                    status = "SUCCESS"
                elif type(conclusion) is str and conclusion in {
                    "failure",
                    "cancelled",
                    "timed_out",
                    "action_required",
                }:
                    status = "FAILURE"
        result[name] = status
    return result


class GitHubFactsProvider:
    def __init__(self, config: dict, read: Callable[[str], dict]):
        validate_config(config)
        self.config = json.loads(json.dumps(config))
        self.read = read

    def _pr(self) -> dict:
        config = self.config
        pr = self.read(f"/repos/{config['repository']}/pulls/{config['pull_request']}")
        try:
            if (
                type(pr["number"]) is not int
                or pr["number"] != config["pull_request"]
                or pr["base"]["repo"]["full_name"] != config["repository"]
                or pr["head"]["repo"]["full_name"] != config["repository"]
                or type(pr["draft"]) is not bool
                or type(pr["merged"]) is not bool
                or type(pr["state"]) is not str
                or pr["state"] not in {"open", "closed"}
            ):
                raise IndependentReviewError("github_pr_binding")
            return {
                "head_sha": pr["head"]["sha"],
                "base_sha": pr["base"]["sha"],
                "branch": pr["head"]["ref"],
                "pr_draft": pr["draft"],
                "pr_state": "MERGED" if pr["merged"] else pr["state"].upper(),
            }
        except (KeyError, TypeError) as error:
            raise IndependentReviewError("github_invalid_pr") from error

    def fetch(self, cycle: dict) -> dict:
        config = self.config
        repo = self.read(f"/repos/{config['repository']}")
        if repo.get("full_name") != config["repository"]:
            raise IndependentReviewError("github_repository_binding")
        before = self._pr()
        if cycle["ticket"] != config["ticket"] or cycle["branch"] != before["branch"]:
            raise IndependentReviewError("cycle_binding")
        head = before["head_sha"]
        checks = normalize_checks(
            self.read(
                f"/repos/{config['repository']}/commits/{quote(str(head), safe='')}/"
                "check-runs?filter=all&per_page=100"
            ),
            head,
            config["required_checks"],
        )
        if self._pr() != before:
            raise IndependentReviewError("github_snapshot_changed")
        facts = {
            "schema_version": "1.0",
            "repository": config["repository"],
            "ticket": config["ticket"],
            "pull_request": config["pull_request"],
            "pr_exists": True,
            **{key: value for key, value in before.items() if key != "branch"},
            "cycle_state": cycle["state"],
            "implementation_sha": cycle["current_head_sha"],
            "ci_sha": head,
            "checks": checks,
        }
        validate_facts(facts, config)
        return facts
