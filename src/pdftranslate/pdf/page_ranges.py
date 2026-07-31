"""One-based CLI page range parsing."""

from __future__ import annotations

import re

from pdftranslate.pdf.errors import InvalidPageRangeError

_PAGE_TOKEN = re.compile(r"^(?P<start>[1-9]\d*)(?:-(?P<end>[1-9]\d*))?$")


def parse_page_range(value: str | None, page_count: int) -> tuple[int, ...]:
    """Parse `1,3-5` into unique ascending one-based page numbers."""
    if page_count < 1:
        raise InvalidPageRangeError("cannot select pages from an empty PDF")
    if value is None:
        return tuple(range(1, page_count + 1))

    stripped = value.strip()
    if not stripped:
        raise InvalidPageRangeError("page range must not be empty")

    selected: list[int] = []
    previous = 0
    for raw_token in stripped.split(","):
        token = raw_token.strip()
        match = _PAGE_TOKEN.fullmatch(token)
        if match is None:
            raise InvalidPageRangeError(
                f"invalid page range {value!r}; use one-based values such as '1,3-5'"
            )

        start = int(match.group("start"))
        end = int(match.group("end") or start)
        if start > end:
            raise InvalidPageRangeError(f"descending page range is not allowed: {token!r}")
        if end > page_count:
            raise InvalidPageRangeError(
                f"page {end} is outside the document's 1-{page_count} page range"
            )

        for page_number in range(start, end + 1):
            if page_number <= previous:
                raise InvalidPageRangeError(
                    "page ranges must be strictly increasing and contain no duplicates"
                )
            selected.append(page_number)
            previous = page_number

    return tuple(selected)
