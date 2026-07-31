"""Pure deterministic font-size and safe-expansion helpers."""

from __future__ import annotations

import math
from decimal import Decimal

from pdftranslate.domain.text_block import BoundingBox, TextBlock


def initial_font_size(block: TextBlock, default: float) -> float:
    """Use the largest reliable source span size, otherwise a documented default."""
    sizes = tuple(
        span.font_size
        for span in block.spans
        if span.font_size is not None
        and math.isfinite(span.font_size)
        and 0 < span.font_size <= 144
    )
    return max(sizes) if sizes else default


def font_size_candidates(start: float, minimum: float, step: float) -> tuple[float, ...]:
    """Produce a stable descending sequence that always includes the minimum."""
    current = Decimal(str(max(start, minimum)))
    lower = Decimal(str(minimum))
    decrement = Decimal(str(step))
    values: list[float] = []
    while current > lower:
        values.append(float(current))
        current -= decrement
    values.append(float(lower))
    return tuple(dict.fromkeys(values))


def safe_expanded_bbox(
    block: TextBlock,
    page_blocks: tuple[TextBlock, ...],
    page_height: float,
    gap: float,
) -> BoundingBox:
    """Expand downward without crossing the next horizontally overlapping block."""
    source = block.bbox
    limit = page_height
    for other in page_blocks:
        if other.id == block.id or other.bbox.y0 < source.y1:
            continue
        horizontally_overlaps = other.bbox.x0 < source.x1 and other.bbox.x1 > source.x0
        if horizontally_overlaps:
            limit = min(limit, other.bbox.y0 - gap)
    return BoundingBox(x0=source.x0, y0=source.y0, x1=source.x1, y1=max(source.y1, limit))
