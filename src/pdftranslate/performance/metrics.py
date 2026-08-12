"""Small deterministic performance metric helpers."""

from __future__ import annotations

import math
from statistics import median

from pdftranslate.performance.models import TimingDistribution


def throughput(count: int, seconds: float) -> float:
    """Return a zero-safe rate."""
    if seconds <= 0 or count <= 0:
        return 0.0
    return count / seconds


def aggregate_timings(values: list[float]) -> TimingDistribution:
    clean = sorted(value for value in values if value >= 0)
    if not clean:
        return TimingDistribution(count=0)
    return TimingDistribution(
        count=len(clean),
        minimum=clean[0],
        median=median(clean),
        percentile_95=clean[max(0, math.ceil(len(clean) * 0.95) - 1)],
        maximum=clean[-1],
    )


def bytes_to_human(value: int | None) -> str:
    if value is None:
        return "n/a"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} GiB"
