"""How long should a rejected push wait, and when should its job stop?"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG = Path("config") / "push-retry.json"


@dataclass(frozen=True)
class PushRetry:
    deadline_seconds: dict[str, float]
    base_step_seconds: float
    ceiling_seconds: float
    ceiling_after: int

    def deadline_for(self, job: str) -> float:
        return self.deadline_seconds.get(job, self.deadline_seconds["default"])

    def backoff_seconds(self, failures: int) -> float:
        """The unjittered step; cap before exponentiation to avoid overflow."""
        if failures < 1:
            raise ValueError("failures must be 1 or more")
        return float(
            min(
                self.base_step_seconds * 2 ** min(failures - 1, self.ceiling_after),
                self.ceiling_seconds,
            )
        )


def load_retry(path: Path) -> PushRetry:
    """Read each knob by name; invalid or missing values stop before any git write."""
    declared = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(declared, dict):
        raise ValueError("push retry config must be an object")

    def read_seconds(value: object, key: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a finite number of seconds greater than 0")
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{key} must be a finite number of seconds greater than 0")
        return float(value)

    deadlines = declared.get("deadline_seconds")
    if not isinstance(deadlines, dict):
        raise ValueError("deadline_seconds must be an object with a default deadline")
    if "default" not in deadlines:
        raise ValueError("deadline_seconds.default is missing")
    deadline = {
        job: read_seconds(value, f"deadline_seconds.{job}")
        for job, value in deadlines.items()
    }
    base = read_seconds(declared.get("base_step_seconds"), "base_step_seconds")
    ceiling = read_seconds(declared.get("ceiling_seconds"), "ceiling_seconds")
    count = declared.get("ceiling_after")
    if type(count) is not int or count < 1:
        raise ValueError("ceiling_after must be a whole number, 1 or more")
    if base > ceiling:
        raise ValueError("base_step_seconds must not exceed ceiling_seconds")
    return PushRetry(deadline, base, ceiling, count)
