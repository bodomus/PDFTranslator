"""Best-effort runner facade: integration I/O must not stop safe local work."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scripts.project_tracking import ProjectTracking


class TrackingHooks:
    def __init__(self, root: Path, ticket: str, text: str, warn: Callable[[str], None]) -> None:
        self.warn = warn
        self.human_review = root / ".agent-cycle" / ticket / "human-review.json"
        self.adapter: ProjectTracking | None = None
        self.data: dict[str, Any] = {"warnings": []}
        try:
            self.adapter = ProjectTracking(root, ticket, text, warn=warn)
            self.data = self.adapter.data
        except Exception as error:
            self.failure("tracking configuration/audit", error)

    def failure(self, action: str, error: Exception) -> None:
        message = f"{action}: {type(error).__name__}; integration disabled, local cycle continues"
        self.data["warnings"].append(message)
        self.warn("Integration warning: " + message)
        self.adapter = None
        with contextlib.suppress(OSError):
            self.human_review.unlink(missing_ok=True)

    def call(self, action: str, *args: Any) -> None:
        if self.adapter is None:
            return
        try:
            getattr(self.adapter, action)(*args)
        except Exception as error:
            self.failure(action, error)
