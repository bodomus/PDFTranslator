"""Pure review-envelope grammar, loaded by harness callers at process startup.

No orchestration dependencies: a running parent retains this generation even when
an implementer changes repository source. New code takes effect on the next invocation.
"""

from __future__ import annotations

import re

REVIEW_SENTINEL_BEGIN = "<<<AGENT_CYCLE_REVIEW_JSON>>>"
REVIEW_SENTINEL_END = "<<<END_AGENT_CYCLE_REVIEW_JSON>>>"
JSON_FENCE = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n?```", re.DOTALL)


class ReviewProtocolError(ValueError):
    """An ambiguous or malformed review envelope."""


def single_envelope(stdout: str) -> tuple[str, str]:
    """Return the sole envelope body and outside text, rejecting ambiguous delimiters."""
    begin_count = stdout.count(REVIEW_SENTINEL_BEGIN)
    end_count = stdout.count(REVIEW_SENTINEL_END)
    if begin_count or end_count:
        if begin_count != 1 or end_count != 1:
            raise ReviewProtocolError(
                "reviewer output has duplicate or unmatched review delimiters"
            )
        begin = stdout.find(REVIEW_SENTINEL_BEGIN)
        end = stdout.find(REVIEW_SENTINEL_END)
        if end < begin:
            raise ReviewProtocolError("reviewer output has reversed review delimiters")
        body = stdout[begin + len(REVIEW_SENTINEL_BEGIN) : end]
        outside = stdout[:begin] + stdout[end + len(REVIEW_SENTINEL_END) :]
        return body, outside
    matches = list(JSON_FENCE.finditer(stdout))
    if matches:
        if len(matches) != 1:
            raise ReviewProtocolError("reviewer output has multiple fenced results")
        match = matches[0]
        body = match.group(1)
        outside = stdout[: match.start()] + stdout[match.end() :]
        return body, outside
    return stdout, ""
