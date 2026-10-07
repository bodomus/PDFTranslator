"""Immutable review transport contract, isolated from authorization policy."""

from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlsplit

from scripts.github_review_facts import NoRedirect
from scripts.independent_review_policy import IndependentReviewError


@dataclass(frozen=True)
class DispatchRequest:
    repository: str
    ticket: str
    pull_request: int
    generation: int
    head_sha: str
    base_sha: str
    schema_version: str = "1.0"
    review_profile: str = "strict-independent-review"

    def instructions(self) -> str:
        return (
            f"Review repository {self.repository}\nPR {self.pull_request}\n"
            f"generation {self.generation}\n"
            f"Review exact HEAD SHA {self.head_sha} against exact BASE SHA {self.base_sha}.\n"
            "Do not substitute current branch HEAD. Do not review a newer SHA.\n"
            "Do not mutate repository state. Do not merge.\n"
            "Return structured PASS or CHANGES_REQUIRED bound to generation and reviewed_sha "
            "using the PDFTR-49 result schema."
        )


@dataclass(frozen=True)
class DispatchReceipt:
    outcome: Literal["DISPATCHED", "DEFINITE_NOT_DISPATCHED", "DISPATCH_UNCERTAIN"]
    external_request_id: str | None = None


class IndependentReviewDispatcher(Protocol):
    def dispatch(self, request: DispatchRequest) -> DispatchReceipt: ...


class HTTPSReviewDispatcher:
    """Trusted connector POST, not a ChatGPT/OpenAI API implementation.

    Provider must grant the worker read-only capabilities. No redirects, retries,
    arbitrary commands or credential-bearing response fields are accepted.
    """

    def __init__(self, endpoint: str, token: str):
        url = urlsplit(endpoint)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise IndependentReviewError("invalid_connector_endpoint")
        self.endpoint = endpoint
        self.token = token

    def dispatch(self, request: DispatchRequest) -> DispatchReceipt:
        if not self.token:
            return DispatchReceipt("DEFINITE_NOT_DISPATCHED")
        payload = {**asdict(request), "instructions": request.instructions()}
        outgoing = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.token},
            method="POST",
        )
        try:
            with urllib.request.build_opener(NoRedirect()).open(outgoing, timeout=30) as response:
                body = response.read(4097)
                if response.status not in {200, 201, 202} or len(body) > 4096:
                    return DispatchReceipt("DISPATCH_UNCERTAIN")
            value = json.loads(body)
            # Exact echoed identity; no provider-controlled prose is persisted.
            expected = asdict(request)
            if type(value) is not dict or set(value) != set(expected) | {"external_request_id"}:
                return DispatchReceipt("DISPATCH_UNCERTAIN")
            if any(type(value[k]) is not type(v) or value[k] != v for k, v in expected.items()):
                return DispatchReceipt("DISPATCH_UNCERTAIN")
            identifier = value["external_request_id"]
            if (
                type(identifier) is not str
                or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identifier) is None
                or self.token in identifier
            ):
                return DispatchReceipt("DISPATCH_UNCERTAIN")
            return DispatchReceipt("DISPATCHED", identifier)
        except (OSError, ValueError):
            return DispatchReceipt("DISPATCH_UNCERTAIN")


def persist_receipt(
    root: Path, directory: Path, request: DispatchRequest, receipt: DispatchReceipt
):
    """Diagnostic receipt only; policy history is the sole authorization store."""
    temporary = root / "temp" / "independent-review"
    target = directory / f"independent-dispatch-{request.generation}.json"
    for path in (temporary, *temporary.parents, target, *target.parents):
        if path.is_symlink() or path.is_junction():
            raise IndependentReviewError("symbolic_receipt")
    temporary.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=temporary, suffix=".json", delete=False
        ) as stream:
            name = Path(stream.name)
            json.dump({**asdict(request), **asdict(receipt)}, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        if name is not None:
            name.unlink(missing_ok=True)
