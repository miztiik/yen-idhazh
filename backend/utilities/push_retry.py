"""How long should a rejected push wait, and when should its job stop?"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG = Path("config") / "push-retry.json"


@dataclass(frozen=True)
class PushRetry:
    deadline_seconds: float
    work_deadline_seconds: float
    base_step_seconds: float
    ceiling_seconds: float
    ceiling_after: int

    def deadline_for(self, job: str) -> float:
        return self.work_deadline_seconds if job == "work" else self.deadline_seconds

    def backoff_seconds(self, failures: int) -> float:
        """The unjittered step; cap before exponentiation to avoid overflow."""
        if failures < 1:
            raise ValueError("failures must be 1 or more")
        exponent = failures - 1
        if failures > self.ceiling_after or exponent >= (
            math.log2(self.ceiling_seconds) - math.log2(self.base_step_seconds)
        ):
            return self.ceiling_seconds
        return min(math.ldexp(self.base_step_seconds, exponent), self.ceiling_seconds)


def load_retry(path: Path) -> PushRetry:
    """Read each knob by name; invalid or missing values stop before any git write."""
    declared = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(declared, dict):
        raise ValueError("push retry config must be an object")

    def read_seconds(key: str) -> float:
        value = declared.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a finite number of seconds greater than 0")
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{key} must be a finite number of seconds greater than 0")
        return float(value)

    deadline = read_seconds("deadline_seconds")
    work_deadline = read_seconds("work_deadline_seconds")
    base = read_seconds("base_step_seconds")
    ceiling = read_seconds("ceiling_seconds")
    count = declared.get("ceiling_after")
    if type(count) is not int or count < 1:
        raise ValueError("ceiling_after must be a whole number, 1 or more")
    if base > ceiling:
        raise ValueError("base_step_seconds must not exceed ceiling_seconds")
    return PushRetry(deadline, work_deadline, base, ceiling, count)
