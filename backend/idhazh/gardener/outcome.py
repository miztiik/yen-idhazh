"""What does one gardener shard come to: its exit code, and what it hands the commit loop?

The runner writes the record and decides which paths the shard changed. It
starts no process, because nothing under `backend/idhazh/` may, so landing those
paths on `main` is `backend/utilities/gardener_publish.py`'s. This module is
what the two share: the four exit codes, what each one means to a person, the
order that picks the worst, and the `Shard` one hands the other.

**Exit codes, worst first:** 2 is ownership or integrity and is never retried;
3 is a push main refused - every try failed, and main did not move after the
last - and is retried at the next wake; 1 is a task that failed and is retried
at the next wake; 0 is everything landed, or nothing did because main moved on
and the next wake does the work again. A shard reports the worst code any part
of it earned.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model, RelPath
from idhazh.contracts.gardener_events import TaskFinished

EXIT_OK: Final = 0
EXIT_TASK_FAILED: Final = 1
EXIT_INTEGRITY: Final = 2
EXIT_PUSH_REFUSED: Final = 3

#: What each exit code means, for a person: one fixed sentence a code, which the
#: shard's last event carries and its job summary leads with.
MEANS: Final[Mapping[int, str]] = {
    EXIT_OK: "no task failed",
    EXIT_TASK_FAILED: "a task or the shard itself failed, and a person reads why",
    EXIT_INTEGRITY: "a gardener check refused the shard, and a person fixes the cause",
    EXIT_PUSH_REFUSED: "every push failed, and main refused the last one",
}

#: The four codes in the order a shard reports them: the worst one it earned.
_WORST_FIRST: Final = (EXIT_INTEGRITY, EXIT_PUSH_REFUSED, EXIT_TASK_FAILED, EXIT_OK)


def worst(*codes: int) -> int:
    """The worst of these exit codes, by the order above. No code at all is success."""
    return next((code for code in _WORST_FIRST if code in codes), EXIT_OK)


class Shard(Model):
    """What one shard hands the commit loop: its record, every path it changed, and the message."""

    index: int = Field(ge=0, description="Which shard of the wake this is.")
    task_names: tuple[str, ...] = Field(description="The tasks it ran, in the order they ran.")
    record_path: RelPath = Field(description="The one record the shard wrote.")
    written_paths: frozenset[RelPath] = Field(
        description="Every file the shard wrote, the record among them."
    )
    deleted_paths: frozenset[RelPath] = Field(description="Every file the shard deleted.")
    owned_prefixes: frozenset[RelPath] = Field(
        description="The task and venue declarations that permit these exact changes."
    )
    message: str = Field(min_length=1, description="The commit message the shard lands under.")

    @model_validator(mode="after")
    def _the_record_is_one_of_the_writes(self) -> Self:
        if self.record_path not in self.written_paths:
            raise ValueError("the shard's record is one of the files it writes")
        both = sorted(self.written_paths & self.deleted_paths)
        if both:
            raise ValueError(f"{', '.join(both)} is both written and deleted by one shard")
        if self.owned_prefixes & {"state", "state/raw", "state/compact"}:
            raise ValueError("the shard must name owned folders, not a blanket state root")
        return self


@dataclass(frozen=True, slots=True)
class Outcome:
    """What one run of the runner came to: its exit code, its record, and what is left to land.

    `landing` is None exactly when there is nothing to land, which is when the
    shard stopped before it wrote a record. `finished_tasks` is how each task
    that ran ended, the events the runner logged, in the order the tasks ran: a
    shard refused after some of its tasks ran still says how those ended.
    `downloaded_bytes` is what the tasks downloaded to read, None when nobody
    measured it, and `over_budget` says whether that passed `max_downloaded_mb`,
    decided once by the runner.
    """

    exit_code: int
    record: Path | None
    landing: Shard | None
    finished_tasks: tuple[TaskFinished, ...] = ()
    downloaded_bytes: int | None = None
    over_budget: bool = False
